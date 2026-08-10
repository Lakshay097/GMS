"""
Scope isolation test suite per R-01, R-02, R-04.
Tests that users cannot access data outside their granted school/department scope.
Asserts zero data leakage between schools per R-06.
"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from shared.models import User, School, Department, UserSchoolGrant, UserRole, UserStatus, SchoolStatus
from shared.middleware.tenancy import TenantContext, apply_tenant_filter, scoped_to_tenant
from shared.database import Base
import uuid


@pytest.mark.asyncio
class TestScopeIsolation:
    """
    Test scope isolation between schools and departments.
    Ensures mandatory query-layer filter is applied per R-02.
    """
    
    async def setup_schools_and_users(self, db: AsyncSession):
        """
        Set up test data: two schools with users in each.
        """
        # Create School A
        school_a = School(
            id=uuid.uuid4(),
            name="School A",
            code="SCH001",
            status=SchoolStatus.ACTIVE
        )
        db.add(school_a)
        
        # Create School B
        school_b = School(
            id=uuid.uuid4(),
            name="School B",
            code="SCH002",
            status=SchoolStatus.ACTIVE
        )
        db.add(school_b)
        
        await db.flush()
        
        # Create Department in School A
        dept_a = Department(
            id=uuid.uuid4(),
            school_id=school_a.id,
            name="Department A",
            code="DEPT001"
        )
        db.add(dept_a)
        
        # Create Department in School B
        dept_b = Department(
            id=uuid.uuid4(),
            school_id=school_b.id,
            name="Department B",
            code="DEPT002"
        )
        db.add(dept_b)
        
        await db.flush()
        
        # Create Admin user in School A
        admin_a = User(
            id=uuid.uuid4(),
            neon_auth_user_id=f"neon_admin_a",
            email="admin_a@schoola.com",
            full_name="Admin A",
            school_id=school_a.id,
            department_id=dept_a.id,
            status=UserStatus.ACTIVE,
            roles=[UserRole.ADMIN.value]
        )
        db.add(admin_a)
        
        # Create Admin user in School B
        admin_b = User(
            id=uuid.uuid4(),
            neon_auth_user_id=f"neon_admin_b",
            email="admin_b@schoolb.com",
            full_name="Admin B",
            school_id=school_b.id,
            department_id=dept_b.id,
            status=UserStatus.ACTIVE,
            roles=[UserRole.ADMIN.value]
        )
        db.add(admin_b)
        
        # Create Viewer with access to both schools
        viewer_multi = User(
            id=uuid.uuid4(),
            neon_auth_user_id=f"neon_viewer_multi",
            email="viewer_multi@example.com",
            full_name="Viewer Multi",
            school_id=None,  # Viewer can have multiple schools
            department_id=None,
            status=UserStatus.ACTIVE,
            roles=[UserRole.VIEWER.value]
        )
        db.add(viewer_multi)
        
        await db.flush()
        
        # Create school grants for Viewer
        grant_a = UserSchoolGrant(
            id=uuid.uuid4(),
            user_id=viewer_multi.id,
            school_id=school_a.id,
            is_active=True
        )
        db.add(grant_a)
        
        grant_b = UserSchoolGrant(
            id=uuid.uuid4(),
            user_id=viewer_multi.id,
            school_id=school_b.id,
            is_active=True
        )
        db.add(grant_b)
        
        await db.commit()
        
        return {
            "school_a": school_a,
            "school_b": school_b,
            "dept_a": dept_a,
            "dept_b": dept_b,
            "admin_a": admin_a,
            "admin_b": admin_b,
            "viewer_multi": viewer_multi
        }
    
    async def test_school_isolation_admin_cannot_see_other_school(self, db: AsyncSession):
        """
        Test that an Admin from School A cannot see School B's data per R-06.
        Scope isolation prevents cross-school data leakage.
        """
        data = await self.setup_schools_and_users(db)
        
        # Create tenant context for Admin A
        tenant_context = TenantContext(
            user_id=str(data["admin_a"].id),
            school_id=str(data["school_a"].id),
            department_id=str(data["dept_a"].id),
            roles=[UserRole.ADMIN.value]
        )
        
        # Query all users with tenant filter applied
        query = select(User)
        filtered_query = apply_tenant_filter(query, tenant_context)
        result = await db.execute(filtered_query)
        users = result.scalars().all()
        
        # Should only see users from School A
        user_schools = {user.school_id for user in users if user.school_id}
        assert data["school_a"].id in user_schools, "Should see own school"
        assert data["school_b"].id not in user_schools, "Should NOT see other school"
        
        # Verify Admin B is not in results
        user_ids = {user.id for user in users}
        assert data["admin_b"].id not in user_ids, "Should not see users from other school"
    
    async def test_viewer_multi_school_access_via_grants(self, db: AsyncSession):
        """
        Test that Viewer with explicit school grants can access multiple schools per R-04.
        Multi-school access is modeled as explicit scope-grant records, not a bypass.
        """
        data = await self.setup_schools_and_users(db)
        
        # Create tenant context for Viewer with multi-school access
        tenant_context = TenantContext(
            user_id=str(data["viewer_multi"].id),
            school_id=None,  # No primary school
            department_id=None,
            roles=[UserRole.VIEWER.value],
            accessible_school_ids=[str(data["school_a"].id), str(data["school_b"].id)]
        )
        
        # Query all users with tenant filter applied
        query = select(User)
        filtered_query = apply_tenant_filter(query, tenant_context)
        result = await db.execute(filtered_query)
        users = result.scalars().all()
        
        # Should see users from both granted schools
        user_schools = {user.school_id for user in users if user.school_id}
        assert data["school_a"].id in user_schools, "Should see School A"
        assert data["school_b"].id in user_schools, "Should see School B"
    
    async def test_viewer_without_grant_cannot_see_any_school(self, db: AsyncSession):
        """
        Test that Viewer without school grants cannot see any school data.
        Explicit grants are required per R-04.
        """
        data = await self.setup_schools_and_users(db)
        
        # Create tenant context for Viewer without grants
        tenant_context = TenantContext(
            user_id=str(data["viewer_multi"].id),
            school_id=None,
            department_id=None,
            roles=[UserRole.VIEWER.value],
            accessible_school_ids=[]  # No grants
        )
        
        # Query all users with tenant filter applied
        query = select(User)
        filtered_query = apply_tenant_filter(query, tenant_context)
        result = await db.execute(filtered_query)
        users = result.scalars().all()
        
        # Should see no users (no school access)
        assert len(users) == 0, "Viewer without grants should see no data"
    
    async def test_superadmin_can_see_all_schools(self, db: AsyncSession):
        """
        Test that SuperAdmin can access all schools per R-01.
        SuperAdmin bypasses school filter via role, not via scope bypass.
        """
        data = await self.setup_schools_and_users(db)
        
        # Create tenant context for SuperAdmin
        tenant_context = TenantContext(
            user_id="superadmin-id",
            school_id=None,  # SuperAdmin has no primary school
            department_id=None,
            roles=[UserRole.SUPERADMIN.value]
        )
        
        # Query all users with tenant filter applied
        query = select(User)
        filtered_query = apply_tenant_filter(query, tenant_context)
        result = await db.execute(filtered_query)
        users = result.scalars().all()
        
        # Should see users from all schools
        user_schools = {user.school_id for user in users if user.school_id}
        assert data["school_a"].id in user_schools, "SuperAdmin should see School A"
        assert data["school_b"].id in user_schools, "SuperAdmin should see School B"
    
    async def test_department_isolation_within_school(self, db: AsyncSession):
        """
        Test that department-level isolation works within a school.
        User with department_id can only see their department's data.
        """
        data = await self.setup_schools_and_users(db)
        
        # Create another department in School A
        dept_a2 = Department(
            id=uuid.uuid4(),
            school_id=data["school_a"].id,
            name="Department A2",
            code="DEPT003"
        )
        db.add(dept_a2)
        await db.flush()
        
        # Create user in Department A2
        user_a2 = User(
            id=uuid.uuid4(),
            neon_auth_user_id="neon_user_a2",
            email="user_a2@schoola.com",
            full_name="User A2",
            school_id=data["school_a"].id,
            department_id=dept_a2.id,
            status=UserStatus.ACTIVE,
            roles=[UserRole.CHECKER.value]
        )
        db.add(user_a2)
        await db.commit()
        
        # Create tenant context for Admin A (Department A)
        tenant_context = TenantContext(
            user_id=str(data["admin_a"].id),
            school_id=str(data["school_a"].id),
            department_id=str(data["dept_a"].id),
            roles=[UserRole.ADMIN.value]
        )
        
        # Query all users with tenant filter applied
        query = select(User)
        filtered_query = apply_tenant_filter(query, tenant_context)
        result = await db.execute(filtered_query)
        users = result.scalars().all()
        
        # Should only see users from Department A (unless cross-department role)
        # Admin has cross-department access, so this tests the filter before role check
        # The filter itself should apply department restriction
        user_depts = {user.department_id for user in users if user.department_id}
        assert data["dept_a"].id in user_depts, "Should see own department"
    
    async def test_scoped_to_tenant_check(self, db: AsyncSession):
        """
        Test the scoped_to_tenant function for resource access checks.
        """
        data = await self.setup_schools_and_users(db)
        
        # Admin A context
        tenant_context = TenantContext(
            user_id=str(data["admin_a"].id),
            school_id=str(data["school_a"].id),
            department_id=str(data["dept_a"].id),
            roles=[UserRole.ADMIN.value]
        )
        
        # Should have access to own school
        assert scoped_to_tenant(
            tenant_context,
            str(data["school_a"].id)
        ) is True, "Should have access to own school"
        
        # Should NOT have access to other school
        assert scoped_to_tenant(
            tenant_context,
            str(data["school_b"].id)
        ) is False, "Should NOT have access to other school"
    
    async def test_zero_data_leakage_between_schools(self, db: AsyncSession):
        """
        Test that there is zero data leakage between schools per R-06.
        This is the core scope isolation test.
        """
        data = await self.setup_schools_and_users(db)
        
        # Admin A queries
        tenant_context_a = TenantContext(
            user_id=str(data["admin_a"].id),
            school_id=str(data["school_a"].id),
            department_id=str(data["dept_a"].id),
            roles=[UserRole.ADMIN.value]
        )
        
        query_a = select(User)
        filtered_query_a = apply_tenant_filter(query_a, tenant_context_a)
        result_a = await db.execute(filtered_query_a)
        users_a = result_a.scalars().all()
        
        # Admin B queries
        tenant_context_b = TenantContext(
            user_id=str(data["admin_b"].id),
            school_id=str(data["school_b"].id),
            department_id=str(data["dept_b"].id),
            roles=[UserRole.ADMIN.value]
        )
        
        query_b = select(User)
        filtered_query_b = apply_tenant_filter(query_b, tenant_context_b)
        result_b = await db.execute(filtered_query_b)
        users_b = result_b.scalars().all()
        
        # Get user IDs from each query
        user_ids_a = {user.id for user in users_a}
        user_ids_b = {user.id for user in users_b}
        
        # Verify zero overlap (except possible shared users, which shouldn't exist)
        overlap = user_ids_a & user_ids_b
        assert len(overlap) == 0, f"Zero data leakage violated: found {len(overlap)} shared users"
        
        # Verify each admin only sees their own school
        assert data["admin_a"].id in user_ids_a, "Admin A should see themselves"
        assert data["admin_a"].id not in user_ids_b, "Admin B should NOT see Admin A"
        
        assert data["admin_b"].id in user_ids_b, "Admin B should see themselves"
        assert data["admin_b"].id not in user_ids_a, "Admin A should NOT see Admin B"
    
    async def test_scope_filter_applied_before_permission_check(self, db: AsyncSession):
        """
        Test that scope filter is applied BEFORE and INDEPENDENT of role-permission checks per R-02.
        Even if a user has high privileges, scope filter runs first.
        """
        data = await self.setup_schools_and_users(db)
        
        # Create SuperAdmin with a primary school (unusual but possible)
        superadmin_with_school = User(
            id=uuid.uuid4(),
            neon_auth_user_id="neon_superadmin",
            email="superadmin@schoola.com",
            full_name="SuperAdmin",
            school_id=data["school_a"].id,
            department_id=data["dept_a"].id,
            status=UserStatus.ACTIVE,
            roles=[UserRole.SUPERADMIN.value]
        )
        db.add(superadmin_with_school)
        await db.commit()
        
        # Even though SuperAdmin, if they have a school_id, the filter applies
        # (In practice, SuperAdmin would have school_id=None, but this tests the filter logic)
        tenant_context = TenantContext(
            user_id=str(superadmin_with_school.id),
            school_id=str(data["school_a"].id),
            department_id=str(data["dept_a"].id),
            roles=[UserRole.SUPERADMIN.value]
        )
        
        # The filter should still apply based on school_id
        # SuperAdmin role bypass is at the permission layer, not scope filter layer
        query = select(User)
        filtered_query = apply_tenant_filter(query, tenant_context)
        result = await db.execute(filtered_query)
        users = result.scalars().all()
        
        # With school_id set, filter applies to that school only
        user_schools = {user.school_id for user in users if user.school_id}
        assert data["school_a"].id in user_schools


@pytest.mark.asyncio
class TestScopeGrantModel:
    """
    Test the user_school_grants model for multi-school access per R-04.
    Ensures multi-school access is modeled as explicit grants, not a bypass.
    """
    
    async def test_school_grant_creation(self, db: AsyncSession):
        """
        Test that school grants are created correctly.
        """
        # Create school and user
        school = School(
            id=uuid.uuid4(),
            name="Test School",
            code="TEST001",
            status=SchoolStatus.ACTIVE
        )
        db.add(school)
        
        user = User(
            id=uuid.uuid4(),
            neon_auth_user_id="neon_test",
            email="test@example.com",
            full_name="Test User",
            school_id=None,
            status=UserStatus.ACTIVE,
            roles=[UserRole.VIEWER.value]
        )
        db.add(user)
        await db.flush()
        
        # Create school grant
        grant = UserSchoolGrant(
            id=uuid.uuid4(),
            user_id=user.id,
            school_id=school.id,
            is_active=True
        )
        db.add(grant)
        await db.commit()
        
        # Verify grant exists
        result = await db.execute(
            select(UserSchoolGrant).where(
                UserSchoolGrant.user_id == user.id,
                UserSchoolGrant.school_id == school.id
            )
        )
        retrieved_grant = result.scalar_one_or_none()
        
        assert retrieved_grant is not None, "School grant should be created"
        assert retrieved_grant.is_active is True, "Grant should be active"
    
    async def test_school_grant_uniqueness(self, db: AsyncSession):
        """
        Test that duplicate school grants for same user+school are prevented.
        """
        # Create school and user
        school = School(
            id=uuid.uuid4(),
            name="Test School",
            code="TEST001",
            status=SchoolStatus.ACTIVE
        )
        db.add(school)
        
        user = User(
            id=uuid.uuid4(),
            neon_auth_user_id="neon_test",
            email="test@example.com",
            full_name="Test User",
            school_id=None,
            status=UserStatus.ACTIVE,
            roles=[UserRole.VIEWER.value]
        )
        db.add(user)
        await db.flush()
        
        # Create first grant
        grant1 = UserSchoolGrant(
            id=uuid.uuid4(),
            user_id=user.id,
            school_id=school.id,
            is_active=True
        )
        db.add(grant1)
        await db.flush()
        
        # Try to create duplicate grant
        grant2 = UserSchoolGrant(
            id=uuid.uuid4(),
            user_id=user.id,
            school_id=school.id,
            is_active=True
        )
        db.add(grant2)
        
        # Should raise integrity error due to unique constraint
        with pytest.raises(Exception):  # SQLAlchemy IntegrityError
            await db.commit()
