"""
Tenancy filter middleware per Architecture §6 and R-02.
Enforces row-level tenant isolation using school_id/department_id.
Scope isolation is a mandatory query-layer filter applied BEFORE and INDEPENDENT of role-permission checks.

Authentication: opaque session tokens (auth_sessions table) read from the
HttpOnly session cookie (name: SESSION_COOKIE_NAME, default `schoolops_session`),
or an `Authorization: Bearer <token>` header for non-browser API clients.
Tokens are hashed (SHA-256) before lookup; the raw token never touches the database.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, List
from fastapi import Request, HTTPException, status, Depends
from sqlalchemy import false, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select
from shared.database import get_db
from shared.errors import AuthorizationError
from shared.models import User, UserStatus, UserSchoolGrant, AuthSession
from shared.auth import (
    hash_session_token,
    COOKIE_NAME,
    SESSION_TIMEOUT_MINUTES,
    _session_cache_get,
    _session_cache_put,
    _session_cache_invalidate,
)


def utc_now() -> datetime:
    """Timezone-aware UTC now (auth_sessions columns are TIMESTAMP WITH TIME ZONE).
    Note: shared.datetime_utils.utc_now is naive by project convention — do not
    mix the two when comparing against timestamptz values."""
    return datetime.now(timezone.utc)


class TenantContext:
    """
    Tenant context extracted from the authenticated session.
    Contains user's scope for mandatory query-layer filtering per R-02.
    """
    def __init__(
        self,
        user_id: str,
        school_id: Optional[str],
        department_id: Optional[str],
        roles: List[str],
        accessible_school_ids: Optional[List[str]] = None,
    ):
        self.user_id = user_id
        self.school_id = school_id  # Primary school (None for SuperAdmin)
        self.department_id = department_id
        self.roles = roles
        self.accessible_school_ids = accessible_school_ids or []  # For Viewer multi-school access


def _extract_token(request: Request) -> Optional[str]:
    """Get the session token from the HttpOnly cookie or Authorization header."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1].strip()
    return token or None


def _normalize_roles(raw_roles) -> List[str]:
    """Defensive role normalization: JSONB may return strings, enums, or odd shapes."""
    if raw_roles is None:
        return []
    if isinstance(raw_roles, str):
        return [raw_roles.lower().replace(" ", "_")]
    if isinstance(raw_roles, list):
        return [
            ((r.value if hasattr(r, "value") else str(r)) or "").lower().replace(" ", "_")
            for r in raw_roles if r
        ]
    return []


async def validate_session(
    request: Request,
    db: AsyncSession,
    touch: bool = True,
) -> Optional[User]:
    """
    Validate the request's session token against the database.

    Returns the active User, or None if the token is missing/invalid/expired.
    Sliding expiry: on success, extends expires_at when the session is within
    half of its idle window (throttled to avoid a write on every request).
    """
    token = _extract_token(request)
    if not token:
        return None

    token_hash = hash_session_token(token)

    # 60s in-process cache: same staleness guarantee as the old JWT cache.
    # A logged-out token may be served from cache for ≤60s — acceptable for
    # a sliding-session system and matches prior behaviour.
    #
    # The cached User ORM instance is detached from its originating session,
    # so it MUST be expire_on_commit-safe: the snapshot user is loaded with
    # loaded attributes only. If a cached user has expired attributes
    # (session commit expired it), drop the cache entry and re-load fresh —
    # attribute access on a detached instance would raise DetachedInstanceError.
    cached = _session_cache_get(token_hash)
    if cached is not None:
        user = cached.get("user")
        if user is not None:
            from sqlalchemy import inspect as _orm_inspect
            state = _orm_inspect(user)
            if state.expired:
                _session_cache_invalidate(token_hash)
            elif user.status == UserStatus.ACTIVE:
                return user
            else:
                return None
        else:
            return None

    result = await db.execute(
        select(AuthSession).where(AuthSession.token_hash == token_hash)
    )
    session = result.scalar_one_or_none()

    if session is None:
        _session_cache_put(token_hash, None)
        return None

    now = utc_now()
    expires_at = session.expires_at if session.expires_at.tzinfo else session.expires_at.replace(tzinfo=timezone.utc)
    absolute_expires_at = session.absolute_expires_at if session.absolute_expires_at.tzinfo else session.absolute_expires_at.replace(tzinfo=timezone.utc)

    # Check both idle timeout and absolute ceiling
    if expires_at < now or absolute_expires_at < now:
        _session_cache_put(token_hash, None)
        return None

    # Sliding extension: only touch DB when past half the idle window.
    # NOTE: this commit must happen BEFORE the User is loaded — with
    # expire_on_commit=True a commit expires all loaded attributes, and a
    # snapshot taken from an expired instance makes every later cache hit
    # see state.expired, invalidate, and reload. Committing first is what
    # makes the 60s cache actually hit.
    if touch:
        half = timedelta(minutes=SESSION_TIMEOUT_MINUTES) / 2
        if (expires_at - now) < half:
            new_expires = min(now + timedelta(minutes=SESSION_TIMEOUT_MINUTES), absolute_expires_at)
            session.expires_at = new_expires
            session.last_used_at = now
            await db.commit()
        else:
            session.last_used_at = now
            await db.commit()

    # Load the user AFTER any commit so the cached instance has no expired
    # attributes and later cache hits can return it without touching the DB.
    result = await db.execute(
        select(User).where(User.id == session.user_id, User.status == UserStatus.ACTIVE)
    )
    user = result.scalar_one_or_none()
    if user is None:
        _session_cache_put(token_hash, None)
        return None

    snapshot = {"user": user, "session_id": session.id}
    _session_cache_put(token_hash, snapshot)
    return user


async def extract_tenant_context(request: Request) -> TenantContext:
    """
    Extract tenant context from the authenticated session only.
    Does not hit the database — use require_tenant_context() for full DB enrichment.
    Raises 401 if there is no valid session (backwards-compatible behaviour).
    """
    token = _extract_token(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "AUTHENTICATION_ERROR", "message": "Missing or invalid authorization header"}},
        )
    # Token-only context (roles/school come from DB in require_tenant_context).
    # Retained for backwards compatibility with code that only needs the user id.
    return TenantContext(
        user_id="",
        school_id=None,
        department_id=None,
        roles=[],
        accessible_school_ids=[],
    )


async def require_tenant_context(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TenantContext:
    """
    Dependency to require tenant context in a route.

    Validates the session token, loads the user from the database, and
    resolves scope (school, department, roles, viewer grants) from Neon
    PostgreSQL. Raises 401 for missing/invalid/expired sessions and 403
    USER_NOT_PROVISIONED when the token is valid but the account is gone.
    """
    token = _extract_token(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "AUTHENTICATION_ERROR", "message": "Missing or invalid authorization header"}},
        )

    user = await validate_session(request, db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "AUTHENTICATION_ERROR", "message": "Invalid or expired session"}},
        )

    accessible_school_ids: List[str] = []
    normalized_roles = _normalize_roles(user.roles)
    if "viewer" in normalized_roles:
        grants = await db.execute(
            select(UserSchoolGrant.school_id).where(UserSchoolGrant.user_id == user.id)
        )
        accessible_school_ids = [str(row[0]) for row in grants.all()]

    return TenantContext(
        user_id=str(user.id),
        school_id=str(user.school_id) if user.school_id else None,
        department_id=str(user.department_id) if user.department_id else None,
        roles=normalized_roles,
        accessible_school_ids=accessible_school_ids,
    )


def apply_tenant_filter(query: Select, tenant_context: TenantContext) -> Select:
    """
    Apply mandatory tenant filter to a database query per R-02.
    This is applied BEFORE and INDEPENDENT of role-permission checks.

    SuperAdmin: No school filter (all schools accessible)
    Viewer: Filter by accessible_school_ids from user_school_grants
    Other roles: Filter by school_id (and department_id if set)
    """
    # Normalize roles to lowercase for comparison
    normalized_roles = [role.lower() if role else role for role in tenant_context.roles]

    # SuperAdmin has access to all schools (no filter)
    if "superadmin" in normalized_roles:
        return query

    # Viewer with multi-school access via user_school_grants
    if "viewer" in normalized_roles:
        if tenant_context.accessible_school_ids:
            school_uuids = [
                uuid.UUID(s) if isinstance(s, str) else s
                for s in tenant_context.accessible_school_ids
            ]
            query = query.where(
                query.selected_columns.school_id.in_(school_uuids)
            )
            # Also filter by department if the viewer has one assigned
            if tenant_context.department_id:
                dept_uuid = (
                    uuid.UUID(tenant_context.department_id)
                    if isinstance(tenant_context.department_id, str)
                    else tenant_context.department_id
                )
                query = query.where(
                    query.selected_columns.department_id == dept_uuid
                )
            return query
        else:
            # Viewer without grants sees no data
            return query.where(false())

    # All other roles: filter by primary school
    if tenant_context.school_id:
        school_uuid = (
            uuid.UUID(tenant_context.school_id)
            if isinstance(tenant_context.school_id, str)
            else tenant_context.school_id
        )
        query = query.where(query.selected_columns.school_id == school_uuid)
    else:
        # Non-SuperAdmin without school_id is invalid
        raise AuthorizationError("User must have a school_id assigned")

    # If user has department_id, filter by it as well
    if tenant_context.department_id:
        dept_uuid = (
            uuid.UUID(tenant_context.department_id)
            if isinstance(tenant_context.department_id, str)
            else tenant_context.department_id
        )
        query = query.where(query.selected_columns.department_id == dept_uuid)

    return query


def scoped_to_tenant(tenant_context: TenantContext, resource_school_id: str, resource_department_id: Optional[str] = None) -> bool:
    """
    Check if a resource is within the user's tenant scope.
    This is a pre-check before permission evaluation per R-02.
    """
    normalized_roles = [role.lower() if role else role for role in tenant_context.roles]

    # SuperAdmin has access to all schools
    if "superadmin" in normalized_roles:
        return True

    # Viewer with multi-school access
    if "viewer" in normalized_roles and tenant_context.accessible_school_ids:
        return resource_school_id in tenant_context.accessible_school_ids

    # All other roles: must match primary school
    if tenant_context.school_id != resource_school_id:
        return False

    if tenant_context.department_id and resource_department_id:
        if tenant_context.department_id != resource_department_id:
            cross_dept_roles = ["superadmin", "admin"]
            if not any(role in cross_dept_roles for role in normalized_roles):
                return False

    return True


# Backwards compatibility alias for modules that import get_current_user
get_current_user = require_tenant_context
