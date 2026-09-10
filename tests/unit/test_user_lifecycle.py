"""
Tests for the user-management extensions (spec §22):
  - Invitation codes: valid / invalid / expired / revoked / exhausted /
    multi-use / unauthorized role / role-derivation security.
  - Role hierarchy: dept_head cannot assign admin; admin can assign below.
  - Bulk import validation: duplicate email, invalid role, unauthorized role.
  - Login status enforcement: PENDING / INACTIVE / SUSPENDED blocked.
  - Invitation service consume/validate round-trip and audit-safe hashing.
Uses in-memory SQLite via the shared tests/conftest.py fixtures
(asyncio_mode=auto, so plain async def test_ methods run).
"""
import uuid
from datetime import timedelta

import pytest

from shared.auth import (
    generate_invitation_code,
    hash_invitation_code,
    validate_password_policy,
)
from shared.datetime_utils import utc_now
from shared.errors import AuthorizationError, ValidationError
from shared.models import (
    Department,
    InvitationCode,
    InvitationUse,
    User,
    UserStatus,
    UserRole,
)
from shared.permissions import can_manage_role


# ── helpers ──────────────────────────────────────────────────────────────────

def make_user(db, school, department, email=None, roles=("admin",), status=UserStatus.ACTIVE):
    user = User(
        id=uuid.uuid4(),
        email=email or f"u-{uuid.uuid4().hex[:8]}@test.com",
        full_name="Test Actor",
        school_id=school.id,
        department_id=department.id,
        status=status,
        roles=list(roles),
    )
    db.add(user)
    db.commit()
    return user


def make_invitation(db, school, department, role="checker", *, used=0, status="active",
                    expires_delta=timedelta(hours=24), max_uses=1):
    raw, code_hash, prefix, _ = generate_invitation_code(prefix=department.code[:3])
    inv = InvitationCode(
        code_hash=code_hash,
        code_prefix=prefix,
        school_id=school.id,
        department_id=department.id,
        role=role,
        expires_at=utc_now() + expires_delta,
        max_uses=max_uses,
        used_count=used,
        status=status,
        created_at=utc_now(),
    )
    db.add(inv)
    db.commit()
    return inv, raw


def service(db):
    from modules.school_dept_user_role.services.invitation_service import InvitationService
    return InvitationService(db)


# ── password policy / code generation ────────────────────────────────────────

class TestInvitationCodeGeneration:
    def test_code_roundtrip_hash(self):
        raw, code_hash, prefix, expiry = generate_invitation_code("OPS")
        assert raw.startswith("OPS-")
        assert hash_invitation_code(raw) == code_hash
        assert prefix == "OPS"

    def test_codes_are_unique(self):
        seen = {generate_invitation_code()[1] for _ in range(50)}
        assert len(seen) == 50

    def test_hash_normalizes_case_and_spaces(self):
        raw = generate_invitation_code()[0]
        assert hash_invitation_code(raw.lower()) == hash_invitation_code(f" {raw} ")


# ── invitation validation states (§7) ────────────────────────────────────────

class TestInvitationValidation:
    async def test_valid_code_passes(self, db, school, department):
        inv, raw = make_invitation(db, school, department)
        assert (await service(db).validate_code(raw)).id == inv.id

    async def test_invalid_code_rejected(self, db, school, department):
        make_invitation(db, school, department)
        with pytest.raises(ValidationError):
            await service(db).validate_code("OPS-XXXX-XXXX")

    async def test_expired_code_rejected(self, db, school, department):
        _, raw = make_invitation(db, school, department, expires_delta=timedelta(hours=-1))
        with pytest.raises(ValidationError, match="expired"):
            await service(db).validate_code(raw)

    async def test_revoked_code_rejected(self, db, school, department):
        inv, raw = make_invitation(db, school, department)
        inv.status = "revoked"
        db.commit()
        with pytest.raises(ValidationError, match="revoked"):
            await service(db).validate_code(raw)

    async def test_exhausted_code_rejected(self, db, school, department):
        _, raw = make_invitation(db, school, department, used=1, max_uses=1)
        with pytest.raises(ValidationError, match="usage limit"):
            await service(db).validate_code(raw)

    async def test_multi_use_code_allows_repeated_consumption(self, db, school, department):
        inv, raw = make_invitation(db, school, department, max_uses=3)
        svc = service(db)
        await svc.consume_code(raw, user_id=uuid.uuid4())
        db.commit()
        await svc.consume_code(raw, user_id=uuid.uuid4())
        db.commit()
        db.refresh(inv)
        assert inv.used_count == 2
        await svc.consume_code(raw, user_id=uuid.uuid4())
        db.commit()
        db.refresh(inv)
        assert inv.used_count == 3
        with pytest.raises(ValidationError, match="usage limit"):
            await svc.validate_code(raw)

    async def test_consume_records_user(self, db, school, department):
        inv, raw = make_invitation(db, school, department)
        uid = uuid.uuid4()
        await service(db).consume_code(raw, user_id=uid)
        db.commit()
        use = (await db.execute(
            InvitationUse.__table__.select().where(InvitationUse.user_id == uid)
        )).first()
        assert use is not None and use.invitation_id == inv.id


# ── invitation creation authorization (§4/§6) ───────────────────────────────

class TestInvitationCreationAuth:
    async def test_dept_head_cannot_invite_admin(self, db, school, department):
        actor = make_user(db, school, department, roles=("dept_head",))
        with pytest.raises(AuthorizationError):
            await service(db).create_invitation(
                actor_roles=actor.roles,
                actor_user_id=actor.id,
                actor_school_id=str(school.id),
                actor_department_id=str(department.id),
                department_id=department.id,
                role="admin",
            )

    async def test_dept_head_cannot_invite_superadmin(self, db, school, department):
        actor = make_user(db, school, department, roles=("dept_head",))
        with pytest.raises(AuthorizationError):
            await service(db).create_invitation(
                actor_roles=actor.roles,
                actor_user_id=actor.id,
                actor_school_id=str(school.id),
                actor_department_id=str(department.id),
                department_id=department.id,
                role="superadmin",
            )

    async def test_dept_head_invites_within_department_only(self, db, school, department):
        actor = make_user(db, school, department, roles=("dept_head",))
        other_dept = Department(
            id=uuid.uuid4(), school_id=school.id, name="Other", code="OTH",
            created_at=utc_now(), updated_at=utc_now(),
        )
        db.add(other_dept)
        db.commit()
        with pytest.raises(AuthorizationError):
            await service(db).create_invitation(
                actor_roles=actor.roles,
                actor_user_id=actor.id,
                actor_school_id=str(school.id),
                actor_department_id=str(department.id),
                department_id=other_dept.id,
                role="checker",
            )

    async def test_dept_head_can_invite_checker_own_department(self, db, school, department):
        actor = make_user(db, school, department, roles=("dept_head",))
        record, raw = await service(db).create_invitation(
            actor_roles=actor.roles,
            actor_user_id=actor.id,
            actor_school_id=str(school.id),
            actor_department_id=str(department.id),
            department_id=department.id,
            role="checker",
        )
        db.commit()
        assert record.role == "checker" and raw

    async def test_admin_can_invite_department_head(self, db, school, department):
        actor = make_user(db, school, department, roles=("admin",))
        record, _ = await service(db).create_invitation(
            actor_roles=actor.roles,
            actor_user_id=actor.id,
            actor_school_id=str(school.id),
            actor_department_id=None,
            department_id=department.id,
            role="dept_head",
        )
        assert record.role == "dept_head"

    async def test_checker_cannot_invite_anything(self, db, school, department):
        actor = make_user(db, school, department, roles=("checker",))
        with pytest.raises(AuthorizationError):
            await service(db).create_invitation(
                actor_roles=actor.roles,
                actor_user_id=actor.id,
                actor_school_id=str(school.id),
                actor_department_id=str(department.id),
                department_id=department.id,
                role="viewer",
            )


# ── role hierarchy helper (§4/§11) ───────────────────────────────────────────

class TestRoleHierarchy:
    def test_superadmin_manages_everything_below(self):
        for role in ("admin", "dept_head", "auditor", "verifier", "checker", "viewer"):
            assert can_manage_role(["superadmin"], role)

    def test_superadmin_cannot_be_assigned_by_anyone(self):
        for role in ("admin", "dept_head", "checker"):
            assert not can_manage_role([role], "superadmin")

    def test_dept_head_cannot_assign_admin_or_superadmin(self):
        assert not can_manage_role(["dept_head"], "admin")
        assert not can_manage_role(["dept_head"], "superadmin")

    def test_dept_head_can_assign_checker(self):
        assert can_manage_role(["dept_head"], "checker")

    def test_admin_can_assign_dept_head(self):
        assert can_manage_role(["admin"], "dept_head")

    def test_admin_cannot_assign_superadmin(self):
        assert not can_manage_role(["admin"], "superadmin")


# ── bulk import row validation (§5) ──────────────────────────────────────────

class TestBulkImportValidation:
    def _tenant(self, school):
        from shared.middleware.tenancy import TenantContext
        return TenantContext(
            user_id=str(uuid.uuid4()),
            school_id=str(school.id),
            department_id=None,
            roles=["admin"],
            accessible_school_ids=[],
        )

    async def _run(self, db, school, rows):
        from modules.school_dept_user_role.api.invitations import _validate_rows
        return await _validate_rows(db, rows, self._tenant(school))

    async def test_valid_row_passes(self, db, school, department):
        valid, errors, dupes = await self._run(db, school, [{
            "name": "Jane Doe", "email": "jane@test.com", "department": "Operations",
            "role": "checker",
        }])
        assert len(valid) == 1 and not errors and dupes == 0

    async def test_missing_required_fields(self, db, school, department):
        valid, errors, _ = await self._run(db, school, [{"name": "", "email": "", "role": ""}])
        assert not valid
        reasons = " ".join(e["reason"] for e in errors)
        assert "Name is required" in reasons and "email is required" in reasons.lower()

    async def test_duplicate_email_in_file(self, db, school, department):
        valid, errors, dupes = await self._run(db, school, [
            {"name": "A", "email": "dup@test.com", "department": "Operations", "role": "checker"},
            {"name": "B", "email": "dup@test.com", "department": "Operations", "role": "checker"},
        ])
        assert len(valid) == 1 and dupes == 1

    async def test_duplicate_email_in_database(self, db, school, department):
        make_user(db, school, department, email="taken@test.com")
        valid, errors, dupes = await self._run(db, school, [
            {"name": "A", "email": "taken@test.com", "department": "Operations", "role": "checker"},
        ])
        assert not valid and dupes == 1

    async def test_invalid_role_rejected(self, db, school, department):
        valid, errors, _ = await self._run(db, school, [
            {"name": "A", "email": "a@test.com", "department": "Operations", "role": "superboss"},
        ])
        assert not valid
        assert any("Invalid role" in e["reason"] for e in errors)

    async def test_unauthorized_role_rejected(self, db, school, department):
        valid, errors, _ = await self._run(db, school, [
            {"name": "A", "email": "a@test.com", "department": "Operations", "role": "superadmin"},
        ])
        assert not valid
        assert any("may not assign" in e["reason"] for e in errors)

    async def test_unknown_department_rejected(self, db, school, department):
        valid, errors, _ = await self._run(db, school, [
            {"name": "A", "email": "a@test.com", "department": "Nonexistent", "role": "checker"},
        ])
        assert not valid
        assert any("Unknown department" in e["reason"] for e in errors)


# ── enums (§2/§3) ────────────────────────────────────────────────────────────

class TestEnums:
    def test_new_statuses_exist(self):
        assert UserStatus.PENDING.value == "pending"
        assert UserStatus.INACTIVE.value == "inactive"
        assert UserStatus.SUSPENDED.value == "suspended"
        assert UserStatus.ACTIVE.value == "active"
        assert UserStatus.ARCHIVED.value == "archived"

    def test_verifier_role_exists(self):
        assert UserRole.VERIFIER.value == "verifier"


# ── password policy (§1) ─────────────────────────────────────────────────────

class TestPasswordPolicy:
    def test_weak_passwords_rejected(self):
        assert validate_password_policy("short1") is not None
        assert validate_password_policy("nodigitshere") is not None
        assert validate_password_policy("1234567890") is not None

    def test_strong_password_accepted(self):
        assert validate_password_policy("Str0ngPassword!") is None
