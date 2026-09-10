"""
Authentication API endpoints — fully self-managed (no external identity provider).

Flow:
  POST /auth/login             → verify Argon2id password, create DB session, set HttpOnly cookie
  POST /auth/logout            → invalidate the server-side session row, clear cookie
  GET  /auth/me                → current authenticated user (from session)
  POST /auth/change-password   → authenticated password change (requires current password)
  POST /auth/forgot-password   → issue single-use reset token (uniform response, no enumeration)
  POST /auth/reset-password    → consume reset token, set new password, invalidate all sessions
  GET  /auth/sessions          → list active sessions for the current user
  DELETE /auth/sessions/{id}   → revoke one of my sessions
  GET  /auth/schools           → public school list for signup / complete-signup
  POST /auth/mfa/setup         → TOTP setup (feature-flag gated, as before)

Sessions:
  - Raw token lives ONLY in a Secure/HttpOnly/SameSite cookie (or Bearer header).
  - Database stores SHA-256(token) in auth_sessions — never the raw token.
  - Sliding idle expiry (SESSION_TIMEOUT_MINUTES) with an absolute ceiling.
"""
import logging
import os
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException, status, Depends, Request, Response
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from slowapi import Limiter
from slowapi.util import get_remote_address

from shared.auth import (
    hash_password,
    verify_password,
    validate_password_policy,
    needs_rehash,
    generate_session_token,
    hash_session_token,
    session_expiry_dates,
    generate_password_reset_token,
    generate_email_verification_token,
    encrypt_mfa_secret,
    generate_mfa_secret,
    COOKIE_NAME,
    SESSION_TIMEOUT_MINUTES,
    SESSION_ABSOLUTE_TIMEOUT_HOURS,
    PASSWORD_RESET_TIMEOUT_MINUTES,
)
from shared.models import User, UserStatus, School, SchoolStatus, UserRole, AuthSession, PasswordResetToken, EmailVerificationToken


def utc_now():
    """Timezone-aware UTC now — auth_sessions/password_reset_tokens use timestamptz."""
    return datetime.now(timezone.utc)


def naive_utc_now():
    """Naive UTC now — legacy columns (users.updated_at, notifications.*) are
    TIMESTAMP WITHOUT TIME ZONE; asyncpg rejects aware datetimes on them."""
    return _naive_utc_now()


from shared.datetime_utils import utc_now as _naive_utc_now  # noqa: E402
from shared.database import get_db
from shared.errors import AuthenticationError, AuthorizationError
from shared.middleware.tenancy import (
    TenantContext,
    require_tenant_context,
    validate_session,
    _normalize_roles,
)
from shared.utils import get_client_ip
from shared.permissions import PermissionMatrix

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])

# Rate limiter for auth endpoints (H3 security fix)
limiter = Limiter(key_func=get_client_ip)

# Brute-force protection: lock account after repeated failures (per-account).
MAX_FAILED_LOGINS = int(os.getenv("MAX_FAILED_LOGINS", "5"))
LOCKOUT_MINUTES = int(os.getenv("LOCKOUT_MINUTES", "15"))


# ── Request / Response models ─────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=1024)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=1024)
    new_password: str = Field(..., min_length=1, max_length=1024)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=10, max_length=256)
    new_password: str = Field(..., min_length=1, max_length=1024)


class SessionResponse(BaseModel):
    """Session response — same shape the frontend AuthContext already consumes."""
    user: Optional[dict] = None
    session: Optional[dict] = None
    valid: bool


class TokenVerificationResponse(BaseModel):
    valid: bool
    user_id: Optional[str] = None
    email: Optional[str] = None
    school_id: Optional[str] = None
    department_id: Optional[str] = None
    roles: List[str]
    message: str


class PublicSchoolOption(BaseModel):
    code: str
    name: str


class SignupResponse(BaseModel):
    success: bool
    user_id: Optional[str] = None
    email: Optional[str] = None
    roles: List[str]
    message: str


class MFASetupResponse(BaseModel):
    secret: str
    qr_code_url: str
    message: str


# ── Cookie helpers ────────────────────────────────────────────────────────────

def _set_session_cookie(response: Response, raw_token: str, max_age_seconds: int) -> None:
    env = os.getenv("ENV", "development")
    response.set_cookie(
        key=COOKIE_NAME,
        value=raw_token,
        httponly=True,
        secure=env == "production",  # HTTPS-only in production; localhost dev uses http
        samesite="lax",
        path="/",
        max_age=max_age_seconds,
    )


def _clear_session_cookie(response: Response) -> None:
    env = os.getenv("ENV", "development")
    response.delete_cookie(
        key=COOKIE_NAME,
        httponly=True,
        secure=env == "production",
        samesite="lax",
        path="/",
    )


# ── Internal helpers ──────────────────────────────────────────────────────────

def _user_payload(user: User) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "school_id": str(user.school_id) if user.school_id else None,
        "department_id": str(user.department_id) if user.department_id else None,
        "roles": _normalize_roles(user.roles),
        "mfa_enabled": bool(user.mfa_enabled),
        # Capability payload derived from the backend permission matrix (R-48):
        # rides on the session-cache snapshot, so warm /auth/me hits stay DB-free.
        "capabilities": PermissionMatrix.capabilities_for_roles(_normalize_roles(user.roles)),
    }


def _resolve_client_meta(request: Request) -> tuple:
    try:
        ip = get_client_ip(request)
    except Exception:
        ip = None
    ua = request.headers.get("user-agent", "")[:500]
    return ip, ua


async def _create_session(
    db: AsyncSession,
    user: User,
    request: Request,
    response: Response,
) -> dict:
    """Create an auth_sessions row, set the cookie, and return session metadata."""
    raw_token, token_hash = generate_session_token()
    expires_at, absolute_expires_at = session_expiry_dates()
    ip, ua = _resolve_client_meta(request)

    auth_session = AuthSession(
        user_id=user.id,
        token_hash=token_hash,
        created_at=utc_now(),
        expires_at=expires_at,
        absolute_expires_at=absolute_expires_at,
        last_used_at=utc_now(),
        ip_address=ip,
        user_agent=ua,
    )
    db.add(auth_session)
    await db.commit()

    max_age = int(timedelta(hours=SESSION_ABSOLUTE_TIMEOUT_HOURS).total_seconds())
    _set_session_cookie(response, raw_token, max_age)

    return {"expires_at": absolute_expires_at.isoformat()}


async def _purge_expired_sessions(db: AsyncSession) -> None:
    """Delete sessions idle-expired more than SESSION_CLEANUP_GRACE_HOURS ago."""
    from shared.auth import SESSION_CLEANUP_GRACE_HOURS
    cutoff = utc_now() - timedelta(hours=SESSION_CLEANUP_GRACE_HOURS)
    await db.execute(delete(AuthSession).where(AuthSession.expires_at < cutoff))


# ── Public endpoints ──────────────────────────────────────────────────────────

@router.get("/schools", response_model=List[PublicSchoolOption])
@limiter.limit("30/minute")
async def list_schools_public(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Public (unauthenticated) listing of active schools.
    Returns only code + name — no sensitive data.
    """
    result = await db.execute(
        select(School.code, School.name)
        .where(School.status == SchoolStatus.ACTIVE)
        .order_by(School.name)
    )
    return [PublicSchoolOption(code=row.code, name=row.name) for row in result.all()]


@router.post("/login", response_model=SessionResponse)
@limiter.limit("10/minute")  # Brute-force protection (H3)
async def login(
    request: Request,
    response: Response,
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Email + password login.

    Uniform error responses prevent account enumeration: unknown email and
    wrong password produce the identical 401 message. Repeated failures lock
    the account temporarily (MAX_FAILED_LOGINS within LOCKOUT_MINUTES).
    """
    generic_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": {"code": "INVALID_CREDENTIALS", "message": "Invalid email or password"}},
    )

    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if user is None:
        # Constant-ish work factor: still hash a dummy password to blunt timing oracles
        verify_password("$argon2id$invalid-placeholder-hash", body.password)
        raise generic_error

    if user.status == UserStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "ACCOUNT_PENDING", "message": "This account has not been activated yet. Use your invitation code to sign up first."}},
        )
    if user.status == UserStatus.SUSPENDED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "ACCOUNT_SUSPENDED", "message": "This account is suspended. Contact your administrator."}},
        )
    if user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "ACCOUNT_DISABLED", "message": "This account has been disabled. Contact your administrator."}},
        )

    # Account lockout check
    # users.locked_until is TIMESTAMP WITH TIME ZONE (timestamptz) — use aware UTC.
    now = utc_now()
    if user.locked_until is not None:
        # Normalise to aware for comparison — handles any legacy naive values in DB.
        locked_until = user.locked_until if user.locked_until.tzinfo else user.locked_until.replace(tzinfo=timezone.utc)
        if locked_until > now:
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail={"error": {"code": "ACCOUNT_LOCKED", "message": "Too many failed attempts. Try again later."}},
            )
        else:
            user.locked_until = None
            user.failed_login_count = 0

    if not verify_password(user.password_hash, body.password):
        user.failed_login_count = (user.failed_login_count or 0) + 1
        if user.failed_login_count >= MAX_FAILED_LOGINS:
            user.locked_until = now + timedelta(minutes=LOCKOUT_MINUTES)
            user.failed_login_count = 0
        await db.commit()
        logger.warning("Failed login for %s (attempt %s)", body.email, user.failed_login_count)
        raise generic_error

    # Success — reset failure counters, opportunistically upgrade weak hashes
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = utc_now()  # §2: last login tracking — TIMESTAMP WITH TIME ZONE
    if user.password_hash and needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)

    session_meta = await _create_session(db, user, request, response)

    logger.info("Login succeeded for %s", body.email)
    return SessionResponse(
        user=_user_payload(user),
        session=session_meta,
        valid=True,
    )


@router.post("/logout")
async def logout(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    """
    Invalidate the server-side session (row deleted) and clear the cookie.
    An old token can no longer authenticate after logout.
    """
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1].strip()

    if token:
        token_hash = hash_session_token(token)
        try:
            result = await db.execute(
                select(AuthSession).where(AuthSession.token_hash == token_hash)
            )
            session_row = result.scalar_one_or_none()
            if session_row:
                await db.delete(session_row)
                await db.commit()
        except Exception:
            # Table missing (migration not yet applied) or DB unavailable —
            # the cookie is cleared either way; the stale row becomes inert
            # because the raw token is discarded by the client.
            logger.warning("logout: could not delete session row", exc_info=True)
        # Evict from the in-process cache
        from shared.auth import _session_cache_invalidate
        _session_cache_invalidate(token_hash)

    _clear_session_cookie(response)
    return {"message": "Logout successful"}


@router.get("/get-session", response_model=SessionResponse)
@router.get("/me", response_model=SessionResponse)
@limiter.limit("60/minute")
async def get_session(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Get current session information (authenticated user from the DB session).
    Kept the /auth/get-session path for frontend compatibility.
    """
    user = await validate_session(request, db, touch=False)
    if user is None:
        return SessionResponse(user=None, session=None, valid=False)
    return SessionResponse(
        user=_user_payload(user),
        session={"valid": True},
        valid=True,
    )


@router.post("/verify", response_model=TokenVerificationResponse)
@limiter.limit("20/minute")
async def verify_token(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Validate the session token and return identity claims.
    Replaces the old Clerk JWT verification with session validation.
    """
    user = await validate_session(request, db, touch=False)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "INVALID_TOKEN", "message": "Invalid or expired session"}},
        )
    return TokenVerificationResponse(
        valid=True,
        user_id=str(user.id),
        email=user.email,
        school_id=str(user.school_id) if user.school_id else None,
        department_id=str(user.department_id) if user.department_id else None,
        roles=_normalize_roles(user.roles),
        message="Session valid",
    )


# ── Password management ───────────────────────────────────────────────────────

@router.post("/change-password")
@limiter.limit("5/minute")
async def change_password(
    request: Request,
    body: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Change my password. Requires the current password. Revokes all other sessions."""
    user = await validate_session(request, db, touch=False)
    if user is None:
        raise AuthenticationError()

    if not verify_password(user.password_hash, body.current_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_CREDENTIALS", "message": "Current password is incorrect"}},
        )

    policy_error = validate_password_policy(body.new_password)
    if policy_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "WEAK_PASSWORD", "message": policy_error}},
        )

    user.password_hash = hash_password(body.new_password)
    user.updated_at = naive_utc_now()
    user.failed_login_count = 0
    user.locked_until = None

    # Security: revoke every session except the current one
    current_token = request.cookies.get(COOKIE_NAME)
    current_hash = hash_session_token(current_token) if current_token else None
    result = await db.execute(select(AuthSession).where(AuthSession.user_id == user.id))
    for row in result.scalars().all():
        if current_hash and row.token_hash == current_hash:
            continue
        await db.delete(row)

    await db.commit()
    return {"success": True, "message": "Password changed. Other sessions have been signed out."}


@router.post("/forgot-password")
@limiter.limit("5/minute")
async def forgot_password(request: Request, body: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    """
    Request a password reset. Always returns 200 with the same body —
    never reveals whether the email exists (enumeration prevention, M1).
    """
    result = await db.execute(select(User).where(User.email == body.email, User.status == UserStatus.ACTIVE))
    user = result.scalar_one_or_none()

    if user:
        raw_token, token_hash, expires_at = generate_password_reset_token()
        db.add(PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            created_at=utc_now(),
            expires_at=expires_at,
        ))
        await db.commit()
        logger.info("Password reset token issued for %s", body.email)

        # Build the deep-link.  APP_URL is validated at startup in production;
        # in dev it defaults to localhost so links work without configuration.
        app_url = (os.getenv("APP_URL") or "http://localhost:5173").rstrip("/")
        reset_link = f"{app_url}/auth/reset-password?token={raw_token}"

        # Delivery — explicit, deterministic behavior in both modes. The raw
        # token is NEVER returned in the API response (it would let anyone
        # take over the account).
        if os.getenv("EMAIL_PROVIDER_API_KEY"):
            # Email provider configured → deliver via the notification service
            # (Resend). The service enqueues; a queue worker sends it.
            try:
                from platform_services.notification_service.service import NotificationPayload, NotificationService
                from shared.platform_models import NotificationCategory, NotificationChannel
                await NotificationService(db).dispatch(NotificationPayload(
                    user_id=user.id,
                    category=NotificationCategory.INFORMATIONAL.value,
                    title="Reset your SchoolOps password",
                    body=(
                        f"<p>Hi {user.full_name or 'there'},</p>"
                        f"<p>A password reset was requested for your SchoolOps account.</p>"
                        f"<p><a href=\"{reset_link}\">Click here to reset your password</a></p>"
                        f"<p>Or copy this link into your browser:<br>{reset_link}</p>"
                        f"<p>This link expires in {PASSWORD_RESET_TIMEOUT_MINUTES} minutes and can only be used once.</p>"
                        f"<p>If you did not request this, you can safely ignore this email.</p>"
                    ),
                    channel=NotificationChannel.EMAIL,
                    entity_type="user",
                    entity_id=user.id,
                ))
            except Exception as exc:
                logger.warning("Password-reset email dispatch failed: %s", exc)
        else:
            # No email provider configured (self-hosted default). Persist the
            # token as an in-app notification row so it is durably recoverable
            # — an operator reads it from the notifications table (or hands the
            # user an admin-issued token via POST /api/v1/users/{id}/set-password
            # or scripts/set_user_passwords.py). The response above stays uniform.
            from shared.platform_models import (
                Notification as NotificationRow,
                NotificationCategory,
                NotificationChannel,
                NotificationStatus,
            )
            from shared.datetime_utils import utc_now as _naive_utc_now
            db.add(NotificationRow(
                user_id=user.id,
                category=NotificationCategory.INFORMATIONAL.value,
                channel=NotificationChannel.IN_APP,
                title="Password reset requested",
                body=(
                    f"A password reset was requested for your account. "
                    f"Single-use link (valid {PASSWORD_RESET_TIMEOUT_MINUTES} minutes): {reset_link}"
                ),
                status=NotificationStatus.DISPATCHED,
                dispatched_at=_naive_utc_now(),
                entity_type="user",
                entity_id=user.id,
            ))
            await db.commit()
            logger.warning(
                "EMAIL_PROVIDER_API_KEY is not configured: password-reset link for %s was persisted "
                "as an in-app notification (notifications.user_id=%s) instead of being emailed. "
                "Deliver it out-of-band, or configure the email provider for automatic delivery.",
                body.email, user.id,
            )

    return {"success": True, "message": "If that email is registered, reset instructions have been sent."}


@router.post("/reset-password")
@limiter.limit("5/minute")
async def reset_password(request: Request, body: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Consume a single-use reset token and set a new password. Revokes all sessions."""
    token_hash = hash_session_token(body.token)
    result = await db.execute(select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash))
    reset_row = result.scalar_one_or_none()

    if reset_row is None or reset_row.used_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_TOKEN", "message": "Reset token is invalid or already used"}},
        )

    expires_at = reset_row.expires_at if reset_row.expires_at.tzinfo else reset_row.expires_at.replace(tzinfo=timezone.utc)
    if expires_at < utc_now():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "TOKEN_EXPIRED", "message": "Reset token has expired. Request a new one."}},
        )

    policy_error = validate_password_policy(body.new_password)
    if policy_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "WEAK_PASSWORD", "message": policy_error}},
        )

    result = await db.execute(select(User).where(User.id == reset_row.user_id))
    user = result.scalar_one_or_none()
    if user is None or user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_TOKEN", "message": "Reset token is invalid"}},
        )

    user.password_hash = hash_password(body.new_password)
    user.updated_at = naive_utc_now()
    user.failed_login_count = 0
    user.locked_until = None
    reset_row.used_at = utc_now()  # password_reset_tokens.used_at is TIMESTAMP WITH TIME ZONE

    # Invalidate every existing session
    await db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))

    await db.commit()
    return {"success": True, "message": "Password has been reset. Please sign in."}


# ── Email verification ────────────────────────────────────────────────────────

@router.get("/verify-email")
@limiter.limit("10/minute")
async def verify_email(
    request: Request,
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Consume a single-use email-verification token and mark the account verified.

    Reached via the deep-link:
        GET /auth/verify-email?token=<raw_token>

    The frontend sends the user here after clicking the link in their
    activation email. On success the account transitions from PENDING → ACTIVE
    (if it was PENDING) and email_verified is set to True.

    Rate-limited to 10/min to blunt enumeration of token space.
    Token is never echoed back in any error response.
    """
    token_hash = hash_session_token(token)
    result = await db.execute(
        select(EmailVerificationToken).where(EmailVerificationToken.token_hash == token_hash)
    )
    record = result.scalar_one_or_none()

    _invalid = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"error": {"code": "INVALID_TOKEN", "message": "Verification link is invalid or already used."}},
    )

    if record is None or record.used_at is not None:
        raise _invalid

    expires_at = record.expires_at if record.expires_at.tzinfo else record.expires_at.replace(tzinfo=timezone.utc)
    if expires_at < utc_now():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "TOKEN_EXPIRED", "message": "Verification link has expired. Ask your administrator to resend the activation email."}},
        )

    user_result = await db.execute(select(User).where(User.id == record.user_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        raise _invalid

    # Mark verified; activate PENDING accounts
    user.email_verified = True
    if user.status == UserStatus.PENDING:
        user.status = UserStatus.ACTIVE
    user.updated_at = naive_utc_now()
    record.used_at = utc_now()
    await db.commit()

    logger.info("Email verified for user %s", user.email)
    return {
        "success": True,
        "message": "Email verified. You can now sign in.",
        "was_pending": user.status == UserStatus.ACTIVE,  # always True after the update above
    }


# ── Session management (multi-device) ─────────────────────────────────────────

@router.get("/sessions")
async def list_sessions(request: Request, db: AsyncSession = Depends(get_db)):
    """List my active sessions (device, IP, expiry)."""
    user = await validate_session(request, db, touch=False)
    if user is None:
        raise AuthenticationError()

    result = await db.execute(
        select(AuthSession).where(AuthSession.user_id == user.id).order_by(AuthSession.last_used_at.desc())
    )
    now = utc_now()
    sessions = []
    for s in result.scalars().all():
        exp = s.expires_at if s.expires_at.tzinfo else s.expires_at.replace(tzinfo=timezone.utc)
        if exp < now:
            continue
        sessions.append({
            "id": str(s.id),
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "last_used_at": s.last_used_at.isoformat() if s.last_used_at else None,
            "expires_at": exp.isoformat(),
            "ip_address": s.ip_address,
            "user_agent": s.user_agent,
        })
    return {"sessions": sessions}


@router.delete("/sessions/{session_id}")
async def revoke_session(session_id: UUID, request: Request, db: AsyncSession = Depends(get_db)):
    """Revoke one of my own sessions (sign out a single device)."""
    user = await validate_session(request, db, touch=False)
    if user is None:
        raise AuthenticationError()

    result = await db.execute(
        select(AuthSession).where(AuthSession.id == session_id, AuthSession.user_id == user.id)
    )
    session_row = result.scalar_one_or_none()
    if session_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Session not found"}},
        )

    await db.delete(session_row)
    await db.commit()
    from shared.auth import _session_cache_invalidate
    _session_cache_invalidate(session_row.token_hash)
    return {"success": True}


# ── Signup completion (school picker after first admin provisions users) ──────

@router.post("/complete-signup", response_model=SignupResponse)
@limiter.limit("3/minute")
async def complete_signup_with_school_id(
    request: Request,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """
    Attach a school to the CURRENT authenticated user who has no school yet.
    The user must already be signed in (session cookie) — accounts are created
    by an Admin or by create_admin.py, never by anonymous signup.
    """
    user = await validate_session(request, db, touch=False)
    if user is None:
        raise AuthenticationError()

    email = body.get("email")
    full_name = body.get("full_name")
    school_code = body.get("school_code")
    phone = body.get("phone")
    employee_id = body.get("employee_id")

    if not school_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "VALIDATION_ERROR", "message": "school_code is required"}},
        )

    # Resolve school
    result = await db.execute(
        select(School).where(School.code == school_code, School.status == SchoolStatus.ACTIVE)
    )
    school = result.scalar_one_or_none()
    if not school:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_SCHOOL_CODE", "message": "Invalid or inactive school code. Please contact your administrator."}},
        )

    # Only users with no school can pick one; SuperAdmins manage all schools.
    roles = _normalize_roles(user.roles)
    if "superadmin" in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "SuperAdmins manage all schools and cannot be bound to one."}},
        )
    if user.school_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "ALREADY_ASSIGNED", "message": "Your account is already assigned to a school."}},
        )

    user.school_id = school.id
    if full_name and not user.full_name:
        user.full_name = full_name
    if phone:
        user.phone = phone
    if employee_id and not user.employee_id:
        user.employee_id = employee_id
    user.updated_at = naive_utc_now()
    await db.commit()

    return SignupResponse(
        success=True,
        user_id=str(user.id),
        email=user.email,
        roles=_normalize_roles(user.roles),
        message="Account setup complete.",
    )


# ── MFA setup (feature-flag gated, as before) ─────────────────────────────────

@router.post("/mfa/setup", response_model=MFASetupResponse)
async def setup_mfa(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    tenant_context: TenantContext = Depends(require_tenant_context),
):
    """
    Set up MFA for a user (TOTP). Gated behind FEATURE_FLAG_MFA_ENABLED (M3).
    """
    if not os.getenv("FEATURE_FLAG_MFA_ENABLED"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MFA feature not enabled"
        )

    # Only self or SuperAdmin
    if str(tenant_context.user_id) != str(user_id) and "superadmin" not in tenant_context.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": "You may only manage your own MFA"}},
        )

    result = await db.execute(
        select(User).where(User.id == user_id, User.status == UserStatus.ACTIVE)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "USER_NOT_FOUND", "message": "User not found"}},
        )

    secret = generate_mfa_secret()
    user.mfa_secret = encrypt_mfa_secret(secret)
    user.mfa_enabled = True
    user.updated_at = naive_utc_now()
    await db.commit()

    totp_uri = f"otpauth://totp/SchoolOps:{user.email}?secret={secret}&issuer=SchoolOps"
    return MFASetupResponse(
        secret=secret,
        qr_code_url=totp_uri,
        message="MFA setup successful. Please scan the QR code with your authenticator app."
    )

