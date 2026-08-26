"""
Clerk integration for authentication and authorization.
Implements Clerk JWT verification using JWKS endpoint.
MFA support for Admin and SuperAdmin roles per R-56.
"""
import os
import time
from typing import Optional, Dict, Any, List, Tuple
from jose import JWTError, jwt as jose_jwt
import jwt as pyjwt
from jwt import PyJWKClient, InvalidTokenError
from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import httpx
import pyotp
from cryptography.fernet import Fernet
import base64

load_dotenv()

# Clerk configuration
CLERK_JWKS_URL = os.getenv("CLERK_JWKS_URL")
CLERK_SECRET_KEY = os.getenv("CLERK_SECRET_KEY")
MFA_REQUIRED_ROLES = os.getenv("MFA_REQUIRED_ROLES", "Admin,SuperAdmin").split(",")
SESSION_TIMEOUT_MINUTES = int(os.getenv("SESSION_TIMEOUT_MINUTES", "30"))

# Separate platform JWT secret for HS256 signing (C4 security fix)
# Platform tokens are only used in tests; production tokens come from Clerk (RS256).
# Falls back to CLERK_SECRET_KEY with a warning if not set.
PLATFORM_JWT_SECRET = os.getenv("PLATFORM_JWT_SECRET")
if not PLATFORM_JWT_SECRET:
    if CLERK_SECRET_KEY:
        import warnings as _warnings
        _warnings.warn(
            "PLATFORM_JWT_SECRET not set. Falling back to CLERK_SECRET_KEY for HS256 signing. "
            "Set PLATFORM_JWT_SECRET in production to separate platform token signing from Clerk API key.",
            stacklevel=2,
        )
        PLATFORM_JWT_SECRET = CLERK_SECRET_KEY
    else:
        PLATFORM_JWT_SECRET = None

# Cached JWKS client for Clerk (RS256 / asymmetric session JWTs)
_jwks_client: Optional[PyJWKClient] = None

# Token cache to reduce verification overhead
_token_cache: Dict[str, Tuple[Dict[str, Any], float]] = {}
CACHE_TTL_SECONDS = 300  # 5 minutes cache for JWT tokens
SESSION_CACHE_TTL_SECONDS = 60  # 1 minute cache for session validation


def _get_jwks_client() -> Optional[PyJWKClient]:
    """Return a cached PyJWKClient for Clerk JWKS, or None if unconfigured."""
    global _jwks_client
    if not CLERK_JWKS_URL:
        return None
    if _jwks_client is None:
        _jwks_client = PyJWKClient(CLERK_JWKS_URL)
    return _jwks_client


def _is_cache_valid(timestamp: float, ttl: int = CACHE_TTL_SECONDS) -> bool:
    """Check if cache entry is still valid."""
    return (time.time() - timestamp) < ttl

# Encryption key for MFA secrets (data at rest per R-57)
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
env = os.getenv("ENV", "development")

if not ENCRYPTION_KEY:
    if env == "production":
        raise ValueError(
            "ENCRYPTION_KEY environment variable is required in production. "
            "This key is used to encrypt MFA secrets at rest. "
            "Without it, the application cannot start securely. "
            "Note: Changing this key will invalidate existing encrypted MFA secrets."
        )
    else:
        # Generate a key for development only
        print("WARNING: ENCRYPTION_KEY not set. Generating a temporary key for development only.")
        ENCRYPTION_KEY = Fernet.generate_key().decode()
        print(f"Generated ENCRYPTION_KEY: {ENCRYPTION_KEY}")
        print("This key will change on restart. Set ENCRYPTION_KEY in your .env file for persistence.")

cipher_suite = Fernet(ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class ClerkClient:
    """
    Client for interacting with Clerk authentication.
    Handles JWT verification and MFA token management.
    """

    def __init__(self):
        self.jwks_url = CLERK_JWKS_URL
        self.secret_key = CLERK_SECRET_KEY
    
    async def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verify a JWT token from Clerk using JWKS.

        Args:
            token: JWT token string

        Returns:
            User claims if valid, None otherwise
        """
        try:
            return decode_access_token(token)
        except Exception:
            return None

    async def get_user_claims(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch user claims from Clerk API to supplement JWT claims.

        Clerk JWTs don't include user profile data, so we fetch it separately.

        Args:
            user_id: Clerk user ID

        Returns:
            User claims dict if found, None otherwise
        """
        if not self.secret_key:
            return None

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://api.clerk.com/v1/users/{user_id}",
                    headers={"Authorization": f"Bearer {self.secret_key}"}
                )
                if response.status_code == 200:
                    user_data = response.json()
                    # Map Clerk user data to our expected claims
                    return {
                        "sub": user_data.get("id"),
                        "email": user_data.get("email_addresses", [{}])[0].get("email_address") if user_data.get("email_addresses") else None,
                        "name": user_data.get("first_name") + " " + user_data.get("last_name", "") if user_data.get("first_name") else user_data.get("username"),
                        # Note: roles, school_id, department_id come from our database
                        "roles": [],
                        "school_id": None,
                        "department_id": None
                    }
                return None
        except httpx.HTTPError:
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
    if not PLATFORM_JWT_SECRET:
        raise ValueError("Neither PLATFORM_JWT_SECRET nor CLERK_SECRET_KEY is configured")
    encoded_jwt = jose_jwt.encode(to_encode, PLATFORM_JWT_SECRET, algorithm="HS256")
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and verify a JWT access token with caching.

    Uses Clerk JWKS verification (RS256 session tokens).
    Clerk JWTs contain 'sub' for user ID and standard JWT claims.

    Args:
        token: JWT token string

    Returns:
        Token payload if valid, None otherwise
    """
    if not token:
        print("DEBUG: decode_access_token called with empty token")
        return None

    print(f"DEBUG: decode_access_token called with token length: {len(token)}")

    # Check cache first
    if token in _token_cache:
        cached_payload, timestamp = _token_cache[token]
        if _is_cache_valid(timestamp):
            print("DEBUG: Token found in cache")
            return cached_payload
        else:
            del _token_cache[token]
            print("DEBUG: Token found in cache but expired")

    # Clerk asymmetric JWT via JWKS
    jwks_client = _get_jwks_client()
    if jwks_client is not None:
        try:
            print("DEBUG: Attempting JWKS verification")
            signing_key = jwks_client.get_signing_key_from_jwt(token)
            payload = pyjwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256", "ES256"],
                options={"verify_aud": False, "verify_exp": True, "verify_nbf": False, "leeway": 120},
            )
            print(f"DEBUG: JWKS verification successful, payload keys: {list(payload.keys())}")
            # Cache the successful verification
            _token_cache[token] = (payload, time.time())
            return payload
        except (InvalidTokenError, JWTError, Exception) as e:
            # Log the error for debugging
            print(f"DEBUG: JWKS verification failed: {e}")
            pass

    # Fallback to HS256 for platform-issued tokens (tests / internal)
    if not PLATFORM_JWT_SECRET:
        print("DEBUG: PLATFORM_JWT_SECRET not set, cannot attempt HS256 fallback")
        return None
    try:
        print("DEBUG: Attempting HS256 verification")
        payload = pyjwt.decode(
            token,
            PLATFORM_JWT_SECRET,
            algorithms=["HS256"],
            options={"verify_exp": True},
        )
        print(f"DEBUG: HS256 verification successful, payload keys: {list(payload.keys())}")
        # Cache the successful verification
        _token_cache[token] = (payload, time.time())
        return payload
    except (InvalidTokenError, JWTError, Exception) as e:
        print(f"DEBUG: HS256 verification failed: {e}")
        try:
            # python-jose fallback for older token shapes
            print("DEBUG: Attempting python-jose HS256 verification")
            payload = jose_jwt.decode(
                token,
                PLATFORM_JWT_SECRET,
                algorithms=["HS256"],
                options={"verify_exp": True},
            )
            print(f"DEBUG: python-jose verification successful, payload keys: {list(payload.keys())}")
            # Cache the successful verification
            _token_cache[token] = (payload, time.time())
            return payload
        except JWTError as e:
            print(f"DEBUG: python-jose verification failed: {e}")
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
auth_client = ClerkClient()


async def sync_roles_to_clerk(clerk_user_id: str, roles: List[str]) -> bool:
    """
    Sync user roles from the database to Clerk's publicMetadata.
    
    The frontend reads roles from Clerk's publicMetadata to control navigation.
    This function must be called whenever roles are created, assigned, or revoked
    in the database to keep the two systems in sync.
    
    Args:
        clerk_user_id: The Clerk user ID (e.g., user_xxx)
        roles: List of role strings to sync (e.g., ["superadmin", "admin"])
        
    Returns:
        True if sync succeeded, False otherwise (logged, never raises)
    """
    if not CLERK_SECRET_KEY or not clerk_user_id:
        print(f"WARNING: sync_roles_to_clerk skipped - CLERK_SECRET_KEY={'set' if CLERK_SECRET_KEY else 'missing'}, clerk_user_id={'set' if clerk_user_id else 'missing'}")
        return False
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"https://api.clerk.com/v1/users/{clerk_user_id}/metadata",
                headers={
                    "Authorization": f"Bearer {CLERK_SECRET_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "publicMetadata": {
                        "roles": roles
                    }
                },
                timeout=10.0
            )
            if response.status_code == 200:
                print(f"DEBUG: Clerk roles synced for {clerk_user_id}: {roles}")
                return True
            else:
                print(f"WARNING: Clerk roles sync failed for {clerk_user_id}: {response.status_code} {response.text}")
                return False
    except Exception as e:
        print(f"ERROR: Clerk roles sync exception for {clerk_user_id}: {e}")
        return False
