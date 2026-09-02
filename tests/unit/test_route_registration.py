"""
Smoke tests for full-app route registration.

Catches the class of error where `from __future__ import annotations` combined
with the dynamic `_register_dash_module` import mechanism causes Pydantic 2.5+
to fail resolving string annotations at route-definition time.  That error
crashes the module import, which cascades to kill every `/api/v1/*` route
(returning 404 for everything).

Run:  pytest tests/unit/test_route_registration.py -v
"""
from __future__ import annotations  # NOTE: This is fine here — the test file
                                      # itself doesn't define FastAPI routes.

import importlib
import sys
import types
from typing import get_type_hints

import pytest


# ── helpers ──────────────────────────────────────────────────────────────────


def _import_app():
    """Import the FastAPI app, forcing a clean state if needed."""
    # Ensure .env is loaded for module-level side effects
    from dotenv import load_dotenv
    load_dotenv()

    from api.main import app
    return app


def _collect_routes(app):
    """Walk all mounted sub-routers and return a flat list of (path, methods, name).
    
    Handles Starlette 1.6.0 / FastAPI's `_IncludedRouter` objects which wrap
    sub-routers from `include_router()`.  The routes live inside
    `original_router.routes` on the `_IncludedRouter`.
    """
    routes = []
    
    def _walk(obj, depth=0):
        if depth > 10:  # prevent infinite recursion
            return
        # _IncludedRouter wraps an APIRouter via original_router
        if type(obj).__name__ == '_IncludedRouter':
            if hasattr(obj, 'original_router'):
                _walk(obj.original_router, depth + 1)
            return
        # Check for a routes attribute (APIRouter, Mount)
        if hasattr(obj, 'routes'):
            for sub in obj.routes:
                _walk(sub, depth + 1)
        # Check if it's an APIRoute / Route with path + methods
        if hasattr(obj, 'path') and hasattr(obj, 'methods') and obj.methods:
            routes.append((obj.path, obj.methods, getattr(obj, 'name', '?')))
    
    for route in app.routes:
        _walk(route)
    
    return routes


# ── Module-level import test ─────────────────────────────────────────────────


class TestAppImportsCleanly:
    """The full app must import without any Pydantic / import errors."""

    def test_app_imports(self):
        """Importing the FastAPI app must not raise."""
        app = _import_app()
        assert app is not None

    def test_all_module_routers_load(self):
        """Every module router registered in main.py must load without error."""
        expected_modules = [
            "modules.observation_capture.api.routes",
            "modules.kra_kpi_library.api.routes",
            "modules.dashboards_reports_search.api.routes",
            "modules.task_management.api.routes",
            "modules.org_management.api.routes",
            "modules.settings_master_data.api.configuration_routes",
            "modules.settings_master_data.api.feature_flags_routes",
            "modules.audit_discrepancy.api.routes",
            "modules.school_dept_user_role.api.schools",
            "modules.school_dept_user_role.api.users",
            "modules.school_dept_user_role.api.departments",
        ]
        for mod_name in expected_modules:
            try:
                mod = importlib.import_module(mod_name)
                assert hasattr(mod, "router"), f"{mod_name} has no 'router' attribute"
            except Exception as exc:
                pytest.fail(f"Failed to import {mod_name}: {exc}")


# ── Route registration tests ────────────────────────────────────────────────


class TestRouteRegistration:
    """Verify that the expected API routes exist and respond correctly."""

    @pytest.fixture(autouse=True)
    def _app(self):
        self.app = _import_app()
        self.routes = _collect_routes(self.app)

    def _paths_for_prefix(self, prefix: str) -> list[tuple]:
        """Return all routes whose path starts with prefix."""
        return [
            (path, methods, name)
            for path, methods, name in self.routes
            if path.startswith(prefix)
        ]

    # -- Observation Capture --

    def test_observation_routes_registered(self):
        obs = self._paths_for_prefix("/observations")
        assert len(obs) >= 5, (
            f"Expected ≥5 observation routes, found {len(obs)}: "
            f"{[p for p, _, _ in obs]}"
        )

    def test_observation_post_exists(self):
        methods_by_path = {}
        for p, m, _ in self.routes:
            methods_by_path.setdefault(p, set()).update(m)
        assert "/observations" in methods_by_path
        assert "POST" in methods_by_path["/observations"]

    def test_observation_get_list_exists(self):
        methods_by_path = {}
        for p, m, _ in self.routes:
            methods_by_path.setdefault(p, set()).update(m)
        assert "/observations" in methods_by_path
        assert "GET" in methods_by_path["/observations"]

    def test_observation_get_by_id_exists(self):
        methods_by_path = {}
        for p, m, _ in self.routes:
            methods_by_path.setdefault(p, set()).update(m)
        assert "/observations/{observation_id}" in methods_by_path
        assert "GET" in methods_by_path["/observations/{observation_id}"]

    def test_observation_submissions_by_date_exists(self):
        methods_by_path = {}
        for p, m, _ in self.routes:
            methods_by_path.setdefault(p, set()).update(m)
        assert "/observations/submissions-by-date" in methods_by_path

    def test_observation_audit_history_exists(self):
        methods_by_path = {}
        for p, m, _ in self.routes:
            methods_by_path.setdefault(p, set()).update(m)
        assert "/observations/{observation_id}/audit-history" in methods_by_path

    def test_observation_verify_exists(self):
        methods_by_path = {}
        for p, m, _ in self.routes:
            methods_by_path.setdefault(p, set()).update(m)
        key = "/observations/{observation_id}/verify"
        assert key in methods_by_path
        assert "POST" in methods_by_path[key]

    def test_observation_reject_exists(self):
        methods_by_path = {}
        for p, m, _ in self.routes:
            methods_by_path.setdefault(p, set()).update(m)
        key = "/observations/{observation_id}/reject"
        assert key in methods_by_path
        assert "POST" in methods_by_path[key]

    # -- KPI --

    def test_kpi_routes_registered(self):
        kpis = self._paths_for_prefix("/kpis")
        assert len(kpis) >= 3, (
            f"Expected ≥3 KPI routes, found {len(kpis)}: "
            f"{[p for p, _, _ in kpis]}"
        )

    # -- Tasks --

    def test_task_routes_registered(self):
        tasks = self._paths_for_prefix("/tasks")
        assert len(tasks) >= 3, (
            f"Expected ≥3 task routes, found {len(tasks)}: "
            f"{[p for p, _, _ in tasks]}"
        )

    def test_task_complete_exists(self):
        methods_by_path = {}
        for p, m, _ in self.routes:
            methods_by_path.setdefault(p, set()).update(m)
        key = "/tasks/{task_id}/complete"
        assert key in methods_by_path
        assert "POST" in methods_by_path[key]

    # -- Dashboard --

    def test_dashboard_route_registered(self):
        methods_by_path = {}
        for p, m, _ in self.routes:
            methods_by_path.setdefault(p, set()).update(m)
        assert "/dashboard" in methods_by_path
        assert "GET" in methods_by_path["/dashboard"]

    # -- Search --

    def test_search_route_registered(self):
        methods_by_path = {}
        for p, m, _ in self.routes:
            methods_by_path.setdefault(p, set()).update(m)
        assert "/search" in methods_by_path
        assert "GET" in methods_by_path["/search"]

    # -- Global summary --

    def test_minimum_total_route_count(self):
        """The app must have at least 30 routes (sanity check against accidental mass-deletion)."""
        assert len(self.routes) >= 30, (
            f"Only {len(self.routes)} routes registered — likely an import error"
        )


# ── Pydantic annotation resolution tests ────────────────────────────────────


class TestPydanticAnnotationResolution:
    """
    Verify that every route handler's type annotations can be resolved by
    Pydantic/FastAPI.  This catches the exact class of bug where
    `from __future__ import annotations` + dynamic module registration
    causes `PydanticUndefinedAnnotation`.

    We simulate what FastAPI does at startup: iterate every route, look at
    the endpoint function, and call `typing.get_type_hints()` on it.
    """

    @pytest.fixture(autouse=True)
    def _app(self):
        self.app = _import_app()
        self.routes = _collect_routes(self.app)

    def test_all_endpoint_annotations_resolve(self):
        """Every endpoint function's type hints must resolve without error."""
        failures = []
        for path, methods, name in self.routes:
            route_obj = None
            for r in self.app.routes:
                if hasattr(r, "routes"):
                    for sub in r.routes:
                        if getattr(sub, "path", None) == path and getattr(sub, "methods", None) == methods:
                            route_obj = sub
                            break
                elif getattr(r, "path", None) == path and getattr(r, "methods", None) == methods:
                    route_obj = r
                    break

            if route_obj is None or not hasattr(route_obj, "endpoint"):
                continue

            endpoint = route_obj.endpoint
            try:
                hints = get_type_hints(endpoint)
                # Verify each hint is an actual type, not a string
                for param_name, hint in hints.items():
                    assert not isinstance(hint, str), (
                        f"Route {methods} {path} ({name}): param '{param_name}' "
                        f"has unresolved string annotation: {hint!r}"
                    )
            except Exception as exc:
                failures.append(f"{methods} {path}: {exc}")

        if failures:
            pytest.fail(
                "Unresolved type annotations found:\n"
                + "\n".join(f"  - {f}" for f in failures)
            )

    def test_observation_route_annotations_resolve(self):
        """Specifically verify observation routes have no forward-ref issues."""
        from modules.observation_capture.api.routes import (
            submit_observation,
            list_observations,
            get_observation,
            get_submissions_by_date,
            get_audit_history,
        )
        for fn in [
            submit_observation,
            list_observations,
            get_observation,
            get_submissions_by_date,
            get_audit_history,
        ]:
            hints = get_type_hints(fn)
            for param, hint in hints.items():
                assert not isinstance(hint, str), (
                    f"{fn.__name__}.{param}: unresolved annotation {hint!r}"
                )


# ── No `from __future__ import annotations` in route files ───────────────────


class TestNoFutureAnnotationsInRouteFiles:
    """
    Route files that define FastAPI endpoints with Pydantic model parameters
    must NOT use `from __future__ import annotations`.  That import converts
    annotations to strings, which Pydantic 2.5 on Python 3.11 (Docker) cannot
    resolve when the module is loaded via `_register_dash_module`.

    If you need to add this import back, you must also ensure that every
    Pydantic model type used as a function parameter is resolvable by Pydantic's
    TypeAdapter at route-definition time.
    """

    ROUTE_FILES = [
        "modules/observation-capture/api/routes.py",
        "modules/kra-kpi-library/api/routes.py",
        "modules/dashboards-reports-search/api/routes.py",
        "modules/task_management/api/routes.py",
        "modules/org_management/api/routes.py",
        "modules/settings_master_data/api/configuration_routes.py",
        "modules/settings_master_data/api/feature_flags_routes.py",
    ]

    @pytest.mark.parametrize("route_file", ROUTE_FILES)
    def test_no_future_annotations(self, route_file: str):
        """Route file must not use `from __future__ import annotations`."""
        try:
            with open(route_file) as f:
                content = f.read()
        except FileNotFoundError:
            pytest.skip(f"{route_file} not found")

        # Check for the import at the top of the file (before any class/function defs)
        lines = content.split("\n")
        for line in lines[:20]:  # Only check first 20 lines (imports section)
            stripped = line.strip()
            if stripped.startswith("from __future__ import annotations"):
                pytest.fail(
                    f"{route_file} uses `from __future__ import annotations`. "
                    f"This causes PydanticUndefinedAnnotation errors in Docker. "
                    f"Remove it — eagerly-resolved annotations are required."
                )
                return
            # Stop checking once we hit a class or function definition
            if stripped.startswith("class ") or stripped.startswith("def ") or stripped.startswith("async def "):
                return


# ── Pydantic model schema validation ────────────────────────────────────────


class TestSchemaImports:
    """Verify that all Pydantic schema classes can be imported and instantiated."""

    def test_observation_schemas_import(self):
        from modules.observation_capture.schemas import (
            ObservationSubmitRequest,
            ObservationResponse,
            ReopenRequest,
            ReopenApprovalRequest,
            RejectRequest,
            VerifyRequest,
        )
        # Verify they're actual Pydantic model classes
        for cls in [
            ObservationSubmitRequest,
            ObservationResponse,
            ReopenRequest,
            ReopenApprovalRequest,
            RejectRequest,
            VerifyRequest,
        ]:
            assert hasattr(cls, "model_validate"), f"{cls.__name__} is not a Pydantic model"
            assert hasattr(cls, "model_fields"), f"{cls.__name__} is not a Pydantic model"

    def test_observation_submit_request_fields(self):
        """ObservationSubmitRequest must have the expected fields."""
        from modules.observation_capture.schemas import ObservationSubmitRequest

        fields = ObservationSubmitRequest.model_fields
        required = {"kpi_id", "kpi_version", "checker_id", "department_id"}
        assert required.issubset(set(fields.keys())), (
            f"Missing required fields: {required - set(fields.keys())}"
        )

    def test_observation_response_fields(self):
        """ObservationResponse must have audit and edit tracking fields."""
        from modules.observation_capture.schemas import ObservationResponse

        fields = set(ObservationResponse.model_fields.keys())
        assert "is_locked" in fields
        assert "evidence_count" in fields
        assert "status" in fields

    def test_kra_kpi_schemas_import(self):
        from modules.kra_kpi_library.schemas import (
            KraCreateRequest,
            KraResponse,
            KpiCreateRequest,
            KpiResponse,
            ObservationSubmitRequest,
        )
        for cls in [KraCreateRequest, KraResponse, KpiCreateRequest, KpiResponse, ObservationSubmitRequest]:
            assert hasattr(cls, "model_validate")

    def test_task_schemas_import(self):
        """Task schemas defined inline in routes.py should be importable."""
        from modules.task_management.api.routes import TaskCreate, TaskOut, TaskCompleteRequest

        for cls in [TaskCreate, TaskOut, TaskCompleteRequest]:
            assert hasattr(cls, "model_validate"), f"{cls.__name__} is not a Pydantic model"

    def test_org_management_schemas_import(self):
        from modules.org_management.schemas import (
            SchoolCreateRequest,
            SchoolResponse,
            DepartmentCreateRequest,
            KpiEntryCreateRequest,
            KpiEntryResponse,
        )
        for cls in [SchoolCreateRequest, SchoolResponse, DepartmentCreateRequest, KpiEntryCreateRequest, KpiEntryResponse]:
            assert hasattr(cls, "model_validate")


# ── Model rebuild / forward ref tests ────────────────────────────────────────


class TestModelRebuild:
    """
    After all schemas are imported, every model must have a valid core schema.
    If a model has unresolved forward references, `__pydantic_core_schema__`
    will be missing.
    """

    def _check_model(self, cls):
        name = cls.__name__
        assert hasattr(cls, "__pydantic_core_schema__"), (
            f"{name} is missing __pydantic_core_schema__ — likely has unresolved forward references"
        )

    def test_observation_schemas_built(self):
        from modules.observation_capture.schemas import (
            ObservationSubmitRequest,
            ObservationResponse,
        )
        self._check_model(ObservationSubmitRequest)
        self._check_model(ObservationResponse)

    def test_kra_kpi_schemas_built(self):
        from modules.kra_kpi_library.schemas import (
            KraCreateRequest,
            KpiCreateRequest,
            KpiResponse,
        )
        for cls in [KraCreateRequest, KpiCreateRequest, KpiResponse]:
            self._check_model(cls)

    def test_task_schemas_built(self):
        from modules.task_management.api.routes import TaskCreate, TaskOut
        self._check_model(TaskCreate)
        self._check_model(TaskOut)

    def test_org_schemas_built(self):
        from modules.org_management.schemas import (
            SchoolCreateRequest,
            KpiEntryCreateRequest,
        )
        self._check_model(SchoolCreateRequest)
        self._check_model(KpiEntryCreateRequest)
