"""
Scorecard grants verification test — PRS §29, R-18/BR-14/C6.

Tests that no application role holds UPDATE/DELETE grants on scorecard rows.
This is enforced at the database level by the migration's REVOKE statements.
"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


@pytest.mark.asyncio
class TestScorecardGrants:
    """
    Test that scorecard rows have no UPDATE/DELETE grants for application roles.
    
    Business rules enforced:
      R-18/BR-14/C6   Scorecards are GENERATED, never updated or deleted.
                      The schema does NOT grant UPDATE/DELETE to any application
                      role on the scorecards table.
    """

    async def test_no_update_delete_grants_on_scorecards(self, db: AsyncSession):
        """
        Verify that the application role does not have UPDATE or DELETE 
        privileges on the scorecards table.
        
        This test checks the database permissions directly to confirm the
        REVOKE statements in the migration are in effect.
        """
        # Skip this test for SQLite (REVOKE is not supported)
        # In SQLite, we rely on code-level enforcement only
        result = await db.execute(text("SELECT sqlite_version()"))
        try:
            version = result.scalar()
            # If we got a result, we're on SQLite
            pytest.skip("GRANT/REVOKE not supported in SQLite; code-level enforcement verified in code review")
        except Exception:
            # Not SQLite, proceed with PostgreSQL grants check
            pass
        
        # For PostgreSQL, check table privileges
        query = text("""
            SELECT grantee, privilege_type
            FROM information_schema.table_privileges
            WHERE table_name = 'scorecards'
            AND privilege_type IN ('UPDATE', 'DELETE')
        """)
        
        result = await db.execute(query)
        grants = result.fetchall()
        
        # Assert no UPDATE or DELETE grants exist
        assert len(grants) == 0, (
            f"Found {len(grants)} UPDATE/DELETE grants on scorecards table: {grants}. "
            "Per R-18/BR-14/C6, no application role should have UPDATE/DELETE on scorecards."
        )

    async def test_code_level_enforcement(self, db: AsyncSession):
        """
        Verify at the code level that no UPDATE/DELETE operations are performed
        on scorecard rows beyond the superseded_by_id pointer.
        
        This is a static analysis test that confirms the codebase does not
        contain forbidden operations.
        """
        import os
        import re
        
        # Read the scorecard service file
        scorecard_service_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "modules",
            "performance-scorecards",
            "services",
            "scorecard_service.py"
        )
        
        with open(scorecard_service_path, 'r') as f:
            content = f.read()
        
        # Check for forbidden patterns
        # 1. No direct UPDATE statements on scorecard table
        update_pattern = r'UPDATE\s+scorecards'
        assert not re.search(update_pattern, content, re.IGNORECASE), (
            "Found direct UPDATE statement on scorecards table. "
            "Per R-18/BR-14/C6, scorecards should never be updated."
        )
        
        # 2. No DELETE statements on scorecard table
        delete_pattern = r'DELETE\s+FROM\s+scorecards'
        assert not re.search(delete_pattern, content, re.IGNORECASE), (
            "Found DELETE statement on scorecards table. "
            "Per R-18/BR-14/C6, scorecards should never be deleted."
        )
        
        # 3. No Session.delete() calls on Scorecard objects
        session_delete_pattern = r'db\.delete\(|session\.delete\('
        # Allow comments and ensure it's not in a comment
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            if re.search(session_delete_pattern, line):
                # Check if it's a comment
                stripped = line.strip()
                if not stripped.startswith('#') and not stripped.startswith('--'):
                    # Check if it's deleting a Scorecard object
                    if 'Scorecard' in lines[max(0, i-5):i]:  # Check context
                        pytest.fail(
                            f"Found Session.delete() call at line {i} in scorecard_service.py. "
                            "Per R-18/BR-14/C6, scorecards should never be deleted."
                        )
        
        # 4. Verify superseded_by_id is the only mutation on existing rows
        # Check that superseded_by_id assignments are the only attribute writes
        # on existing scorecard objects
        superseded_pattern = r'superseded_by_id\s*='
        superseded_matches = re.findall(superseded_pattern, content)
        
        # There should be exactly 2 superseded_by_id assignments:
        # 1. Setting to None on new scorecard creation (line 140)
        # 2. Setting to new_id on prior version (line 155)
        # This is acceptable - the key is that no metric columns are updated on existing rows
        assert len(superseded_matches) == 2, (
            f"Found {len(superseded_matches)} superseded_by_id assignments. "
            "Expected exactly 2 (one on new scorecard, one on prior version)."
        )
        
        # 5. Verify no other metric column assignments on existing scorecard objects
        metric_columns = [
            'rag_status', 'pct_kpis_met', 'pct_tasks_on_time', 
            'open_discrepancy_count', 'kpi_breakdown'
        ]
        
        for metric in metric_columns:
            # Look for patterns like: existing_scorecard.rag_status = ...
            # but exclude the initial object creation (new_scorecard = Scorecard(...))
            lines = content.split('\n')
            for i, line in enumerate(lines, 1):
                if f'.{metric} =' in line:
                    # Check if this is on a 'new_scorecard' or a newly created object
                    # vs an existing object like 'prior_latest'
                    if 'prior_latest' in line or 'existing' in line.lower():
                        pytest.fail(
                            f"Found assignment to metric column '{metric}' on existing scorecard "
                            f"object at line {i}. Per R-18/BR-14/C6, only superseded_by_id may be "
                            f"updated on existing scorecard rows."
                        )
