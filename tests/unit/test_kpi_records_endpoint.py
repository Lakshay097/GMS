"""
Tests for GET /observations/kpi-records — the complete KPI × date matrix
including blank (un-entered) KPIs, with role-based scoping and combined
server-side filters (date range, KRA, department, KPI).
"""
from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from modules.observation_capture.api.routes import list_kpi_records
from shared.middleware.tenancy import TenantContext
from shared.models import Department, School
from shared.platform_models import KPI, KRA, DepartmentKpiAssignment, Observation


def _ctx(user_id: str, school_id=None, department_id=None, roles=None, accessible=None):
    return TenantContext(
        user_id=user_id,
        school_id=str(school_id) if school_id else None,
        department_id=str(department_id) if department_id else None,
        roles=roles or [],
        accessible_school_ids=[str(s) for s in accessible] if accessible else None,
    )


async def _seed_world(db: AsyncSession):
    """School A (depts Academics + Security), School B; 3 KPIs across 2 KRAs."""
    school_a = School(
        id=uuid4(), name="School A", code="SCHA", timezone="Asia/Kolkata",
        working_days=["mon"], created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
    )
    school_b = School(
        id=uuid4(), name="School B", code="SCHB", timezone="Asia/Kolkata",
        working_days=["mon"], created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
    )
    db.add_all([school_a, school_b])
    await db.flush()

    dept_acad = Department(id=uuid4(), school_id=school_a.id, name="Academics", code="ACA")
    dept_sec = Department(id=uuid4(), school_id=school_a.id, name="Security", code="SEC")
    dept_b = Department(id=uuid4(), school_id=school_b.id, name="B Dept", code="BDP")
    db.add_all([dept_acad, dept_sec, dept_b])
    await db.flush()

    kra_acad = KRA(id=uuid4(), name="Academic Excellence", status="active")
    kra_safe = KRA(id=uuid4(), name="Campus Safety", status="active")
    db.add_all([kra_acad, kra_safe])
    await db.flush()

    kpi_daily = KPI(
        kpi_id=uuid4(), version=1, kra_id=kra_acad.id, title="Student Pass Rate",
        target_value=Decimal("90"), comparator=">=", unit_of_measure="percent",
        frequency_code="daily", status="active", created_by=None,
    )
    kpi_blank = KPI(
        kpi_id=uuid4(), version=1, kra_id=kra_safe.id, title="Safety Walkthroughs",
        target_value=Decimal("1"), comparator=">=", unit_of_measure="count",
        frequency_code="daily", status="active", created_by=None,
    )
    kpi_monthly = KPI(
        kpi_id=uuid4(), version=1, kra_id=kra_safe.id, title="Fire Drill Completed",
        target_value=Decimal("1"), comparator=">=", unit_of_measure="count",
        frequency_code="monthly", status="active", created_by=None,
    )
    db.add_all([kpi_daily, kpi_blank, kpi_monthly])
    await db.flush()

    db.add_all([
        DepartmentKpiAssignment(id=uuid4(), department_id=dept_acad.id, kpi_id=kpi_daily.kpi_id),
        DepartmentKpiAssignment(id=uuid4(), department_id=dept_acad.id, kpi_id=kpi_blank.kpi_id),
        DepartmentKpiAssignment(id=uuid4(), department_id=dept_sec.id, kpi_id=kpi_monthly.kpi_id),
        DepartmentKpiAssignment(id=uuid4(), department_id=dept_b.id, kpi_id=kpi_daily.kpi_id),
    ])

    checker_id = uuid4()
    # Daily KPI entered on Sep 7 only; monthly KPI entered Sep 7 (covers all of September)
    db.add_all([
        Observation(
            id=uuid4(), kpi_id=kpi_daily.kpi_id, kpi_version=1, checker_id=checker_id,
            department_id=dept_acad.id, school_id=school_a.id,
            value_numeric=Decimal("92"), auto_result="met", rag_status="green",
            status="pending", submitted_at=datetime(2026, 9, 7, 10, 0, 0), is_late=False,
            submission_token=uuid4(),
        ),
        Observation(
            id=uuid4(), kpi_id=kpi_monthly.kpi_id, kpi_version=1, checker_id=checker_id,
            department_id=dept_sec.id, school_id=school_a.id,
            value_numeric=Decimal("1"), auto_result="met", rag_status="green",
            status="verified", submitted_at=datetime(2026, 9, 7, 9, 0, 0), is_late=False,
            submission_token=uuid4(),
        ),
    ])
    await db.commit()
    return {
        "school_a": school_a, "school_b": school_b,
        "dept_acad": dept_acad, "dept_sec": dept_sec, "dept_b": dept_b,
        "kra_acad": kra_acad, "kra_safe": kra_safe,
        "kpi_daily": kpi_daily, "kpi_blank": kpi_blank, "kpi_monthly": kpi_monthly,
    }


@pytest.mark.asyncio
class TestKpiRecordsMatrix:
    async def test_superadmin_sees_all_kpis_including_blanks(self, db: AsyncSession):
        w = await _seed_world(db)
        rows = await list_kpi_records(
            date_from=date(2026, 9, 6), date_to=date(2026, 9, 8),
            kra_id=None, department_id=None, kpi_id=None,
            tenant_context=_ctx(str(uuid4()), roles=["superadmin"]), db=db,
        )
        titles = {r.kpi_title for r in rows}
        assert titles == {"Student Pass Rate", "Safety Walkthroughs", "Fire Drill Completed"}

        daily = next(r for r in rows if r.kpi_title == "Student Pass Rate")
        # entered on the 7th only; the 6th and 8th must NOT be dropped
        assert set(daily.entries.keys()) == {"2026-09-07"}
        assert daily.entries["2026-09-07"].value_numeric == Decimal("92")

        blank = next(r for r in rows if r.kpi_title == "Safety Walkthroughs")
        assert blank.entries == {}  # all-blank KPI still returned

        monthly = next(r for r in rows if r.kpi_title == "Fire Drill Completed")
        # monthly entry covers every requested September day
        assert set(monthly.entries.keys()) == {"2026-09-06", "2026-09-07", "2026-09-08"}
        assert monthly.entries["2026-09-07"].status == "verified"

    async def test_checker_scoped_to_assigned_department_kpis(self, db: AsyncSession):
        w = await _seed_world(db)
        rows = await list_kpi_records(
            date_from=date(2026, 9, 6), date_to=date(2026, 9, 8),
            kra_id=None, department_id=None, kpi_id=None,
            tenant_context=_ctx(str(uuid4()), school_id=w["school_a"].id,
                                department_id=w["dept_acad"].id, roles=["checker"]),
            db=db,
        )
        titles = {r.kpi_title for r in rows}
        assert titles == {"Student Pass Rate", "Safety Walkthroughs"}  # only their dept's KPIs

    async def test_checker_forged_filters_cannot_escape_scope(self, db: AsyncSession):
        w = await _seed_world(db)
        # Ask for another school's department and an unassigned KPI explicitly.
        rows = await list_kpi_records(
            date_from=date(2026, 9, 6), date_to=date(2026, 9, 8),
            kra_id=None, department_id=w["dept_b"].id, kpi_id=w["kpi_daily"].kpi_id,
            tenant_context=_ctx(str(uuid4()), school_id=w["school_a"].id,
                                department_id=w["dept_acad"].id, roles=["checker"]),
            db=db,
        )
        assert rows == []

    async def test_kra_filter_narrows(self, db: AsyncSession):
        w = await _seed_world(db)
        rows = await list_kpi_records(
            date_from=date(2026, 9, 6), date_to=date(2026, 9, 8),
            kra_id=w["kra_safe"].id, department_id=None, kpi_id=None,
            tenant_context=_ctx(str(uuid4()), roles=["superadmin"]), db=db,
        )
        assert {r.kpi_title for r in rows} == {"Safety Walkthroughs", "Fire Drill Completed"}

    async def test_combined_converging_filters(self, db: AsyncSession):
        w = await _seed_world(db)
        rows = await list_kpi_records(
            date_from=date(2026, 9, 6), date_to=date(2026, 9, 8),
            kra_id=w["kra_safe"].id, department_id=w["dept_sec"].id,
            kpi_id=w["kpi_monthly"].kpi_id,
            tenant_context=_ctx(str(uuid4()), roles=["superadmin"]), db=db,
        )
        assert [r.kpi_title for r in rows] == ["Fire Drill Completed"]

    async def test_combined_contradictory_filters_empty(self, db: AsyncSession):
        w = await _seed_world(db)
        rows = await list_kpi_records(
            date_from=date(2026, 9, 6), date_to=date(2026, 9, 8),
            kra_id=w["kra_acad"].id, department_id=w["dept_sec"].id,
            kpi_id=None,
            tenant_context=_ctx(str(uuid4()), roles=["superadmin"]), db=db,
        )
        assert rows == []  # Security owns no Academic KPIs

    async def test_admin_school_scoped_and_out_of_school_dept_empty(self, db: AsyncSession):
        w = await _seed_world(db)
        base = _ctx(str(uuid4()), school_id=w["school_a"].id, roles=["admin"])
        rows = await list_kpi_records(
            date_from=date(2026, 9, 6), date_to=date(2026, 9, 8),
            kra_id=None, department_id=None, kpi_id=None, tenant_context=base, db=db,
        )
        # School A has all three KPIs assigned somewhere
        assert {r.kpi_title for r in rows} == {"Student Pass Rate", "Safety Walkthroughs", "Fire Drill Completed"}

        # Explicitly requesting School B's department yields nothing, not School B data.
        rows_b = await list_kpi_records(
            date_from=date(2026, 9, 6), date_to=date(2026, 9, 8),
            kra_id=None, department_id=w["dept_b"].id, kpi_id=None,
            tenant_context=base, db=db,
        )
        assert rows_b == []

    async def test_reversed_range_rejected(self, db: AsyncSession):
        await _seed_world(db)
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            await list_kpi_records(
                date_from=date(2026, 9, 8), date_to=date(2026, 9, 6),
                kra_id=None, department_id=None, kpi_id=None,
                tenant_context=_ctx(str(uuid4()), roles=["superadmin"]), db=db,
            )
        assert exc.value.status_code == 400

    async def test_oversized_range_rejected(self, db: AsyncSession):
        await _seed_world(db)
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            await list_kpi_records(
                date_from=date(2026, 1, 1), date_to=date(2026, 12, 31),
                kra_id=None, department_id=None, kpi_id=None,
                tenant_context=_ctx(str(uuid4()), roles=["superadmin"]), db=db,
            )
        assert exc.value.status_code == 400

    async def test_department_name_resolved_not_uuid(self, db: AsyncSession):
        w = await _seed_world(db)
        rows = await list_kpi_records(
            date_from=date(2026, 9, 6), date_to=date(2026, 9, 8),
            kra_id=None, department_id=None, kpi_id=None,
            tenant_context=_ctx(str(uuid4()), roles=["superadmin"]), db=db,
        )
        daily = next(r for r in rows if r.kpi_title == "Student Pass Rate")
        # Assigned to Academics (School A) and B Dept (School B)
        assert daily.department_name is not None
        assert "Academics" in daily.department_name
        assert "B Dept" in daily.department_name
