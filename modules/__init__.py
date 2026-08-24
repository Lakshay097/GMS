"""Business modules package."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _register_dash_module(import_name: str, folder_name: str) -> None:
    """Register hyphenated module folders under dotted import names."""
    if import_name in sys.modules:
        return

    module_path = Path(__file__).parent / folder_name
    if not module_path.is_dir():
        return

    spec = importlib.util.spec_from_file_location(
        import_name,
        module_path / "__init__.py",
        submodule_search_locations=[str(module_path)],
    )
    if spec is None or spec.loader is None:
        return

    module = importlib.util.module_from_spec(spec)
    sys.modules[import_name] = module
    spec.loader.exec_module(module)


_register_dash_module("modules.school_dept_user_role", "school-dept-user-role")
_register_dash_module("modules.kra_kpi_library", "kra-kpi-library")
_register_dash_module("modules.observation_capture", "observation-capture")
_register_dash_module("modules.audit_discrepancy", "audit_discrepancy")
_register_dash_module("modules.performance_scorecards", "performance-scorecards")
_register_dash_module("modules.dashboards_reports_search", "dashboards-reports-search")
_register_dash_module("modules.task_management", "task-management")
