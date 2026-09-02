"""
Scorecard grants verification test - PRS section 29, R-18/BR-14/C6.

Tests that no application role holds UPDATE/DELETE grants on scorecard rows.
This is enforced at the database level by the migration's REVOKE statements.
NOTE: performance_scorecards module was removed. Skipping entire test.
"""
import pytest
pytest.skip("performance_scorecards module removed", allow_module_level=True)
