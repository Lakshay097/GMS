"""
Integration contract tests — caller modules use stable interfaces
without knowing service internals (Prompt 4 acceptance).
"""
import uuid
from datetime import datetime

import pytest

from platform_services.audit_log_service.service import AuditLogService
from platform_services.checklist_scheduler.service import ChecklistScheduler
from platform_services.compliance_scheduler.service import ComplianceScheduler
from platform_services.configuration_engine.service import ConfigurationEngine
from platform_services.interfaces import (
    IAuditLogService,
    IChecklistScheduler,
    IComplianceScheduler,
    IConfigurationEngine,
    IMasterDataService,
    INotificationService,
    IRuleEngine,
    IWorkflowEngine,
)
from platform_services.master_data_service.service import MasterDataService
from platform_services.notification_service.service import NotificationPayload, NotificationService
from platform_services.rule_engine.service import RuleEngine
from platform_services.rule_engine.strategies import WorstStatusWinsStrategy
from platform_services.workflow_engine.service import (
    TransitionDefinition,
    WorkflowDefinitionData,
    WorkflowEngine,
)
from shared.datetime_utils import utc_now
from shared.platform_models import ChecklistTemplate, ChecklistTemplateStatus, NotificationCategory
from shared.task_queue import InMemoryQueue


@pytest.mark.asyncio
async def test_configuration_engine_contract(db, school):
    """Caller uses IConfigurationEngine protocol only."""
    service: IConfigurationEngine = ConfigurationEngine(db)
    await service.seed_defaults()
    timeout = await service.get("session_timeout_minutes", school_id=school.id)
    assert isinstance(timeout, int)


@pytest.mark.asyncio
async def test_rule_engine_contract():
    engine: IRuleEngine = RuleEngine()
    engine.register_strategy(WorstStatusWinsStrategy())
    assert engine.aggregate("worst_status_wins", ["met", "not_met"]) == "not_met"


@pytest.mark.asyncio
async def test_workflow_engine_contract(db):
    engine: IWorkflowEngine = WorkflowEngine(db)
    await engine.register_definition(
        WorkflowDefinitionData(
            entity_type="task",
            initial_state="open",
            transitions=[TransitionDefinition(from_state="open", to_state="completed")],
        )
    )
    result = await engine.transition("task", "open", "completed")
    assert result.to_state == "completed"


@pytest.mark.asyncio
async def test_notification_service_contract(db, user):
    service: INotificationService = NotificationService(db, queue=InMemoryQueue())
    notif_id = await service.dispatch(
        NotificationPayload(
            user_id=user.id,
            category=NotificationCategory.TASK_ASSIGNMENT.value,
            title="Task assigned",
            body="You have a new task",
        )
    )
    assert notif_id is not None


@pytest.mark.asyncio
async def test_audit_log_service_contract(db, user):
    service: IAuditLogService = AuditLogService(db)
    entry_id = await service.append(
        "test_action",
        "test_entity",
        uuid.uuid4(),
        actor_id=user.id,
    )
    await db.commit()
    assert entry_id is not None


@pytest.mark.asyncio
async def test_master_data_service_contract(db):
    service: IMasterDataService = MasterDataService(db)
    await service.create_entry("task_type", "remediation", "Remediation")
    entries = await service.get_active_entries("task_type")
    assert len(entries) == 1


@pytest.mark.asyncio
async def test_checklist_scheduler_contract(db, school, department):
    template = ChecklistTemplate(
        template_id=uuid.uuid4(),
        version=1,
        title="Contract Test Template",
        school_id=school.id,
        department_id=department.id,
        frequency_code="daily",
        status=ChecklistTemplateStatus.ACTIVE,
        created_at=utc_now(),
    )
    db.add(template)
    await db.commit()

    scheduler: IChecklistScheduler = ChecklistScheduler(db)
    results = await scheduler.run_for_school(school.id, as_of=datetime(2026, 8, 7))
    assert len(results) >= 1


@pytest.mark.asyncio
async def test_compliance_scheduler_contract(db, school, kpi):
    await ConfigurationEngine(db).seed_defaults()
    scheduler: IComplianceScheduler = ComplianceScheduler(db)
    result = await scheduler.run(as_of=datetime(2026, 8, 7, 12, 0, 0))
    assert result.run_id is not None
