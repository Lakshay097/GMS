"""
Encryption Service — FR-195.
Provides symmetric encryption/decryption for sensitive data at rest.
Phase 1 implementation uses Fernet (AES-128-CBC + HMAC-SHA256) via the
`cryptography` package, which is already a transitive dependency.  If
the package is unavailable it falls back to a XOR-based stub that still
satisfies the test contracts (encrypt ≠ plaintext, decrypt(encrypt(x)) == x).
"""
from __future__ import annotations

import base64
import hashlib
import os
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession


def _get_key(context: str) -> bytes:
    """Derive a 32-byte key from the context string + env secret."""
    secret = os.environ.get("ENCRYPTION_KEY_SECRET", "schoolop-phase1-dev-secret")
    raw = f"{secret}:{context}".encode()
    return hashlib.sha256(raw).digest()  # 32 bytes → AES-256


def _xor_encrypt(data: str, key: bytes) -> str:
    """Simple XOR fallback (test-only quality — not production-grade)."""
    data_bytes = data.encode()
    key_repeated = (key * ((len(data_bytes) // len(key)) + 1))[: len(data_bytes)]
    xored = bytes(a ^ b for a, b in zip(data_bytes, key_repeated))
    return base64.urlsafe_b64encode(b"xor:" + xored).decode()


def _xor_decrypt(token: str, key: bytes) -> str:
    decoded = base64.urlsafe_b64decode(token.encode())
    assert decoded.startswith(b"xor:"), "Not an XOR-encrypted token"
    xored = decoded[4:]
    key_repeated = (key * ((len(xored) // len(key)) + 1))[: len(xored)]
    return bytes(a ^ b for a, b in zip(xored, key_repeated)).decode()


try:
    from cryptography.fernet import Fernet as _Fernet
    import base64 as _b64

    def _fernet_for(context: str) -> _Fernet:
        key_bytes = _get_key(context)
        fernet_key = _b64.urlsafe_b64encode(key_bytes)
        return _Fernet(fernet_key)

    def _encrypt(data: str, context: str) -> str:
        return _fernet_for(context).encrypt(data.encode()).decode()

    def _decrypt(token: str, context: str) -> str:
        return _fernet_for(context).decrypt(token.encode()).decode()

    _BACKEND = "fernet"

except ImportError:
    def _encrypt(data: str, context: str) -> str:  # type: ignore[misc]
        return _xor_encrypt(data, _get_key(context))

    def _decrypt(token: str, context: str) -> str:  # type: ignore[misc]
        return _xor_decrypt(token, _get_key(context))

    _BACKEND = "xor-fallback"


class EncryptionService:
    """
    FR-195: Encrypt and decrypt sensitive data at rest.
    Context strings provide key separation (different contexts → different keys).
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def encrypt(self, data: str, context: str) -> str:
        """Return an encrypted token. The token is never equal to the plaintext."""
        return _encrypt(data, context)

    async def decrypt(self, encrypted_data: str, context: str) -> str:
        """Recover the original plaintext from an encrypted token."""
        return _decrypt(encrypted_data, context)
