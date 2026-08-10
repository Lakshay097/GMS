"""
KPI service — PRS §22-23.
Versioning (R-17/BR-05), validation (PRS §52), and Rule Engine integration (R-35).
"""
from __future__ import annotations

import re
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy import func, String
from sqlalchemy.ext.asyncio import AsyncSession

from platform_services.configuration_engine.constants import ConfigKey
from platform_services.configuration_engine.service import ConfigurationEngine
from platform_services.master_data_service.service import MasterDataService
from platform_services.notification_service.service import (
    NotificationPayload,
    NotificationService,
)
from platform_services.rule_engine.service import RuleEngine
from shared.datetime_utils import utc_now
from shared.errors import BusinessRuleError, ConflictError, NotFoundError, ValidationError
from shared.platform_models import (
    VALID_COMPARATORS,
    AutoResult,
    DepartmentKpiAssignment,
    KPI,
    KraStatus,
    KpiCaptureType,
    KpiEventTimePoint,
    KpiFormulaType,
    KpiStatus,
    NonWorkingDayPolicy,
    NotificationCategory,
    NotificationChannel,
    Observation,
    RagStatus,
)
from shared.models import User, UserRole
from shared.platform_models import KRA
from platform_services.rule_engine.kpi_calculation import normalize_comparator


VERSION_TRIGGER_FIELDS = frozenset({"target_value", "comparator", "unit_of_measure"})

FREQUENCY_ALIASES = {
    "annually": "annual",
    "half-yearly": "half_yearly",
    "half_yearly": "half_yearly",
    "times-per-day": "times_per_day",
    "ad-hoc": "ad_hoc",
    "event-triggered": "event_triggered",
    "event_triggered": "event_triggered",
    "event-driven": "event_triggered",
    "event_driven": "event_triggered",
    "termly": "termly",
    "quaterly": "quarterly",  # SME seed typo seen in Principal tab
    "quarterly": "quarterly",
}

CAPTURE_TYPE_ALIASES = {
    "value": KpiCaptureType.VALUE_READING.value,
    "value reading": KpiCaptureType.VALUE_READING.value,  # SME-approved label (2026-08-08)
    "event time": KpiCaptureType.EVENT_TIME.value,
    "value + event time": KpiCaptureType.VALUE_AND_EVENT_TIME.value,
}

# Q3/D1 RESOLVED (in-platform): Marketing Manager and Telecaller are no longer held.
# Do not reintroduce role holds here without updating assumptions-log.md.
HELD_ROLE_MARKERS: tuple[str, ...] = ()

CORE_ROLE_MARKER = "core (no role manual)"

PLACEHOLDER_PATTERNS = (
    "_n/a_",
    "_not specified in manual_",
    "_not specified — school-level default_",
    "_not specified - school-level default_",
    "_target not numerically specified in manual",
    "defined ",
    "x/",
    "x%",
)


class KpiService:
    def __init__(
        self,
        db: AsyncSession,
        *,
        config_engine: Optional[ConfigurationEngine] = None,
        rule_engine: Optional[RuleEngine] = None,
        master_data: Optional[MasterDataService] = None,
        notification_service: Optional[NotificationService] = None,
    ):
        self.db = db
        self.config_engine = config_engine or ConfigurationEngine(db)
        self.rule_engine = rule_engine or RuleEngine()
        self.master_data = master_data or MasterDataService(db)
        self._notification_service = notification_service or NotificationService(db)

    async def create_kpi(
        self,
        *,
        kra_id: UUID,
        title: str,
        target_value: Decimal,
        comparator: str,
        unit_of_measure: str,
        frequency_code: str,
        created_by: Optional[UUID] = None,
        capture_type: str = KpiCaptureType.VALUE_READING.value,
        category_code: Optional[str] = None,
        is_sensitive: bool = False,
        evidence_required: bool = False,
        amber_tolerance_band: Optional[Decimal] = None,
        working_days: Optional[list[str]] = None,
        non_working_day_policy: str = NonWorkingDayPolicy.SKIP.value,
        event_time_points: Optional[list[dict]] = None,
    ) -> KPI:
        await self._validate_kra(kra_id)
        try:
            comparator = normalize_comparator(comparator)
        except Exception as exc:
            raise ValidationError("Invalid comparator — must be one of >=, <=, =, <, >", field="comparator") from exc
        await self._validate_frequency(frequency_code)
        self._validate_capture_type(capture_type, event_time_points or [])

        kpi = KPI(
            kpi_id=uuid.uuid4(),
            version=1,
            kra_id=kra_id,
            title=title,
            target_value=target_value,
            comparator=comparator,
            unit_of_measure=unit_of_measure,
            frequency_code=frequency_code,
            formula_type=KpiFormulaType.THRESHOLD_COMPARISON,
            capture_type=KpiCaptureType(capture_type),
            category_code=category_code,
            is_sensitive=is_sensitive,
            evidence_required=evidence_required,
            amber_tolerance_band=amber_tolerance_band,
            working_days=working_days,
            non_working_day_policy=NonWorkingDayPolicy(non_working_day_policy),
            status=KpiStatus.ACTIVE,
            created_by=created_by,
        )
        self.db.add(kpi)
        await self.db.flush()
        await self._replace_event_time_points(kpi, event_time_points or [])
        await self.db.commit()
        await self.db.refresh(kpi)
        
        # Notify Admins per PRS §49 Notification Matrix
        # Category 7 (INFORMATIONAL) - In-App, Email channels
        from shared.models import User, UserRole
        from sqlalchemy import select
        
        # Get KRA to determine school context
        kra = await self.db.get(KRA, kra_id)
        if kra and created_by:
            # Notify the creator
            await self._notification_service.dispatch(
                NotificationPayload(
                    user_id=created_by,
                    category=NotificationCategory.INFORMATIONAL.value,
                    title="KPI Created",
                    body=f"New KPI '{title}' has been created successfully",
                    channel=NotificationChannel.IN_APP,
                    entity_type="kpi",
                    entity_id=kpi.kpi_id,
                )
            )
            
            # Notify SuperAdmins (global scope)
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
                        title="KPI Created",
                        body=f"New KPI '{title}' has been created in the Global KPI Library",
                        channel=NotificationChannel.EMAIL,
                        entity_type="kpi",
                        entity_id=kpi.kpi_id,
                    )
                )
        
        return kpi

    async def get_current_kpi(self, kpi_id: UUID) -> KPI:
        result = await self.db.execute(
            select(KPI).where(KPI.kpi_id == kpi_id, KPI.status == KpiStatus.ACTIVE)
        )
        kpi = result.scalar_one_or_none()
        if kpi is None:
            raise NotFoundError("KPI")
        return kpi

    async def get_kpi_version(self, kpi_id: UUID, version: int) -> KPI:
        kpi = await self.db.get(KPI, {"kpi_id": kpi_id, "version": version})
        if kpi is None:
            raise NotFoundError("KPI version")
        return kpi

    async def list_current_kpis(self, *, kra_id: Optional[UUID] = None) -> list[KPI]:
        query = select(KPI).where(KPI.status == KpiStatus.ACTIVE)
        if kra_id is not None:
            query = query.where(KPI.kra_id == kra_id)
        result = await self.db.execute(query.order_by(KPI.title))
        return list(result.scalars().all())

    async def list_versions(self, kpi_id: UUID) -> list[KPI]:
        result = await self.db.execute(
            select(KPI).where(KPI.kpi_id == kpi_id).order_by(KPI.version.desc())
        )
        versions = list(result.scalars().all())
        if not versions:
            raise NotFoundError("KPI")
        return versions

    async def update_kpi(
        self,
        kpi_id: UUID,
        *,
        updated_by: Optional[UUID] = None,
        **fields: Any,
    ) -> KPI:
        """
        Edit KPI fields. Target/Comparator/Unit changes create a new version (R-17/FR-049).
        Prior version becomes deprecated when superseded; immutable once referenced (FR-050).
        """
        current = await self.get_current_kpi(kpi_id)
        if current.is_immutable:
            version_fields = {k: v for k, v in fields.items() if v is not None}
            if any(k in VERSION_TRIGGER_FIELDS for k in version_fields):
                return await self._create_new_version(current, updated_by=updated_by, **version_fields)
            raise BusinessRuleError(
                "KPI version is immutable because it is referenced by observations (R-17/FR-050)",
                details={"kpi_id": str(kpi_id), "version": current.version},
            )

        version_fields = {}
        mutable_fields = {}
        for key, value in fields.items():
            if value is None:
                continue
            if key in VERSION_TRIGGER_FIELDS:
                version_fields[key] = value
            else:
                mutable_fields[key] = value

        if version_fields:
            return await self._create_new_version(
                current,
                updated_by=updated_by,
                **version_fields,
                **mutable_fields,
            )

        for key, value in mutable_fields.items():
            if key == "capture_type":
                self._validate_capture_type(value, fields.get("event_time_points") or [])
                setattr(current, key, KpiCaptureType(value))
            elif key == "non_working_day_policy":
                setattr(current, key, NonWorkingDayPolicy(value))
            else:
                setattr(current, key, value)

        if "event_time_points" in fields and fields["event_time_points"] is not None:
            await self._replace_event_time_points(current, fields["event_time_points"])

        await self.db.commit()
        await self.db.refresh(current)
        return current

    async def deprecate_kpi(self, kpi_id: UUID) -> KPI:
        current = await self.get_current_kpi(kpi_id)
        current.status = KpiStatus.DEPRECATED
        await self.db.commit()
        await self.db.refresh(current)
        return current

    async def assign_to_department(
        self,
        *,
        department_id: UUID,
        kpi_id: UUID,
        assigned_by: Optional[UUID] = None,
    ) -> DepartmentKpiAssignment:
        await self.get_current_kpi(kpi_id)
        existing = await self.db.execute(
            select(DepartmentKpiAssignment).where(
                DepartmentKpiAssignment.department_id == department_id,
                DepartmentKpiAssignment.kpi_id == kpi_id,
            )
        )
        if existing.scalar_one_or_none():
            raise ConflictError("KPI already assigned to department")

        assignment = DepartmentKpiAssignment(
            department_id=department_id,
            kpi_id=kpi_id,
            assigned_by=assigned_by,
        )
        self.db.add(assignment)
        await self.db.commit()
        await self.db.refresh(assignment)
        return assignment

    async def validate_observation_submission(
        self,
        *,
        kpi_id: UUID,
        kpi_version: int,
    ) -> KPI:
        """Block submissions against deprecated KPI versions (R-21/PRS §52)."""
        kpi = await self.get_kpi_version(kpi_id, kpi_version)
        if kpi.status == KpiStatus.DEPRECATED:
            raise BusinessRuleError(
                "Submission against a deprecated KPI version is not allowed (R-21)",
                details={
                    "kpi_id": str(kpi_id),
                    "kpi_version": kpi_version,
                    "status": kpi.status.value,
                },
            )
        return kpi

    async def submit_observation(
        self,
        *,
        kpi_id: UUID,
        kpi_version: int,
        checker_id: UUID,
        department_id: UUID,
        school_id: UUID,
        value_numeric: Optional[Decimal] = None,
        value_text: Optional[str] = None,
        is_late: bool = False,
        submission_token: Optional[UUID] = None,
        asset_id: Optional[UUID] = None,
    ) -> Observation:
        kpi = await self.validate_observation_submission(kpi_id=kpi_id, kpi_version=kpi_version)

        if value_numeric is None and value_text is None:
            raise ValidationError("Observation value is required", field="value_numeric")

        # BR-23: Enforce asset retirement - block new assignment to retired assets
        if asset_id is not None:
            from shared.platform_models import Asset, AssetStatus
            asset = await self.db.get(Asset, asset_id)
            if asset is None or asset.status != AssetStatus.ACTIVE:
                raise ValidationError(
                    "Cannot assign observation to retired or non-existent asset",
                    field="asset_id"
                )

        calc = await self.compute_kpi_result(
            kpi=kpi,
            value_numeric=value_numeric,
            school_id=school_id,
            is_late=is_late,
        )

        observation = Observation(
            kpi_id=kpi_id,
            kpi_version=kpi_version,
            checker_id=checker_id,
            department_id=department_id,
            school_id=school_id,
            value_numeric=value_numeric,
            value_text=value_text,
            auto_result=AutoResult(calc["auto_result"]) if calc["auto_result"] else AutoResult.N_A,
            rag_status=RagStatus(calc["rag_status"]),
            is_late=is_late,
            submission_token=submission_token or uuid.uuid4(),
            asset_id=asset_id,
        )
        self.db.add(observation)
        await self.db.flush()

        await self._mark_kpi_immutable_if_referenced(kpi_id, kpi_version)
        await self.db.commit()
        await self.db.refresh(observation)
        return observation

    async def compute_kpi_result(
        self,
        *,
        kpi: KPI,
        value_numeric: Optional[Decimal],
        school_id: Optional[UUID] = None,
        is_late: bool = False,
    ) -> dict:
        """Compute auto-result and RAG via Rule Engine with config-driven params (R-35/R-36/R-37)."""
        await self.config_engine.seed_defaults()
        decimal_places = await self.config_engine.get(ConfigKey.KPI_ROUNDING_DECIMAL_PLACES)
        rounding_mode = await self.config_engine.get(ConfigKey.KPI_ROUNDING_MODE)
        missing_data_behavior = await self.config_engine.get(ConfigKey.KPI_MISSING_DATA_BEHAVIOR)
        amber_band = await self.config_engine.get_amber_tolerance_band(
            category_code=kpi.category_code,
            school_id=school_id,
            kpi_override=kpi.amber_tolerance_band,
        )

        return self.rule_engine.compute_kpi_result(
            formula_type=kpi.formula_type.value,
            value=value_numeric,
            target=Decimal(str(kpi.target_value)),
            comparator=kpi.comparator,
            amber_band_pct=Decimal(str(amber_band)),
            is_late=is_late,
            decimal_places=int(decimal_places),
            rounding_mode=str(rounding_mode),
            missing_data_behavior=str(missing_data_behavior),
        )

    async def import_from_seed_file(
        self,
        *,
        seed_file_path: Optional[str] = None,
        confirm_sme_review: bool = False,
        created_by: Optional[UUID] = None,
    ) -> dict:
        """
        Import KPI catalogue from kpi-seed-data.md.

        Q3/D1: Marketing Manager and Telecaller rows are included (in-platform).
        Q5/D3: Core KRA Set rows (Role = "Core (no role manual)") are included.

        SME column review remains a hard gate — confirm_sme_review must be true
        after an actual SuperAdmin column pass; D1/D3 resolution alone is not
        content sign-off (kpi-seed-data.md status / §3).
        """
        if not confirm_sme_review:
            raise BusinessRuleError(
                "KPI seed import requires confirm_sme_review=true after SME sign-off "
                "(kpi-seed-data.md blocking-items section)",
                details={"imported": 0, "skipped": 0, "core_imported": 0},
            )

        path = Path(seed_file_path or "specs/kpi-seed-data.md")
        if not path.exists():
            raise ValidationError(f"Seed file not found: {path}", field="seed_file_path")

        content = path.read_text(encoding="utf-8")
        rows = self._parse_seed_tables(content)
        imported = 0
        skipped = 0
        core_imported = 0
        role_imported = 0
        kra_cache: dict[str, UUID] = {}

        for row in rows:
            if self._should_skip_seed_row(row):
                skipped += 1
                continue

            kra_name = row["kra"].strip()
            if kra_name not in kra_cache:
                existing = await self.db.execute(select(KRA).where(KRA.name == kra_name))
                kra = existing.scalar_one_or_none()
                if kra is None:
                    description = (
                        "Core KRA Set (D3) — default taxonomy for schools without a role manual"
                        if row.get("source") == "core"
                        else None
                    )
                    kra = KRA(name=kra_name, description=description, status=KraStatus.ACTIVE)
                    self.db.add(kra)
                    await self.db.flush()
                kra_cache[kra_name] = kra.id

            try:
                target = self._parse_target(row["target"])
                comparator = normalize_comparator(row["comparator"])
                frequency = self._normalize_frequency(row["frequency"])
                await self._validate_frequency(frequency)
                capture_type = CAPTURE_TYPE_ALIASES.get(
                    row["capture_type"].strip().lower(),
                    KpiCaptureType.VALUE_READING.value,
                )
                policy = self._parse_non_working_day_policy(row["non_working_day_policy"])
                event_points = []
                if capture_type != KpiCaptureType.VALUE_READING.value:
                    point_name = row.get("event_time_points", "").strip()
                    if point_name and point_name.lower() not in ("n/a", ""):
                        event_points = [{"name": point_name}]

                category_code = None
                if row.get("source") == "core":
                    # D3 categories: Safety, Academics, Facilities, Finance (basic), Staff Compliance
                    category_code = kra_name.lower().replace(" ", "_").replace("(", "").replace(")", "")

                await self.create_kpi(
                    kra_id=kra_cache[kra_name],
                    title=row["kpi"].strip(),
                    target_value=target,
                    comparator=comparator,
                    unit_of_measure=self._normalize_unit(row["unit"]),
                    frequency_code=frequency,
                    created_by=created_by,
                    capture_type=capture_type,
                    category_code=category_code,
                    is_sensitive=row.get("sensitive", "no").strip().lower() == "yes",
                    evidence_required=row.get("evidence_required", "no").strip().lower() in ("yes", "true", "1"),
                    non_working_day_policy=policy,
                    event_time_points=event_points,
                )
                imported += 1
                if row.get("source") == "core":
                    core_imported += 1
                else:
                    role_imported += 1
            except (ValidationError, BusinessRuleError, ValueError):
                skipped += 1

        return {
            "imported": imported,
            "skipped": skipped,
            "kra_count": len(kra_cache),
            "core_imported": core_imported,
            "role_imported": role_imported,
        }

    async def _create_new_version(
        self,
        current: KPI,
        *,
        updated_by: Optional[UUID] = None,
        **fields: Any,
    ) -> KPI:
        if fields.get("comparator") is not None:
            fields["comparator"] = normalize_comparator(fields["comparator"])

        new_version = KPI(
            kpi_id=current.kpi_id,
            version=current.version + 1,
            kra_id=current.kra_id,
            title=fields.get("title", current.title),
            target_value=fields.get("target_value", current.target_value),
            comparator=fields.get("comparator", current.comparator),
            unit_of_measure=fields.get("unit_of_measure", current.unit_of_measure),
            frequency_code=fields.get("frequency_code", current.frequency_code),
            formula_type=current.formula_type,
            capture_type=KpiCaptureType(fields.get("capture_type", current.capture_type.value)),
            category_code=fields.get("category_code", current.category_code),
            is_sensitive=fields.get("is_sensitive", current.is_sensitive),
            amber_tolerance_band=fields.get("amber_tolerance_band", current.amber_tolerance_band),
            working_days=fields.get("working_days", current.working_days),
            non_working_day_policy=NonWorkingDayPolicy(
                fields.get("non_working_day_policy", current.non_working_day_policy.value)
            ),
            status=KpiStatus.ACTIVE,
            created_by=updated_by or current.created_by,
        )

        current.status = KpiStatus.DEPRECATED
        self.db.add(new_version)
        await self.db.flush()

        event_points = fields.get("event_time_points")
        if event_points is not None:
            await self._replace_event_time_points(new_version, event_points)
        else:
            await self._copy_event_time_points(current, new_version)

        await self.db.commit()
        await self.db.refresh(new_version)
        return new_version

    async def _mark_kpi_immutable_if_referenced(self, kpi_id: UUID, version: int) -> None:
        count_result = await self.db.execute(
            select(func.count()).select_from(Observation).where(
                Observation.kpi_id == kpi_id,
                Observation.kpi_version == version,
            )
        )
        if count_result.scalar_one() > 0:
            kpi = await self.get_kpi_version(kpi_id, version)
            kpi.is_immutable = True

    async def _validate_kra(self, kra_id: UUID) -> KRA:
        kra = await self.db.get(KRA, kra_id)
        if kra is None:
            raise NotFoundError("KRA")
        if kra.status == KraStatus.DEPRECATED:
            raise ValidationError("Cannot create KPI under a deprecated KRA", field="kra_id")
        return kra

    async def _validate_frequency(self, frequency_code: str) -> None:
        entries = await self.master_data.get_active_entries("frequency")
        valid_codes = {entry.code for entry in entries}
        if valid_codes and frequency_code not in valid_codes:
            raise ValidationError(
                f"Unsupported frequency '{frequency_code}' — must be a Master Data frequency code",
                field="frequency_code",
                details={"supported": sorted(valid_codes)},
            )

    def _validate_capture_type(self, capture_type: str, event_time_points: list) -> None:
        try:
            parsed = KpiCaptureType(capture_type)
        except ValueError as exc:
            raise ValidationError("Invalid capture_type", field="capture_type") from exc
        if parsed != KpiCaptureType.VALUE_READING and not event_time_points:
            raise ValidationError(
                "Event Time capture requires at least one event time point (PRS §23.6)",
                field="event_time_points",
            )

    async def _replace_event_time_points(self, kpi: KPI, points: list) -> None:
        existing = await self.db.execute(
            select(KpiEventTimePoint).where(
                KpiEventTimePoint.kpi_id == kpi.kpi_id,
                KpiEventTimePoint.kpi_version == kpi.version,
            )
        )
        for point in existing.scalars().all():
            await self.db.delete(point)

        for point in points:
            self.db.add(
                KpiEventTimePoint(
                    kpi_id=kpi.kpi_id,
                    kpi_version=kpi.version,
                    name=point["name"] if isinstance(point, dict) else point.name,
                    capture_mode_allowed=(
                        point.get("capture_mode_allowed", "manual_only")
                        if isinstance(point, dict)
                        else point.capture_mode_allowed
                    ),
                    target_time=point.get("target_time") if isinstance(point, dict) else point.target_time,
                )
            )

    async def _copy_event_time_points(self, source: KPI, target: KPI) -> None:
        result = await self.db.execute(
            select(KpiEventTimePoint).where(
                KpiEventTimePoint.kpi_id == source.kpi_id,
                KpiEventTimePoint.kpi_version == source.version,
            )
        )
        for point in result.scalars().all():
            self.db.add(
                KpiEventTimePoint(
                    kpi_id=target.kpi_id,
                    kpi_version=target.version,
                    name=point.name,
                    capture_mode_allowed=point.capture_mode_allowed,
                    target_time=point.target_time,
                )
            )

    @staticmethod
    def _parse_seed_tables(content: str) -> list[dict]:
        """
        Parse Role|KRA|KPI seed tables (kpi-seed-data.md layout).
        Includes Marketing/Telecaller (Q3) and Core KRA Set (Q5).
        HELD_ROLE_MARKERS is empty after D1 resolution; kept for future holds only.
        """
        rows: list[dict] = []
        role_first = False
        for line in content.splitlines():
            if not line.startswith("|") or line.startswith("|---"):
                continue
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if not cells:
                continue

            header0 = cells[0].lower()
            if header0 in {"kra", "role"}:
                role_first = header0 == "role"
                continue

            if role_first:
                if len(cells) < 7:
                    continue
                role_name = cells[0]
                if any(marker in role_name.lower() for marker in HELD_ROLE_MARKERS):
                    continue
                kra, kpi, unit, comparator, target, frequency = cells[1:7]
                sensitive = cells[7] if len(cells) > 7 else "no"
                capture_type = cells[8] if len(cells) > 8 else "Value"
                event_time_points = cells[9] if len(cells) > 9 else ""
                non_working_day_policy = cells[10] if len(cells) > 10 else "Skip"
                asset_location_scoped = cells[11] if len(cells) > 11 else "none"
                evidence_required = cells[12] if len(cells) > 12 else "no"
                source = "core" if CORE_ROLE_MARKER in role_name.lower() else "role_manual"
            else:
                # Legacy KRA|KPI layout (no Role column)
                if len(cells) < 6:
                    continue
                role_name = ""
                kra, kpi, unit, comparator, target, frequency = cells[0:6]
                sensitive = cells[6] if len(cells) > 6 else "no"
                capture_type = cells[7] if len(cells) > 7 else "Value"
                event_time_points = cells[8] if len(cells) > 8 else ""
                non_working_day_policy = cells[9] if len(cells) > 9 else "Skip"
                asset_location_scoped = cells[10] if len(cells) > 10 else "none"
                evidence_required = cells[11] if len(cells) > 11 else "no"
                source = "role_manual"

            rows.append(
                {
                    "role": role_name,
                    "source": source,
                    "kra": kra,
                    "kpi": kpi,
                    "unit": unit,
                    "comparator": comparator,
                    "target": target,
                    "frequency": frequency,
                    "sensitive": sensitive,
                    "capture_type": capture_type,
                    "event_time_points": event_time_points,
                    "non_working_day_policy": non_working_day_policy,
                    "asset_location_scoped": asset_location_scoped,
                    "evidence_required": evidence_required,
                }
            )
        return rows

    @staticmethod
    def _should_skip_seed_row(row: dict) -> bool:
        for field in ("comparator", "target", "frequency", "unit"):
            value = row.get(field, "").strip().lower()
            if not value:
                return True
            if any(pattern in value for pattern in PLACEHOLDER_PATTERNS):
                return True
        return False

    @staticmethod
    def _parse_target(raw: str) -> Decimal:
        cleaned = raw.replace("%", "").replace("±", "").strip()
        match = re.search(r"[-+]?\d+(?:\.\d+)?", cleaned)
        if not match:
            raise ValueError(f"Cannot parse target: {raw}")
        return Decimal(match.group())

    @staticmethod
    def _normalize_frequency(raw: str) -> str:
        value = raw.strip().lower()
        # "annual (twice yearly)" → annual
        if "(" in value:
            value = value.split("(", 1)[0].strip()
        value = value.replace(" ", "_")
        return FREQUENCY_ALIASES.get(value, value)

    @staticmethod
    def _normalize_unit(raw: str) -> str:
        value = raw.strip().lower()
        if value in ("%", "percent", "percentage"):
            return "percent"
        if value in ("hours", "hour"):
            return "hours"
        if not value or value in ("n/a", "_n/a_"):
            return "count"
        return value.replace(" ", "_")

    @staticmethod
    def _parse_non_working_day_policy(raw: str) -> str:
        value = raw.strip().lower()
        if "shift forward" in value:
            return NonWorkingDayPolicy.SHIFT_FORWARD.value
        if "shift backward" in value:
            return NonWorkingDayPolicy.SHIFT_BACKWARD.value
        # SME: "Not Applicable on non-working days" → Skip (no compliance cycle that day)
        return NonWorkingDayPolicy.SKIP.value
