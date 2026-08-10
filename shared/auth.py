"""
Neon Auth integration for authentication and authorization.
Implements Better Auth-backed authentication per Architecture §18.
MFA support for Admin and SuperAdmin roles per R-56.
"""
import os
from typing import Optional, Dict, Any, List
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import httpx
import pyotp
from cryptography.fernet import Fernet
import base64

load_dotenv()

# Neon Auth configuration
NEON_AUTH_PROJECT_ID = os.getenv("NEON_AUTH_PROJECT_ID")
NEON_AUTH_PUBLISHABLE_KEY = os.getenv("NEON_AUTH_PUBLISHABLE_KEY")
NEON_AUTH_SECRET_KEY = os.getenv("NEON_AUTH_SECRET_KEY")
MFA_REQUIRED_ROLES = os.getenv("MFA_REQUIRED_ROLES", "Admin,SuperAdmin").split(",")
SESSION_TIMEOUT_MINUTES = int(os.getenv("SESSION_TIMEOUT_MINUTES", "30"))

# Encryption key for MFA secrets (data at rest per R-57)
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
if not ENCRYPTION_KEY:
    # Generate a key if not provided (for development only)
    ENCRYPTION_KEY = Fernet.generate_key().decode()
cipher_suite = Fernet(ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class NeonAuthClient:
    """
    Client for interacting with Neon Auth API.
    Handles authentication, MFA, and token management.
    """
    
    def __init__(self):
        self.project_id = NEON_AUTH_PROJECT_ID
        self.publishable_key = NEON_AUTH_PUBLISHABLE_KEY
        self.secret_key = NEON_AUTH_SECRET_KEY
        self.base_url = f"https://auth.neon.tech/v1/projects/{self.project_id}"
    
    async def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verify a JWT token from Neon Auth.
        
        Args:
            token: JWT token string
            
        Returns:
            User claims if valid, None otherwise
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=["HS256"]
            )
            return payload
        except JWTError:
            return None
    
    async def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch user details from Neon Auth.
        
        Args:
            user_id: User identifier
            
        Returns:
            User data if found, None otherwise
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/users/{user_id}",
                headers={"Authorization": f"Bearer {self.secret_key}"}
            )
            if response.status_code == 200:
                return response.json()
            return None
    
    async def check_mfa_required(self, user_roles: List[str]) -> bool:
        """
        Check if MFA is required for the given user roles per R-56.
        
        Args:
            user_roles: List of user roles
            
        Returns:
            True if MFA is required, False otherwise
        """
        return any(role in MFA_REQUIRED_ROLES for role in user_roles)
    
    def generate_mfa_secret(self) -> str:
        """
        Generate a new TOTP secret for MFA.
        
        Returns:
            Base32 encoded secret
        """
        return pyotp.random_base32()
    
    def encrypt_mfa_secret(self, secret: str) -> str:
        """
        Encrypt MFA secret for storage (data at rest per R-57).
        
        Args:
            secret: Plain text MFA secret
            
        Returns:
            Encrypted secret
        """
        encrypted = cipher_suite.encrypt(secret.encode())
        return base64.urlsafe_b64encode(encrypted).decode()
    
    def decrypt_mfa_secret(self, encrypted_secret: str) -> str:
        """
        Decrypt MFA secret from storage.
        
        Args:
            encrypted_secret: Encrypted MFA secret
            
        Returns:
            Plain text MFA secret
        """
        encrypted = base64.urlsafe_b64decode(encrypted_secret.encode())
        decrypted = cipher_suite.decrypt(encrypted)
        return decrypted.decode()
    
    def verify_mfa_token(self, secret: str, token: str) -> bool:
        """
        Verify TOTP token against secret.
        
        Args:
            secret: MFA secret (plain text)
            token: 6-digit TOTP token
            
        Returns:
            True if valid, False otherwise
        """
        totp = pyotp.TOTP(secret)
        return totp.verify(token, valid_window=1)  # Allow 1 step tolerance


# Password verification functions removed per AQ6 architecture.
# FastAPI does NOT verify passwords - Neon Auth owns password verification entirely.
# These functions are kept only for Phase 2 SSO migration compatibility if needed.


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: Token payload data
        expires_delta: Optional expiration time delta
        
    Returns:
        JWT token string
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=SESSION_TIMEOUT_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, NEON_AUTH_SECRET_KEY, algorithm="HS256")
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and verify a JWT access token.
    
    Args:
        token: JWT token string
        
    Returns:
        Token payload if valid, None otherwise
    """
    try:
        payload = jwt.decode(
            token,
            NEON_AUTH_SECRET_KEY,
            algorithms=["HS256"],
            options={"verify_exp": True}
        )
        return payload
    except JWTError:
        return None


# SSO/OAuth connector scaffolding for Phase 2
class SSOConnector:
    """
    SSO/OAuth connector for Phase 2 integration.
    Currently empty scaffolding per AQ5 assumption.
    """
    
    def __init__(self):
        self.provider = os.getenv("SSO_PROVIDER")
        self.client_id = os.getenv("SSO_CLIENT_ID")
        self.client_secret = os.getenv("SSO_CLIENT_SECRET")
    
    async def authenticate(self, code: str) -> Optional[Dict[str, Any]]:
        """
        Authenticate via SSO/OAuth.
        
        Args:
            code: Authorization code from SSO provider
            
        Returns:
            User data if successful, None otherwise
        """
        # Phase 2 implementation
        raise NotImplementedError("SSO/OAuth is Phase 2 scope")


# Global auth client instance
auth_client = NeonAuthClient()
