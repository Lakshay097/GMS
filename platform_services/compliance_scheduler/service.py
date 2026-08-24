"""
Compliance Scheduler — Architecture §5.7a, BR-24, PRS §23.16-23.17.
Generates KPI compliance record shells (not ChecklistInstances).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_services.compliance_scheduler.holiday_resolver import (
    HolidayResolver,
    localize_due_date,
)
from platform_services.configuration_engine.service import ConfigurationEngine
from platform_services.master_data_service.service import MasterDataService
from shared.datetime_utils import utc_now
from shared.models import School
from shared.platform_models import (
    ComplianceObservation,
    ComplianceStatus,
    ComplianceSchedulerRunLog,
    KPI,
    NonWorkingDayPolicy,
    SchedulerRunStatus,
)

DEFAULT_SCHOOL_TIMEZONE = os.getenv("DEFAULT_SCHOOL_TIMEZONE", "Asia/Kolkata")


@dataclass
class ComplianceRunResult:
    run_id: UUID
    records_generated: int
    records_backfilled: int
    status: SchedulerRunStatus


class ComplianceScheduler:
    """
    Distinct from ChecklistScheduler — generates compliance_observations shells.
    Idempotent (BR-24/R-76), timezone-aware (R-77), backfill-capable, holiday-aware.
    """

    FREQUENCY_DAYS = {
        "daily": 1,
        "weekly": 7,
        "monthly": 30,
    }

    def __init__(self, db: AsyncSession):
        self.db = db
        self.master_data = MasterDataService(db)
        self.config = ConfigurationEngine(db)
        self.holiday_resolver = HolidayResolver(self.master_data)

    async def run(
        self,
        *,
        as_of: Optional[datetime] = None,
        last_run_at: Optional[datetime] = None,
    ) -> ComplianceRunResult:
        as_of = as_of or utc_now()
        run_log = ComplianceSchedulerRunLog(
            started_at=as_of,
            status=SchedulerRunStatus.SUCCESS,
        )
        self.db.add(run_log)
        await self.db.flush()

        generated = 0
        backfilled = 0
        timezones_seen: set[str] = set()

        try:
            schools = await self._get_active_schools()
            for school in schools:
                tz = school.timezone or DEFAULT_SCHOOL_TIMEZONE
                timezones_seen.add(tz)
                working_days = school.working_days or [
                    "mon", "tue", "wed", "thu", "fri", "sat"
                ]
                kpis = await self._get_active_kpis_for_school(school.id)

                for kpi in kpis:
                    freq_days = self.FREQUENCY_DAYS.get(kpi.frequency_code, 1)
                    kpi_working_days = kpi.working_days or working_days
                    policy = kpi.non_working_day_policy or NonWorkingDayPolicy.SKIP

                    due_dates = self._compute_due_dates(
                        as_of=as_of,
                        last_run_at=last_run_at,
                        freq_days=freq_days,
                        timezone_name=tz,
                    )

                    for due_date in due_dates:
                        due_at = await self._resolve_due_datetime(
                            due_date=due_date,
                            policy=policy,
                            school_id=school.id,
                            working_days=kpi_working_days,
                            timezone_name=tz,
                        )
                        if due_at is None:
                            continue

                        is_backfill = last_run_at is not None and due_date < as_of.date()
                        created = await self._create_compliance_record(
                            kpi=kpi,
                            school_id=school.id,
                            due_at=due_at,
                            asset_id=None,  # TODO: Add asset_id when KPI is asset-specific
                        )
                        if created:
                            if is_backfill:
                                backfilled += 1
                            else:
                                generated += 1

            run_log.records_generated = generated
            run_log.records_backfilled = backfilled
            run_log.school_timezone_batch = ",".join(sorted(timezones_seen))
            run_log.finished_at = utc_now()
            run_log.status = SchedulerRunStatus.SUCCESS
        except Exception as exc:
            run_log.status = SchedulerRunStatus.FAILED
            run_log.error_detail = str(exc)
            run_log.finished_at = utc_now()

        await self.db.commit()
        return ComplianceRunResult(
            run_id=run_log.id,
            records_generated=generated,
            records_backfilled=backfilled,
            status=run_log.status,
        )

    async def _get_active_schools(self) -> list[School]:
        result = await self.db.execute(select(School))
        return list(result.scalars().all())

    async def _get_active_kpis_for_school(self, school_id: UUID) -> list[KPI]:
        result = await self.db.execute(select(KPI).where(KPI.status == "active"))
        return list(result.scalars().all())

    def _compute_due_dates(
        self,
        *,
        as_of: datetime,
        last_run_at: Optional[datetime],
        freq_days: int,
        timezone_name: str,
    ) -> list[date]:
        """Compute due dates including backfill for missed runs."""
        from zoneinfo import ZoneInfo

        tz = ZoneInfo(timezone_name)
        local_now = as_of.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz)
        today = local_now.date()

        if last_run_at is None:
            return [today]

        local_last = last_run_at.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz)
        dates: list[date] = []
        current = local_last.date()
        while current <= today:
            dates.append(current)
            current += timedelta(days=freq_days)
        if today not in dates:
            dates.append(today)
        return sorted(set(dates))

    async def _resolve_due_datetime(
        self,
        *,
        due_date: date,
        policy: NonWorkingDayPolicy,
        school_id: UUID,
        working_days: list[str],
        timezone_name: str,
    ) -> Optional[datetime]:
        resolved_date = await self.holiday_resolver.apply_non_working_day_policy(
            due_date,
            policy,
            school_id=school_id,
            working_days=working_days,
        )
        if resolved_date is None:
            return None
        return localize_due_date(resolved_date, timezone_name=timezone_name)

    async def _create_compliance_record(
        self,
        *,
        kpi: KPI,
        school_id: UUID,
        due_at: datetime,
        asset_id: Optional[UUID] = None,
    ) -> bool:
        # BR-23: Enforce asset retirement - block new assignment to retired assets
        if asset_id is not None:
            if not await self.master_data.is_asset_active(asset_id):
                # Skip creating compliance record for retired assets
                return False

        existing = await self.db.execute(
            select(ComplianceObservation).where(
                ComplianceObservation.kpi_id == kpi.kpi_id,
                ComplianceObservation.kpi_version == kpi.version,
                ComplianceObservation.school_id == school_id,
                ComplianceObservation.department_id.is_(None),
                ComplianceObservation.location_id.is_(None),
                ComplianceObservation.asset_id == asset_id,
                ComplianceObservation.due_at == due_at,
            )
        )
        if existing.scalar_one_or_none():
            return False

        grace_hours = await self.config.get("grace_period_hours", school_id=school_id)
        grace_elapsed = due_at + timedelta(hours=grace_hours)

        record = ComplianceObservation(
            kpi_id=kpi.kpi_id,
            kpi_version=kpi.version,
            school_id=school_id,
            department_id=None,
            asset_id=asset_id,
            due_at=due_at,
            grace_period_elapsed_at=grace_elapsed,
            compliance_status=ComplianceStatus.OPEN,
        )
        self.db.add(record)
        await self.db.flush()
        return True

    async def sweep_grace_periods(
        self,
        *,
        as_of: Optional[datetime] = None,
    ) -> int:
        """
        Transition OPEN / LATE_SUBMITTABLE shells to CLOSED_MISSED once
        grace_period_elapsed_at has passed with no submission (FR-264 / R-84).

        Scorecard generation is NOT triggered here — callers must invoke
        ScorecardService.generate() separately when a cycle needs scoring.
        
        Uses distributed locking to prevent concurrent execution issues.
        """
        from shared.distributed_lock import with_distributed_lock
        
        # Use distributed lock to prevent concurrent execution
        async with with_distributed_lock("grace_period_sweep", ttl=120) as lock_acquired:
            if not lock_acquired:
                # Lock already held by another process, skip execution
                return 0
            
            as_of = as_of or utc_now()
            result = await self.db.execute(
                select(ComplianceObservation).where(
                    ComplianceObservation.compliance_status.in_(
                        [ComplianceStatus.OPEN, ComplianceStatus.LATE_SUBMITTABLE]
                    ),
                    ComplianceObservation.grace_period_elapsed_at.is_not(None),
                    ComplianceObservation.grace_period_elapsed_at <= as_of,
                )
            )
            shells = result.scalars().all()
            for shell in shells:
                shell.compliance_status = ComplianceStatus.CLOSED_MISSED
            if shells:
                await self.db.flush()
            return len(shells)
