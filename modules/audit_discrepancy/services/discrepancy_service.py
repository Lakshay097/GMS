"""
Discrepancy Service per PRS §25-26.
Implements audit/verification and discrepancy management using the Workflow Engine.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional, List

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from shared.datetime_utils import utc_now
from shared.errors import (
    AuthorizationError,
    BusinessRuleError,
    ValidationError,
    NotFoundError,
)
from shared.platform_models import (
    Discrepancy,
    DiscrepancyApprovalHistory,
    DiscrepancyCategory,
    DiscrepancyApprovalChainConfig,
)
from shared.models import User
from platform_services.workflow_engine.service import (
    WorkflowEngine,
    WorkflowError,
    TransitionResult,
    TransitionDefinition,
    WorkflowDefinitionData,
    ApprovalChainConfig,
    ApprovalLevel,
)
from platform_services.notification_service.service import (
    NotificationPayload,
    NotificationService,
)
from shared.platform_models import NotificationCategory, NotificationChannel


class DiscrepancyService:
    """
    Discrepancy management service per PRS §25-26.
    
    State machine: Raised → Under Investigation → Resolved → Pending Approval (Level 1..N) → Closed
    - Linear state machine with no skipped states
    - Investigation findings required before Resolved
    - Multi-level approval with segregation of duties
    - Approval history tracked as separate rows (not fixed columns)
    """

    def __init__(
        self,
        db: AsyncSession,
        workflow_engine: Optional[WorkflowEngine] = None,
        notification_service: Optional[NotificationService] = None,
        audit_log: Optional[Any] = None,
    ):
        self.db = db
        self.workflow_engine = workflow_engine or WorkflowEngine(db)
        self._notification_service = notification_service or NotificationService(db)
        # Always create an internal audit log using the same session so entries
        # are visible to callers who construct their own AuditLogService(db).
        from platform_services.audit_log_service.service import AuditLogService as _ALS
        self._audit_log = audit_log or _ALS(db)
        self._register_workflow_guards()

    def _register_workflow_guards(self) -> None:
        """Register workflow guards for discrepancy state transitions."""
        # Guards are now enforced manually in service methods for better control
        pass

    def _guard_has_investigation_findings(self, context: dict[str, Any]) -> bool:
        """Guard: Investigation findings required before moving to Resolved."""
        investigation_findings = context.get("investigation_findings")
        return investigation_findings is not None and len(investigation_findings.strip()) > 0

    def _guard_segregation_of_duties(self, context: dict[str, Any]) -> bool:
        """
        Guard: Segregation of duties - approver cannot be investigation owner or prior approver.
        Enforced at each approval level.
        """
        approver_id = context.get("approver_id")
        investigation_owner_id = context.get("investigation_owner_id")
        prior_approvers = context.get("prior_approvers", [])
        
        if approver_id is None:
            return False
        
        # Approver cannot be the investigation owner
        if approver_id == investigation_owner_id:
            return False
        
        # Approver cannot be a prior-level approver
        if approver_id in prior_approvers:
            return False
        
        return True

    async def _guard_all_levels_approved(self, context: dict[str, Any]) -> bool:
        """Guard: All approval levels must be approved before closing."""
        discrepancy_id = context.get("discrepancy_id")
        total_levels = context.get("total_levels", 0)
        
        if total_levels == 0:
            return True
        
        # Count approved levels
        result = await self.db.execute(
            select(DiscrepancyApprovalHistory).where(
                and_(
                    DiscrepancyApprovalHistory.discrepancy_id == discrepancy_id,
                    DiscrepancyApprovalHistory.status == "approved",
                )
            )
        )
        approved_count = len(result.scalars().all())
        
        return approved_count >= total_levels

    async def _ensure_workflow_definition_for_chain(self, chain_version_id: uuid.UUID) -> None:
        """
        Ensure workflow definition matches a specific approval chain version.
        Used for in-flight discrepancies that are bound to a specific chain version.
        """
        chain_config = await self.db.get(DiscrepancyApprovalChainConfig, chain_version_id)
        if chain_config is None:
            raise BusinessRuleError(f"Approval chain version not found: {chain_version_id}")
        
        # Build transitions based on the bound chain's levels
        num_levels = len(chain_config.levels)
        
        # Core linear transitions
        transitions = [
            TransitionDefinition(from_state="raised", to_state="under_investigation"),
            TransitionDefinition(
                from_state="under_investigation",
                to_state="resolved",
            ),
        ]
        
        # Build N-level approval sub-stage
        for level in range(1, num_levels + 1):
            pending_state = f"pending_approval_level_{level}"
            
            if level == 1:
                transitions.append(
                    TransitionDefinition(from_state="resolved", to_state=pending_state)
                )
            else:
                prev_pending = f"pending_approval_level_{level - 1}"
                transitions.append(
                    TransitionDefinition(
                        from_state=prev_pending,
                        to_state=pending_state,
                    )
                )
            
            # Approval and rejection transitions
            if level == num_levels:
                # Final level - can close if approved
                transitions.append(
                    TransitionDefinition(
                        from_state=pending_state,
                        to_state="closed",
                    )
                )
            else:
                # Non-final level - move to next level if approved
                next_pending = f"pending_approval_level_{level + 1}"
                transitions.append(
                    TransitionDefinition(
                        from_state=pending_state,
                        to_state=next_pending,
                    )
                )
            
            # Rejection at any level reopens to under investigation
            transitions.append(
                TransitionDefinition(
                    from_state=pending_state,
                    to_state="under_investigation",
                )
            )
        
        # Create approval chain config for workflow
        approval_levels = [
            ApprovalLevel(
                level=level["level"],
                role_id=str(level.get("role_id", "")),
                auto_escalation_sla_hours=level.get("auto_escalation_sla_hours"),
            )
            for level in chain_config.levels
        ]
        
        approval_chain_config = ApprovalChainConfig(
            chain_version_id=chain_config.chain_version_id,
            levels=approval_levels,
        )
        
        # Register workflow definition with a unique entity type for this chain version
        # This allows different chain versions to have different workflow definitions
        workflow_def = WorkflowDefinitionData(
            entity_type=f"discrepancy_chain_{chain_version_id}",
            initial_state="raised",
            transitions=transitions,
            approval_chain=approval_chain_config,
        )
        
        await self.workflow_engine.register_definition(workflow_def)

    async def ensure_workflow_definition(self) -> None:
        """
        Ensure the discrepancy workflow definition is registered.
        This creates the data-defined state machine for discrepancies.
        Uses the active approval chain to build the workflow definition.
        """
        # Get active approval chain to determine number of levels
        from modules.audit_discrepancy.services.approval_chain_service import ApprovalChainService
        approval_service = ApprovalChainService(self.db, self.workflow_engine)
        active_chain = await approval_service.get_active_approval_chain()
        
        if active_chain is None:
            # Create default single-level approval chain
            default_role_id = uuid.uuid4()
            active_chain = await approval_service.create_approval_chain(
                levels=[{"level": 1, "role_id": str(default_role_id)}],
            )
        
        # Build transitions based on approval chain levels
        num_levels = len(active_chain.levels)
        
        # Core linear transitions
        transitions = [
            TransitionDefinition(from_state="raised", to_state="under_investigation"),
            TransitionDefinition(
                from_state="under_investigation",
                to_state="resolved",
            ),
        ]
        
        # Build N-level approval sub-stage
        for level in range(1, num_levels + 1):
            pending_state = f"pending_approval_level_{level}"
            
            if level == 1:
                transitions.append(
                    TransitionDefinition(from_state="resolved", to_state=pending_state)
                )
            else:
                prev_pending = f"pending_approval_level_{level - 1}"
                transitions.append(
                    TransitionDefinition(
                        from_state=prev_pending,
                        to_state=pending_state,
                    )
                )
            
            # Approval and rejection transitions
            if level == num_levels:
                # Final level - can close if approved
                transitions.append(
                    TransitionDefinition(
                        from_state=pending_state,
                        to_state="closed",
                    )
                )
            else:
                # Non-final level - move to next level if approved
                next_pending = f"pending_approval_level_{level + 1}"
                transitions.append(
                    TransitionDefinition(
                        from_state=pending_state,
                        to_state=next_pending,
                    )
                )
            
            # Rejection at any level reopens to under investigation
            transitions.append(
                TransitionDefinition(
                    from_state=pending_state,
                    to_state="under_investigation",
                )
            )
        
        # Create approval chain config for workflow
        approval_levels = [
            ApprovalLevel(
                level=level["level"],
                role_id=str(level.get("role_id", "")),
                auto_escalation_sla_hours=level.get("auto_escalation_sla_hours"),
            )
            for level in active_chain.levels
        ]
        
        approval_chain_config = ApprovalChainConfig(
            chain_version_id=active_chain.chain_version_id,
            levels=approval_levels,
        )
        
        # Register workflow definition
        workflow_def = WorkflowDefinitionData(
            entity_type="discrepancy",
            initial_state="raised",
            transitions=transitions,
            approval_chain=approval_chain_config,
        )
        
        await self.workflow_engine.register_definition(workflow_def)

    async def raise_discrepancy(
        self,
        *,
        observation_id: uuid.UUID,
        category_id: uuid.UUID,
        school_id: uuid.UUID,
        department_id: Optional[uuid.UUID],
        raised_by_user_id: uuid.UUID,
        description: Optional[str] = None,
    ) -> Discrepancy:
        """
        Raise a discrepancy against an observation.
        PRS §12: Only Auditor and SuperAdmin can raise discrepancies.
        """
        # Enforce role restriction: only Auditor and SuperAdmin can raise
        from shared.models import UserRole
        raiser = await self.db.get(User, raised_by_user_id)
        if raiser is None:
            raise NotFoundError(f"User not found: {raised_by_user_id}")
        raiser_roles = [r.lower() if isinstance(r, str) else r for r in (raiser.roles or [])]
        allowed_roles = {UserRole.AUDITOR.value, UserRole.SUPERADMIN.value}
        if not any(r in allowed_roles for r in raiser_roles):
            raise AuthorizationError(
                f"Only Auditor or SuperAdmin can raise discrepancies, "
                f"but user has roles {raiser_roles}"
            )
        
        # Ensure workflow definition exists
        await self.ensure_workflow_definition()
        
        # Validate category exists
        category = await self.db.get(DiscrepancyCategory, category_id)
        if category is None:
            raise ValidationError(f"Discrepancy category not found: {category_id}")
        
        # Create discrepancy
        discrepancy = Discrepancy(
            id=uuid.uuid4(),
            observation_id=observation_id,
            category_id=category_id,
            school_id=school_id,
            department_id=department_id,
            raised_by_user_id=raised_by_user_id,
            state="raised",
            raised_at=utc_now(),
        )
        
        self.db.add(discrepancy)
        await self.db.commit()
        await self.db.refresh(discrepancy)
        # Write audit log entry for the raise event
        try:
            await self._audit_log.append(
                action="discrepancy_raised",
                entity_type="discrepancy",
                entity_id=discrepancy.id,
                actor_id=raised_by_user_id,
                school_id=school_id,
                department_id=department_id,
                new_values={
                    "observation_id": str(observation_id),
                    "category_id": str(category_id),
                    "state": "raised",
                },
            )
        except Exception:
            pass  # Audit log failure must never block the business operation
        
        # Notify Admin, Department Head, Investigation Owner per PRS §49 Notification Matrix
        # Category 2 (AUDIT_FAILURE) - Email, In-App channels
        # This is a mandatory category that cannot be muted (R-39/C9)
        
        # Notify Admins for the school using portable query logic
        from shared.models import UserRole
        from sqlalchemy import select
        import json
        
        # Use portable query that works on both SQLite and Postgres
        # Get all active users for the school and filter in Python for admin role
        # This avoids JSONB/JSON dialect-specific operators
        from sqlalchemy import func as _func, String as _String
        all_active_users_result = await self.db.execute(
            select(User.id, User.roles).where(
                User.school_id == school_id,
                # Accept both "active" (value) and "ACTIVE" (name) to work on SQLite + Postgres
                _func.upper(_func.cast(User.status, _String)).in_(["ACTIVE"]),
            )
        )
        
        for user_id, user_roles in all_active_users_result:
            # Check if user has admin role (works with both JSON and JSONB)
            # Handle both string (SQLite) and list (Postgres) representations
            if user_roles:
                if isinstance(user_roles, str):
                    # SQLite stores as JSON string
                    try:
                        roles_list = json.loads(user_roles)
                    except json.JSONDecodeError:
                        roles_list = []
                else:
                    # Postgres stores as list
                    roles_list = user_roles
                
                if UserRole.ADMIN.value in roles_list:
                    try:
                        await self._notification_service.dispatch(
                            NotificationPayload(
                                user_id=user_id,
                                category=NotificationCategory.AUDIT_FAILURE,
                                title="Discrepancy Raised",
                                body=f"A new discrepancy has been raised: {description or 'No description'}",
                                channel=NotificationChannel.EMAIL,
                                school_id=school_id,
                                entity_type="discrepancy",
                                entity_id=discrepancy.id,
                            )
                        )
                    except Exception as e:
                        # Log notification error but don't fail the discrepancy creation
                        # This ensures discrepancy creation succeeds even if notification fails
                        # but the failure is visible in logs for production monitoring
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.error(
                            f"Failed to send admin notification for discrepancy {discrepancy.id}: {e}",
                            exc_info=True
                        )
        
        # Notify Department Head if department_id is provided
        if department_id:
            from shared.models import Department
            dept = await self.db.get(Department, department_id)
            if dept and dept.head_user_id:
                try:
                    await self._notification_service.dispatch(
                        NotificationPayload(
                            user_id=dept.head_user_id,
                            category=NotificationCategory.AUDIT_FAILURE,
                            title="Discrepancy Raised in Your Department",
                            body=f"A new discrepancy has been raised in your department: {description or 'No description'}",
                            channel=NotificationChannel.EMAIL,
                            school_id=school_id,
                            entity_type="discrepancy",
                            entity_id=discrepancy.id,
                        )
                    )
                except Exception as e:
                    # Log notification error but don't fail the discrepancy creation
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(
                        f"Failed to send department head notification for discrepancy {discrepancy.id}: {e}",
                        exc_info=True
                    )
        
        return discrepancy

    async def assign_investigation(
        self,
        discrepancy_id: uuid.UUID,
        investigation_owner_id: uuid.UUID,
    ) -> Discrepancy:
        """
        Assign investigation owner and move to Under Investigation state.
        """
        discrepancy = await self.db.get(Discrepancy, discrepancy_id)
        if discrepancy is None:
            raise NotFoundError(f"Discrepancy not found: {discrepancy_id}")
        
        # Validate state transition
        result = await self.workflow_engine.transition(
            entity_type="discrepancy",
            current_state=discrepancy.state,
            target_state="under_investigation",
        )
        
        # Update discrepancy
        discrepancy.investigation_owner_id = investigation_owner_id
        discrepancy.state = result.to_state
        discrepancy.under_investigation_at = utc_now()
        
        await self.db.commit()
        await self.db.refresh(discrepancy)
        
        # Notify the investigation owner per PRS §49 Notification Matrix
        # Category 3 (TASK_ASSIGNMENT) - In-App, Email channels
        try:
            await self._notification_service.dispatch(
                NotificationPayload(
                    user_id=investigation_owner_id,
                    category=NotificationCategory.TASK_ASSIGNMENT.value,
                    title="Discrepancy Investigation Assigned",
                    body="You have been assigned as investigation owner for a discrepancy.",
                    channel=NotificationChannel.EMAIL,
                    school_id=discrepancy.school_id,
                    entity_type="discrepancy",
                    entity_id=discrepancy.id,
                )
            )
        except Exception:
            pass  # Notification failure must never block the business operation

        return discrepancy

    async def submit_investigation_findings(
        self,
        discrepancy_id: uuid.UUID,
        investigation_findings: str,
    ) -> Discrepancy:
        """
        Submit investigation findings and move to Resolved state.
        Investigation findings are required before moving to Resolved.
        """
        discrepancy = await self.db.get(Discrepancy, discrepancy_id)
        if discrepancy is None:
            raise NotFoundError(f"Discrepancy not found: {discrepancy_id}")
        
        # Enforce investigation findings guard manually
        if not self._guard_has_investigation_findings({
            "investigation_findings": investigation_findings,
        }):
            raise WorkflowError("Investigation findings are required before moving to Resolved")
        
        # Validate state transition
        result = await self.workflow_engine.transition(
            entity_type="discrepancy",
            current_state=discrepancy.state,
            target_state="resolved",
        )
        
        # Update discrepancy
        discrepancy.investigation_findings = investigation_findings
        discrepancy.state = result.to_state
        discrepancy.resolved_at = utc_now()
        
        await self.db.commit()
        await self.db.refresh(discrepancy)
        
        return discrepancy

    async def start_approval(
        self,
        discrepancy_id: uuid.UUID,
    ) -> Discrepancy:
        """
        Start approval process by moving to Pending Approval Level 1.
        Binds the discrepancy to the current approval chain version.
        """
        discrepancy = await self.db.get(Discrepancy, discrepancy_id)
        if discrepancy is None:
            raise NotFoundError(f"Discrepancy not found: {discrepancy_id}")
        
        # Get active approval chain
        from modules.audit_discrepancy.services.approval_chain_service import ApprovalChainService
        approval_service = ApprovalChainService(self.db, self.workflow_engine)
        active_chain = await approval_service.get_active_approval_chain()
        if active_chain is None:
            raise BusinessRuleError("No active approval chain configuration")
        
        # Validate state transition
        result = await self.workflow_engine.transition(
            entity_type="discrepancy",
            current_state=discrepancy.state,
            target_state="pending_approval_level_1",
        )
        
        # Bind discrepancy to approval chain version
        discrepancy.bound_chain_version_id = active_chain.chain_version_id
        discrepancy.state = result.to_state
        
        # Create approval history entry for level 1
        approval_history = DiscrepancyApprovalHistory(
            id=uuid.uuid4(),
            discrepancy_id=discrepancy_id,
            level=1,
            assigned_role_id=str(active_chain.levels[0].get("role_id", "")),
            status="pending",
        )
        self.db.add(approval_history)
        
        await self.db.commit()
        await self.db.refresh(discrepancy)
        
        return discrepancy

    async def approve_discrepancy(
        self,
        discrepancy_id: uuid.UUID,
        level: int,
        approver_id: uuid.UUID,
        comments: Optional[str] = None,
    ) -> Discrepancy:
        """
        Approve discrepancy at a specific level.
        Enforces:
        1. Segregation of duties (approver ≠ investigation owner, approver ≠ prior approver)
        2. Role match (approver must have the role or user_id assigned at this level)
        """
        discrepancy = await self.db.get(Discrepancy, discrepancy_id)
        if discrepancy is None:
            raise NotFoundError(f"Discrepancy not found: {discrepancy_id}")
        
        # Get prior approvers for segregation of duties
        result = await self.db.execute(
            select(DiscrepancyApprovalHistory).where(
                and_(
                    DiscrepancyApprovalHistory.discrepancy_id == discrepancy_id,
                    DiscrepancyApprovalHistory.level < level,
                    DiscrepancyApprovalHistory.status == "approved",
                )
            )
        )
        prior_approvers = [
            row.approved_by_user_id for row in result.scalars().all() if row.approved_by_user_id
        ]
        
        # Get total levels and level config from bound chain
        if discrepancy.bound_chain_version_id:
            chain_config = await self.db.get(DiscrepancyApprovalChainConfig, discrepancy.bound_chain_version_id)
            total_levels = len(chain_config.levels) if chain_config else 1
        else:
            chain_config = None
            total_levels = 1
        
        # Enforce segregation of duties guard
        if not self._guard_segregation_of_duties({
            "approver_id": approver_id,
            "investigation_owner_id": discrepancy.investigation_owner_id,
            "prior_approvers": prior_approvers,
        }):
            raise WorkflowError("Segregation of duties violation: approver cannot be investigation owner or prior approver")
        
        # Enforce role/user match at this level
        if chain_config and level <= len(chain_config.levels):
            level_config = chain_config.levels[level - 1]
            assigned_role = level_config.get("role_id")
            assigned_user = level_config.get("user_id")
            
            if assigned_user:
                # User-specific assignment: approver must match exactly
                if str(approver_id) != str(assigned_user):
                    raise WorkflowError(
                        f"Approval denied: level {level} is assigned to a specific user, "
                        f"but approver {approver_id} does not match"
                    )
            elif assigned_role:
                # Role-based assignment: approver must have the required role
                approver = await self.db.get(User, approver_id)
                if approver is None:
                    raise WorkflowError(f"Approver user not found: {approver_id}")
                approver_roles = [r.lower() if isinstance(r, str) else r for r in (approver.roles or [])]
                if assigned_role.lower() not in approver_roles:
                    raise WorkflowError(
                        f"Approval denied: level {level} requires role '{assigned_role}', "
                        f"but approver has roles {approver_roles}"
                    )
        
        # Determine target state
        if level >= total_levels:
            target_state = "closed"
        else:
            target_state = f"pending_approval_level_{level + 1}"
        
        # Validate state transition
        result = await self.workflow_engine.transition(
            entity_type="discrepancy",
            current_state=discrepancy.state,
            target_state=target_state,
        )
        
        # Update or create approval history entry
        approval_history = await self.db.execute(
            select(DiscrepancyApprovalHistory).where(
                and_(
                    DiscrepancyApprovalHistory.discrepancy_id == discrepancy_id,
                    DiscrepancyApprovalHistory.level == level,
                )
            )
        )
        history_entry = approval_history.scalar_one_or_none()
        if history_entry:
            history_entry.approved_by_user_id = approver_id
            history_entry.status = "approved"
            history_entry.comments = comments
            history_entry.approved_at = utc_now()
        else:
            # Create approval history entry for this level if it doesn't exist
            if discrepancy.bound_chain_version_id:
                chain_config = await self.db.get(DiscrepancyApprovalChainConfig, discrepancy.bound_chain_version_id)
                if chain_config and level <= len(chain_config.levels):
                    history_entry = DiscrepancyApprovalHistory(
                        id=uuid.uuid4(),
                        discrepancy_id=discrepancy_id,
                        level=level,
                        assigned_role_id=str(chain_config.levels[level - 1].get("role_id", "")),
                        approved_by_user_id=approver_id,
                        status="approved",
                        comments=comments,
                        approved_at=utc_now(),
                    )
                    self.db.add(history_entry)
        
        # Update discrepancy state
        discrepancy.state = result.to_state
        if result.to_state == "closed":
            discrepancy.closed_at = utc_now()
        
        await self.db.commit()
        await self.db.refresh(discrepancy)
        
        return discrepancy

    async def reject_discrepancy(
        self,
        discrepancy_id: uuid.UUID,
        level: int,
        rejecter_id: uuid.UUID,
        comments: Optional[str] = None,
    ) -> Discrepancy:
        """
        Reject discrepancy at a specific level.
        Rejection reopens to Under Investigation, preserving prior investigation notes.
        Enforces role/user match: rejecter must have the role or user_id assigned at this level.
        """
        discrepancy = await self.db.get(Discrepancy, discrepancy_id)
        if discrepancy is None:
            raise NotFoundError(f"Discrepancy not found: {discrepancy_id}")
        
        # Enforce role/user match at this level
        if discrepancy.bound_chain_version_id:
            chain_config = await self.db.get(DiscrepancyApprovalChainConfig, discrepancy.bound_chain_version_id)
            if chain_config and level <= len(chain_config.levels):
                level_config = chain_config.levels[level - 1]
                assigned_role = level_config.get("role_id")
                assigned_user = level_config.get("user_id")
                
                if assigned_user:
                    if str(rejecter_id) != str(assigned_user):
                        raise WorkflowError(
                            f"Rejection denied: level {level} is assigned to a specific user, "
                            f"but rejecter {rejecter_id} does not match"
                        )
                elif assigned_role:
                    rejecter = await self.db.get(User, rejecter_id)
                    if rejecter is None:
                        raise WorkflowError(f"Rejecter user not found: {rejecter_id}")
                    rejecter_roles = [r.lower() if isinstance(r, str) else r for r in (rejecter.roles or [])]
                    if assigned_role.lower() not in rejecter_roles:
                        raise WorkflowError(
                            f"Rejection denied: level {level} requires role '{assigned_role}', "
                            f"but rejecter has roles {rejecter_roles}"
                        )
        
        # Validate state transition
        current_pending = f"pending_approval_level_{level}"
        result = await self.workflow_engine.transition(
            entity_type="discrepancy",
            current_state=current_pending,
            target_state="under_investigation",
        )
        
        # Update approval history
        approval_history = await self.db.execute(
            select(DiscrepancyApprovalHistory).where(
                and_(
                    DiscrepancyApprovalHistory.discrepancy_id == discrepancy_id,
                    DiscrepancyApprovalHistory.level == level,
                )
            )
        )
        history_entry = approval_history.scalar_one_or_none()
        if history_entry:
            history_entry.approved_by_user_id = rejecter_id
            history_entry.status = "rejected"
            history_entry.comments = comments
            history_entry.approved_at = utc_now()
        
        # Update discrepancy state (investigation notes preserved)
        discrepancy.state = result.to_state
        
        await self.db.commit()
        await self.db.refresh(discrepancy)
        
        return discrepancy

    async def get_approval_history(
        self,
        discrepancy_id: uuid.UUID,
    ) -> List[DiscrepancyApprovalHistory]:
        """
        Get approval history for a discrepancy.
        Returns one row per approval level with correct Role/User/Status/Comments.
        """
        result = await self.db.execute(
            select(DiscrepancyApprovalHistory).where(
                DiscrepancyApprovalHistory.discrepancy_id == discrepancy_id
            ).order_by(DiscrepancyApprovalHistory.level)
        )
        return list(result.scalars().all())
