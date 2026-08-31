"""
Authentication API endpoints.
Under AQ6 architecture: FastAPI does NOT verify passwords.
Clerk (via frontend) owns password verification and issues JWT tokens.
FastAPI only validates Bearer tokens from Clerk using JWKS endpoint.
Supports both Bearer token and httpOnly cookie authentication for enhanced security.
"""
import os
from fastapi import APIRouter, HTTPException, status, Depends, Request, Response
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from slowapi import Limiter
from slowapi.util import get_remote_address
import httpx
from shared.auth import (
    decode_access_token,
    auth_client,
    create_access_token,
    CLERK_SECRET_KEY,
)
from shared.datetime_utils import utc_now
from shared.models import User, UserStatus, School, SchoolStatus, UserRole
from shared.database import get_db
from shared.errors import AuthenticationError, AuthorizationError
from shared.middleware.tenancy import TenantContext
from shared.utils import get_client_ip


router = APIRouter(prefix="/auth", tags=["authentication"])

# Rate limiter for auth endpoints (H3 security fix)
limiter = Limiter(key_func=get_client_ip)


class TokenVerificationResponse(BaseModel):
    """Token verification response model."""
    valid: bool
    user_id: Optional[str] = None
    email: Optional[str] = None
    school_id: Optional[str] = None
    department_id: Optional[str] = None
    roles: List[str]
    message: str


class SessionResponse(BaseModel):
    """Session response model for Clerk compatibility."""
    user: Optional[dict] = None
    session: Optional[dict] = None
    valid: bool


class CompleteSignupRequest(BaseModel):
    """Request model for completing signup with School ID after Clerk signup."""
    clerk_user_id: str = Field(..., min_length=1)
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=255)
    school_code: str = Field(..., min_length=1, max_length=50)
    phone: Optional[str] = Field(None, max_length=50)
    employee_id: Optional[str] = Field(None, max_length=50)


class SignupResponse(BaseModel):
    """Response model for user signup."""
    success: bool
    user_id: Optional[str] = None
    email: Optional[str] = None
    roles: List[str]
    message: str


class ProvisioningCheckRequest(BaseModel):
    """Request model for checking user provisioning."""
    email: EmailStr


class ProvisioningCheckResponse(BaseModel):
    """Response model for provisioning check."""
    provisioned: bool
    message: str


class MFASetupResponse(BaseModel):
    """MFA setup response model."""
    secret: str
    qr_code_url: str
    message: str


@router.get("/get-session", response_model=SessionResponse)
@limiter.limit("60/minute")  # Rate limit session checks (increased: multiple components call this on page load)
async def get_session(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Get current session information.
    Compatible with Clerk frontend components.
    """
    auth_header = request.headers.get("Authorization")

    if not auth_header or not auth_header.startswith("Bearer "):
        return SessionResponse(
            user=None,
            session=None,
            valid=False
        )

    token = auth_header.split(" ")[1]

    # JWT validation only (Clerk uses JWTs, no session token fallback needed)
    payload = decode_access_token(token)

    if not payload:
        return SessionResponse(
            user=None,
            session=None,
            valid=False
        )

    # Try to get user from database
    user_id = payload.get("sub")
    email = payload.get("email")
    print(f"DEBUG: get-session sub={user_id} email={email}")
    if user_id:
        try:
            user = None

            # 1. Find by platform UUID (for platform-issued tokens)
            #    Clerk sub values like "user_xxx" are NOT UUIDs — skip to avoid DataError
            import uuid as _uuid
            try:
                _uuid.UUID(str(user_id))
                result = await db.execute(
                    select(User).where(User.id == user_id, User.status == UserStatus.ACTIVE)
                )
                user = result.scalar_one_or_none()
                if user:
                    print(f"DEBUG: get-session found by platform UUID={user_id} → roles={user.roles}")
            except ValueError:
                # Not a UUID — this is a Clerk user ID, skip step 1
                pass

            # 2. Find by clerk_user_id (for Clerk tokens)
            if not user:
                result = await db.execute(
                    select(User).where(User.clerk_user_id == user_id, User.status == UserStatus.ACTIVE)
                )
                user = result.scalar_one_or_none()
                if user:
                    print(f"DEBUG: get-session found by clerk_user_id={user_id} → roles={user.roles}")

            # 3. Fallback: find by email and auto-link clerk_user_id
            #    This handles users created via create_superadmin.py or scripts
            #    that set a placeholder clerk_user_id (e.g. manual-setup-xxx)
            if not user and email:
                # Check for ALL users with this email (including archived) to detect duplicates
                all_email_users = await db.execute(
                    select(User).where(User.email == email)
                )
                all_users = all_email_users.scalars().all()
                if len(all_users) > 1:
                    print(f"WARNING: get-session found {len(all_users)} duplicate records for {email}!")
                    for du in all_users:
                        print(f"  → id={du.id} clerk_user_id={du.clerk_user_id} roles={du.roles} status={du.status}")

                    # Merge strategy: find the record with the most roles (likely the SuperAdmin)
                    # and consolidate the real clerk_user_id onto it, then archive the rest
                    best_user = None
                    best_role_count = -1
                    for candidate in all_users:
                        if candidate.status == UserStatus.ACTIVE:
                            role_count = len(candidate.roles or [])
                            # Prefer: more roles > real clerk_user_id > any active
                            if (role_count > best_role_count or
                                (role_count == best_role_count and
                                 not candidate.clerk_user_id.startswith("manual-setup-") and
                                 best_user and best_user.clerk_user_id.startswith("manual-setup-"))):
                                best_role_count = role_count
                                best_user = candidate

                    if best_user is None:
                        best_user = all_users[0]

                    # Consolidate: set real clerk_user_id on the best record
                    if best_user.clerk_user_id.startswith("manual-setup-"):
                        best_user.clerk_user_id = user_id

                    # Archive the other active records (don't hard-delete)
                    for candidate in all_users:
                        if candidate.id != best_user.id and candidate.status == UserStatus.ACTIVE:
                            candidate.status = UserStatus.ARCHIVED
                            candidate.archived_at = utc_now()
                            candidate.updated_at = utc_now()
                            print(f"DEBUG: get-session archived duplicate user {candidate.id} (clerk_user_id={candidate.clerk_user_id}, roles={candidate.roles})")

                    user = best_user
                    await db.commit()
                    print(f"DEBUG: get-session merged duplicates for {email}: kept id={user.id} clerk_user_id={user.clerk_user_id} roles={user.roles}")

                elif len(all_users) == 1:
                    user = all_users[0]
                    # Auto-link placeholder clerk_user_id
                    if user.clerk_user_id.startswith("manual-setup-"):
                        user.clerk_user_id = user_id
                        user.updated_at = utc_now()
                        await db.commit()
                        print(f"DEBUG: get-session auto-linked {email}: clerk_user_id → {user_id}, roles={user.roles}")
                else:
                    print(f"DEBUG: get-session no user found for email={email}")

            # 3b. Refresh roles from Clerk for existing users if they might be stale.
            #     This handles users created by the webhook with "Viewer" role before
            #     Clerk metadata was fully processed. Only checks users whose roles
            #     look incomplete (i.e. only have Viewer) to avoid unnecessary API calls.
            if user and CLERK_SECRET_KEY:
                existing_roles_lower = [str(r).lower() for r in (user.roles or [])]
                if existing_roles_lower == ["viewer"] or not existing_roles_lower:
                    try:
                        async with httpx.AsyncClient() as clerk_http:
                            clerk_resp = await clerk_http.get(
                                f"https://api.clerk.com/v1/users/{user_id}",
                                headers={"Authorization": f"Bearer {CLERK_SECRET_KEY}"},
                                timeout=5.0,
                            )
                            if clerk_resp.status_code == 200:
                                clerk_data = clerk_resp.json()
                                pub_meta = clerk_data.get("public_metadata", {}) or {}
                                clerk_roles = pub_meta.get("roles", []) or []
                                if clerk_roles:
                                    refreshed_roles = [str(r).lower() for r in clerk_roles]
                                    if set(refreshed_roles) != set(existing_roles_lower):
                                        user.roles = refreshed_roles
                                        user.updated_at = utc_now()
                                        await db.commit()
                                        print(f"DEBUG: get-session refreshed roles for {email}: {existing_roles_lower} → {refreshed_roles}")
                    except Exception as clerk_err:
                        print(f"DEBUG: get-session Clerk role refresh failed: {clerk_err}")

            # 4. Auto-provision any Clerk user not yet in Neon DB
            #    If the JWT is valid but the user doesn't exist in Neon DB,
            #    fetch their profile from Clerk and create a record so every
            #    Clerk user is always present in Neon DB.
            #    SuperAdmins get school_id=None (they manage all schools).
            #    Other roles also get school_id=None and will be redirected
            #    to /auth/complete-signup to pick a school.
            if not user and email:
                # Default to Viewer with no school; override from Clerk metadata if available
                roles_from_clerk = ["Viewer"]
                full_name_from_clerk = email.split("@")[0]

                if CLERK_SECRET_KEY:
                    try:
                        async with httpx.AsyncClient() as clerk_http:
                            clerk_resp = await clerk_http.get(
                                f"https://api.clerk.com/v1/users/{user_id}",
                                headers={"Authorization": f"Bearer {CLERK_SECRET_KEY}"},
                                timeout=5.0,
                            )
                            if clerk_resp.status_code == 200:
                                clerk_data = clerk_resp.json()
                                pub_meta = clerk_data.get("public_metadata", {}) or {}
                                clerk_roles = pub_meta.get("roles", []) or []
                                if clerk_roles:
                                    roles_from_clerk = [str(r).lower() for r in clerk_roles]
                                full_name_from_clerk = (
                                    (clerk_data.get("first_name") or "")
                                    + " "
                                    + (clerk_data.get("last_name") or "")
                                ).strip() or full_name_from_clerk
                            else:
                                print(f"DEBUG: get-session Clerk API returned {clerk_resp.status_code}")
                    except Exception as clerk_err:
                        print(f"DEBUG: get-session Clerk API lookup failed: {clerk_err}")

                user = User(
                    clerk_user_id=user_id,
                    email=email,
                    full_name=full_name_from_clerk,
                    school_id=None,  # Non-SuperAdmins will be routed to complete-signup
                    department_id=None,
                    status=UserStatus.ACTIVE,
                    roles=roles_from_clerk,
                    mfa_enabled=False,
                )
                db.add(user)
                await db.commit()
                await db.refresh(user)
                print(f"DEBUG: get-session auto-provisioned user {email}: id={user.id} roles={roles_from_clerk}")

            if user:
                # Defensive: ensure roles is always a list of lowercase strings.
                # JSONB can return various shapes depending on how the row was created.
                raw_roles = user.roles or []
                if isinstance(raw_roles, str):
                    normalized_roles = [raw_roles.lower()]
                elif isinstance(raw_roles, list):
                    normalized_roles = [
                        (r.value if hasattr(r, 'value') else str(r)).lower().replace(' ', '_')
                        for r in raw_roles if r
                    ]
                else:
                    normalized_roles = []
                print(f"DEBUG: get-session returning user={user.email} roles={normalized_roles}")
                return SessionResponse(
                    user={
                        "id": str(user.id),
                        "email": user.email,
                        "full_name": user.full_name,
                        "school_id": str(user.school_id) if user.school_id else None,
                        "department_id": str(user.department_id) if user.department_id else None,
                        "roles": normalized_roles,
                        "mfa_enabled": user.mfa_enabled
                    },
                    session={
                        "token": token,
                        "expires_at": payload.get("exp")
                    },
                    valid=True
                )
        except Exception as e:
            print(f"DEBUG: get-session lookup error: {e}")
            pass

    print(f"DEBUG: get-session no user found for sub={user_id} email={email}")
    return SessionResponse(
        user=None,
        session=None,
        valid=False
    )


@router.post("/verify", response_model=TokenVerificationResponse)
@limiter.limit("20/minute")  # Rate limit token verification
async def verify_token(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Verify Clerk Bearer token and extract user identity.
    This is FastAPI's only auth responsibility under AQ6.
    Password verification is handled entirely by Clerk on the frontend.
    """
    auth_header = request.headers.get("Authorization")

    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "MISSING_TOKEN", "message": "Missing or invalid authorization header"}}
        )

    token = auth_header.split(" ")[1]

    # JWT validation only (Clerk uses JWTs)
    payload = decode_access_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "INVALID_TOKEN", "message": "Invalid or expired token"}}
        )

    # Clerk JWTs only contain minimal claims (sub, iss, exp, etc.)
    # We need to fetch user data from database using clerk_user_id
    user_id = payload.get("sub")
    email = payload.get("email")
    user_data = None

    if user_id:
        try:
            # Try to find user by clerk_user_id
            result = await db.execute(
                select(User).where(User.clerk_user_id == user_id, User.status == UserStatus.ACTIVE)
            )
            user = result.scalar_one_or_none()

            # Fallback: match by email (for users with placeholder clerk_user_id)
            if user is None and email:
                result = await db.execute(
                    select(User).where(User.email == email, User.status == UserStatus.ACTIVE)
                )
                user = result.scalar_one_or_none()
                # Auto-link clerk_user_id for future fast-path lookups
                if user is not None and user.clerk_user_id != user_id:
                    user.clerk_user_id = user_id
                    user.updated_at = utc_now()
                    await db.commit()

            if user:
                # Defensive: ensure roles is always a list of lowercase strings
                raw_roles = user.roles or []
                if isinstance(raw_roles, str):
                    norm_roles = [raw_roles.lower()]
                elif isinstance(raw_roles, list):
                    norm_roles = [
                        (r.value if hasattr(r, 'value') else str(r)).lower().replace(' ', '_')
                        for r in raw_roles if r
                    ]
                else:
                    norm_roles = []
                user_data = {
                    "user_id": str(user.id),
                    "email": user.email,
                    "school_id": str(user.school_id) if user.school_id else None,
                    "department_id": str(user.department_id) if user.department_id else None,
                    "roles": norm_roles
                }
        except Exception as e:
            # Log error but don't fail token verification
            print(f"Error fetching user data: {e}")

    # If user not found in database, fetch from Clerk to get roles from publicMetadata.
    # Clerk JWTs don't contain role claims, so we must call the Clerk API.
    if not user_data:
        clerk_roles = []
        clerk_email = email
        if CLERK_SECRET_KEY and user_id:
            try:
                async with httpx.AsyncClient() as clerk_http:
                    clerk_resp = await clerk_http.get(
                        f"https://api.clerk.com/v1/users/{user_id}",
                        headers={"Authorization": f"Bearer {CLERK_SECRET_KEY}"},
                        timeout=5.0,
                    )
                    if clerk_resp.status_code == 200:
                        clerk_data = clerk_resp.json()
                        pub_meta = clerk_data.get("public_metadata", {}) or {}
                        raw_roles = pub_meta.get("roles", []) or []
                        clerk_roles = [str(r).lower() for r in raw_roles]
                        # Get email from Clerk if not in JWT
                        if not clerk_email:
                            email_addrs = clerk_data.get("email_addresses", []) or []
                            if email_addrs:
                                clerk_email = email_addrs[0].get("email_address")
            except Exception as clerk_err:
                print(f"DEBUG: verify Clerk API lookup failed: {clerk_err}")

        return TokenVerificationResponse(
            valid=True,
            user_id=user_id,
            email=clerk_email,
            school_id=None,
            department_id=None,
            roles=clerk_roles,
            message="Token valid (user not provisioned in database)"
        )

    return TokenVerificationResponse(
        valid=True,
        user_id=user_data["user_id"],
        email=user_data["email"],
        school_id=user_data["school_id"],
        department_id=user_data["department_id"],
        roles=user_data["roles"],
        message="Token valid"
    )


@router.post("/mfa/setup", response_model=MFASetupResponse)
async def setup_mfa(
    user_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Set up MFA for a user.
    Generates TOTP secret and QR code URL.
    MFA is managed by Clerk; this endpoint is for Phase 2 SSO integration.

    SECURITY NOTE (M3): This route is gated behind FEATURE_FLAG_MFA_ENABLED.
    Returns 503 if the feature flag is not set.
    """
    # Feature flag gating (M3 security fix)
    if not os.getenv("FEATURE_FLAG_MFA_ENABLED"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MFA feature not enabled"
        )
    
    # Find user
    result = await db.execute(
        select(User).where(User.id == user_id, User.status == UserStatus.ACTIVE)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "USER_NOT_FOUND", "message": "User not found"}}
        )
    
    # Generate MFA secret
    secret = auth_client.generate_mfa_secret()
    
    # Encrypt and store secret
    encrypted_secret = auth_client.encrypt_mfa_secret(secret)
    user.mfa_secret = encrypted_secret
    user.mfa_enabled = True
    user.updated_at = utc_now()
    
    await db.commit()
    
    # Generate QR code URL (for authenticator apps)
    totp_uri = f"otpauth://totp/SchoolOps:{user.email}?secret={secret}&issuer=SchoolOps"
    
    return MFASetupResponse(
        secret=secret,
        qr_code_url=totp_uri,
        message="MFA setup successful. Please scan the QR code with your authenticator app."
    )




@router.post("/link-account")
@limiter.limit("5/minute")  # Rate limit account linking (prevents enumeration)
async def link_account(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """
    Links the Clerk JWT token's sub to an existing platform user record.
    If no platform user exists, automatically creates one with a default school.

    Called automatically by the frontend after sign-in when a 403 USER_NOT_PROVISIONED
    is encountered. This handles three scenarios:

    1. Self-signed up users who already have proper clerk_user_id from signup
    2. Manually created users with placeholder clerk_user_id (manual-setup-*)
    3. New users who need automatic platform account creation

    Returns the user's id, email and roles so the frontend can confirm the link.

    Security note (M1): Returns uniform response to prevent email enumeration.
    Status code is always 200; additional info needed is indicated by a field.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "MISSING_TOKEN", "message": "Missing or invalid authorization header"}},
        )

    token = auth_header.split(" ")[1]

    # JWT validation only (Clerk uses JWTs)
    payload = decode_access_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "INVALID_TOKEN", "message": "Invalid or expired token"}},
        )

    clerk_sub = str(payload.get("sub") or payload.get("id") or "")
    email = payload.get("email")
    name = payload.get("name") or "User"

    if not clerk_sub:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "MISSING_SUB", "message": "Token does not contain a sub claim"}},
        )

    # Get school code from request body first (uniform processing)
    body: dict = {}
    try:
        body = await request.json()
    except Exception:
        pass
    school_code = body.get("school_code") if body else None
    email = email or body.get("email")

    # If no school_code provided, check if user already exists before requiring one.
    # SuperAdmins and users with an existing school don't need a school_code.
    # This prevents the redirect loop where already-provisioned superadmins
    # get stuck on /auth/complete-signup because link-account short-circuits.
    if not school_code:
        # Try to find the user by clerk_user_id first, then by email
        existing_user = None
        if clerk_sub:
            result = await db.execute(
                select(User).where(User.clerk_user_id == clerk_sub)
            )
            existing_user = result.scalar_one_or_none()

        if existing_user is None and email:
            result = await db.execute(select(User).where(User.email == email))
            existing_user = result.scalar_one_or_none()

        if existing_user is not None and existing_user.status == UserStatus.ACTIVE:
            # User already exists — link clerk_user_id if needed, then return success
            if existing_user.clerk_user_id != clerk_sub:
                existing_user.clerk_user_id = clerk_sub
                existing_user.updated_at = utc_now()
                await db.commit()

            response.set_cookie(
                key="auth_token",
                value=token,
                httponly=True,
                secure=True,
                samesite="lax",
                path="/",
                max_age=1800
            )
            return {
                "linked": True,
                "user_id": str(existing_user.id),
                "email": existing_user.email,
                "roles": [(r.value if hasattr(r, "value") else str(r)).lower().replace(" ", "_") for r in (existing_user.roles or []) if r],
                "school_id": str(existing_user.school_id) if existing_user.school_id else None,
            }

        # User truly not provisioned — need school code to create account
        response.set_cookie(
            key="auth_token",
            value=token,
            httponly=True,
            secure=True,  # Only sent over HTTPS
            samesite="lax",  # CSRF protection
            path="/",
            max_age=1800  # 30 minutes (matches SESSION_TIMEOUT_MINUTES)
        )
        return {
            "linked": False,
            "requires_school_code": True,
            "message": "School code is required to complete account setup."
        }

    # First try to find a user whose clerk_user_id already matches — already linked
    result = await db.execute(
        select(User).where(User.clerk_user_id == clerk_sub)
    )
    user = result.scalar_one_or_none()

    if user is None:
        # If not found by clerk_user_id, try fallback methods for legacy users
        if email:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()

    # If still no user found, create new user (school_code is now guaranteed to be present)
    if user is None:
        # Validate school code
        school_result = await db.execute(
            select(School).where(
                School.code == school_code,
                School.status == SchoolStatus.ACTIVE
            )
        )
        school = school_result.scalar_one_or_none()

        if not school:
            # Return 200 with error instead of 400 to prevent enumeration (M1 fix)
            return {
                "linked": False,
                "error": "INVALID_SCHOOL_CODE",
                "message": "Invalid or inactive school code. Please contact your administrator."
            }

        # Create new user automatically
        from shared.datetime_utils import utc_now
        from uuid import uuid4
        import asyncio  # For timing attack prevention

        # Add small random delay to prevent timing attacks (M1 security fix)
        await asyncio.sleep(0.1 + (hash(clerk_sub) % 10) / 100)  # 0.1-0.2s random delay

        new_user = User(
            id=uuid4(),
            clerk_user_id=clerk_sub,
            email=email or "unknown@example.com",
            full_name=name,
            school_id=school.id,
            department_id=None,
            status=UserStatus.ACTIVE,
            roles=[UserRole.VIEWER.value],
            mfa_enabled=False,
            language_preference="en",
            created_at=utc_now(),
            updated_at=utc_now()
        )

        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        user = new_user
    else:
        # User already exists (found by clerk_user_id or email fallback).
        # Update school_id if not yet assigned.
        from shared.datetime_utils import utc_now as _utc_now

        if not user.school_id:
            school_result = await db.execute(
                select(School).where(
                    School.code == school_code,
                    School.status == SchoolStatus.ACTIVE
                )
            )
            school = school_result.scalar_one_or_none()
            if school:
                user.school_id = school.id
                user.updated_at = _utc_now()
                await db.commit()
                await db.refresh(user)

    # Update clerk_user_id if it was a placeholder or mismatched
    if user.clerk_user_id != clerk_sub:
        user.clerk_user_id = clerk_sub
        from shared.datetime_utils import utc_now
        user.updated_at = utc_now()
        await db.commit()
        await db.refresh(user)

    # Set auth cookie for subsequent requests (B2 auth wiring fix)
    response.set_cookie(
        key="auth_token",
        value=token,
        httponly=True,
        secure=True,  # Only sent over HTTPS
        samesite="lax",  # CSRF protection
        path="/",
        max_age=1800  # 30 minutes (matches SESSION_TIMEOUT_MINUTES)
    )

    # Return uniform response to prevent email enumeration (M1 security fix)
    # No longer include 'created' field that reveals whether user was newly created
    return {
        "linked": True,
        "user_id": str(user.id),
        "email": user.email,
        "roles": [(r.value if hasattr(r, "value") else str(r)).lower().replace(' ', '_') for r in (user.roles or []) if r],
        "school_id": str(user.school_id) if user.school_id else None,
    }


@router.post("/complete-signup", response_model=SignupResponse)
@limiter.limit("3/minute")  # Rate limit signup (prevents abuse)
async def complete_signup_with_school_id(
    request: CompleteSignupRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Complete signup with School ID validation after Clerk signup.
    - Requires a valid School code
    - Requires a valid Clerk user ID (from Clerk signup)
    - Creates user with VIEWER role by default
    - Role can be upgraded by SuperAdmin/Admin/DeptHead later
    """
    # Validate school code exists and is active
    result = await db.execute(
        select(School).where(
            School.code == request.school_code,
            School.status == SchoolStatus.ACTIVE
        )
    )
    school = result.scalar_one_or_none()

    if not school:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "INVALID_SCHOOL_CODE",
                    "message": "Invalid or inactive school code. Please contact your administrator."
                }
            }
        )

    # Check if user with this email already exists
    existing_user = await db.execute(
        select(User).where(User.email == request.email)
    )
    if existing_user.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "USER_EXISTS",
                    "message": "A user with this email already exists. Please contact your administrator."
                }
            }
        )

    # Check if user with this Clerk ID already exists
    existing_clerk_user = await db.execute(
        select(User).where(User.clerk_user_id == request.clerk_user_id)
    )
    if existing_clerk_user.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "CLERK_USER_EXISTS",
                    "message": "This Clerk account is already linked to a platform user."
                }
            }
        )

    # Create new user with VIEWER role and proper Clerk ID
    from shared.datetime_utils import utc_now
    from uuid import uuid4

    new_user = User(
        id=uuid4(),
        clerk_user_id=request.clerk_user_id,  # Use actual Clerk user ID
        email=request.email,
        full_name=request.full_name,
        school_id=school.id,
        department_id=None,  # Will be assigned by DeptHead later
        status=UserStatus.ACTIVE,
        roles=[UserRole.VIEWER.value],
        mfa_enabled=False,
        phone=request.phone,
        employee_id=request.employee_id,
        language_preference="en",
        created_at=utc_now(),
        updated_at=utc_now()
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return SignupResponse(
        success=True,
        user_id=str(new_user.id),
        email=new_user.email,
        roles=new_user.roles,
        message="Account created successfully with VIEWER access. Please sign in."
    )


@router.post("/logout")
async def logout(response: Response):
    """
    Logout endpoint.
    Clears the httpOnly auth cookie and token invalidation is handled by Neon Auth on the frontend.
    """
    response.delete_cookie(
        key="auth_token",
        httponly=True,
        secure=True,
        samesite="lax",
        path="/"
    )
    return {"message": "Logout successful"}


@router.post("/sso/{provider}")
async def sso_login(provider: str):
    """
    Phase 2, reserved: Neon Auth SSO/OAuth connector.
    Placeholder - Phase 2 scope per AQ5.
    
    SECURITY NOTE (M3): This route is gated behind FEATURE_FLAG_SSO_ENABLED.
    Returns 503 if the feature flag is not set.
    """
    # Feature flag gating (M3 security fix)
    if not os.getenv("FEATURE_FLAG_SSO_ENABLED"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SSO feature not enabled"
        )
    
    return {"message": f"SSO login for {provider} - Phase 2 scope"}


@router.post("/set-auth-cookie")
async def set_auth_cookie(request: Request, response: Response):
    """
    Set httpOnly auth cookie after Clerk exchange.
    This endpoint receives the token from the frontend and sets it as an httpOnly cookie
    for enhanced security (XSS protection).
    """
    try:
        body = await request.json()
        token = body.get("token")

        if not token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "MISSING_TOKEN", "message": "Token is required"}}
            )

        # Verify the token before setting the cookie
        # JWT validation only (Clerk uses JWTs)
        payload = decode_access_token(token)

        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": {"code": "INVALID_TOKEN", "message": "Invalid or expired token"}}
            )
        
        # Set httpOnly cookie with security attributes
        response.set_cookie(
            key="auth_token",
            value=token,
            httponly=True,
            secure=True,  # Only sent over HTTPS
            samesite="lax",  # CSRF protection
            path="/",
            max_age=1800  # 30 minutes (matches SESSION_TIMEOUT_MINUTES)
        )
        
        return {"message": "Auth cookie set successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "COOKIE_SET_FAILED", "message": f"Failed to set auth cookie: {str(e)}"}}
        )


@router.post("/check-provisioning", response_model=ProvisioningCheckResponse)
@limiter.limit("20/minute")  # Rate limit provisioning checks
async def check_provisioning(request: ProvisioningCheckRequest, db: AsyncSession = Depends(get_db)):
    """
    Check if a user is provisioned in the system before allowing sign-in.
    This prevents users from signing in if they don't have a database record.
    """
    try:
        result = await db.execute(
            select(User).where(
                User.email == request.email,
                User.status == UserStatus.ACTIVE
            )
        )
        user = result.scalar_one_or_none()

        if user:
            return ProvisioningCheckResponse(
                provisioned=True,
                message="User is provisioned in the system"
            )
        else:
            return ProvisioningCheckResponse(
                provisioned=False,
                message="User is not provisioned. Please contact your administrator."
            )
    except Exception as e:
        # Log error but don't fail the check for security
        print(f"Error checking provisioning: {e}")
        return ProvisioningCheckResponse(
            provisioned=False,
            message="Unable to verify provisioning. Please contact your administrator."
        )
