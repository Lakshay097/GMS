"""
Service layer for School, Department, KRA, KPI, KPI_Entry CRUD.
All operations are async and use SQLAlchemy.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import select, func, and_, text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import School, SchoolStatus, Department, DepartmentStatus
from shared.platform_models import (
    KRA, KPI, KraStatus, KpiStatus, KpiComparator,
    Asset, AssetStatus,
)
from shared.errors import ValidationError, NotFoundError
from shared.datetime_utils import utc_now


class OrgService:
    """Unified service for org entity CRUD."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── School CRUD ───────────────────────────────────────────────────────

    async def create_school(
        self,
        name: str,
        code: str,
        address: Optional[str] = None,
        contact_email: Optional[str] = None,
        contact_phone: Optional[str] = None,
        timezone_: Optional[str] = None,
    ) -> School:
        # Check unique name
        existing = await self.db.execute(
            select(School).where(
                School.name == name,
                School.status != SchoolStatus.DEACTIVATED,
            )
        )
        if existing.scalar_one_or_none():
            raise ValidationError("School name already exists", field="name")

        # Check unique code
        existing_code = await self.db.execute(
            select(School).where(School.code == code)
        )
        if existing_code.scalar_one_or_none():
            raise ValidationError("School code already exists", field="code")

        school = School(
            name=name,
            code=code,
            status=SchoolStatus.ACTIVE,
            address=address,
            contact_email=contact_email,
            contact_phone=contact_phone,
            timezone=timezone_,
        )
        self.db.add(school)
        await self.db.commit()
        await self.db.refresh(school)
        return school

    async def list_schools(
        self,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[School], int]:
        query = select(School)
        count_query = select(func.count(School.id))

        if status:
            query = query.where(School.status == status)
            count_query = count_query.where(School.status == status)

        total = (await self.db.execute(count_query)).scalar() or 0
        result = await self.db.execute(
            query.offset((page - 1) * page_size).limit(page_size)
        )
        return list(result.scalars().all()), total

    async def get_school(self, school_id: UUID) -> School:
        school = await self.db.get(School, school_id)
        if not school:
            raise NotFoundError("School not found")
        return school

    async def update_school(self, school_id: UUID, **kwargs) -> School:
        school = await self.get_school(school_id)
        for key, value in kwargs.items():
            if value is not None and hasattr(school, key):
                setattr(school, key, value)
        school.updated_at = utc_now()
        await self.db.commit()
        await self.db.refresh(school)
        return school

    async def deactivate_school(self, school_id: UUID) -> School:
        school = await self.get_school(school_id)
        if school.status == SchoolStatus.DEACTIVATED:
            raise ValidationError("School is already deactivated")
        school.status = SchoolStatus.DEACTIVATED
        school.deactivated_at = utc_now()
        school.updated_at = utc_now()
        await self.db.commit()
        await self.db.refresh(school)
        return school

    # ── Department CRUD ───────────────────────────────────────────────────

    async def create_department(
        self,
        name: str,
        code: str,
        school_id: UUID,
        description: Optional[str] = None,
    ) -> Department:
        # Verify school exists and is active
        school = await self.get_school(school_id)
        if school.status != SchoolStatus.ACTIVE:
            raise ValidationError("Department must belong to an active school", field="school_id")

        # Check unique code within school
        existing = await self.db.execute(
            select(Department).where(
                Department.school_id == school_id,
                Department.code == code,
            )
        )
        if existing.scalar_one_or_none():
            raise ValidationError("Department code already exists in this school", field="code")

        dept = Department(
            school_id=school_id,
            name=name,
            code=code,
            status=DepartmentStatus.ACTIVE,
            description=description,
        )
        self.db.add(dept)
        await self.db.commit()
        await self.db.refresh(dept)
        return dept

    async def list_departments(
        self,
        school_id: Optional[UUID] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[Department], int]:
        query = select(Department)
        count_query = select(func.count(Department.id))

        if school_id:
            query = query.where(Department.school_id == school_id)
            count_query = count_query.where(Department.school_id == school_id)
        if status:
            query = query.where(Department.status == status)
            count_query = count_query.where(Department.status == status)

        total = (await self.db.execute(count_query)).scalar() or 0
        result = await self.db.execute(
            query.offset((page - 1) * page_size).limit(page_size)
        )
        return list(result.scalars().all()), total

    async def get_department(self, dept_id: UUID) -> Department:
        dept = await self.db.get(Department, dept_id)
        if not dept:
            raise NotFoundError("Department not found")
        return dept

    async def update_department(self, dept_id: UUID, **kwargs) -> Department:
        dept = await self.get_department(dept_id)
        for key, value in kwargs.items():
            if value is not None and hasattr(dept, key):
                setattr(dept, key, value)
        dept.updated_at = utc_now()
        await self.db.commit()
        await self.db.refresh(dept)
        return dept

    async def deactivate_department(self, dept_id: UUID) -> Department:
        dept = await self.get_department(dept_id)
        if dept.status == DepartmentStatus.ARCHIVED:
            raise ValidationError("Department is already archived")
        dept.status = DepartmentStatus.ARCHIVED
        dept.archived_at = utc_now()
        dept.updated_at = utc_now()
        await self.db.commit()
        await self.db.refresh(dept)
        return dept

    # ── KRA CRUD ──────────────────────────────────────────────────────────

    async def create_kra(
        self,
        name: str,
        description: Optional[str] = None,
    ) -> KRA:
        kra = KRA(
            name=name,
            description=description,
            status=KraStatus.ACTIVE.value,
        )
        self.db.add(kra)
        await self.db.commit()
        await self.db.refresh(kra)
        return kra

    async def list_kras(
        self,
        include_deprecated: bool = False,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[KRA], int]:
        query = select(KRA)
        count_query = select(func.count(KRA.id))

        if not include_deprecated:
            query = query.where(KRA.status == KraStatus.ACTIVE.value)
            count_query = count_query.where(KRA.status == KraStatus.ACTIVE.value)

        total = (await self.db.execute(count_query)).scalar() or 0
        result = await self.db.execute(
            query.offset((page - 1) * page_size).limit(page_size)
        )
        return list(result.scalars().all()), total

    async def get_kra(self, kra_id: UUID) -> KRA:
        kra = await self.db.get(KRA, kra_id)
        if not kra:
            raise NotFoundError("KRA not found")
        return kra

    async def update_kra(self, kra_id: UUID, **kwargs) -> KRA:
        kra = await self.get_kra(kra_id)
        for key, value in kwargs.items():
            if value is not None and hasattr(kra, key):
                setattr(kra, key, value)
        kra.updated_at = utc_now()
        await self.db.commit()
        await self.db.refresh(kra)
        return kra

    async def archive_kra(self, kra_id: UUID) -> KRA:
        kra = await self.get_kra(kra_id)
        kra.status = KraStatus.DEPRECATED.value
        kra.updated_at = utc_now()
        await self.db.commit()
        await self.db.refresh(kra)
        return kra

    # ── KPI CRUD ──────────────────────────────────────────────────────────

    async def create_kpi(
        self,
        kra_id: UUID,
        title: str,
        target_value: Decimal = Decimal("100"),
        comparator: str = ">=",
        unit_of_measure: str = "percent",
        frequency_code: str = "daily",
        capture_type: str = "value_reading",
        description: Optional[str] = None,
        owner: Optional[UUID] = None,
        category_code: Optional[str] = None,
        is_sensitive: bool = False,
        evidence_required: bool = False,
        amber_tolerance_band: Optional[Decimal] = None,
        created_by: Optional[UUID] = None,
    ) -> KPI:
        # Verify KRA exists and is active
        kra = await self.get_kra(kra_id)
        if kra.status != KraStatus.ACTIVE.value:
            raise ValidationError("KPI must belong to an active KRA", field="kra_id")

        kpi = KPI(
            kpi_id=uuid4(),
            version=1,
            kra_id=kra_id,
            title=title,
            description=description,
            owner=owner,
            target_value=target_value,
            comparator=comparator,
            unit_of_measure=unit_of_measure,
            frequency_code=frequency_code,
            capture_type=capture_type,
            category_code=category_code,
            is_sensitive=is_sensitive,
            evidence_required=evidence_required,
            amber_tolerance_band=amber_tolerance_band,
            status=KpiStatus.ACTIVE.value,
            is_immutable=False,
            created_by=created_by,
        )
        self.db.add(kpi)
        await self.db.commit()
        await self.db.refresh(kpi)
        return kpi

    async def list_kpis(
        self,
        kra_id: Optional[UUID] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[KPI], int]:
        # Get latest version of each KPI
        subq = (
            select(
                KPI.kpi_id,
                func.max(KPI.version).label("max_version"),
            )
            .group_by(KPI.kpi_id)
        )
        if kra_id:
            subq = subq.where(KPI.kra_id == kra_id)
        if status:
            subq = subq.where(KPI.status == status)

        subq = subq.subquery()

        query = select(KPI).join(
            subq,
            and_(KPI.kpi_id == subq.c.kpi_id, KPI.version == subq.c.max_version),
        )
        count_query = select(func.count()).select_from(subq)

        total = (await self.db.execute(count_query)).scalar() or 0
        result = await self.db.execute(
            query.offset((page - 1) * page_size).limit(page_size)
        )
        return list(result.scalars().all()), total

    async def get_current_kpi(self, kpi_id: UUID) -> KPI:
        """Get the latest version of a KPI."""
        result = await self.db.execute(
            select(KPI)
            .where(KPI.kpi_id == kpi_id)
            .order_by(KPI.version.desc())
            .limit(1)
        )
        kpi = result.scalar_one_or_none()
        if not kpi:
            raise NotFoundError("KPI not found")
        return kpi

    async def update_kpi(self, kpi_id: UUID, updated_by: Optional[UUID] = None, **kwargs) -> KPI:
        """Create a new version of the KPI (versioned update)."""
        current = await self.get_current_kpi(kpi_id)
        if current.is_immutable:
            raise ValidationError("KPI is immutable and cannot be updated")

        # Create new version
        new_version = KPI(
            kpi_id=current.kpi_id,
            version=current.version + 1,
            kra_id=current.kra_id,
            title=kwargs.get("title", current.title),
            description=kwargs.get("description", current.description),
            owner=kwargs.get("owner", current.owner),
            target_value=kwargs.get("target_value", current.target_value),
            comparator=kwargs.get("comparator", current.comparator),
            unit_of_measure=kwargs.get("unit_of_measure", current.unit_of_measure),
            frequency_code=kwargs.get("frequency_code", current.frequency_code),
            capture_type=kwargs.get("capture_type", current.capture_type),
            category_code=kwargs.get("category_code", current.category_code),
            is_sensitive=kwargs.get("is_sensitive", current.is_sensitive),
            evidence_required=kwargs.get("evidence_required", current.evidence_required),
            amber_tolerance_band=kwargs.get("amber_tolerance_band", current.amber_tolerance_band),
            status=kwargs.get("status", current.status),
            is_immutable=False,
            created_by=updated_by or current.created_by,
        )

        # Deprecate previous version
        current.status = KpiStatus.DEPRECATED.value
        current.is_immutable = True

        self.db.add(new_version)
        await self.db.commit()
        await self.db.refresh(new_version)
        return new_version

    async def deprecate_kpi(self, kpi_id: UUID) -> KPI:
        kpi = await self.get_current_kpi(kpi_id)
        kpi.status = KpiStatus.DEPRECATED.value
        kpi.is_immutable = True
        await self.db.commit()
        await self.db.refresh(kpi)
        return kpi

    # ── KPI_Entry CRUD ────────────────────────────────────────────────────

    async def create_kpi_entry(
        self,
        kpi_id: UUID,
        check_name: Optional[str] = None,
        check_type: Optional[str] = None,
        value: Optional[Decimal] = None,
        value_text: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        asset_id: Optional[UUID] = None,
        department_id: Optional[UUID] = None,
        school_id: Optional[UUID] = None,
        recorded_by: Optional[UUID] = None,
        notes: Optional[str] = None,
        evidence: Optional[list[dict]] = None,
        legacy_kpi_id: Optional[UUID] = None,
    ) -> dict:
        """Create a new KPI entry. Auto-computes status based on KPI target."""
        # Verify KPI exists and is active
        kpi = await self.get_current_kpi(kpi_id)
        if kpi.status != KpiStatus.ACTIVE.value:
            raise ValidationError("Cannot log entry against a deprecated KPI", field="kpi_id")

        # Auto-compute status based on target comparison
        auto_status = "pending"
        if value is not None and kpi.target_value is not None:
            comp = kpi.comparator
            target = float(kpi.target_value)
            actual = float(value)
            if comp == ">=" and actual >= target:
                auto_status = "pass"
            elif comp == "<=" and actual <= target:
                auto_status = "pass"
            elif comp == ">" and actual > target:
                auto_status = "pass"
            elif comp == "<" and actual < target:
                auto_status = "pass"
            elif comp == "=" and actual == target:
                auto_status = "pass"
            else:
                auto_status = "fail"

        # If KPI is sensitive, require under_review first
        if kpi.is_sensitive and auto_status in ("pass", "fail"):
            auto_status = "under_review"

        # If KPI requires evidence, check evidence is provided
        if kpi.evidence_required and (not evidence or len(evidence) == 0):
            raise ValidationError("Evidence is required for this KPI", field="evidence")

        # Use the new kpi_entries table
        from shared.platform_models import KpiEntry
        entry = KpiEntry(
            id=uuid4(),
            kpi_id=kpi_id,
            check_name=check_name,
            check_type=check_type,
            value=value,
            value_text=value_text,
            timestamp=timestamp or utc_now(),
            asset_id=asset_id,
            department_id=department_id,
            school_id=school_id,
            recorded_by=recorded_by,
            status=auto_status,
            notes=notes,
            evidence=evidence,
            legacy_kpi_id=legacy_kpi_id,
        )
        self.db.add(entry)
        await self.db.commit()
        await self.db.refresh(entry)
        return entry

    async def list_kpi_entries(
        self,
        kpi_id: Optional[UUID] = None,
        department_id: Optional[UUID] = None,
        school_id: Optional[UUID] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list, int]:
        from shared.platform_models import KpiEntry

        query = select(KpiEntry)
        count_query = select(func.count(KpiEntry.id))

        filters = []
        if kpi_id:
            filters.append(KpiEntry.kpi_id == kpi_id)
        if department_id:
            filters.append(KpiEntry.department_id == department_id)
        if school_id:
            filters.append(KpiEntry.school_id == school_id)
        if status:
            filters.append(KpiEntry.status == status)

        if filters:
            query = query.where(and_(*filters))
            count_query = count_query.where(and_(*filters))

        total = (await self.db.execute(count_query)).scalar() or 0
        result = await self.db.execute(
            query.order_by(KpiEntry.timestamp.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    async def get_kpi_entry(self, entry_id: UUID):
        from shared.platform_models import KpiEntry
        entry = await self.db.get(KpiEntry, entry_id)
        if not entry:
            raise NotFoundError("KPI Entry not found")
        return entry

    async def update_kpi_entry(self, entry_id: UUID, **kwargs):
        from shared.platform_models import KpiEntry
        entry = await self.get_kpi_entry(entry_id)
        for key, value in kwargs.items():
            if value is not None and hasattr(entry, key):
                setattr(entry, key, value)
        entry.updated_at = utc_now()
        await self.db.commit()
        await self.db.refresh(entry)
        return entry

    # ── Dashboard ─────────────────────────────────────────────────────────

    async def get_dashboard_summary(
        self,
        school_id: Optional[UUID] = None,
        department_id: Optional[UUID] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> dict:
        from shared.platform_models import KpiEntry

        # Counts
        total_schools = (await self.db.execute(select(func.count(School.id)))).scalar() or 0
        total_departments = (await self.db.execute(select(func.count(Department.id)))).scalar() or 0
        total_kras = (await self.db.execute(select(func.count(KRA.id)))).scalar() or 0
        total_kpis = (await self.db.execute(
            select(func.count(func.distinct(KPI.kpi_id)))
        )).scalar() or 0

        # Entry filters
        entry_filters = []
        if school_id:
            entry_filters.append(KpiEntry.school_id == school_id)
        if department_id:
            entry_filters.append(KpiEntry.department_id == department_id)
        if date_from:
            entry_filters.append(KpiEntry.timestamp >= date_from)
        if date_to:
            entry_filters.append(KpiEntry.timestamp <= date_to)

        where_clause = and_(*entry_filters) if entry_filters else True

        total_entries = (await self.db.execute(
            select(func.count(KpiEntry.id)).where(where_clause)
        )).scalar() or 0

        # Entries by status
        status_rows = (await self.db.execute(
            select(KpiEntry.status, func.count(KpiEntry.id))
            .where(where_clause)
            .group_by(KpiEntry.status)
        )).all()
        entries_by_status = {row[0]: row[1] for row in status_rows}

        # Entries by school
        school_rows = (await self.db.execute(
            select(
                KpiEntry.school_id,
                School.name,
                KpiEntry.status,
                func.count(KpiEntry.id),
            )
            .join(School, KpiEntry.school_id == School.id, isouter=True)
            .where(where_clause)
            .group_by(KpiEntry.school_id, School.name, KpiEntry.status)
        )).all()

        school_map: dict = {}
        for school_id_val, school_name, status_val, count_val in school_rows:
            key = str(school_id_val) if school_id_val else "unassigned"
            if key not in school_map:
                school_map[key] = {"school_id": str(school_id_val), "school_name": school_name or "Unassigned", "pass": 0, "fail": 0, "pending": 0}
            if status_val in school_map[key]:
                school_map[key][status_val] = count_val
        entries_by_school = list(school_map.values())

        # Entries by KPI
        kpi_rows = (await self.db.execute(
            select(
                KpiEntry.kpi_id,
                KPI.title,
                KpiEntry.status,
                func.count(KpiEntry.id),
            )
            .join(KPI, KpiEntry.kpi_id == KPI.kpi_id, isouter=True)
            .where(where_clause)
            .group_by(KpiEntry.kpi_id, KPI.title, KpiEntry.status)
        )).all()

        kpi_map: dict = {}
        for kpi_id_val, kpi_title, status_val, count_val in kpi_rows:
            key = str(kpi_id_val)
            if key not in kpi_map:
                kpi_map[key] = {"kpi_id": key, "title": kpi_title or "Unknown", "pass": 0, "fail": 0, "pending": 0}
            if status_val in kpi_map[key]:
                kpi_map[key][status_val] = count_val
        entries_by_kpi = list(kpi_map.values())

        return {
            "total_schools": total_schools,
            "total_departments": total_departments,
            "total_kras": total_kras,
            "total_kpis": total_kpis,
            "total_entries": total_entries,
            "entries_by_status": entries_by_status,
            "entries_by_school": entries_by_school,
            "entries_by_kpi": entries_by_kpi,
        }
