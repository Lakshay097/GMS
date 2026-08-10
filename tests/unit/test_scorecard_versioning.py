"""
Scorecard versioning test — PRS §29.

Tests that:
1. Regenerating a Scorecard for the same period produces a new version
2. The old version is retained and marked superseded
3. No code path attempts to mutate the old row (beyond superseded_by_id pointer)

Business rules enforced:
  R-18/BR-14/C6   Scorecards are GENERATED, never updated or deleted.
"""
# Force memory queue to avoid boto3 dependency - must be before other imports
import os
os.environ["QUEUE_PROVIDER"] = "memory"

import pytest
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from modules.performance_scorecards.services.scorecard_service import ScorecardService
from shared.platform_models import Scorecard, ScorecardSubjectType, RagStatus


@pytest.mark.asyncio
class TestScorecardVersioning:
    """
    Test scorecard versioning behavior per PRS §29 and R-18/BR-14/C6.
    """

    async def test_regeneration_creates_new_version(
        self,
        db: AsyncSession,
        school,
        department,
        user,
    ):
        """
        Test that regenerating a scorecard for the same period produces a new version.
        
        Given:
          - A scorecard v1 exists for a user and cycle
        When:
          - Generate another scorecard for the same user and cycle
        Then:
          - A new scorecard v2 is created
          - v1 is retained with superseded_by_id pointing to v2
          - v2 has superseded_by_id = NULL (is the current version)
        """
        # Arrange
        cycle_start = date(2026, 1, 1)
        cycle_end = date(2026, 3, 31)
        
        service = ScorecardService(db)
        
        # Generate v1
        v1 = await service.generate(
            subject_type=ScorecardSubjectType.USER,
            subject_id=user.id,
            cycle_start=cycle_start,
            cycle_end=cycle_end,
        )
        await db.commit()
        
        # Assert v1 properties
        assert v1.version == 1
        assert v1.superseded_by_id is None
        
        # Act - Generate v2 for the same cycle
        v2 = await service.generate(
            subject_type=ScorecardSubjectType.USER,
            subject_id=user.id,
            cycle_start=cycle_start,
            cycle_end=cycle_end,
        )
        await db.commit()
        
        # Assert v2 properties
        assert v2.version == 2
        assert v2.superseded_by_id is None  # v2 is current
        assert v2.id != v1.id
        
        # Re-fetch v1 to verify it was superseded
        await db.refresh(v1)
        assert v1.superseded_by_id == v2.id
        
        # Verify both versions exist in database
        versions = await service.list_versions(
            subject_type=ScorecardSubjectType.USER,
            subject_id=user.id,
            cycle_start=cycle_start,
            cycle_end=cycle_end,
        )
        assert len(versions) == 2
        assert versions[0].version == 1
        assert versions[1].version == 2
        assert versions[0].superseded_by_id == versions[1].id
        assert versions[1].superseded_by_id is None

    async def test_third_generation_creates_v3(
        self,
        db: AsyncSession,
        school,
        department,
        user,
    ):
        """
        Test that a third generation creates v3, and v2 becomes superseded.
        
        This validates the versioning chain: v1 -> v2 -> v3
        """
        cycle_start = date(2026, 4, 1)
        cycle_end = date(2026, 6, 30)
        
        service = ScorecardService(db)
        
        # Generate v1
        v1 = await service.generate(
            subject_type=ScorecardSubjectType.USER,
            subject_id=user.id,
            cycle_start=cycle_start,
            cycle_end=cycle_end,
        )
        await db.commit()
        
        # Generate v2
        v2 = await service.generate(
            subject_type=ScorecardSubjectType.USER,
            subject_id=user.id,
            cycle_start=cycle_start,
            cycle_end=cycle_end,
        )
        await db.commit()
        
        # Generate v3
        v3 = await service.generate(
            subject_type=ScorecardSubjectType.USER,
            subject_id=user.id,
            cycle_start=cycle_start,
            cycle_end=cycle_end,
        )
        await db.commit()
        
        # Refresh all
        await db.refresh(v1)
        await db.refresh(v2)
        
        # Assert version chain
        assert v1.version == 1
        assert v2.version == 2
        assert v3.version == 3
        
        # v1 superseded by v2, v2 superseded by v3, v3 is current
        assert v1.superseded_by_id == v2.id
        assert v2.superseded_by_id == v3.id
        assert v3.superseded_by_id is None
        
        # Verify all three versions exist
        versions = await service.list_versions(
            subject_type=ScorecardSubjectType.USER,
            subject_id=user.id,
            cycle_start=cycle_start,
            cycle_end=cycle_end,
        )
        assert len(versions) == 3
        assert [v.version for v in versions] == [1, 2, 3]

    async def test_old_version_metrics_unchanged(
        self,
        db: AsyncSession,
        school,
        department,
        user,
    ):
        """
        Test that when a new version is generated, the old version's metrics
        are not mutated (only superseded_by_id changes).
        
        This validates R-18/BR-14/C6: no UPDATE on metric columns.
        """
        cycle_start = date(2026, 7, 1)
        cycle_end = date(2026, 9, 30)
        
        service = ScorecardService(db)
        
        # Generate v1
        v1 = await service.generate(
            subject_type=ScorecardSubjectType.USER,
            subject_id=user.id,
            cycle_start=cycle_start,
            cycle_end=cycle_end,
        )
        await db.commit()
        
        # Capture v1 metrics
        original_metrics = {
            "rag_status": v1.rag_status,
            "pct_kpis_met": v1.pct_kpis_met,
            "pct_tasks_on_time": v1.pct_tasks_on_time,
            "open_discrepancy_count": v1.open_discrepancy_count,
            "kpi_breakdown": v1.kpi_breakdown,
        }
        
        # Generate v2
        v2 = await service.generate(
            subject_type=ScorecardSubjectType.USER,
            subject_id=user.id,
            cycle_start=cycle_start,
            cycle_end=cycle_end,
        )
        await db.commit()
        
        # Refresh v1
        await db.refresh(v1)
        
        # Assert v1 metrics unchanged (only superseded_by_id changed)
        assert v1.rag_status == original_metrics["rag_status"]
        assert v1.pct_kpis_met == original_metrics["pct_kpis_met"]
        assert v1.pct_tasks_on_time == original_metrics["pct_tasks_on_time"]
        assert v1.open_discrepancy_count == original_metrics["open_discrepancy_count"]
        assert v1.kpi_breakdown == original_metrics["kpi_breakdown"]
        
        # Only superseded_by_id changed
        assert v1.superseded_by_id == v2.id

    async def test_different_cycles_create_independent_versions(
        self,
        db: AsyncSession,
        school,
        department,
        user,
    ):
        """
        Test that scorecards for different cycles are independent.
        
        Each cycle should start at version 1, not continue from previous cycles.
        """
        service = ScorecardService(db)
        
        # Cycle 1
        cycle1_start = date(2026, 1, 1)
        cycle1_end = date(2026, 3, 31)
        
        v1_cycle1 = await service.generate(
            subject_type=ScorecardSubjectType.USER,
            subject_id=user.id,
            cycle_start=cycle1_start,
            cycle_end=cycle1_end,
        )
        await db.commit()
        
        # Cycle 2
        cycle2_start = date(2026, 4, 1)
        cycle2_end = date(2026, 6, 30)
        
        v1_cycle2 = await service.generate(
            subject_type=ScorecardSubjectType.USER,
            subject_id=user.id,
            cycle_start=cycle2_start,
            cycle_end=cycle2_end,
        )
        await db.commit()
        
        # Both should be version 1 (independent cycles)
        assert v1_cycle1.version == 1
        assert v1_cycle2.version == 1
        assert v1_cycle1.superseded_by_id is None
        assert v1_cycle2.superseded_by_id is None

    async def test_department_level_scorecard_versioning(
        self,
        db: AsyncSession,
        school,
        department,
    ):
        """
        Test that department-level scorecards also version correctly.
        """
        cycle_start = date(2026, 1, 1)
        cycle_end = date(2026, 3, 31)
        
        service = ScorecardService(db)
        
        # Generate v1 for department
        v1 = await service.generate(
            subject_type=ScorecardSubjectType.DEPARTMENT,
            subject_id=department.id,
            cycle_start=cycle_start,
            cycle_end=cycle_end,
        )
        await db.commit()
        
        assert v1.version == 1
        assert v1.superseded_by_id is None
        
        # Generate v2
        v2 = await service.generate(
            subject_type=ScorecardSubjectType.DEPARTMENT,
            subject_id=department.id,
            cycle_start=cycle_start,
            cycle_end=cycle_end,
        )
        await db.commit()
        
        await db.refresh(v1)
        
        assert v2.version == 2
        assert v2.superseded_by_id is None
        assert v1.superseded_by_id == v2.id

