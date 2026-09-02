"""
Seed script: creates test School, Departments, KRA, and KPI records.

Usage:
    python scripts/seed_test_data.py

Idempotent — skips records that already exist (matched by unique name/code).
Uses raw SQL for KPI inserts to avoid PostgreSQL native enum type issues.
"""

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import select, text
from shared.database import engine, AsyncSessionLocal
from shared.models import School, Department, SchoolStatus, DepartmentStatus
from shared.platform_models import KRA, KraStatus
from shared.datetime_utils import utc_now


async def seed():
    async with AsyncSessionLocal() as db:
        now = utc_now()

        # ── School ──────────────────────────────────────────────────────
        school_result = await db.execute(
            select(School).where(School.code == "SCH-TEST")
        )
        school = school_result.scalar_one_or_none()
        if school is None:
            school = School(
                name="School-test",
                code="SCH-TEST",
                status=SchoolStatus.ACTIVE,
                address="123 Test Street, Test City",
                contact_email="admin@school-test.example.com",
                contact_phone="+1-555-0100",
                timezone="UTC",
            )
            db.add(school)
            await db.flush()
            print(f"[OK] Created school: {school.name} (id={school.id})")
        else:
            print(f"[SKIP] School '{school.name}' already exists (id={school.id})")

        # ── Departments ─────────────────────────────────────────────────
        departments_data = [
            ("Academics", "DEPT-ACAD", "Academic affairs and curriculum management"),
            ("Security", "DEPT-SEC", "Campus security and safety operations"),
        ]
        dept_ids = {}
        for dept_name, dept_code, desc in departments_data:
            existing = await db.execute(
                select(Department).where(
                    Department.school_id == school.id,
                    Department.code == dept_code,
                )
            )
            dept = existing.scalar_one_or_none()
            if dept is None:
                dept = Department(
                    school_id=school.id,
                    name=dept_name,
                    code=dept_code,
                    status=DepartmentStatus.ACTIVE,
                    description=desc,
                )
                db.add(dept)
                await db.flush()
                print(f"[OK] Created department: {dept.name} (id={dept.id})")
            else:
                print(f"[SKIP] Department '{dept.name}' already exists (id={dept.id})")
            dept_ids[dept_code] = dept.id

        # ── KRAs ────────────────────────────────────────────────────────
        kra_data = [
            ("Academic Excellence", "Measures the quality of academic outcomes across the school"),
            ("Campus Safety", "Tracks security incident response and safety compliance"),
        ]
        kra_ids = {}
        for kra_name, kra_desc in kra_data:
            kra_result = await db.execute(
                select(KRA).where(KRA.name == kra_name)
            )
            kra = kra_result.scalar_one_or_none()
            if kra is None:
                kra = KRA(
                    name=kra_name,
                    description=kra_desc,
                    status=KraStatus.ACTIVE.value,
                )
                db.add(kra)
                await db.flush()
                print(f"[OK] Created KRA: {kra.name} (id={kra.id})")
            else:
                print(f"[SKIP] KRA '{kra.name}' already exists (id={kra.id})")
            kra_ids[kra_name] = kra.id

        await db.commit()

        # ── KPIs (raw SQL to avoid native enum type issues) ─────────────
        kpi_records = [
            {
                "title": "Student Pass Rate",
                "kra_name": "Academic Excellence",
                "target_value": 85,
                "comparator": ">=",
                "unit_of_measure": "percent",
                "frequency_code": "daily",
                "formula_type": "threshold_comparison",
                "capture_type": "value_reading",
                "category_code": "academic",
                "is_sensitive": False,
                "evidence_required": False,
            },
            {
                "title": "Safety Incident Response Time",
                "kra_name": "Campus Safety",
                "target_value": 15,
                "comparator": "<=",
                "unit_of_measure": "minutes",
                "frequency_code": "daily",
                "formula_type": "threshold_comparison",
                "capture_type": "event_time",
                "category_code": "security",
                "is_sensitive": True,
                "evidence_required": True,
            },
            {
                "title": "Monthly Attendance Rate",
                "kra_name": "Academic Excellence",
                "target_value": 92,
                "comparator": ">=",
                "unit_of_measure": "percent",
                "frequency_code": "monthly",
                "formula_type": "threshold_comparison",
                "capture_type": "value_and_event_time",
                "category_code": "academic",
                "is_sensitive": False,
                "evidence_required": False,
                "amber_tolerance_band": 5,
            },
            {
                "title": "Fire Drill Completed",
                "kra_name": "Campus Safety",
                "target_value": 1,
                "comparator": ">=",
                "unit_of_measure": "yes/no",
                "frequency_code": "monthly",
                "formula_type": "threshold_comparison",
                "capture_type": "check",
                "category_code": "security",
                "is_sensitive": False,
                "evidence_required": True,
            },
        ]

        for rec in kpi_records:
            # Check if already exists
            check = await db.execute(
                text("SELECT kpi_id FROM kpis WHERE title = :title LIMIT 1"),
                {"title": rec["title"]},
            )
            if check.scalar_one_or_none():
                print(f"[SKIP] KPI '{rec['title']}' already exists")
                continue

            kpi_id = uuid.uuid4()
            kra_id = str(kra_ids[rec["kra_name"]])
            now_str = now.isoformat()

            await db.execute(
                text("""
                    INSERT INTO kpis (
                        kpi_id, version, kra_id, title, target_value, comparator,
                        unit_of_measure, frequency_code, formula_type, capture_type,
                        category_code, is_sensitive, evidence_required,
                        amber_tolerance_band, non_working_day_policy, status,
                        is_immutable, created_at
                    ) VALUES (
                        :kpi_id, 1, :kra_id, :title, :target_value, :comparator,
                        :unit_of_measure, :frequency_code, :formula_type, :capture_type,
                        :category_code, :is_sensitive, :evidence_required,
                        :amber_tolerance_band, 'skip', 'active',
                        false, :created_at
                    )
                """),
                {
                    "kpi_id": str(kpi_id),
                    "kra_id": kra_id,
                    "title": rec["title"],
                    "target_value": rec["target_value"],
                    "comparator": rec["comparator"],
                    "unit_of_measure": rec["unit_of_measure"],
                    "frequency_code": rec["frequency_code"],
                    "formula_type": rec["formula_type"],
                    "capture_type": rec["capture_type"],
                    "category_code": rec.get("category_code"),
                    "is_sensitive": rec.get("is_sensitive", False),
                    "evidence_required": rec.get("evidence_required", False),
                    "amber_tolerance_band": rec.get("amber_tolerance_band"),
                    "created_at": now,
                },
            )
            print(f"[OK] Created KPI: {rec['title']} (id={kpi_id})")

        # ── Event Time Points (required for event_time / value_and_event_time KPIs) ──
        event_time_kpis = [
            ("Safety Incident Response Time", "Incident Response"),
            ("Monthly Attendance Rate", "Month End Check"),
        ]
        for kpi_title, point_name in event_time_kpis:
            kpi_check = await db.execute(
                text("SELECT kpi_id, version FROM kpis WHERE title = :title"),
                {"title": kpi_title},
            )
            kpi_row = kpi_check.first()
            if kpi_row is None:
                continue

            etp_check = await db.execute(
                text(
                    "SELECT id FROM kpi_event_time_points "
                    "WHERE kpi_id = :kpi_id AND kpi_version = :version"
                ),
                {"kpi_id": str(kpi_row[0]), "version": kpi_row[1]},
            )
            if etp_check.scalar_one_or_none():
                print(f"[SKIP] Event time point '{point_name}' for '{kpi_title}' already exists")
                continue

            await db.execute(
                text("""
                    INSERT INTO kpi_event_time_points (
                        id, kpi_id, kpi_version, name, capture_mode_allowed
                    ) VALUES (
                        :id, :kpi_id, :version, :name, 'manual_only'
                    )
                """),
                {
                    "id": str(uuid.uuid4()),
                    "kpi_id": str(kpi_row[0]),
                    "version": kpi_row[1],
                    "name": point_name,
                },
            )
            print(f"[OK] Created event time point: {point_name} for {kpi_title}")

        # ── Assign KPIs to departments ──────────────────────────────────
        assignments = [
            ("DEPT-ACAD", "Student Pass Rate"),
            ("DEPT-ACAD", "Monthly Attendance Rate"),
            ("DEPT-SEC", "Safety Incident Response Time"),
            ("DEPT-SEC", "Fire Drill Completed"),
        ]

        for dept_code, kpi_title in assignments:
            dept_id = str(dept_ids[dept_code])
            kpi_check = await db.execute(
                text("SELECT kpi_id FROM kpis WHERE title = :title"),
                {"title": kpi_title},
            )
            kpi_row = kpi_check.first()
            if kpi_row is None:
                continue

            assign_check = await db.execute(
                text(
                    "SELECT id FROM department_kpi_assignments "
                    "WHERE department_id = :dept_id AND kpi_id = :kpi_id"
                ),
                {"dept_id": dept_id, "kpi_id": str(kpi_row[0])},
            )
            if assign_check.scalar_one_or_none():
                print(f"[SKIP] Assignment {kpi_title} -> {dept_code} already exists")
                continue

            await db.execute(
                text("""
                    INSERT INTO department_kpi_assignments (
                        id, department_id, kpi_id, assigned_at
                    ) VALUES (
                        :id, :dept_id, :kpi_id, :assigned_at
                    )
                """),
                {
                    "id": str(uuid.uuid4()),
                    "dept_id": dept_id,
                    "kpi_id": str(kpi_row[0]),
                    "assigned_at": now,
                },
            )
            print(f"[OK] Assigned KPI '{kpi_title}' to dept '{dept_code}'")

        await db.commit()
        print("\n[DONE] Seed complete!")


if __name__ == "__main__":
    asyncio.run(seed())
