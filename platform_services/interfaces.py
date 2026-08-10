"""
Stable public interfaces for platform services.
Caller modules depend on these protocols, not internal implementations.
"""
from __future__ import annotations

from typing import Any, Optional, Protocol
from uuid import UUID


class IConfigurationEngine(Protocol):
    async def get(
        self, key: str, *, school_id: Optional[UUID] = None, department_id: Optional[UUID] = None
    ) -> Any: ...

    async def set_override(
        self, key: str, scope_type: str, scope_id: UUID, value: Any, *, updated_by: Optional[UUID] = None
    ) -> None: ...


class IRuleEngine(Protocol):
    def aggregate(self, strategy_name: str, statuses: list[str]) -> str: ...


class IWorkflowEngine(Protocol):
    async def transition(
        self, entity_type: str, current_state: str, target_state: str, context: Optional[dict] = None
    ) -> Any: ...


class INotificationService(Protocol):
    async def dispatch(self, payload: Any) -> UUID: ...


class IAuditLogService(Protocol):
    async def append(
        self,
        action: str,
        entity_type: str,
        entity_id: Optional[UUID],
        *,
        actor_id: Optional[UUID] = None,
    ) -> UUID: ...


class IMasterDataService(Protocol):
    async def get_active_entries(self, category: str) -> list[Any]: ...


class IChecklistScheduler(Protocol):
    async def run_for_school(self, school_id: UUID, *, as_of: Optional[Any] = None) -> list[Any]: ...


class IComplianceScheduler(Protocol):
    async def run(self, *, as_of: Optional[Any] = None, last_run_at: Optional[Any] = None) -> Any: ...
