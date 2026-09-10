"""
Self-managed authentication for SchoolOps.

Replaces Clerk entirely:
  - Password hashing: Argon2id (never plaintext, never MD5/SHA-1).
  - Sessions: opaque cryptographically-random tokens stored in Neon PostgreSQL.
    Only a SHA-256 HASH of the token is persisted; the browser receives the raw
    token exclusively through a Secure, HttpOnly, SameSite cookie.
  - Login / logout / session validation / password change / password reset.

Authorization (roles, permissions, school/department isolation) remains in
shared.middleware.tenancy / shared.middleware.permissions — authentication
answers "who is the user", authorization answers "what can they do".
"""
import hashlib
import hmac
import logging
import os
import re
import secrets
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from dotenv import load_dotenv
from cryptography.fernet import Fernet

load_dotenv()

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────

SESSION_TIMEOUT_MINUTES = int(os.getenv("SESSION_TIMEOUT_MINUTES", "30"))
SESSION_ABSOLUTE_TIMEOUT_HOURS = int(os.getenv("SESSION_ABSOLUTE_TIMEOUT_HOURS", "12"))
SESSION_CLEANUP_GRACE_HOURS = int(os.getenv("SESSION_CLEANUP_GRACE_HOURS", "24"))
COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "schoolops_session")
MFA_REQUIRED_ROLES = os.getenv("MFA_REQUIRED_ROLES", "Admin,SuperAdmin").split(",")

# ── Argon2id password hashing ─────────────────────────────────────────────────

try:
    from argon2 import PasswordHasher
    from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

    _hasher = PasswordHasher(
        time_cost=3,        # OWASP-recommended Argon2id parameters
        memory_cost=65536,  # 64 MiB
        parallelism=4,
        hash_len=32,
        salt_len=16,
    )

    def hash_password(password: str) -> str:
        """Hash a password with Argon2id (salted, self-contained hash string)."""
        return _hasher.hash(password)

    def verify_password(password_hash: Optional[str], password: str) -> bool:
        """Verify a password against an Argon2id hash in constant time."""
        if not password_hash or not password:
            return False
        try:
            return _hasher.verify(password_hash, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError, Exception):
            return False

    def needs_rehash(password_hash: str) -> bool:
        """True if the hash should be upgraded (parameters changed since hashing)."""
        try:
            return _hasher.check_needs_rehash(password_hash)
        except Exception:
            return False

except ImportError:  # pragma: no cover — argon2-cffi is in requirements.txt
    raise ImportError(
        "argon2-cffi is required for password hashing. "
        "Install it with: pip install argon2-cffi"
    )

# ── Password policy ───────────────────────────────────────────────────────────

MIN_PASSWORD_LENGTH = int(os.getenv("MIN_PASSWORD_LENGTH", "10"))


def validate_password_policy(password: str) -> Optional[str]:
    """
    Validate a password against the platform policy.
    Returns an error message, or None when the password is acceptable.
    """
    if not password or len(password) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters long"
    if not re.search(r"[A-Za-z]", password):
        return "Password must contain at least one letter"
    if not re.search(r"\d", password):
        return "Password must contain at least one number"
    return None

# ── Session tokens ────────────────────────────────────────────────────────────

def generate_session_token() -> Tuple[str, str]:
    """
    Generate a cryptographically secure session token.

    Returns (raw_token, token_hash). Only token_hash is ever stored in the
    database; the raw token goes to the browser in an HTTP-only cookie.
    """
    raw_token = secrets.token_urlsafe(48)
    return raw_token, hash_session_token(raw_token)


def hash_session_token(token: str) -> str:
    """SHA-256 hash of a session token — this is what gets persisted."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def compare_session_tokens(token_hash_a: str, token_hash_b: str) -> bool:
    """Constant-time comparison of two session-token hashes."""
    return hmac.compare_digest(token_hash_a, token_hash_b)

# ── Session expiry helpers ────────────────────────────────────────────────────

def session_expiry_dates(now: Optional[datetime] = None) -> Tuple[datetime, datetime]:
    """
    Returns (expires_at, absolute_expires_at) for a new session.
    - expires_at: sliding idle timeout (extended on activity).
    - absolute_expires_at: hard ceiling regardless of activity.
    """
    now = now or datetime.now(timezone.utc)
    return (
        now + timedelta(minutes=SESSION_TIMEOUT_MINUTES),
        now + timedelta(hours=SESSION_ABSOLUTE_TIMEOUT_HOURS),
    )


# ── MFA secret encryption (data at rest per R-57) ────────────────────────────

ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
_env = os.getenv("ENV", "development")

if not ENCRYPTION_KEY:
    if _env == "production":
        raise ValueError(
            "ENCRYPTION_KEY environment variable is required in production. "
            "This key is used to encrypt MFA secrets at rest. "
            "Note: Changing this key will invalidate existing encrypted MFA secrets."
        )
    else:
        logger.warning("ENCRYPTION_KEY not set. Generating a temporary key for development only.")
        ENCRYPTION_KEY = Fernet.generate_key().decode()
        print(f"Generated ENCRYPTION_KEY: {ENCRYPTION_KEY}")
        print("This key will change on restart. Set ENCRYPTION_KEY in your .env file for persistence.")

cipher_suite = Fernet(ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY)


def generate_mfa_secret() -> str:
    """Generate a new base32 TOTP secret for MFA."""
    import pyotp
    return pyotp.random_base32()


def encrypt_mfa_secret(secret: str) -> str:
    """Encrypt an MFA secret for storage (data at rest per R-57)."""
    encrypted = cipher_suite.encrypt(secret.encode())
    return encrypted.decode()


def decrypt_mfa_secret(encrypted_secret: str) -> str:
    """Decrypt an MFA secret from storage."""
    decrypted = cipher_suite.decrypt(encrypted_secret.encode())
    return decrypted.decode()


def verify_mfa_token(secret: str, token: str) -> bool:
    """Verify a 6-digit TOTP token against a secret (1 step tolerance)."""
    import pyotp
    totp = pyotp.TOTP(secret)
    return totp.verify(token, valid_window=1)


def check_mfa_required(user_roles: list) -> bool:
    """Check if MFA is required for the given user roles per R-56."""
    return any(role in MFA_REQUIRED_ROLES for role in user_roles)

# ── Password reset tokens ─────────────────────────────────────────────

PASSWORD_RESET_TIMEOUT_MINUTES = int(os.getenv("PASSWORD_RESET_TIMEOUT_MINUTES", "30"))


def generate_password_reset_token() -> Tuple[str, str, datetime]:
    """
    Generate a password-reset token.
    Returns (raw_token, token_hash, expires_at). Only the hash is stored.
    """
    raw_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=PASSWORD_RESET_TIMEOUT_MINUTES)
    return raw_token, hash_session_token(raw_token), expires_at


# ── Invitation codes (user-management spec §6-7) ────────────────────────────

import string as _string
import uuid as _uuid

INVITE_EXPIRY_HOURS = int(os.getenv("INVITE_EXPIRY_HOURS", "72"))
INVITE_MAX_USES_CAP = int(os.getenv("INVITE_MAX_USES_CAP", "100"))

# Crockford-style alphabet (no 0/O/1/I) for human-readable codes.
_INVITE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"


def generate_invitation_code(prefix: str = "OPS") -> Tuple[str, str, str, datetime]:
    """
    Generate a human-readable invitation code: PREFIX-XXXX-XXXX.

    Entropy: 8 chars from a 31-symbol alphabet ≈ 39.6 bits — sufficient for
    short-lived, rate-limited, use-capped credentials that are HASHED at
    rest and never grant login by themselves (signup also requires email +
    a policy-checked password, and brute force is bounded by expiry plus
    the 10/minute signup rate limit).

    Returns (raw_code, code_hash, code_prefix, expires_at).
    Only code_hash + code_prefix are persisted; the raw code is shown once.
    """
    import secrets as _secrets

    def _segment() -> str:
        return "".join(_secrets.choice(_INVITE_ALPHABET) for _ in range(4))

    safe_prefix = "".join(ch for ch in (prefix or "OPS").upper() if ch in _string.ascii_uppercase)[:3] or "OPS"
    raw_code = f"{safe_prefix}-{_segment()}-{_segment()}"
    expires_at = datetime.now(timezone.utc) + timedelta(hours=INVITE_EXPIRY_HOURS)
    return raw_code, hash_invitation_code(raw_code), safe_prefix, expires_at


def hash_invitation_code(raw_code: str) -> str:
    """Deterministic SHA-256 of a normalized invitation code (lookup-safe)."""
    normalized = "".join((raw_code or "").upper().split())
    return hash_session_token(normalized)


def generate_email_verification_token() -> Tuple[str, str, datetime]:
    """Generate a single-use email-verification token (same shape as reset tokens)."""
    raw_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=48)
    return raw_token, hash_session_token(raw_token), expires_at

# ── Legacy compatibility shims (tests / internal tooling) ─────────────────────

# Some tests and internal tooling sign their own platform tokens. The platform
# secret is used ONLY for that; user sessions never touch JWTs.
PLATFORM_JWT_SECRET = os.getenv("PLATFORM_JWT_SECRET")
if not PLATFORM_JWT_SECRET and _env != "production":
    PLATFORM_JWT_SECRET = None


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a platform JWT (HS256) for tests/internal services — NOT for user sessions."""
    import jwt as pyjwt
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=SESSION_TIMEOUT_MINUTES)
    to_encode.update({"exp": expire})
    if not PLATFORM_JWT_SECRET:
        raise ValueError("PLATFORM_JWT_SECRET is not configured")
    return pyjwt.encode(to_encode, PLATFORM_JWT_SECRET, algorithm="HS256")


def decode_access_token(token: str) -> Optional[dict]:
    """
    Decode a platform-issued HS256 JWT (tests/internal services only).

    Real user sessions are opaque tokens validated against the auth_sessions
    table — this function is never part of the browser login flow.
    """
    if not token or not PLATFORM_JWT_SECRET:
        return None
    try:
        import jwt as pyjwt
        return pyjwt.decode(
            token,
            PLATFORM_JWT_SECRET,
            algorithms=["HS256"],
            options={"verify_exp": True},
        )
    except Exception:
        return None

# ── In-memory session cache (optional optimization, bounded) ──────────────────
# Caches "token_hash → session snapshot" for 60s to avoid a DB round-trip on
# every request. Entries are evicted LRU-style; logout deletes the row so a
# cached entry is at most 60s stale — same guarantee as the Clerk token cache.

_session_cache: OrderedDict[str, Tuple[Optional[dict], float]] = OrderedDict()
SESSION_CACHE_TTL_SECONDS = 60
SESSION_CACHE_MAX_ENTRIES = 1000


def _session_cache_get(token_hash: str) -> Optional[dict]:
    entry = _session_cache.get(token_hash)
    if entry is None:
        return None
    snapshot, ts = entry
    import time
    if (time.time() - ts) < SESSION_CACHE_TTL_SECONDS:
        _session_cache.move_to_end(token_hash)
        return snapshot  # may be None (negative cache)
    _session_cache.pop(token_hash, None)
    return None


def _session_cache_put(token_hash: str, snapshot: Optional[dict]) -> None:
    import time
    if token_hash in _session_cache:
        _session_cache.move_to_end(token_hash)
    _session_cache[token_hash] = (snapshot, time.time())
    while len(_session_cache) > SESSION_CACHE_MAX_ENTRIES:
        _session_cache.popitem(last=False)


def _session_cache_invalidate(token_hash: str) -> None:
    _session_cache.pop(token_hash, None)
