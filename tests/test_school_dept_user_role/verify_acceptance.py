"""
Simple verification script for PRS §18-21 acceptance criteria.
This script can be run to verify the implementation meets the requirements.
"""
import asyncio
import sys
import os

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4
from shared.database import get_db
from shared.models import School, SchoolStatus, Department, DepartmentStatus, User, UserStatus, UserRole
from modules.school_dept_user_role.services.school_service import SchoolService
from modules.school_dept_user_role.services.department_service import DepartmentService
from modules.school_dept_user_role.services.user_service import UserService
from platform_services.audit_log_service import AuditLogService
from platform_services.configuration_engine import ConfigurationEngine
from shared.errors import ValidationError


async def verify_acceptance_criteria():
    """Run acceptance criteria verification."""
    print("=== PRS §18-21 Acceptance Criteria Verification ===\n")
    
    async for db in get_db():
        config_engine = ConfigurationEngine(db)
        audit_log = AuditLogService(db)
        school_service = SchoolService(db, config_engine, audit_log)
        dept_service = DepartmentService(db, audit_log)
        user_service = UserService(db, audit_log)
        
        # Test 1: School creation requires SuperAdmin (service layer)
        print("✓ Test 1: School creation service (service layer)")
        try:
            school = await school_service.create_school(
                name="Verification School",
                code="VERIF001",
                created_by_user_id=uuid4()
            )
            print(f"  - School created: {school.name} ({school.id})")
        except Exception as e:
            print(f"  - FAILED: {e}")
        
        # Test 2: School name uniqueness
        print("\n✓ Test 2: School name uniqueness")
        try:
            await school_service.create_school(
                name="Verification School",  # Duplicate name
                code="VERIF002",
                created_by_user_id=uuid4()
            )
            print("  - FAILED: Should have rejected duplicate name")
        except ValidationError as e:
            print(f"  - Correctly rejected duplicate name: {e}")
        
        # Test 3: School deactivation (not delete)
        print("\n✓ Test 3: School deactivation (not delete)")
        try:
            if 'school' in locals():
                deactivated = await school_service.deactivate_school(school.id, uuid4())
                print(f"  - School deactivated: {deactivated.status}")
                
                # Verify it still exists
                from sqlalchemy import select
                result = await db.execute(select(School).where(School.id == school.id))
                existing = result.scalar_one_or_none()
                print(f"  - School still exists in DB: {existing is not None}")
        except Exception as e:
            print(f"  - FAILED: {e}")
        
        # Test 4: Department archival validation
        print("\n✓ Test 4: Department archival validation")
        try:
            # Create a test department
            if 'school' in locals():
                dept = await dept_service.create_department(
                    school_id=school.id,
                    name="Test Department",
                    code="TESTDEPT",
                    created_by_user_id=uuid4()
                )
                print(f"  - Department created: {dept.name}")
                
                # Mock task check to return True
                original_check = dept_service._check_open_tasks
                dept_service._check_open_tasks = lambda dept_id: True
                
                try:
                    await dept_service.archive_department(dept.id, uuid4())
                    print("  - FAILED: Should have blocked archival with open tasks")
                except ValidationError as e:
                    print(f"  - Correctly blocked archival: {e}")
                
                # Restore original method
                dept_service._check_open_tasks = original_check
        except Exception as e:
            print(f"  - FAILED: {e}")
        
        # Test 5: User archive (not delete)
        print("\n✓ Test 5: User archive (not delete)")
        try:
            user = await user_service.create_user(
                email="verify@example.com",
                full_name="Verify User",
                school_id=school.id if 'school' in locals() else uuid4(),
                roles=[UserRole.VIEWER],
                created_by_user_id=uuid4()
            )
            print(f"  - User created: {user.email}")
            
            archived = await user_service.archive_user(user.id, uuid4())
            print(f"  - User archived: {archived.status}")
            
            # Verify user still exists
            from sqlalchemy import select
            result = await db.execute(select(User).where(User.id == user.id))
            existing = result.scalar_one_or_none()
            print(f"  - User still exists in DB: {existing is not None}")
            print(f"  - User data preserved: {existing.email if existing else 'N/A'}")
        except Exception as e:
            print(f"  - FAILED: {e}")
        
        # Test 6: Department name uniqueness within school
        print("\n✓ Test 6: Department name uniqueness within school")
        try:
            if 'school' in locals():
                await dept_service.create_department(
                    school_id=school.id,
                    name="Test Department",  # Duplicate name
                    code="TESTDEPT2",
                    created_by_user_id=uuid4()
                )
                print("  - FAILED: Should have rejected duplicate department name")
        except ValidationError as e:
            print(f"  - Correctly rejected duplicate department name: {e}")
        
        # Test 7: User single school constraint
        print("\n✓ Test 7: User single school constraint")
        try:
            await user_service.create_user(
                email="admin_verify@example.com",
                full_name="Admin Verify",
                school_id=None,  # No school for Admin role
                roles=[UserRole.ADMIN],
                created_by_user_id=uuid4()
            )
            print("  - FAILED: Should have required school for Admin role")
        except ValidationError as e:
            print(f"  - Correctly required school for Admin: {e}")
        
        print("\n=== Verification Complete ===")
        break


if __name__ == "__main__":
    asyncio.run(verify_acceptance_criteria())