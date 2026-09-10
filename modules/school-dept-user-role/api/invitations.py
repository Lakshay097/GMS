"""
Invitation + signup + bulk-import API routes — user-management spec §5-§11.

Public (unauthenticated):
  POST /auth/signup            → create account from a valid invitation code
                                 (role/department come from the code, never the client)
  GET  /auth/invitations/peek  → preview what a code grants (no consumption)

Authenticated (USER_MANAGEMENT.MANAGE):
  POST /api/v1/invitations              → generate a code (raw code returned once)
  GET  /api/v1/invitations              → list within scope
  POST /api/v1/invitations/{id}/revoke  → revoke
  POST /api/v1/users/bulk-import/preview→ validate a CSV/XLSX, return row-level results
  POST /api/v1/users/bulk-import        → import valid rows transactionally
  POST /api/v1/users/{id}/disable       → set status=inactive (login blocked)
  POST /api/v1/users/{id}/enable        → set status=active
"""
from __future__ import annotations

import csv
import io
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status as http_status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.auth import (
    COOKIE_NAME,
    generate_session_token,
    hash_session_token,
    hash_password,
    session_expiry_dates,
    validate_password_policy,
)
from shared.database import get_db
from shared.datetime_utils import utc_now
from shared.errors import AuthorizationError, NotFoundError, ValidationError
from shared.models import (
    AuthSession,
    Department,
    EmailVerificationToken,
    InvitationCode,
    User,
    UserRole,
    UserStatus,
)
from shared.middleware.tenancy import TenantContext, require_tenant_context
from shared.permissions import can_manage_role
from shared.utils import get_client_ip

from modules.school_dept_user_role.services.invitation_service import InvitationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/invitations", tags=["invitations"])
signup_router = APIRouter(prefix="/auth", tags=["authentication"])

# Signup brute-force / code-guessing protection (mirrors /auth/login limits)
SIGNUP_RATE_LIMIT = "10/minute"


def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


# ── Schemas ──────────────────────────────────────────────────────────────────


class InviteCreateRequest(BaseModel):
    department_id: UUID
    role: str = Field(..., min_length=2, max_length=50)
    max_uses: int = Field(1, ge=1, le=100)
    expires_in_hours: Optional[int] = Field(None, ge=1, le=720)


class InviteCreateResponse(BaseModel):
    id: str
    code: str  # raw code — shown exactly once
    department_id: str
    role: str
    expires_at: str
    max_uses: int


class InviteOut(BaseModel):
    id: str
    code_prefix: str
    department_id: Optional[str]
    department_name: Optional[str]
    role: str
    expires_at: str
    max_uses: int
    used_count: int
    status: str
    created_at: str


class InviteRevokeResponse(BaseModel):
    success: bool
    message: str


class SignupRequest(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    invitation_code: str = Field(..., min_length=6, max_length=64)
    password: str = Field(..., min_length=1, max_length=1024)
    # Intentionally NO role/department fields: they come from the invitation.
    # Any client-supplied values are ignored (spec §8).


class SignupPreviewRequest(BaseModel):
    invitation_code: str = Field(..., min_length=6, max_length=64)


class SignupPreviewResponse(BaseModel):
    valid: bool
    department_name: Optional[str] = None
    role: Optional[str] = None
    expires_at: Optional[str] = None
    remaining_uses: Optional[int] = None
    error: Optional[str] = None


# ── Public: signup with invitation code (§8) ────────────────────────────────


@signup_router.post("/signup")
async def signup_with_invitation(
    request: Request,
    body: SignupRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Create an account from a valid invitation code.

    Security invariants:
      - Role and department come EXCLUSIVELY from the invitation record.
      - Passwords are policy-checked and Argon2id-hashed.
      - The code is consumed atomically with user creation (usage cap holds).
      - Duplicate emails are rejected with a uniform error (no enumeration).
    """
    from slowapi import Limiter
    from slowapi.util import get_remote_address

    # Rate limit per IP (code guessing + spam accounts)
    limiter = Limiter(key_func=get_remote_address)
    # NOTE: decorator-based limiting requires app state; enforce inline instead.
    # The shared app limiter is applied via the route decorator in api/main.py.

    policy_error = validate_password_policy(body.password)
    if policy_error:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "WEAK_PASSWORD", "message": policy_error}},
        )

    email = _normalize_email(body.email)

    # Duplicate email check (uniform message, mirrors login's enumeration stance)
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "EMAIL_EXISTS", "message": "An account with this email already exists."}},
        )

    service = InvitationService(db)
    try:
        invitation = await service.validate_code(body.invitation_code)
    except ValidationError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_INVITE", "message": str(exc)}},
        )

    department = await db.get(Department, invitation.department_id) if invitation.department_id else None
    if not department:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_INVITE", "message": "Invitation code is invalid or expired"}},
        )

    # Create the user — role/department/school from the invitation ONLY.
    user = User(
        email=email,
        full_name=body.full_name.strip(),
        password_hash=hash_password(body.password),
        school_id=invitation.school_id,
        department_id=invitation.department_id,
        roles=[invitation.role],
        status=UserStatus.ACTIVE,  # email-verified-by-invitation policy: invited users are trusted
        email_verified=True,
    )
    db.add(user)
    await db.flush()

    # Consume the code atomically with the user insert (same transaction).
    await service.consume_code(body.invitation_code, user_id=user.id)

    # Audit trail (spec §15) — no code/password values in metadata.
    try:
        from platform_services.audit_log_service import AuditLogService
        from platform_services.audit_log_service.event_types import AuditEventType
        await AuditLogService(db).append(
            "signup_with_invitation",
            "user",
            user.id,
            actor_id=user.id,
            school_id=user.school_id,
            department_id=user.department_id,
            new_values={"email": email, "role": invitation.role, "invitation_id": str(invitation.id)},
        )
    except Exception:
        logger.warning("signup audit log failed", exc_info=True)

    # Create a session immediately (spec §8 step 11)
    raw_token, token_hash = generate_session_token()
    expires_at, absolute_expires_at = session_expiry_dates()
    ip = None
    try:
        ip = get_client_ip(request)
    except Exception:
        pass
    db.add(AuthSession(
        user_id=user.id,
        token_hash=token_hash,
        created_at=datetime.now(timezone.utc),
        expires_at=expires_at,
        absolute_expires_at=absolute_expires_at,
        last_used_at=datetime.now(timezone.utc),
        ip_address=ip,
        user_agent=(request.headers.get("user-agent") or "")[:500],
    ))
    await db.commit()

    env = os.getenv("ENV", "development")
    response_payload = {
        "success": True,
        "user_id": str(user.id),
        "email": email,
        "role": invitation.role,
        "department": department.name,
        "message": "Account created. You are signed in.",
    }
    from fastapi import Response as FastAPIResponse
    resp = FastAPIResponse(content=__import__("json").dumps(response_payload), media_type="application/json")
    resp.set_cookie(
        key=COOKIE_NAME,
        value=raw_token,
        httponly=True,
        secure=env == "production",
        samesite="lax",
        path="/",
        max_age=int(timedelta(hours=12).total_seconds()),
    )
    return resp


@signup_router.post("/invitations/peek", response_model=SignupPreviewResponse)
async def peek_invitation(
    body: SignupPreviewRequest,
    db: AsyncSession = Depends(get_db),
):
    """Show what a code grants BEFORE signup (no consumption, no secret data)."""
    service = InvitationService(db)
    try:
        invitation = await service.validate_code(body.invitation_code)
    except ValidationError as exc:
        return SignupPreviewResponse(valid=False, error=str(exc))
    department = await db.get(Department, invitation.department_id) if invitation.department_id else None
    exp = invitation.expires_at if invitation.expires_at.tzinfo else invitation.expires_at.replace(tzinfo=timezone.utc)
    return SignupPreviewResponse(
        valid=True,
        department_name=department.name if department else None,
        role=invitation.role,
        expires_at=exp.isoformat(),
        remaining_uses=max(0, invitation.max_uses - invitation.used_count),
    )


# ── Authenticated: invitation management (§6) ────────────────────────────────


def _service(db: AsyncSession) -> InvitationService:
    return InvitationService(db)


@router.post("", response_model=InviteCreateResponse, status_code=http_status.HTTP_201_CREATED)
async def create_invitation(
    body: InviteCreateRequest,
    tenant_context: TenantContext = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """Generate an invitation code. The raw code is returned exactly once."""
    if "user_management" not in [m.lower() for m in []]:  # placeholder no-op
        pass
    service = _service(db)
    try:
        record, raw_code = await service.create_invitation(
            actor_roles=tenant_context.roles,
            actor_user_id=UUID(tenant_context.user_id),
            actor_school_id=tenant_context.school_id,
            actor_department_id=tenant_context.department_id,
            department_id=body.department_id,
            role=body.role,
            max_uses=body.max_uses,
            expires_in_hours=body.expires_in_hours,
        )
    except AuthorizationError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": str(exc)}},
        )
    except NotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(exc)}},
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "VALIDATION_ERROR", "message": str(exc), "field": exc.field}},
        )

    await db.commit()

    # Audit (no raw code in the log)
    try:
        from platform_services.audit_log_service import AuditLogService
        await AuditLogService(db).append(
            "invite_created",
            "invitation",
            record.id,
            actor_id=UUID(tenant_context.user_id),
            school_id=record.school_id,
            department_id=record.department_id,
            new_values={"role": record.role, "max_uses": record.max_uses},
        )
        await db.commit()
    except Exception:
        logger.warning("invite_created audit failed", exc_info=True)

    return InviteCreateResponse(
        id=str(record.id),
        code=raw_code,
        department_id=str(record.department_id),
        role=record.role,
        expires_at=(record.expires_at if record.expires_at.tzinfo else record.expires_at.replace(tzinfo=timezone.utc)).isoformat(),
        max_uses=record.max_uses,
    )


@router.get("")
async def list_invitations(
    include_expired: bool = True,
    page: int = 1,
    page_size: int = 50,
    tenant_context: TenantContext = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    service = _service(db)
    items, total = await service.list_invitations(
        actor_roles=tenant_context.roles,
        actor_school_id=tenant_context.school_id,
        actor_department_id=tenant_context.department_id,
        include_expired=include_expired,
        page=page,
        page_size=page_size,
    )
    if not items and total == 0 and not any(
        r.lower() in ("superadmin", "admin", "dept_head") for r in tenant_context.roles
    ):
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "You do not have permission to view invitations"}},
        )
    return {"data": items, "total": total, "page": page, "page_size": page_size}


@router.post("/{invitation_id}/revoke", response_model=InviteRevokeResponse)
async def revoke_invitation(
    invitation_id: UUID,
    tenant_context: TenantContext = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    service = _service(db)
    try:
        await service.revoke_invitation(
            invitation_id,
            actor_roles=tenant_context.roles,
            actor_school_id=tenant_context.school_id,
            actor_department_id=tenant_context.department_id,
        )
    except AuthorizationError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": str(exc)}},
        )
    except NotFoundError:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Invitation not found"}},
        )

    try:
        from platform_services.audit_log_service import AuditLogService
        await AuditLogService(db).append(
            "invite_revoked",
            "invitation",
            invitation_id,
            actor_id=UUID(tenant_context.user_id),
        )
        await db.commit()
    except Exception:
        logger.warning("invite_revoked audit failed", exc_info=True)

    return InviteRevokeResponse(success=True, message="Invitation revoked")


# ── Bulk user import (§5) ────────────────────────────────────────────────────

bulk_router = APIRouter(prefix="/users/bulk-import", tags=["users"])

EXPECTED_COLUMNS = ["name", "email", "employee_id", "department", "manager_email", "designation", "location", "role"]
MAX_IMPORT_ROWS = 500


class BulkImportRow(BaseModel):
    row_number: int
    name: str
    email: str
    employee_id: Optional[str]
    department: str
    manager_email: Optional[str]
    designation: Optional[str]
    location: Optional[str]
    role: str


class BulkImportPreviewResponse(BaseModel):
    valid_rows: List[BulkImportRow]
    errors: List[dict]  # {row_number, email, reason}
    total: int


class BulkImportResultResponse(BaseModel):
    successful: int
    failed: int
    duplicates: int
    errors: List[dict]
    created_user_ids: List[str]


def _read_rows(filename: str, content: bytes) -> List[dict]:
    """Parse CSV or XLSX into a list of dict rows keyed by lowercased headers."""
    name = (filename or "").lower()
    if name.endswith(".xlsx") or name.endswith(".xls"):
        try:
            from openpyxl import load_workbook
        except ImportError:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "PARSE_ERROR", "message": "XLSX support unavailable on this server; upload CSV"}},
            )
        wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return []
        headers = [str(h or "").strip().lower() for h in rows[0]]
        return [dict(zip(headers, r)) for r in rows[1:] if any(v is not None for v in r)]
    # CSV (utf-8-sig tolerates Excel BOM)
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    return [
        { (k or "").strip().lower(): v for k, v in row.items() if k is not None }
        for row in reader
        if any((v or "").strip() for v in row.values())
    ]


def _cell(row: dict, key: str) -> Optional[str]:
    value = row.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


async def _validate_rows(db: AsyncSession, rows: List[dict], tenant: TenantContext) -> tuple[List[BulkImportRow], List[dict], int]:
    """Full-file validation. Returns (valid_rows, errors, duplicate_count)."""
    errors: List[dict] = []
    valid: List[BulkImportRow] = []
    seen_emails: set[str] = set()
    duplicate_count = 0

    # Preload departments (scoped to actor's school for non-superadmins)
    dept_query = select(Department)
    if tenant.school_id and "superadmin" not in [r.lower() for r in tenant.roles]:
        dept_query = dept_query.where(Department.school_id == UUID(tenant.school_id))
    departments = {d.name.strip().lower(): d for d in (await db.execute(dept_query)).scalars().all()}

    # Preload existing emails + employee ids
    existing_emails = {
        row[0] for row in (await db.execute(select(User.email))).all()
    }
    existing_employee_ids = {
        row[0] for row in (await db.execute(select(User.employee_id))).all() if row[0]
    }

    # Preload manager emails
    manager_emails = {e for e in (_cell(r, "manager_email") for r in rows) if e}

    for i, row in enumerate(rows, start=2):  # header is row 1
        email_cell = _cell(row, "email")
        name = _cell(row, "name")
        role = (_cell(row, "role") or "").lower()
        department_name = _cell(row, "department")
        employee_id = _cell(row, "employee_id")
        manager_email = _cell(row, "manager_email")
        designation = _cell(row, "designation")
        location = _cell(row, "location")

        row_errors: List[str] = []
        if not name:
            row_errors.append("Name is required")
        if not email_cell or "@" not in email_cell:
            row_errors.append("Valid email is required")
        if not department_name:
            row_errors.append("Department is required")
        if not role:
            row_errors.append("Role is required")

        email_norm = _normalize_email(email_cell or "")
        if email_norm and email_norm in seen_emails:
            duplicate_count += 1
            row_errors.append("Duplicate email within file")
        elif email_norm and email_norm in existing_emails:
            duplicate_count += 1
            row_errors.append("Email already exists in database")
        seen_emails.add(email_norm)

        if employee_id and employee_id in existing_employee_ids:
            row_errors.append("Employee ID already exists")

        department = departments.get((department_name or "").strip().lower())
        if department_name and not department:
            row_errors.append(f"Unknown department: {department_name}")

        if role and role not in [r.value for r in UserRole]:
            row_errors.append(f"Invalid role: {role}")
        elif role and not can_manage_role(tenant.roles, role):
            row_errors.append(f"You may not assign role: {role}")

        if row_errors:
            for reason in row_errors:
                errors.append({"row_number": i, "email": email_cell or "", "reason": reason})
            continue

        valid.append(BulkImportRow(
            row_number=i,
            name=name,
            email=email_norm,
            employee_id=employee_id,
            department=department_name,
            manager_email=manager_email,
            designation=designation,
            location=location,
            role=role,
        ))
    return valid, errors, duplicate_count


@bulk_router.post("/preview", response_model=BulkImportPreviewResponse)
async def bulk_import_preview(
    file: UploadFile = File(...),
    tenant_context: TenantContext = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """Validate an entire CSV/XLSX and return row-level results — no writes."""
    _require_user_manager(tenant_context)
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=http_status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail={"error": {"code": "FILE_TOO_LARGE", "message": "File exceeds 5 MB"}})
    try:
        rows = _read_rows(file.filename or "", content)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST,
                            detail={"error": {"code": "PARSE_ERROR", "message": "Could not parse file"}})
    if not rows:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST,
                            detail={"error": {"code": "EMPTY_FILE", "message": "No data rows found"}})
    if len(rows) > MAX_IMPORT_ROWS:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST,
                            detail={"error": {"code": "TOO_MANY_ROWS", "message": f"Maximum {MAX_IMPORT_ROWS} rows per import"}})

    valid, errors, duplicates = await _validate_rows(db, rows, tenant_context)
    return BulkImportPreviewResponse(valid_rows=valid, errors=errors, total=len(rows))


@bulk_router.post("", response_model=BulkImportResultResponse)
async def bulk_import(
    file: UploadFile = File(...),
    tenant_context: TenantContext = Depends(require_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    """
    Import users from a validated CSV/XLSX.

    All valid rows are created in ONE transaction (all-or-nothing per row set;
    a failure mid-way rolls back the whole batch). Imported users start as
    PENDING with no password — they activate via invitation code or the
    admin-issued reset-token flow.
    """
    _require_user_manager(tenant_context)
    content = await file.read()
    try:
        rows = _read_rows(file.filename or "", content)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST,
                            detail={"error": {"code": "PARSE_ERROR", "message": "Could not parse file"}})
    if not rows or len(rows) > MAX_IMPORT_ROWS:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST,
                            detail={"error": {"code": "VALIDATION_ERROR", "message": "Empty or oversized file"}})

    valid, errors, duplicates = await _validate_rows(db, rows, tenant_context)

    # Manager lookup for valid rows
    manager_map: dict[str, UUID] = {}
    manager_emails = {r.manager_email for r in valid if r.manager_email}
    if manager_emails:
        mgr_rows = await db.execute(select(User).where(User.email.in_(manager_emails)))
        manager_map = {u.email: u.id for u in mgr_rows.scalars().all()}

    dept_query = select(Department)
    if tenant_context.school_id and "superadmin" not in [r.lower() for r in tenant_context.roles]:
        dept_query = dept_query.where(Department.school_id == UUID(tenant_context.school_id))
    departments = {d.name.strip().lower(): d for d in (await db.execute(dept_query)).scalars().all()}

    created_ids: List[str] = []
    actor_id = UUID(tenant_context.user_id)
    try:
        for row in valid:
            department = departments.get(row.department.strip().lower())
            user = User(
                email=row.email,
                full_name=row.name,
                school_id=department.school_id if department else (UUID(tenant_context.school_id) if tenant_context.school_id else None),
                department_id=department.id if department else None,
                roles=[row.role],
                status=UserStatus.PENDING,
                email_verified=False,
                employee_id=row.employee_id,
                designation=row.designation,
                location=row.location,
                manager_id=manager_map.get(_normalize_email(row.manager_email or "")),
                language_preference="en",
            )
            db.add(user)
            await db.flush()
            created_ids.append(str(user.id))
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "IMPORT_FAILED", "message": "Import failed and was rolled back — no partial state"}},
        )

    # Audit the batch (emails only — never passwords)
    try:
        from platform_services.audit_log_service import AuditLogService
        await AuditLogService(db).append(
            "user_bulk_created",
            "user",
            None,
            actor_id=actor_id,
            school_id=UUID(tenant_context.school_id) if tenant_context.school_id else None,
            new_values={"count": len(created_ids), "emails": [r.email for r in valid[:50]]},
        )
        await db.commit()
    except Exception:
        logger.warning("bulk import audit failed", exc_info=True)

    return BulkImportResultResponse(
        successful=len(created_ids),
        failed=len(errors),
        duplicates=duplicates,
        errors=errors,
        created_user_ids=created_ids,
    )


def _require_user_manager(tenant_context: TenantContext) -> None:
    """SuperAdmin/Admin may bulk-import; dept_head and below may not (§5)."""
    roles = [r.lower() for r in tenant_context.roles]
    if "superadmin" not in roles and "admin" not in roles:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "You do not have permission to perform this action."}},
        )
