"""
Password Policy Service — FR-196.
Validates passwords against the platform security policy (PRS §36).
Policy:
  - Minimum 12 characters
  - At least one uppercase letter
  - At least one lowercase letter
  - At least one digit
  - At least one special character from: !@#$%^&*()_+-=[]{}|;:,.<>?
Phase 2 will add per-school configurable policy via ConfigurationEngine.
"""
from __future__ import annotations

import re
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


_MIN_LENGTH = 12
_SPECIAL_CHARS = r"[!@#$%^&*()\-_=+\[\]{}|;:,.<>?/\\]"

_POLICY_CHECKS = [
    (lambda p: len(p) >= _MIN_LENGTH, "at least 12 characters"),
    (lambda p: bool(re.search(r"[A-Z]", p)), "an uppercase letter"),
    (lambda p: bool(re.search(r"[a-z]", p)), "a lowercase letter"),
    (lambda p: bool(re.search(r"\d", p)), "a digit"),
    (lambda p: bool(re.search(_SPECIAL_CHARS, p)), "a special character"),
]


class PasswordService:
    """
    FR-196: Password policy enforcement.
    validate_password_policy() returns True if the password meets all rules,
    False otherwise.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def validate_password_policy(
        self,
        password: str,
        user_id: Optional[UUID] = None,  # Reserved: Phase 2 will check password history
    ) -> bool:
        """
        Return True if the password satisfies all policy rules, False otherwise.
        Does NOT raise — callers must inspect the return value.
        """
        return all(check(password) for check, _ in _POLICY_CHECKS)

    async def list_policy_violations(self, password: str) -> list[str]:
        """Return a list of human-readable violation descriptions, empty if compliant."""
        return [desc for check, desc in _POLICY_CHECKS if not check(password)]
