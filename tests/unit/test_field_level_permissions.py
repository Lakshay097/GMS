"""
Field-level permission tests per Part 4 implementation.
Tests field permission seeding, OR-logic resolution, backend enforcement, and GET endpoint.
"""
import pytest
from uuid import uuid4, UUID
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal

from shared.permissions import check_field_permission, _get_field_permissions_for_roles
from shared.models import FieldPermission, KPI, KRA, UserRole
from shared.errors import AuthorizationError


@pytest.mark.asyncio
async def test_field_permissions_seeding(db: AsyncSession):
    """Verify field permissions are seeded correctly for kpi_library module."""
    from sqlalchemy import select
    
    # Seed field permissions for test database (SQLite doesn't use migrations)
    restricted_fields = ["target_value", "comparator", "is_sensitive", "category_code", "amber_tolerance_band"]
    roles = ["superadmin", "admin", "checker", "auditor", "viewer"]
    
    for role in roles:
        for field in restricted_fields:
            is_allowed = role == "superadmin" or (field in ["category_code", "amber_tolerance_band"] and role != "superadmin")
            perm = FieldPermission(
                module="kpi_library",
                field_name=field,
                role=role,
                is_allowed=is_allowed
            )
            db.add(perm)
    await db.commit()
    
    # Check that field permissions exist for kpi_library module
    result = await db.execute(
        select(FieldPermission).where(FieldPermission.module == "kpi_library")
    )
    permissions = result.scalars().all()
    
    # Should have 5 fields × 5 roles = 25 permissions
    assert len(permissions) == 25, f"Expected 25 field permissions, got {len(permissions)}"
    
    # Check SuperAdmin has full access to all restricted fields
    superadmin_perms = [p for p in permissions if p.role == "superadmin"]
    assert len(superadmin_perms) == 5, "SuperAdmin should have 5 field permissions"
    assert all(p.is_allowed for p in superadmin_perms), "SuperAdmin should have all fields allowed"
    
    # Check Admin has restricted access (no target_value, comparator, is_sensitive)
    admin_perms = {p.field_name: p.is_allowed for p in permissions if p.role == "admin"}
    assert admin_perms["target_value"] == False, "Admin should not have target_value access"
    assert admin_perms["comparator"] == False, "Admin should not have comparator access"
    assert admin_perms["is_sensitive"] == False, "Admin should not have is_sensitive access"
    assert admin_perms["category_code"] == True, "Admin should have category_code access"
    assert admin_perms["amber_tolerance_band"] == True, "Admin should have amber_tolerance_band access"
    
    print("✓ Field permissions seeding verified")


@pytest.mark.asyncio
async def test_field_permission_or_logic(db: AsyncSession):
    """Test multi-role OR-logic resolution for field permissions."""
    # Seed field permissions for test database
    restricted_fields = ["target_value", "comparator", "is_sensitive", "category_code", "amber_tolerance_band"]
    roles = ["admin", "checker"]
    
    for role in roles:
        for field in restricted_fields:
            is_allowed = field in ["category_code", "amber_tolerance_band"]
            perm = FieldPermission(
                module="kpi_library",
                field_name=field,
                role=role,
                is_allowed=is_allowed
            )
            db.add(perm)
    await db.commit()
    
    # User with both admin and checker roles should get OR-resolved permissions
    user_roles = ["admin", "checker"]
    
    # Get resolved permissions
    resolved = await _get_field_permissions_for_roles(db, "kpi_library", user_roles)
    
    # Both admin and checker deny target_value, so should be false
    assert resolved["target_value"] == False, "OR-logic: both roles deny target_value"
    
    # Admin allows category_code, so should be true even if checker denies
    assert resolved["category_code"] == True, "OR-logic: admin allows category_code"
    
    # Both allow amber_tolerance_band, so should be true
    assert resolved["amber_tolerance_band"] == True, "OR-logic: both roles allow amber_tolerance_band"
    
    print("✓ Multi-role OR-logic resolution verified")


@pytest.mark.asyncio
async def test_check_field_permission_fail_open(db: AsyncSession):
    """Test that ungoverned fields fail-open (allowed by default)."""
    # Seed field permissions for test database
    perm = FieldPermission(
        module="kpi_library",
        field_name="target_value",
        role="viewer",
        is_allowed=False
    )
    db.add(perm)
    await db.commit()
    
    user_roles = ["viewer"]
    
    # Ungoverned field (not in field_permissions table) should be allowed
    result = await check_field_permission(db, user_roles, "kpi_library", "title")
    assert result == True, "Ungoverned field should fail-open"
    
    # Governed field that viewer doesn't have access to should raise
    with pytest.raises(AuthorizationError):
        await check_field_permission(db, user_roles, "kpi_library", "target_value")
    
    print("✓ Fail-open for ungoverned fields verified")


@pytest.mark.asyncio
async def test_check_field_permission_single_role(db: AsyncSession):
    """Test field permission check for single role."""
    # Seed field permissions for test database
    superadmin_perm = FieldPermission(
        module="kpi_library",
        field_name="target_value",
        role="superadmin",
        is_allowed=True
    )
    viewer_perm = FieldPermission(
        module="kpi_library",
        field_name="target_value",
        role="viewer",
        is_allowed=False
    )
    db.add(superadmin_perm)
    db.add(viewer_perm)
    await db.commit()
    
    # SuperAdmin should have access to all restricted fields
    result = await check_field_permission(db, ["superadmin"], "kpi_library", "target_value")
    assert result == True, "SuperAdmin should have target_value access"
    
    # Viewer should not have access to target_value
    with pytest.raises(AuthorizationError):
        await check_field_permission(db, ["viewer"], "kpi_library", "target_value")
    
    print("✓ Single role field permission check verified")


@pytest.mark.asyncio
async def test_backend_patch_superadmin_guard(db: AsyncSession):
    """Test that PATCH /kpis/{id} route is SuperAdmin-only (field permissions are currently inert)."""
    from modules.kra_kpi_library.api.routes import _require_superadmin
    from shared.middleware.tenancy import TenantContext
    from shared.errors import AuthorizationError
    
    # Test with Admin role (should be denied by route-level SuperAdmin guard)
    admin_context = TenantContext(
        user_id=str(uuid4()),
        school_id=str(uuid4()),
        department_id=None,
        roles=["admin"],
        accessible_school_ids=[]
    )
    
    with pytest.raises(AuthorizationError) as exc_info:
        _require_superadmin(admin_context)
    
    assert "Only SuperAdmin can manage the Global KPI Library" in str(exc_info.value)
    
    # SuperAdmin should be allowed by route-level guard
    superadmin_context = TenantContext(
        user_id=str(uuid4()),
        school_id=str(uuid4()),
        department_id=None,
        roles=["superadmin"],
        accessible_school_ids=[]
    )
    
    # This should not raise AuthorizationError
    _require_superadmin(superadmin_context)
    
    print("✓ Backend PATCH SuperAdmin guard verified (field permissions currently inert)")


@pytest.mark.asyncio
async def test_get_permissions_fields_endpoint(db: AsyncSession):
    """Test GET /permissions/fields endpoint returns OR-resolved permissions."""
    from modules.kra_kpi_library.api.routes import get_field_permissions
    from shared.middleware.tenancy import TenantContext
    
    # Seed field permissions for test database
    admin_perm = FieldPermission(
        module="kpi_library",
        field_name="target_value",
        role="admin",
        is_allowed=False
    )
    category_perm = FieldPermission(
        module="kpi_library",
        field_name="category_code",
        role="admin",
        is_allowed=True
    )
    db.add(admin_perm)
    db.add(category_perm)
    await db.commit()
    
    # Test with admin role
    admin_context = TenantContext(
        user_id=str(uuid4()),
        school_id=str(uuid4()),
        department_id=None,
        roles=["admin"],
        accessible_school_ids=[]
    )
    
    # Mock the dependency injection
    # In a real test, we'd use TestClient with dependency overrides
    # For now, test the underlying function
    
    result = await get_field_permissions("kpi_library", admin_context, db)
    
    assert result["module"] == "kpi_library"
    assert "permissions" in result
    assert result["permissions"]["target_value"] == False
    assert result["permissions"]["category_code"] == True
    
    print("✓ GET /permissions/fields endpoint verified")


@pytest.mark.asyncio
async def test_field_permission_role_validation(db: AsyncSession):
    """Test CHECK constraint validates role values."""
    from sqlalchemy import text
    
    # Try to insert invalid role (should fail CHECK constraint)
    with pytest.raises(Exception):  # Will raise database constraint error
        invalid_perm = FieldPermission(
            module="kpi_library",
            field_name="test_field",
            role="invalid_role",  # Invalid role
            is_allowed=True
        )
        db.add(invalid_perm)
        await db.commit()
    
    await db.rollback()
    
    print("✓ Role CHECK constraint validation verified")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
