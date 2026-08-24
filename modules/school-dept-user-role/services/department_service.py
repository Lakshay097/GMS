"""
Department service layer implementing PRS §19 Department Management.
Handles department CRUD, archival, and employee transfer operations.
"""
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload
from uuid import UUID

from shared.models import Department, DepartmentStatus, School, User, UserStatus
from shared.database import get_db
from shared.errors import ValidationError, AuthorizationError, NotFoundError
from shared.datetime_utils import utc_now
from platform_services.audit_log_service import AuditLogService


class DepartmentService:
    """
    Department management service per PRS §19.
    Implements department archival with validation and employee transfer handling.
    """
    
    def __init__(
        self,
        db: AsyncSession,
        audit_log: AuditLogService
    ):
        self.db = db
        self.audit_log = audit_log
    
    async def create_department(
        self,
        school_id: UUID,
        name: str,
        code: str,
        created_by_user_id: UUID,
        description: Optional[str] = None,
        head_user_id: Optional[UUID] = None,
        auto_accept_requests: bool = False,
    ) -> Department:
        """
        Create a new department within a school.
        FR-011: Every Department scoped to exactly one School
        FR-012: Department Name unique within a School
        FR-018: Admin can create additional departments beyond auto-created defaults
        
        Args:
            school_id: School ID
            name: Department name (must be unique within school)
            code: Department code
            description: Optional description
            head_user_id: Optional department head user ID
            created_by_user_id: User ID creating the department
            
        Returns:
            Created Department entity
            
        Raises:
            ValidationError: If department name/code already exists
            NotFoundError: If school not found
        """
        # Verify school exists
        school = await self.db.get(School, school_id)
        if not school:
            raise NotFoundError("School not found")
        
        # Check for existing department with same name in school
        existing = await self.db.execute(
            select(Department).where(
                and_(
                    Department.school_id == school_id,
                    Department.name == name,
                    Department.status != DepartmentStatus.ARCHIVED
                )
            )
        )
        if existing.scalar_one_or_none():
            raise ValidationError(
                "Department name already exists within this school",
                field="name"
            )
        
        # Check for existing department code in school
        existing_code = await self.db.execute(
            select(Department).where(
                and_(
                    Department.school_id == school_id,
                    Department.code == code
                )
            )
        )
        if existing_code.scalar_one_or_none():
            raise ValidationError(
                "Department code already exists within this school",
                field="code"
            )
        
        # Create department
        department = Department(
            school_id=school_id,
            name=name,
            code=code,
            description=description,
            head_user_id=head_user_id,
            auto_accept_requests=auto_accept_requests,
            status=DepartmentStatus.ACTIVE
        )
        
        self.db.add(department)
        await self.db.commit()
        
        # Log the creation
        await self.audit_log.append(
            action="create_department",
            entity_type="department",
            entity_id=department.id,
            actor_id=created_by_user_id,
            school_id=school_id,
            department_id=department.id,
            new_values={
                "name": name,
                "code": code,
                "school_id": str(school_id)
            }
        )
        
        await self.db.refresh(department)
        return department
    
    async def archive_department(
        self,
        department_id: UUID,
        archived_by_user_id: UUID
    ) -> Department:
        """
        Archive a department (soft delete, never hard delete).
        FR-013: Prevent deletion where historical records exist
        FR-014: Block archival while open Tasks or unresolved Discrepancies exist
        
        Args:
            department_id: Department ID to archive
            archived_by_user_id: User ID performing the archival
            
        Returns:
            Updated Department entity
            
        Raises:
            NotFoundError: If department not found
            ValidationError: If archival prerequisites are not met
        """
        department = await self.db.get(Department, department_id)
        if not department:
            raise NotFoundError("Department not found")
        
        if department.status == DepartmentStatus.ARCHIVED:
            raise ValidationError("Department is already archived")
        
        # FR-014: Block archival while open Tasks or unresolved Discrepancies exist
        # Check for open tasks (this would query the tasks table when Task module is implemented)
        # For now, we'll implement a placeholder check
        has_open_tasks = await self._check_open_tasks(department_id)
        if has_open_tasks:
            raise ValidationError(
                "Cannot archive department with open tasks",
                field="tasks"
            )
        
        # Check for unresolved discrepancies (this would query discrepancies table when implemented)
        has_unresolved_discrepancies = await self._check_unresolved_discrepancies(department_id)
        if has_unresolved_discrepancies:
            raise ValidationError(
                "Cannot archive department with unresolved discrepancies",
                field="discrepancies"
            )
        
        # Store old values for audit
        old_values = {"status": department.status.value}
        
        # Update to archived status
        department.status = DepartmentStatus.ARCHIVED
        department.archived_at = utc_now()
        department.updated_at = utc_now()
        
        await self.db.commit()
        
        # Log the archival
        await self.audit_log.append(
            action="archive_department",
            entity_type="department",
            entity_id=department_id,
            actor_id=archived_by_user_id,
            school_id=department.school_id,
            department_id=department_id,
            old_values=old_values,
            new_values={"status": DepartmentStatus.ARCHIVED.value}
        )
        
        await self.db.refresh(department)
        return department
    
    async def update_department(
        self,
        department_id: UUID,
        updated_by_user_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        head_user_id: Optional[UUID] = None,
        auto_accept_requests: Optional[bool] = None,
    ) -> Department:
        """
        Update department details.
        
        Args:
            department_id: Department ID to update
            name: Optional new name
            description: Optional new description
            head_user_id: Optional new department head
            updated_by_user_id: User ID performing the update
            
        Returns:
            Updated Department entity
            
        Raises:
            NotFoundError: If department not found
            ValidationError: If validation fails
        """
        department = await self.db.get(Department, department_id)
        if not department:
            raise NotFoundError("Department not found")
        
        # Store old values for audit
        old_values = {
            "name": department.name,
            "description": department.description,
            "head_user_id": str(department.head_user_id) if department.head_user_id else None,
            "auto_accept_requests": department.auto_accept_requests
        }
        
        # Check name uniqueness if changing
        if name and name != department.name:
            existing = await self.db.execute(
                select(Department).where(
                    and_(
                        Department.school_id == department.school_id,
                        Department.name == name,
                        Department.id != department_id,
                        Department.status != DepartmentStatus.ARCHIVED
                    )
                )
            )
            if existing.scalar_one_or_none():
                raise ValidationError(
                    "Department name already exists within this school",
                    field="name"
                )
            department.name = name
        
        if description is not None:
            department.description = description
        if head_user_id is not None:
            department.head_user_id = head_user_id
        if auto_accept_requests is not None:
            department.auto_accept_requests = auto_accept_requests
        
        department.updated_at = utc_now()
        
        await self.db.commit()
        
        # Log the update
        new_values = {
            "name": department.name,
            "description": department.description,
            "head_user_id": str(department.head_user_id) if department.head_user_id else None
        }
        
        await self.audit_log.append(
            action="update_department",
            entity_type="department",
            entity_id=department_id,
            actor_id=updated_by_user_id,
            school_id=department.school_id,
            department_id=department_id,
            old_values=old_values,
            new_values=new_values
        )
        
        await self.db.refresh(department)
        return department
    
    async def get_department(self, department_id: UUID) -> Department:
        """
        Get department by ID.
        
        Args:
            department_id: Department ID
            
        Returns:
            Department entity
            
        Raises:
            NotFoundError: If department not found
        """
        department = await self.db.get(Department, department_id)
        if not department:
            raise NotFoundError("Department not found")
        return department
    
    async def list_departments(
        self,
        school_id: Optional[UUID] = None,
        status: Optional[DepartmentStatus] = None,
        page: int = 1,
        page_size: int = 50
    ) -> tuple[List[Department], int]:
        """
        List departments with optional filtering and pagination.
        
        Args:
            school_id: Optional school ID filter
            status: Optional status filter
            page: Page number (1-indexed)
            page_size: Page size
            
        Returns:
            Tuple of (departments list, total count)
        """
        # Use selectinload to load school relationship
        query = select(Department).options(selectinload(Department.school))
        
        if school_id:
            query = query.where(Department.school_id == school_id)
        if status:
            query = query.where(Department.status == status)
        
        # Get total count
        count_query = select(func.count(Department.id))
        if school_id:
            count_query = count_query.where(Department.school_id == school_id)
        if status:
            count_query = count_query.where(Department.status == status)
        
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()
        
        # Apply pagination
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await self.db.execute(query)
        departments = result.scalars().all()
        
        return list(departments), total
    
    async def _check_open_tasks(self, department_id: UUID) -> bool:
        """
        Check if department has open tasks.
        Placeholder implementation - Task module will provide actual implementation.
        
        Args:
            department_id: Department ID
            
        Returns:
            True if open tasks exist, False otherwise
        """
        # Placeholder: When Task module is implemented, query the tasks table
        # For now, return False to allow development to proceed
        return False
    
    async def _check_unresolved_discrepancies(self, department_id: UUID) -> bool:
        """
        Check if department has unresolved discrepancies.
        Placeholder implementation - Discrepancy module will provide actual implementation.
        
        Args:
            department_id: Department ID
            
        Returns:
            True if unresolved discrepancies exist, False otherwise
        """
        # Placeholder: When Discrepancy module is implemented, query the discrepancies table
        # For now, return False to allow development to proceed
        return False