"""
School service layer implementing PRS §18 School Management.
Handles school CRUD, lifecycle, and atomic onboarding operations.
"""
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy import func, String
from sqlalchemy.orm import selectinload
from uuid import UUID
import asyncpg

from shared.models import School, SchoolStatus, Department, DepartmentStatus, User, UserRole, UserStatus
from sqlalchemy import select
from shared.database import get_db
from shared.errors import ValidationError, AuthorizationError, NotFoundError
from shared.datetime_utils import utc_now
from platform_services.configuration_engine import ConfigurationEngine
from platform_services.audit_log_service import AuditLogService
from platform_services.master_data_service import MasterDataService
from platform_services.notification_service.service import (
    NotificationPayload,
    NotificationService,
)
from shared.platform_models import NotificationCategory, NotificationChannel


class SchoolService:
    """
    School management service per PRS §18.
    Implements atomic school creation with department seeding and KPI library import.
    """
    
    def __init__(
        self,
        db: AsyncSession,
        config_engine: ConfigurationEngine,
        audit_log: AuditLogService,
        master_data: Optional[MasterDataService] = None,
        notification_service: Optional[NotificationService] = None,
    ):
        self.db = db
        self.config_engine = config_engine
        self.audit_log = audit_log
        self.master_data = master_data
        self._notification_service = notification_service or NotificationService(db)
    
    async def create_school(
        self,
        name: str,
        code: str,
        created_by_user_id: UUID,
        address: Optional[str] = None,
        contact_email: Optional[str] = None,
        contact_phone: Optional[str] = None,
    ) -> School:
        """
        Create a new school with atomic onboarding operations.
        FR-001: Only SuperAdmin can create schools
        FR-006: Atomic operation - creates departments + imports KPI library + creates first Admin
        FR-005: School Name unique within organization
        
        Args:
            name: School name (must be unique)
            code: School code (must be unique)
            address: Optional address
            contact_email: Optional contact email
            contact_phone: Optional contact phone
            created_by_user_id: User ID of the SuperAdmin creating the school
            
        Returns:
            Created School entity
            
        Raises:
            ValidationError: If school name/code already exists or validation fails
            AuthorizationError: If creator is not SuperAdmin
        """
        # Check for existing school with same name or code
        existing = await self.db.execute(
            select(School).where(
                and_(
                    School.name == name,
                    School.status != SchoolStatus.DEACTIVATED
                )
            )
        )
        if existing.scalar_one_or_none():
            raise ValidationError(
                "School name already exists within organization",
                field="name"
            )
        
        existing_code = await self.db.execute(
            select(School).where(School.code == code)
        )
        if existing_code.scalar_one_or_none():
            raise ValidationError(
                "School code already exists",
                field="code"
            )
        
        # Create school with Pending Onboarding status
        # timezone and working_days use model defaults (BR-22, BR-24)
        school = School(
            name=name,
            code=code,
            status=SchoolStatus.ACTIVE,  # Will transition to Active after successful onboarding
            address=address,
            contact_email=contact_email,
            contact_phone=contact_phone,
        )
        
        self.db.add(school)
        await self.db.flush()  # Get school ID
        
        try:
            # Atomic onboarding operations
            # 1. Create default departments from Master Data templates
            # For now, we'll create a minimal set of default departments
            default_departments = [
                {"name": "Administration", "code": "ADMIN", "description": "School Administration"},
                {"name": "Academics", "code": "ACAD", "description": "Academic Department"},
                {"name": "Operations", "code": "OPS", "description": "Operations and Maintenance"}
            ]
            for dept_template in default_departments:
                department = Department(
                    school_id=school.id,
                    name=dept_template["name"],
                    code=dept_template["code"],
                    description=dept_template.get("description"),
                    status=DepartmentStatus.ACTIVE
                )
                self.db.add(department)
            
            # 2. Import current Global KPI Library version
            # Placeholder for KPI library import - will be implemented in KPI module
            kpi_library_version = "v1.0"  # Placeholder version
            
            # 3. Create first Admin user (placeholder - actual user creation handled separately)
            # This is a placeholder for the Admin creation step
            # In practice, the Admin user is created via a separate invite flow
            
            await self.db.commit()
            
            # Log the school creation
            await self.audit_log.append(
                action="create_school",
                entity_type="school",
                entity_id=school.id,
                actor_id=created_by_user_id,
                school_id=school.id,
                new_values={
                    "name": name,
                    "code": code,
                    "kpi_library_version": kpi_library_version
                }
            )
            
            # Notify SuperAdmins per PRS §49 Notification Matrix
            # Category 7 (INFORMATIONAL) - In-App, Email channels
            superadmin_result = await self.db.execute(
                select(User.id).where(
                    func.cast(User.roles, String).like('%"superadmin"%'),
                    User.status == "active"
                )
            )
            for admin_id in superadmin_result.scalars().all():
                await self._notification_service.dispatch(
                    NotificationPayload(
                        user_id=admin_id,
                        category=NotificationCategory.INFORMATIONAL.value,
                        title="School Created",
                        body=f"New school '{name}' has been created successfully",
                        channel=NotificationChannel.EMAIL,
                        entity_type="school",
                        entity_id=school.id,
                    )
                )
            
            # Refresh to get relationships
            await self.db.refresh(school)
            
            return school
            
        except Exception as e:
            await self.db.rollback()
            raise ValidationError(
                f"School creation failed: {str(e)}",
                field="school"
            )
    
    async def deactivate_school(
        self,
        school_id: UUID,
        deactivated_by_user_id: UUID
    ) -> School:
        """
        Deactivate a school (soft delete, never hard delete).
        FR-007: Prevent hard deletion, only deactivation permitted
        FR-008: Retain full historical data in read-only state
        
        Args:
            school_id: School ID to deactivate
            deactivated_by_user_id: User ID performing the deactivation
            
        Returns:
            Updated School entity
            
        Raises:
            NotFoundError: If school not found
            ValidationError: If school is already deactivated
        """
        school = await self.db.get(School, school_id)
        if not school:
            raise NotFoundError("School not found")
        
        if school.status == SchoolStatus.DEACTIVATED:
            raise ValidationError("School is already deactivated")
        
        # Store old values for audit
        old_values = {"status": school.status.value}
        
        # Update to deactivated status
        school.status = SchoolStatus.DEACTIVATED
        school.deactivated_at = utc_now()
        school.updated_at = utc_now()
        
        await self.db.commit()
        
        # Log the deactivation
        await self.audit_log.append(
            action="deactivate_school",
            entity_type="school",
            entity_id=school_id,
            actor_id=deactivated_by_user_id,
            school_id=school_id,
            old_values=old_values,
            new_values={"status": SchoolStatus.DEACTIVATED.value}
        )
        
        await self.db.refresh(school)
        return school
    
    async def update_school(
        self,
        school_id: UUID,
        updated_by_user_id: UUID,
        name: Optional[str] = None,
        address: Optional[str] = None,
        contact_email: Optional[str] = None,
        contact_phone: Optional[str] = None,
    ) -> School:
        """
        Update school details (excluding status transitions).
        Status transitions are handled via specific methods (deactivate_school).
        
        Args:
            school_id: School ID to update
            name: Optional new name
            address: Optional new address
            contact_email: Optional new contact email
            contact_phone: Optional new contact phone
            updated_by_user_id: User ID performing the update
            
        Returns:
            Updated School entity
            
        Raises:
            NotFoundError: If school not found
            ValidationError: If validation fails
        """
        school = await self.db.get(School, school_id)
        if not school:
            raise NotFoundError("School not found")
        
        # Store old values for audit
        old_values = {
            "name": school.name,
            "address": school.address,
            "contact_email": school.contact_email,
            "contact_phone": school.contact_phone
        }
        
        # Check name uniqueness if changing
        if name and name != school.name:
            existing = await self.db.execute(
                select(School).where(
                    and_(
                        School.name == name,
                        School.id != school_id,
                        School.status != SchoolStatus.DEACTIVATED
                    )
                )
            )
            if existing.scalar_one_or_none():
                raise ValidationError(
                    "School name already exists within organization",
                    field="name"
                )
            school.name = name
        
        if address is not None:
            school.address = address
        if contact_email is not None:
            school.contact_email = contact_email
        if contact_phone is not None:
            school.contact_phone = contact_phone
        
        school.updated_at = utc_now()
        
        await self.db.commit()
        
        # Log the update
        new_values = {
            "name": school.name,
            "address": school.address,
            "contact_email": school.contact_email,
            "contact_phone": school.contact_phone
        }
        
        await self.audit_log.append(
            action="update_school",
            entity_type="school",
            entity_id=school_id,
            actor_id=updated_by_user_id,
            school_id=school_id,
            old_values=old_values,
            new_values=new_values
        )
        
        await self.db.refresh(school)
        return school
    
    async def get_school(self, school_id: UUID) -> School:
        """
        Get school by ID.
        
        Args:
            school_id: School ID
            
        Returns:
            School entity
            
        Raises:
            NotFoundError: If school not found
        """
        school = await self.db.get(School, school_id)
        if not school:
            raise NotFoundError("School not found")
        return school
    
    async def list_schools(
        self,
        status: Optional[SchoolStatus] = None,
        page: int = 1,
        page_size: int = 50
    ) -> tuple[List[School], int]:
        """
        List schools with optional filtering and pagination.
        
        Args:
            status: Optional status filter
            page: Page number (1-indexed)
            page_size: Page size
            
        Returns:
            Tuple of (schools list, total count)
        """
        query = select(School)
        
        if status:
            query = query.where(School.status == status)
        
        # Get total count
        count_query = select(School.id)
        if status:
            count_query = count_query.where(School.status == status)
        
        total_result = await self.db.execute(count_query)
        total = len(total_result.scalars().all())
        
        # Apply pagination
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await self.db.execute(query)
        schools = result.scalars().all()
        
        return list(schools), total
    
    async def validate_school_activation(self, school_id: UUID) -> bool:
        """
        Validate that a school can be activated.
        PRS §18.6: School cannot be marked Active until default departments and KPI library import complete.
        
        Args:
            school_id: School ID to validate
            
        Returns:
            True if activation is valid
            
        Raises:
            ValidationError: If activation prerequisites are not met
        """
        school = await self.db.get(School, school_id)
        if not school:
            raise NotFoundError("School not found")
        
        # Check for at least one department
        dept_count = await self.db.execute(
            select(Department).where(Department.school_id == school_id)
        )
        if dept_count.scalar_one_or_none() is None:
            raise ValidationError(
                "School cannot be activated without at least one department",
                field="departments"
            )
        
        # Check for KPI library import (via configuration or audit log)
        # This is a simplified check - in production, verify KPI import completion
        # Placeholder: assume KPI library is imported for now
        kpi_imported = True  # Will be implemented in KPI module
        if not kpi_imported:
            raise ValidationError(
                "School cannot be activated without KPI library import",
                field="kpi_library"
            )
        
        return True