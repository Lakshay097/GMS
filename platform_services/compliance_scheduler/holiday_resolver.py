"""
Holiday and working-day resolution for Compliance Scheduler.
BR-22/FR-240-242: Non-Working-Day Policy application.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timedelta
from typing import Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from platform_services.master_data_service.service import MasterDataService
from shared.platform_models import NonWorkingDayPolicy


class HolidayResolver:
    """Resolves due dates against working days and holiday calendar."""

    def __init__(self, master_data: MasterDataService):
        self.master_data = master_data

    async def is_non_working_day(
        self,
        check_date: date,
        *,
        school_id: UUID,
        working_days: list[str],
    ) -> bool:
        if not MasterDataService.is_working_day(check_date, working_days):
            return True
        return await self.master_data.is_holiday(check_date, school_id=school_id)

    async def apply_non_working_day_policy(
        self,
        due_date: date,
        policy: NonWorkingDayPolicy,
        *,
        school_id: UUID,
        working_days: list[str],
        max_iterations: int = 30,
    ) -> Optional[date]:
        """
        Apply Skip/Shift Forward/Shift Backward policy on a school-local calendar date.
        Returns None for Skip when the date is non-working.
        """
        is_non_working = await self.is_non_working_day(
            due_date, school_id=school_id, working_days=working_days
        )
        if not is_non_working:
            return due_date

        if policy == NonWorkingDayPolicy.SKIP:
            return None

        current = due_date
        for _ in range(max_iterations):
            if policy == NonWorkingDayPolicy.SHIFT_FORWARD:
                current = current + timedelta(days=1)
            else:  # SHIFT_BACKWARD
                current = current - timedelta(days=1)

            if not await self.is_non_working_day(
                current, school_id=school_id, working_days=working_days
            ):
                return current

        return None


def localize_due_date(
    due_date: date,
    *,
    timezone_name: str,
    hour: int = 23,
    minute: int = 59,
) -> datetime:
    """Compute due datetime in school timezone, never server-local/UTC (BR-24/FR-251)."""
    tz = ZoneInfo(timezone_name)
    local_dt = datetime(due_date.year, due_date.month, due_date.day, hour, minute, tzinfo=tz)
    return local_dt.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
