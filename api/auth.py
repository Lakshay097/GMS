"""
Authentication API endpoints.
Under AQ6 architecture: FastAPI does NOT verify passwords.
Neon Auth (via Vite client) owns password verification and issues session tokens.
FastAPI only validates Bearer tokens from Neon Auth using NEON_AUTH_SECRET_KEY.
"""
from fastapi import APIRouter, HTTPException, status, Depends, Request
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from shared.auth import (
    decode_access_token,
    auth_client
)
from shared.datetime_utils import utc_now
from shared.models import User, UserStatus
from shared.database import get_db
from shared.errors import AuthenticationError, AuthorizationError
from shared.middleware.tenancy import TenantContext


router = APIRouter(prefix="/auth", tags=["authentication"])


class TokenVerificationResponse(BaseModel):
    """Token verification response model."""
    valid: bool
    user_id: Optional[str] = None
    email: Optional[str] = None
    school_id: Optional[str] = None
    department_id: Optional[str] = None
    roles: List[str]
    message: str


class MFASetupResponse(BaseModel):
    """MFA setup response model."""
    secret: str
    qr_code_url: str
    message: str


@router.post("/verify", response_model=TokenVerificationResponse)
async def verify_token(request: Request):
    """
    Verify Neon Auth Bearer token and extract user identity.
    This is FastAPI's only auth responsibility under AQ6.
    Password verification is handled entirely by Neon Auth on the frontend.
    """
    auth_header = request.headers.get("Authorization")
    
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "MISSING_TOKEN", "message": "Missing or invalid authorization header"}}
        )
    
    token = auth_header.split(" ")[1]
    payload = decode_access_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "INVALID_TOKEN", "message": "Invalid or expired token"}}
        )
    
    return TokenVerificationResponse(
        valid=True,
        user_id=payload.get("sub"),
        email=payload.get("email"),
        school_id=payload.get("school_id"),
        department_id=payload.get("department_id"),
        roles=payload.get("roles", []),
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
    MFA is managed by Neon Auth; this endpoint is for Phase 2 SSO integration.
    """
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
    totp_uri = f"otpauth://totp/SchoolOP:{user.email}?secret={secret}&issuer=SchoolOP"
    
    return MFASetupResponse(
        secret=secret,
        qr_code_url=totp_uri,
        message="MFA setup successful. Please scan the QR code with your authenticator app."
    )




@router.post("/logout")
async def logout():
    """
    Logout endpoint.
    Token invalidation is handled by Neon Auth on the frontend.
    """
    return {"message": "Logout successful"}


@router.post("/sso/{provider}")
async def sso_login(provider: str):
    """
    Phase 2, reserved: Neon Auth SSO/OAuth connector.
    Placeholder - Phase 2 scope per AQ5.
    """
    return {"message": f"SSO login for {provider} - Phase 2 scope"}
