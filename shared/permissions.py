"""
Permission matrix implementation per PRS §12.
Implements the full permission matrix with role-based access control.
Every request re-evaluates permissions at execution time per R-48.
"""
from typing import Set, List, Optional, Dict, Any
from enum import Enum
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from shared.models import Permission, UserRole, FieldPermission
from shared.errors import AuthorizationError


# Role hierarchy per the user-management spec §4. A role may only manage
# (create/assign/edit) roles STRICTLY BELOW it in this ordering — never its
# own level or above. Used by user-management routes to prevent privilege
# escalation (e.g. a dept_head assigning admin).
ROLE_HIERARCHY: Dict[str, List[str]] = {
    "superadmin": ["admin", "dept_head", "auditor", "verifier", "checker", "viewer"],
    "admin": ["dept_head", "auditor", "verifier", "checker", "viewer"],
    "dept_head": ["auditor", "verifier", "checker", "viewer"],
    "auditor": [],
    "verifier": [],
    "checker": [],
    "viewer": [],
}


def can_manage_role(actor_roles: List[str], target_role: str) -> bool:
    """True if ANY of the actor's roles may assign the target role."""
    target = (target_role or "").lower()
    for role in actor_roles:
        subordinate = ROLE_HIERARCHY.get((role or "").lower(), [])
        if target in subordinate:
            return True
    return False


class Module(str, Enum):
    """Module names per PRS §12 Permission Matrix."""
    SCHOOL = "school"
    DEPARTMENT = "department"
    GLOBAL_KPI_LIBRARY = "global_kpi_library"
    KPI_ASSIGNMENT = "kpi_assignment"
    OBSERVATION = "observation"
    AUDIT = "audit"
    DISCREPANCY = "discrepancy"
    TASK = "task"
    ESCALATION = "escalation"
    PERFORMANCE_REVIEW = "performance_review"
    SCORECARD = "scorecard"
    USER_MANAGEMENT = "user_management"
    EXPORT = "export"
    AUDIT_LOG = "audit_log"
    GLOBAL_CONFIGURATION = "global_configuration"
    ASSET = "asset"
    HOLIDAY_CALENDAR = "holiday_calendar"
    DUPLICATE_OVERRIDE = "duplicate_override"
    REOPEN_REQUEST = "reopen_request"
    # §30-31 Dashboards & Report Catalogue
    DASHBOARD = "dashboard"
    REPORT = "report"
    # §33 Global Search
    SEARCH = "search"


class Action(str, Enum):
    """Action names per PRS §12 Permission Matrix."""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    VERIFY = "verify"
    RAISE = "raise"
    INVESTIGATE = "investigate"
    RESOLVE = "resolve"
    APPROVE = "approve"
    ASSIGN = "assign"
    COMPLETE = "complete"
    CONFIGURE = "configure"
    GENERATE = "generate"
    EXPORT = "export"
    MANAGE = "manage"
    VIEW = "view"
    RETIRE = "retire"
    REACTIVATE = "reactivate"
    OVERRIDE = "override"
    REQUEST = "request"


class ScopeConstraint(str, Enum):
    """Scope constraints per PRS §12."""
    SCHOOL = "school"  # Scoped to user's school
    DEPARTMENT = "department"  # Scoped to user's department
    OWN = "own"  # Only own records
    GRANTED = "granted"  # Only explicitly granted schools (Viewer)
    CATEGORY_DEPENDENT = "category_dependent"  # Depends on category configuration
    GLOBAL = "global"  # No scope restriction


class PermissionMatrix:
    """
    Permission matrix implementation per PRS §12.
    Stores and checks permissions against the canonical matrix.
    """
    
    # Hard-coded permission matrix from PRS §12 for initial load
    # Format: (module, action, role, scope_constraint, is_allowed)
    # Role values must match the lowercase database enum values
    INITIAL_PERMISSIONS = [
        # School Management
        (Module.SCHOOL, Action.CREATE, UserRole.SUPERADMIN, ScopeConstraint.GLOBAL, True),
        (Module.SCHOOL, Action.CREATE, UserRole.ADMIN, ScopeConstraint.SCHOOL, False),
        (Module.SCHOOL, Action.CREATE, UserRole.CHECKER, ScopeConstraint.SCHOOL, False),
        (Module.SCHOOL, Action.CREATE, UserRole.AUDITOR, ScopeConstraint.SCHOOL, False),
        (Module.SCHOOL, Action.CREATE, UserRole.VIEWER, ScopeConstraint.SCHOOL, False),
        
        # Department Management
        (Module.DEPARTMENT, Action.CREATE, UserRole.SUPERADMIN, ScopeConstraint.GLOBAL, True),
        (Module.DEPARTMENT, Action.CREATE, UserRole.ADMIN, ScopeConstraint.SCHOOL, True),
        (Module.DEPARTMENT, Action.CREATE, UserRole.CHECKER, ScopeConstraint.SCHOOL, False),
        (Module.DEPARTMENT, Action.CREATE, UserRole.AUDITOR, ScopeConstraint.SCHOOL, False),
        (Module.DEPARTMENT, Action.CREATE, UserRole.VIEWER, ScopeConstraint.SCHOOL, False),
        
        # Global KPI Library
        (Module.GLOBAL_KPI_LIBRARY, Action.MANAGE, UserRole.SUPERADMIN, ScopeConstraint.GLOBAL, True),
        (Module.GLOBAL_KPI_LIBRARY, Action.MANAGE, UserRole.ADMIN, ScopeConstraint.SCHOOL, False),
        (Module.GLOBAL_KPI_LIBRARY, Action.MANAGE, UserRole.CHECKER, ScopeConstraint.SCHOOL, False),
        (Module.GLOBAL_KPI_LIBRARY, Action.MANAGE, UserRole.AUDITOR, ScopeConstraint.SCHOOL, False),
        (Module.GLOBAL_KPI_LIBRARY, Action.MANAGE, UserRole.VIEWER, ScopeConstraint.SCHOOL, False),
        # All roles can READ the global KPI library (reference data)
        (Module.GLOBAL_KPI_LIBRARY, Action.READ, UserRole.SUPERADMIN, ScopeConstraint.GLOBAL, True),
        (Module.GLOBAL_KPI_LIBRARY, Action.READ, UserRole.ADMIN, ScopeConstraint.SCHOOL, True),
        (Module.GLOBAL_KPI_LIBRARY, Action.READ, UserRole.CHECKER, ScopeConstraint.SCHOOL, True),
        (Module.GLOBAL_KPI_LIBRARY, Action.READ, UserRole.AUDITOR, ScopeConstraint.SCHOOL, True),
        (Module.GLOBAL_KPI_LIBRARY, Action.READ, UserRole.VIEWER, ScopeConstraint.GRANTED, True),
        
        # KPI Assignment
        (Module.KPI_ASSIGNMENT, Action.ASSIGN, UserRole.SUPERADMIN, ScopeConstraint.GLOBAL, True),
        (Module.KPI_ASSIGNMENT, Action.ASSIGN, UserRole.ADMIN, ScopeConstraint.SCHOOL, True),
        (Module.KPI_ASSIGNMENT, Action.ASSIGN, UserRole.CHECKER, ScopeConstraint.SCHOOL, False),
        (Module.KPI_ASSIGNMENT, Action.ASSIGN, UserRole.AUDITOR, ScopeConstraint.SCHOOL, False),
        (Module.KPI_ASSIGNMENT, Action.ASSIGN, UserRole.VIEWER, ScopeConstraint.SCHOOL, False),
        
        # Observation Capture
        (Module.OBSERVATION, Action.CREATE, UserRole.SUPERADMIN, ScopeConstraint.GLOBAL, True),
        (Module.OBSERVATION, Action.CREATE, UserRole.ADMIN, ScopeConstraint.SCHOOL, True),
        (Module.OBSERVATION, Action.CREATE, UserRole.CHECKER, ScopeConstraint.SCHOOL, True),
        (Module.OBSERVATION, Action.CREATE, UserRole.AUDITOR, ScopeConstraint.SCHOOL, False),
        (Module.OBSERVATION, Action.CREATE, UserRole.VIEWER, ScopeConstraint.SCHOOL, False),
        
        # Observation Update (R-24/BR-12/C5): Auditors never edit Observations —
        # they may only Verify or raise a Discrepancy.
        (Module.OBSERVATION, Action.UPDATE, UserRole.SUPERADMIN, ScopeConstraint.GLOBAL, True),
        (Module.OBSERVATION, Action.UPDATE, UserRole.ADMIN, ScopeConstraint.SCHOOL, True),
        (Module.OBSERVATION, Action.UPDATE, UserRole.CHECKER, ScopeConstraint.OWN, True),
        (Module.OBSERVATION, Action.UPDATE, UserRole.AUDITOR, ScopeConstraint.SCHOOL, False),
        (Module.OBSERVATION, Action.UPDATE, UserRole.VIEWER, ScopeConstraint.SCHOOL, False),
        
        # Audit Verification
        (Module.AUDIT, Action.VERIFY, UserRole.SUPERADMIN, ScopeConstraint.GLOBAL, False),
        (Module.AUDIT, Action.VERIFY, UserRole.ADMIN, ScopeConstraint.SCHOOL, False),
        (Module.AUDIT, Action.VERIFY, UserRole.CHECKER, ScopeConstraint.SCHOOL, False),
        (Module.AUDIT, Action.VERIFY, UserRole.AUDITOR, ScopeConstraint.SCHOOL, True),
        (Module.AUDIT, Action.VERIFY, UserRole.VIEWER, ScopeConstraint.SCHOOL, False),
        
        # Discrepancy Management
        (Module.DISCREPANCY, Action.RAISE, UserRole.SUPERADMIN, ScopeConstraint.GLOBAL, True),
        (Module.DISCREPANCY, Action.RAISE, UserRole.ADMIN, ScopeConstraint.SCHOOL, True),
        (Module.DISCREPANCY, Action.RAISE, UserRole.CHECKER, ScopeConstraint.SCHOOL, False),
        (Module.DISCREPANCY, Action.RAISE, UserRole.AUDITOR, ScopeConstraint.SCHOOL, True),
        (Module.DISCREPANCY, Action.RAISE, UserRole.VIEWER, ScopeConstraint.SCHOOL, False),
        
        (Module.DISCREPANCY, Action.INVESTIGATE, UserRole.SUPERADMIN, ScopeConstraint.GLOBAL, True),
        (Module.DISCREPANCY, Action.INVESTIGATE, UserRole.ADMIN, ScopeConstraint.SCHOOL, True),
        (Module.DISCREPANCY, Action.INVESTIGATE, UserRole.CHECKER, ScopeConstraint.SCHOOL, False),
        (Module.DISCREPANCY, Action.INVESTIGATE, UserRole.AUDITOR, ScopeConstraint.SCHOOL, False),
        (Module.DISCREPANCY, Action.INVESTIGATE, UserRole.VIEWER, ScopeConstraint.SCHOOL, False),
        
        (Module.DISCREPANCY, Action.APPROVE, UserRole.SUPERADMIN, ScopeConstraint.GLOBAL, True),
        (Module.DISCREPANCY, Action.APPROVE, UserRole.ADMIN, ScopeConstraint.SCHOOL, True),
        (Module.DISCREPANCY, Action.APPROVE, UserRole.CHECKER, ScopeConstraint.SCHOOL, False),
        (Module.DISCREPANCY, Action.APPROVE, UserRole.AUDITOR, ScopeConstraint.SCHOOL, False),
        (Module.DISCREPANCY, Action.APPROVE, UserRole.VIEWER, ScopeConstraint.SCHOOL, False),
        
        # Task Management
        (Module.TASK, Action.ASSIGN, UserRole.SUPERADMIN, ScopeConstraint.GLOBAL, True),
        (Module.TASK, Action.ASSIGN, UserRole.ADMIN, ScopeConstraint.SCHOOL, True),
        (Module.TASK, Action.ASSIGN, UserRole.CHECKER, ScopeConstraint.SCHOOL, True),  # peer if allowed
        (Module.TASK, Action.ASSIGN, UserRole.AUDITOR, ScopeConstraint.SCHOOL, False),
        (Module.TASK, Action.ASSIGN, UserRole.VIEWER, ScopeConstraint.SCHOOL, False),
        
        (Module.TASK, Action.COMPLETE, UserRole.SUPERADMIN, ScopeConstraint.GLOBAL, True),
        (Module.TASK, Action.COMPLETE, UserRole.ADMIN, ScopeConstraint.SCHOOL, True),
        (Module.TASK, Action.COMPLETE, UserRole.CHECKER, ScopeConstraint.SCHOOL, True),  # as owner
        (Module.TASK, Action.COMPLETE, UserRole.AUDITOR, ScopeConstraint.SCHOOL, False),
        (Module.TASK, Action.COMPLETE, UserRole.VIEWER, ScopeConstraint.SCHOOL, False),
        
        (Module.TASK, Action.APPROVE, UserRole.SUPERADMIN, ScopeConstraint.GLOBAL, True),
        (Module.TASK, Action.APPROVE, UserRole.ADMIN, ScopeConstraint.SCHOOL, True),
        (Module.TASK, Action.APPROVE, UserRole.CHECKER, ScopeConstraint.SCHOOL, False),
        (Module.TASK, Action.APPROVE, UserRole.AUDITOR, ScopeConstraint.SCHOOL, False),
        (Module.TASK, Action.APPROVE, UserRole.VIEWER, ScopeConstraint.SCHOOL, False),
        
        # Escalation Configuration
        (Module.ESCALATION, Action.CONFIGURE, UserRole.SUPERADMIN, ScopeConstraint.GLOBAL, True),
        (Module.ESCALATION, Action.CONFIGURE, UserRole.ADMIN, ScopeConstraint.SCHOOL, True),
        (Module.ESCALATION, Action.CONFIGURE, UserRole.CHECKER, ScopeConstraint.SCHOOL, False),
        (Module.ESCALATION, Action.CONFIGURE, UserRole.AUDITOR, ScopeConstraint.SCHOOL, False),
        (Module.ESCALATION, Action.CONFIGURE, UserRole.VIEWER, ScopeConstraint.SCHOOL, False),
        
        # Scorecard
        (Module.SCORECARD, Action.VIEW, UserRole.SUPERADMIN, ScopeConstraint.GLOBAL, True),
        (Module.SCORECARD, Action.VIEW, UserRole.ADMIN, ScopeConstraint.SCHOOL, True),
        (Module.SCORECARD, Action.VIEW, UserRole.CHECKER, ScopeConstraint.OWN, True),
        (Module.SCORECARD, Action.VIEW, UserRole.AUDITOR, ScopeConstraint.OWN, True),
        (Module.SCORECARD, Action.VIEW, UserRole.VIEWER, ScopeConstraint.GRANTED, True),
        
        # User Management
        (Module.USER_MANAGEMENT, Action.MANAGE, UserRole.SUPERADMIN, ScopeConstraint.GLOBAL, True),
        (Module.USER_MANAGEMENT, Action.MANAGE, UserRole.ADMIN, ScopeConstraint.SCHOOL, True),
        (Module.USER_MANAGEMENT, Action.MANAGE, UserRole.CHECKER, ScopeConstraint.SCHOOL, False),
        (Module.USER_MANAGEMENT, Action.MANAGE, UserRole.AUDITOR, ScopeConstraint.SCHOOL, False),
        (Module.USER_MANAGEMENT, Action.MANAGE, UserRole.VIEWER, ScopeConstraint.SCHOOL, False),
        
        # Export
        (Module.EXPORT, Action.EXPORT, UserRole.SUPERADMIN, ScopeConstraint.GLOBAL, True),
        (Module.EXPORT, Action.EXPORT, UserRole.ADMIN, ScopeConstraint.SCHOOL, True),
        (Module.EXPORT, Action.EXPORT, UserRole.CHECKER, ScopeConstraint.SCHOOL, False),
        (Module.EXPORT, Action.EXPORT, UserRole.AUDITOR, ScopeConstraint.SCHOOL, True),
        (Module.EXPORT, Action.EXPORT, UserRole.VIEWER, ScopeConstraint.GRANTED, True),
        
        # Audit Log
        (Module.AUDIT_LOG, Action.VIEW, UserRole.SUPERADMIN, ScopeConstraint.GLOBAL, True),
        (Module.AUDIT_LOG, Action.VIEW, UserRole.ADMIN, ScopeConstraint.SCHOOL, True),
        (Module.AUDIT_LOG, Action.VIEW, UserRole.CHECKER, ScopeConstraint.SCHOOL, False),
        (Module.AUDIT_LOG, Action.VIEW, UserRole.AUDITOR, ScopeConstraint.SCHOOL, True),
        (Module.AUDIT_LOG, Action.VIEW, UserRole.VIEWER, ScopeConstraint.SCHOOL, False),
        
        # Global Configuration
        (Module.GLOBAL_CONFIGURATION, Action.MANAGE, UserRole.SUPERADMIN, ScopeConstraint.GLOBAL, True),
        (Module.GLOBAL_CONFIGURATION, Action.MANAGE, UserRole.ADMIN, ScopeConstraint.SCHOOL, False),
        (Module.GLOBAL_CONFIGURATION, Action.MANAGE, UserRole.CHECKER, ScopeConstraint.SCHOOL, False),
        (Module.GLOBAL_CONFIGURATION, Action.MANAGE, UserRole.AUDITOR, ScopeConstraint.SCHOOL, False),
        (Module.GLOBAL_CONFIGURATION, Action.MANAGE, UserRole.VIEWER, ScopeConstraint.SCHOOL, False),
        
        # Asset Management
        (Module.ASSET, Action.RETIRE, UserRole.SUPERADMIN, ScopeConstraint.GLOBAL, True),
        (Module.ASSET, Action.RETIRE, UserRole.ADMIN, ScopeConstraint.SCHOOL, True),
        (Module.ASSET, Action.RETIRE, UserRole.CHECKER, ScopeConstraint.SCHOOL, False),
        (Module.ASSET, Action.RETIRE, UserRole.AUDITOR, ScopeConstraint.SCHOOL, False),
        (Module.ASSET, Action.RETIRE, UserRole.VIEWER, ScopeConstraint.SCHOOL, False),
        
        # Holiday Calendar
        (Module.HOLIDAY_CALENDAR, Action.MANAGE, UserRole.SUPERADMIN, ScopeConstraint.GLOBAL, True),
        (Module.HOLIDAY_CALENDAR, Action.MANAGE, UserRole.ADMIN, ScopeConstraint.SCHOOL, True),
        (Module.HOLIDAY_CALENDAR, Action.MANAGE, UserRole.CHECKER, ScopeConstraint.SCHOOL, False),
        (Module.HOLIDAY_CALENDAR, Action.MANAGE, UserRole.AUDITOR, ScopeConstraint.SCHOOL, False),
        (Module.HOLIDAY_CALENDAR, Action.MANAGE, UserRole.VIEWER, ScopeConstraint.SCHOOL, False),
        
        # Duplicate Override
        (Module.DUPLICATE_OVERRIDE, Action.OVERRIDE, UserRole.SUPERADMIN, ScopeConstraint.GLOBAL, True),
        (Module.DUPLICATE_OVERRIDE, Action.OVERRIDE, UserRole.ADMIN, ScopeConstraint.SCHOOL, True),
        (Module.DUPLICATE_OVERRIDE, Action.OVERRIDE, UserRole.CHECKER, ScopeConstraint.SCHOOL, False),
        (Module.DUPLICATE_OVERRIDE, Action.OVERRIDE, UserRole.AUDITOR, ScopeConstraint.SCHOOL, False),
        (Module.DUPLICATE_OVERRIDE, Action.OVERRIDE, UserRole.VIEWER, ScopeConstraint.SCHOOL, False),
        
        # Reopen Request
        (Module.REOPEN_REQUEST, Action.REQUEST, UserRole.SUPERADMIN, ScopeConstraint.GLOBAL, True),
        (Module.REOPEN_REQUEST, Action.REQUEST, UserRole.ADMIN, ScopeConstraint.SCHOOL, True),
        (Module.REOPEN_REQUEST, Action.REQUEST, UserRole.CHECKER, ScopeConstraint.OWN, True),
        (Module.REOPEN_REQUEST, Action.REQUEST, UserRole.AUDITOR, ScopeConstraint.SCHOOL, False),
        (Module.REOPEN_REQUEST, Action.REQUEST, UserRole.VIEWER, ScopeConstraint.SCHOOL, False),
        
        (Module.REOPEN_REQUEST, Action.APPROVE, UserRole.SUPERADMIN, ScopeConstraint.GLOBAL, True),
        (Module.REOPEN_REQUEST, Action.APPROVE, UserRole.ADMIN, ScopeConstraint.SCHOOL, True),
        (Module.REOPEN_REQUEST, Action.APPROVE, UserRole.CHECKER, ScopeConstraint.SCHOOL, False),
        (Module.REOPEN_REQUEST, Action.APPROVE, UserRole.AUDITOR, ScopeConstraint.SCHOOL, False),
        (Module.REOPEN_REQUEST, Action.APPROVE, UserRole.VIEWER, ScopeConstraint.SCHOOL, False),

        # ── Department Head (dept_head) ────────────────────────────────────────
        # Department-scoped management role per PRS §12: assigns KPIs, captures
        # observations, and manages tasks within their own department.
        # Without these rows every check_permission call raises, making the role
        # completely non-functional.
        (Module.SCHOOL, Action.CREATE, UserRole.DEPT_HEAD, ScopeConstraint.DEPARTMENT, False),
        (Module.DEPARTMENT, Action.CREATE, UserRole.DEPT_HEAD, ScopeConstraint.DEPARTMENT, False),
        (Module.GLOBAL_KPI_LIBRARY, Action.MANAGE, UserRole.DEPT_HEAD, ScopeConstraint.DEPARTMENT, False),
        (Module.GLOBAL_KPI_LIBRARY, Action.READ, UserRole.DEPT_HEAD, ScopeConstraint.DEPARTMENT, True),
        (Module.KPI_ASSIGNMENT, Action.ASSIGN, UserRole.DEPT_HEAD, ScopeConstraint.DEPARTMENT, True),
        (Module.OBSERVATION, Action.CREATE, UserRole.DEPT_HEAD, ScopeConstraint.DEPARTMENT, True),
        (Module.OBSERVATION, Action.UPDATE, UserRole.DEPT_HEAD, ScopeConstraint.DEPARTMENT, True),
        (Module.AUDIT, Action.VERIFY, UserRole.DEPT_HEAD, ScopeConstraint.DEPARTMENT, False),
        (Module.DISCREPANCY, Action.RAISE, UserRole.DEPT_HEAD, ScopeConstraint.DEPARTMENT, False),
        (Module.DISCREPANCY, Action.INVESTIGATE, UserRole.DEPT_HEAD, ScopeConstraint.DEPARTMENT, True),
        (Module.DISCREPANCY, Action.APPROVE, UserRole.DEPT_HEAD, ScopeConstraint.DEPARTMENT, False),
        (Module.TASK, Action.ASSIGN, UserRole.DEPT_HEAD, ScopeConstraint.DEPARTMENT, True),
        (Module.TASK, Action.COMPLETE, UserRole.DEPT_HEAD, ScopeConstraint.OWN, True),
        (Module.TASK, Action.APPROVE, UserRole.DEPT_HEAD, ScopeConstraint.DEPARTMENT, True),
        (Module.ESCALATION, Action.CONFIGURE, UserRole.DEPT_HEAD, ScopeConstraint.DEPARTMENT, False),
        (Module.SCORECARD, Action.VIEW, UserRole.DEPT_HEAD, ScopeConstraint.OWN, True),
        (Module.USER_MANAGEMENT, Action.MANAGE, UserRole.DEPT_HEAD, ScopeConstraint.DEPARTMENT, False),
        (Module.EXPORT, Action.EXPORT, UserRole.DEPT_HEAD, ScopeConstraint.DEPARTMENT, True),
        (Module.AUDIT_LOG, Action.VIEW, UserRole.DEPT_HEAD, ScopeConstraint.DEPARTMENT, False),
        (Module.GLOBAL_CONFIGURATION, Action.MANAGE, UserRole.DEPT_HEAD, ScopeConstraint.DEPARTMENT, False),
        (Module.ASSET, Action.RETIRE, UserRole.DEPT_HEAD, ScopeConstraint.DEPARTMENT, False),
        (Module.HOLIDAY_CALENDAR, Action.MANAGE, UserRole.DEPT_HEAD, ScopeConstraint.DEPARTMENT, False),
        (Module.DUPLICATE_OVERRIDE, Action.OVERRIDE, UserRole.DEPT_HEAD, ScopeConstraint.DEPARTMENT, False),
        (Module.REOPEN_REQUEST, Action.REQUEST, UserRole.DEPT_HEAD, ScopeConstraint.OWN, True),
        (Module.REOPEN_REQUEST, Action.APPROVE, UserRole.DEPT_HEAD, ScopeConstraint.DEPARTMENT, False),
        (Module.DASHBOARD, Action.VIEW, UserRole.DEPT_HEAD, ScopeConstraint.DEPARTMENT, True),
        (Module.REPORT, Action.READ, UserRole.DEPT_HEAD, ScopeConstraint.DEPARTMENT, True),
        (Module.REPORT, Action.EXPORT, UserRole.DEPT_HEAD, ScopeConstraint.DEPARTMENT, True),
        (Module.SEARCH, Action.READ, UserRole.DEPT_HEAD, ScopeConstraint.DEPARTMENT, True),
        (Module.SEARCH, Action.CREATE, UserRole.DEPT_HEAD, ScopeConstraint.DEPARTMENT, True),

        # ── Dashboard (PRS §30-31) ──────────────────────────────────────────────
        # All roles can VIEW dashboards — but scope and widget visibility is role-gated
        # inside the service layer (permission matrix drives widget set, not access).
        (Module.DASHBOARD, Action.VIEW, UserRole.SUPERADMIN, ScopeConstraint.GLOBAL, True),
        (Module.DASHBOARD, Action.VIEW, UserRole.ADMIN, ScopeConstraint.SCHOOL, True),
        (Module.DASHBOARD, Action.VIEW, UserRole.CHECKER, ScopeConstraint.SCHOOL, True),
        (Module.DASHBOARD, Action.VIEW, UserRole.AUDITOR, ScopeConstraint.SCHOOL, True),
        (Module.DASHBOARD, Action.VIEW, UserRole.VIEWER, ScopeConstraint.GRANTED, True),

        # ── Report Catalogue (PRS §50) ─────────────────────────────────────────
        # READ: see the report catalogue and run reports (data scoped by tenant filter).
        (Module.REPORT, Action.READ, UserRole.SUPERADMIN, ScopeConstraint.GLOBAL, True),
        (Module.REPORT, Action.READ, UserRole.ADMIN, ScopeConstraint.SCHOOL, True),
        (Module.REPORT, Action.READ, UserRole.CHECKER, ScopeConstraint.SCHOOL, False),
        (Module.REPORT, Action.READ, UserRole.AUDITOR, ScopeConstraint.SCHOOL, True),
        (Module.REPORT, Action.READ, UserRole.VIEWER, ScopeConstraint.GRANTED, True),

        # EXPORT: generate Excel/CSV/PDF downloads (category-level restrictions
        # enforced in the export service per BR-04/BR-19/R-50).
        (Module.REPORT, Action.EXPORT, UserRole.SUPERADMIN, ScopeConstraint.GLOBAL, True),
        (Module.REPORT, Action.EXPORT, UserRole.ADMIN, ScopeConstraint.SCHOOL, True),
        (Module.REPORT, Action.EXPORT, UserRole.CHECKER, ScopeConstraint.SCHOOL, False),
        (Module.REPORT, Action.EXPORT, UserRole.AUDITOR, ScopeConstraint.SCHOOL, True),
        # Viewer export allowed at module level; per-category overrides can deny it (R-50).
        (Module.REPORT, Action.EXPORT, UserRole.VIEWER, ScopeConstraint.CATEGORY_DEPENDENT, True),

        # ── Global Search (PRS §51 / R-60) ────────────────────────────────────
        # All authenticated roles can search; results are permission-scoped identically
        # to direct module access (enforced inside SearchService.search()).
        (Module.SEARCH, Action.READ, UserRole.SUPERADMIN, ScopeConstraint.GLOBAL, True),
        (Module.SEARCH, Action.READ, UserRole.ADMIN, ScopeConstraint.SCHOOL, True),
        (Module.SEARCH, Action.READ, UserRole.CHECKER, ScopeConstraint.SCHOOL, True),
        (Module.SEARCH, Action.READ, UserRole.AUDITOR, ScopeConstraint.SCHOOL, True),
        (Module.SEARCH, Action.READ, UserRole.VIEWER, ScopeConstraint.GRANTED, True),

        # Saved filters — private by default; only the owner can manage them.
        (Module.SEARCH, Action.CREATE, UserRole.SUPERADMIN, ScopeConstraint.GLOBAL, True),
        (Module.SEARCH, Action.CREATE, UserRole.ADMIN, ScopeConstraint.SCHOOL, True),
        (Module.SEARCH, Action.CREATE, UserRole.CHECKER, ScopeConstraint.SCHOOL, True),
        (Module.SEARCH, Action.CREATE, UserRole.AUDITOR, ScopeConstraint.SCHOOL, True),
        (Module.SEARCH, Action.CREATE, UserRole.VIEWER, ScopeConstraint.GRANTED, True),

        # ── Verifier (§4 of the user-management spec) ─────────────────────────
        # Verification-focused role: verifies submitted KPI entries within their
        # department; read-only elsewhere. Mirrors checker's department scope.
        (Module.SCHOOL, Action.CREATE, UserRole.VERIFIER, ScopeConstraint.DEPARTMENT, False),
        (Module.DEPARTMENT, Action.CREATE, UserRole.VERIFIER, ScopeConstraint.DEPARTMENT, False),
        (Module.GLOBAL_KPI_LIBRARY, Action.MANAGE, UserRole.VERIFIER, ScopeConstraint.DEPARTMENT, False),
        (Module.GLOBAL_KPI_LIBRARY, Action.READ, UserRole.VERIFIER, ScopeConstraint.DEPARTMENT, True),
        (Module.KPI_ASSIGNMENT, Action.ASSIGN, UserRole.VERIFIER, ScopeConstraint.DEPARTMENT, False),
        (Module.OBSERVATION, Action.CREATE, UserRole.VERIFIER, ScopeConstraint.DEPARTMENT, False),
        (Module.OBSERVATION, Action.UPDATE, UserRole.VERIFIER, ScopeConstraint.DEPARTMENT, False),
        (Module.AUDIT, Action.VERIFY, UserRole.VERIFIER, ScopeConstraint.DEPARTMENT, True),
        (Module.DISCREPANCY, Action.RAISE, UserRole.VERIFIER, ScopeConstraint.DEPARTMENT, False),
        (Module.DISCREPANCY, Action.INVESTIGATE, UserRole.VERIFIER, ScopeConstraint.DEPARTMENT, False),
        (Module.DISCREPANCY, Action.APPROVE, UserRole.VERIFIER, ScopeConstraint.DEPARTMENT, False),
        (Module.TASK, Action.ASSIGN, UserRole.VERIFIER, ScopeConstraint.DEPARTMENT, False),
        (Module.TASK, Action.COMPLETE, UserRole.VERIFIER, ScopeConstraint.OWN, True),
        (Module.TASK, Action.APPROVE, UserRole.VERIFIER, ScopeConstraint.DEPARTMENT, False),
        (Module.ESCALATION, Action.CONFIGURE, UserRole.VERIFIER, ScopeConstraint.DEPARTMENT, False),
        (Module.SCORECARD, Action.VIEW, UserRole.VERIFIER, ScopeConstraint.OWN, True),
        (Module.USER_MANAGEMENT, Action.MANAGE, UserRole.VERIFIER, ScopeConstraint.DEPARTMENT, False),
        (Module.EXPORT, Action.EXPORT, UserRole.VERIFIER, ScopeConstraint.DEPARTMENT, True),
        (Module.AUDIT_LOG, Action.VIEW, UserRole.VERIFIER, ScopeConstraint.DEPARTMENT, False),
        (Module.GLOBAL_CONFIGURATION, Action.MANAGE, UserRole.VERIFIER, ScopeConstraint.DEPARTMENT, False),
        (Module.ASSET, Action.RETIRE, UserRole.VERIFIER, ScopeConstraint.DEPARTMENT, False),
        (Module.HOLIDAY_CALENDAR, Action.MANAGE, UserRole.VERIFIER, ScopeConstraint.DEPARTMENT, False),
        (Module.DUPLICATE_OVERRIDE, Action.OVERRIDE, UserRole.VERIFIER, ScopeConstraint.DEPARTMENT, False),
        (Module.REOPEN_REQUEST, Action.REQUEST, UserRole.VERIFIER, ScopeConstraint.OWN, True),
        (Module.REOPEN_REQUEST, Action.APPROVE, UserRole.VERIFIER, ScopeConstraint.DEPARTMENT, False),
        (Module.DASHBOARD, Action.VIEW, UserRole.VERIFIER, ScopeConstraint.DEPARTMENT, True),
        (Module.REPORT, Action.READ, UserRole.VERIFIER, ScopeConstraint.DEPARTMENT, True),
        (Module.REPORT, Action.EXPORT, UserRole.VERIFIER, ScopeConstraint.DEPARTMENT, True),
        (Module.SEARCH, Action.READ, UserRole.VERIFIER, ScopeConstraint.DEPARTMENT, True),
        (Module.SEARCH, Action.CREATE, UserRole.VERIFIER, ScopeConstraint.DEPARTMENT, True),
    ]
    
    @staticmethod
    async def initialize_permissions(db: AsyncSession) -> None:
        """
        Initialize the permission matrix in the database.
        Loads the canonical PRS §12 permission matrix.
        Uses ORM to be portable across PostgreSQL and SQLite (tests).
        """
        from sqlalchemy import select, func

        # Fast path: if permissions already seeded, skip all individual queries.
        count_result = await db.execute(
            select(func.count()).select_from(Permission)
        )
        existing_count = count_result.scalar() or 0
        if existing_count >= len(PermissionMatrix.INITIAL_PERMISSIONS):
            return

        for module, action, role, scope_constraint, is_allowed in PermissionMatrix.INITIAL_PERMISSIONS:
            # Use role.value to get the lowercase enum value
            role_value = role.value if hasattr(role, 'value') else str(role).lower()
            scope_value = scope_constraint.value if scope_constraint else None

            # Check if permission already exists
            existing = await db.execute(
                select(Permission).where(
                    Permission.module == module.value,
                    Permission.action == action.value,
                    Permission.role == role_value
                )
            )
            if existing.scalar_one_or_none():
                continue

            # Create permission using ORM (portable across databases)
            permission = Permission(
                module=module.value,
                action=action.value,
                role=role_value,
                scope_constraint=scope_value,
                is_allowed=is_allowed
            )
            db.add(permission)

        await db.commit()
    
    # ── Capability payload for the frontend (R-48 single source of truth) ────
    # Derives every UI-facing capability flag from the SAME matrix rows that
    # seed the DB and enforce requests, so the frontend can never drift from
    # the backend. Memoized per role-set: role sets are few, and the result
    # rides on the session-cache snapshot (no DB on warm /auth/me hits).
    _capability_cache: Dict[frozenset, dict] = {}

    @staticmethod
    def capabilities_for_roles(user_roles: List[str]) -> dict:
        """Capability payload covering every flag the UI gates on.

        Each ``modules.*`` flag maps to the matrix row(s) that the backend
        route enforcing that feature actually checks, so nav/UI gating can
        never disagree with API enforcement.
        """
        roles = frozenset(r.lower().replace(" ", "_") for r in user_roles if r)
        cached = PermissionMatrix._capability_cache.get(roles)
        if cached is not None:
            return cached

        def granted(module: Module, action: Action) -> bool:
            return any(
                m == module and a == action and allowed
                and role.value == r
                for (m, a, role, _scope, allowed) in PermissionMatrix.INITIAL_PERMISSIONS
                for r in roles
            )

        def granted_any(pairs) -> bool:
            return any(granted(m, a) for (m, a) in pairs)

        # Broadest scope among the user's granted rows:
        # GLOBAL → 'all', SCHOOL/GRANTED → 'school', DEPARTMENT → 'department'.
        scope_rank = {
            ScopeConstraint.GLOBAL: 0,
            ScopeConstraint.SCHOOL: 1,
            ScopeConstraint.GRANTED: 1,
            ScopeConstraint.DEPARTMENT: 2,
            ScopeConstraint.OWN: 3,
        }
        scope_label = {0: "all", 1: "school", 2: "department", 3: "school"}
        granted_rows = [
            (m, a, s)
            for (m, a, role, s, allowed) in PermissionMatrix.INITIAL_PERMISSIONS
            if allowed and role.value in roles
        ]
        scope = scope_label[min((scope_rank.get(s, 1) for (_m, _a, s) in granted_rows), default=1)]

        discrepancy_write = [
            (Module.DISCREPANCY, Action.RAISE),
            (Module.DISCREPANCY, Action.INVESTIGATE),
            (Module.DISCREPANCY, Action.APPROVE),
        ]
        create_grants = [
            (Module.OBSERVATION, Action.CREATE),
            (Module.DISCREPANCY, Action.RAISE),
            (Module.TASK, Action.ASSIGN),
            (Module.DEPARTMENT, Action.CREATE),
            (Module.SCHOOL, Action.CREATE),
            (Module.USER_MANAGEMENT, Action.MANAGE),
            (Module.GLOBAL_KPI_LIBRARY, Action.MANAGE),
            (Module.GLOBAL_CONFIGURATION, Action.MANAGE),
            (Module.ESCALATION, Action.CONFIGURE),
        ]
        edit_grants = [
            (Module.OBSERVATION, Action.UPDATE),
            (Module.DISCREPANCY, Action.INVESTIGATE),
            (Module.USER_MANAGEMENT, Action.MANAGE),
            (Module.GLOBAL_KPI_LIBRARY, Action.MANAGE),
            (Module.GLOBAL_CONFIGURATION, Action.MANAGE),
            (Module.ESCALATION, Action.CONFIGURE),
        ]
        # No DELETE rows exist in the matrix; destructive UI powers track the
        # management grants that guard the deactivate/remove endpoints.
        delete_grants = [
            (Module.USER_MANAGEMENT, Action.MANAGE),
            (Module.GLOBAL_CONFIGURATION, Action.MANAGE),
        ]

        caps = {
            "observation": {
                "create": granted(Module.OBSERVATION, Action.CREATE),  # R-22: Checker/DeptHead only
                "verify": granted(Module.AUDIT, Action.VERIFY),        # Auditor only
            },
            "modules": {
                # KPI Entry exists to capture observations — gate it on CREATE,
                # not on the old everyone-true role literal.
                "kpiEntry": granted(Module.OBSERVATION, Action.CREATE),
                "kpiVerification": granted(Module.AUDIT, Action.VERIFY),
                "escalationRules": granted(Module.ESCALATION, Action.CONFIGURE),
                # ── Users / Schools / Tasks / Audit module flags ──────────
                "users": granted(Module.USER_MANAGEMENT, Action.MANAGE),
                "schools": granted(Module.SCHOOL, Action.CREATE),      # FR-001: SuperAdmin only
                "tasks": granted(Module.TASK, Action.ASSIGN),
                # "audit" gates the Discrepancies page: any discrepancy
                # workflow grant (raise / investigate / approve) shows it.
                "audit": granted_any(discrepancy_write),
                # ── Remaining module flags (kept here so the frontend needs
                #    no role literals of its own — R-48) ───────────────────
                "dashboard": granted(Module.DASHBOARD, Action.VIEW),
                "departments": granted(Module.DEPARTMENT, Action.CREATE),
                # GET /observations is tenant-scoped for every authenticated
                # user; the matrix has no OBSERVATION.READ row by design.
                "observations": True,
                "reports": granted(Module.REPORT, Action.READ),
                "kra": granted(Module.GLOBAL_KPI_LIBRARY, Action.READ),
                "settings": granted(Module.GLOBAL_CONFIGURATION, Action.MANAGE),
                "approvalChains": granted(Module.DISCREPANCY, Action.APPROVE),
                # User-management sub-powers (invite codes, bulk import)
                "invites": granted(Module.USER_MANAGEMENT, Action.MANAGE),
                "bulkImport": granted(Module.USER_MANAGEMENT, Action.MANAGE),
            },
            # Coarse action flags consumed by RoleGuard — unions of the
            # matrix rows granting the corresponding class of action.
            "canView": granted(Module.DASHBOARD, Action.VIEW),
            "canCreate": granted_any(create_grants),
            "canEdit": granted_any(edit_grants),
            "canDelete": granted_any(delete_grants),
            "canExport": granted(Module.EXPORT, Action.EXPORT)
                         or granted(Module.REPORT, Action.EXPORT),
            "scope": scope,
        }
        PermissionMatrix._capability_cache[roles] = caps
        return caps

    @staticmethod
    async def check_permission(
        db: AsyncSession,
        user_roles: List[str],
        module: str,
        action: str,
        scope_constraint: Optional[str] = None
    ) -> bool:
        """
        Check if user has permission for a given module/action.
        Re-evaluates on every request per R-48.
        
        Args:
            db: Database session
            user_roles: List of user roles (supports multi-role per R-08)
            module: Module name
            action: Action name
            scope_constraint: Optional scope constraint to verify
            
        Returns:
            True if allowed, False otherwise
            
        Raises:
            AuthorizationError if permission is explicitly denied
        """
        # Normalize role names to lowercase to match database enum
        normalized_roles = [role.lower() if role else role for role in user_roles]
        
        # Check each role - user may hold multiple roles (R-08)
        for role_str in normalized_roles:
            try:
                # Match to enum for validation
                role = UserRole(role_str) if role_str in [r.value for r in UserRole] else None
            except ValueError:
                continue  # Invalid role, skip
            
            # Query permission using ORM (portable across PostgreSQL and SQLite)
            result = await db.execute(
                select(Permission).where(
                    Permission.module == module,
                    Permission.action == action,
                    Permission.role == role_str
                )
            )
            permission = result.scalar_one_or_none()
            
            if permission:
                is_allowed = permission.is_allowed
                perm_scope_constraint = permission.scope_constraint
                
                # If explicitly denied, try next role (don't raise yet)
                if not is_allowed:
                    continue
                
                # If allowed, check scope constraint if provided
                if perm_scope_constraint and scope_constraint:
                    if perm_scope_constraint != scope_constraint:
                        continue  # Scope doesn't match, try next role
                
                # Permission granted
                return True
        
        # No role grants this permission
        raise AuthorizationError(
            f"No permission for {module}.{action} with roles {user_roles}"
        )
    
    @staticmethod
    async def get_user_permissions(
        db: AsyncSession,
        user_roles: List[str]
    ) -> Dict[str, Dict[str, bool]]:
        """
        Get all permissions for a user's roles.
        Useful for frontend permission display.
        
        Args:
            db: Database session
            user_roles: List of user roles
            
        Returns:
            Dictionary of {module: {action: allowed}}
        """
        from sqlalchemy import text
        
        permissions = {}
        normalized_roles = [role.lower() if role else role for role in user_roles]
        
        for role_str in normalized_roles:
            query = text("""
                SELECT module, action, is_allowed 
                FROM permissions 
                WHERE role = :role
            """)
            
            result = await db.execute(query, {"role": role_str})
            role_permissions = result.fetchall()
            
            for module, action, is_allowed in role_permissions:
                if module not in permissions:
                    permissions[module] = {}
                
                # Only set to True if any role allows it
                if is_allowed:
                    permissions[module][action] = True
        
        return permissions


async def _get_field_permissions_for_roles(
    db: AsyncSession,
    module: str,
    user_roles: List[str],
) -> Dict[str, bool]:
    """
    Fetch all field permissions for a module and user roles in a single query.
    Resolve OR-logic in memory (multi-role: one role granting access is sufficient).
    
    Args:
        db: Database session
        module: Module name (e.g., "kpi_library")
        user_roles: List of user roles (supports multi-role per R-08)
        
    Returns:
        Dict[field_name, is_allowed] for governed fields
    """
    normalized_roles = [role.lower() if role else role for role in user_roles]
    
    # Single query: fetch all permissions for (module, role IN user_roles)
    result = await db.execute(
        select(FieldPermission).where(
            FieldPermission.module == module,
            FieldPermission.role.in_(normalized_roles)
        )
    )
    permissions = result.scalars().all()
    
    # Resolve OR-logic in memory: for each field, if ANY role grants access, allow
    field_permissions: Dict[str, bool] = {}
    for perm in permissions:
        if perm.field_name not in field_permissions:
            field_permissions[perm.field_name] = perm.is_allowed
        else:
            # OR-logic: if any role grants access, set to true
            field_permissions[perm.field_name] = field_permissions[perm.field_name] or perm.is_allowed
    
    return field_permissions


async def check_field_permission(
    db: AsyncSession,
    user_roles: List[str],
    module: str,
    field_name: str,
) -> bool:
    """
    Check if user has permission to edit a specific field.
    Uses shared helper for single-query + in-memory OR-resolution.
    Fail-open: if field not governed, allow.
    
    Args:
        db: Database session
        user_roles: List of user roles (supports multi-role per R-08)
        module: Module name (e.g., "kpi_library")
        field_name: Field name (e.g., "target_value")
        
    Returns:
        True if allowed
        
    Raises:
        AuthorizationError if permission denied
    """
    field_permissions = await _get_field_permissions_for_roles(db, module, user_roles)
    
    # Fail-open: if field not governed, allow
    if field_name not in field_permissions:
        return True
    
    # Return resolved permission
    if field_permissions[field_name]:
        return True
    
    raise AuthorizationError(
        f"No field permission for {module}.{field_name} with roles {user_roles}"
    )
