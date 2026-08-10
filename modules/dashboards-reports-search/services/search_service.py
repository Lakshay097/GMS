"""
Global Search service — PRS §33/§51, R-60.

Results are permission-scoped identically to direct module access:
  * school_id filter applied for all non-SuperAdmin roles
  * Viewer gets accessible_school_ids set
  * Sensitive KPIs (is_sensitive=true) hidden from Viewer
  * Entity types with no Read permission for the role are excluded

Saved filters are private by default; only the owner may read/update/delete.
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from modules.dashboards_reports_search.schemas import (
    SavedFilterCreate,
    SavedFilterResponse,
    SavedFilterUpdate,
    SearchHit,
    SearchRequest,
    SearchResponse,
)
from modules.dashboards_reports_search.services.search_indexer import SearchIndexer
from shared.errors import AuthorizationError, NotFoundError
from shared.middleware.tenancy import TenantContext

# Entity types visible per role (R-60: permission-scoped identically to module access)
_ROLE_VISIBLE_ENTITY_TYPES: Dict[str, List[str]] = {
    "superadmin": ["observation", "task", "discrepancy", "kpi", "user", "school", "department"],
    "admin":      ["observation", "task", "discrepancy", "kpi", "user", "school", "department"],
    "checker":    ["observation", "task", "kpi", "department"],
    "auditor":    ["observation", "task", "discrepancy", "kpi", "department"],
    "viewer":     ["observation", "task", "discrepancy", "kpi", "school", "department"],
}


def _normalise_role(roles: List[str]) -> str:
    """Return the highest-privilege role from the list."""
    order = ["superadmin", "admin", "auditor", "checker", "viewer"]
    lower = [r.lower() for r in roles]
    for r in order:
        if r in lower:
            return r
    return "viewer"


def _build_filter(
    entity_type: str,
    tenant: TenantContext,
    primary_role: str,
    date_from: Optional[Any] = None,
    date_to: Optional[Any] = None,
) -> str:
    """Build a Meilisearch filter expression for the given tenant + role."""
    parts: List[str] = []

    if primary_role == "superadmin":
        pass  # no school restriction
    elif primary_role == "viewer" and tenant.accessible_school_ids:
        ids_str = ", ".join(f'"{s}"' for s in tenant.accessible_school_ids)
        parts.append(f"school_id IN [{ids_str}]")
    elif tenant.school_id:
        parts.append(f'school_id = "{tenant.school_id}"')

    if tenant.department_id and primary_role in ("checker",):
        parts.append(f'department_id = "{tenant.department_id}"')

    # Hide sensitive KPIs from Viewer (BR-04)
    if primary_role == "viewer" and entity_type == "kpi":
        parts.append("is_sensitive = false")

    if date_from and entity_type in ("observation",):
        parts.append(f'submitted_at_date >= "{date_from.isoformat()}"')
    if date_to and entity_type in ("observation",):
        parts.append(f'submitted_at_date <= "{date_to.isoformat()}"')

    return " AND ".join(parts) if parts else ""


class SearchService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def search(
        self, req: SearchRequest, tenant: TenantContext
    ) -> SearchResponse:
        primary_role = _normalise_role(tenant.roles)
        allowed_types = _ROLE_VISIBLE_ENTITY_TYPES.get(primary_role, [])

        # Intersect with caller-requested types if provided
        target_types = (
            [t for t in req.entity_types if t in allowed_types]
            if req.entity_types
            else allowed_types
        )

        start_ms = int(time.monotonic() * 1000)
        all_hits: List[SearchHit] = []
        total = 0

        offset = (req.page - 1) * req.page_size

        for entity_type in target_types:
            flt = _build_filter(
                entity_type, tenant, primary_role,
                date_from=req.date_from, date_to=req.date_to,
            )
            raw = await SearchIndexer.search(
                entity_type, req.q,
                filters=flt or None,
                offset=offset,
                limit=req.page_size,
            )
            total += raw.get("estimatedTotalHits", 0)
            for hit in raw.get("hits", []):
                formatted = hit.get("_formatted", {})
                all_hits.append(SearchHit(
                    entity_type=entity_type,
                    entity_id=UUID(hit["id"]) if _is_uuid(hit.get("id", "")) else uuid.uuid4(),
                    school_id=UUID(hit["school_id"]) if hit.get("school_id") and _is_uuid(hit["school_id"]) else None,
                    department_id=UUID(hit["department_id"]) if hit.get("department_id") and _is_uuid(hit["department_id"]) else None,
                    title=hit.get("title") or hit.get("full_name") or hit.get("name") or hit.get("kpi_title", ""),
                    description=hit.get("description") or hit.get("investigation_findings"),
                    status=hit.get("status") or hit.get("state") or hit.get("rag_status"),
                    score=hit.get("_rankingScore"),
                    highlighted=formatted if formatted else None,
                    created_at=_parse_dt(hit.get("created_at")),
                ))

        elapsed_ms = int(time.monotonic() * 1000) - start_ms
        return SearchResponse(
            query=req.q,
            total_hits=total,
            page=req.page,
            page_size=req.page_size,
            processing_time_ms=elapsed_ms,
            hits=all_hits,
        )

    # ── Saved filters ──────────────────────────────────────────────────────────

    async def create_saved_filter(
        self, body: SavedFilterCreate, tenant: TenantContext
    ) -> SavedFilterResponse:
        filter_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        await self.db.execute(
            text(
                """
                INSERT INTO saved_filters
                    (id, owner_user_id, school_id, context, name, filters, is_public,
                     created_at, updated_at)
                VALUES
                    (:id, :owner, :school_id, :context, :name, :filters,
                     :is_public, :now, :now)
                """
            ),
            {
                "id": str(filter_id),
                "owner": tenant.user_id,
                "school_id": tenant.school_id,
                "context": body.context,
                "name": body.name,
                "filters": _json_dumps(body.filters),
                "is_public": body.is_public,
                "now": now,
            },
        )
        await self.db.commit()
        return SavedFilterResponse(
            id=filter_id,
            context=body.context,
            name=body.name,
            filters=body.filters,
            is_public=body.is_public,
            created_at=now,
            updated_at=now,
        )

    async def list_saved_filters(
        self, tenant: TenantContext, context: Optional[str] = None
    ) -> List[SavedFilterResponse]:
        base = (
            "SELECT id, context, name, filters, is_public, created_at, updated_at "
            "FROM saved_filters "
            "WHERE (owner_user_id = :user_id OR is_public = 1)"
        )
        params: Dict[str, Any] = {"user_id": tenant.user_id}
        if context:
            base += " AND context = :context"
            params["context"] = context
        base += " ORDER BY updated_at DESC"
        rows = (await self.db.execute(text(base), params)).fetchall()
        return [
            SavedFilterResponse(
                id=UUID(str(r.id)),
                context=r.context,
                name=r.name,
                filters=_parse_filters(r.filters),
                is_public=bool(r.is_public),
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in rows
        ]

    async def update_saved_filter(
        self, filter_id: UUID, body: SavedFilterUpdate, tenant: TenantContext
    ) -> SavedFilterResponse:
        row = await self._get_owned_filter(filter_id, tenant)
        now = datetime.now(timezone.utc)
        updates: Dict[str, Any] = {"id": str(filter_id), "now": now}
        set_parts: List[str] = ["updated_at = :now"]
        if body.name is not None:
            set_parts.append("name = :name")
            updates["name"] = body.name
        if body.filters is not None:
            set_parts.append("filters = :filters")
            updates["filters"] = _json_dumps(body.filters)
        if body.is_public is not None:
            set_parts.append("is_public = :is_public")
            updates["is_public"] = body.is_public
        await self.db.execute(
            text(f"UPDATE saved_filters SET {', '.join(set_parts)} WHERE id = :id"),
            updates,
        )
        await self.db.commit()
        return await self._get_filter_by_id(filter_id)

    async def delete_saved_filter(
        self, filter_id: UUID, tenant: TenantContext
    ) -> None:
        await self._get_owned_filter(filter_id, tenant)
        await self.db.execute(
            text("DELETE FROM saved_filters WHERE id = :id"),
            {"id": str(filter_id)},
        )
        await self.db.commit()

    # ── Helpers ────────────────────────────────────────────────────────────────

    async def _get_owned_filter(
        self, filter_id: UUID, tenant: TenantContext
    ) -> Any:
        row = await self._get_filter_by_id(filter_id)
        result = await self.db.execute(
            text("SELECT owner_user_id FROM saved_filters WHERE id = :id"),
            {"id": str(filter_id)},
        )
        owner_row = result.fetchone()
        if not owner_row:
            raise NotFoundError("SavedFilter")
        if str(owner_row.owner_user_id) != str(tenant.user_id):
            raise AuthorizationError("You can only modify your own saved filters")
        return row

    async def _get_filter_by_id(self, filter_id: UUID) -> SavedFilterResponse:
        result = await self.db.execute(
            text(
                "SELECT id, context, name, filters, is_public, created_at, updated_at "
                "FROM saved_filters WHERE id = :id"
            ),
            {"id": str(filter_id)},
        )
        row = result.fetchone()
        if not row:
            raise NotFoundError("SavedFilter")
        return SavedFilterResponse(
            id=UUID(str(row.id)),
            context=row.context,
            name=row.name,
            filters=_parse_filters(row.filters),
            is_public=row.is_public,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )


# ── Utility ────────────────────────────────────────────────────────────────────

def _is_uuid(val: str) -> bool:
    try:
        uuid.UUID(val)
        return True
    except (ValueError, AttributeError):
        return False


def _parse_dt(val: Optional[str]) -> Optional[datetime]:
    if not val:
        return None
    try:
        return datetime.fromisoformat(val)
    except (ValueError, TypeError):
        return None


def _json_dumps(obj: Any) -> str:
    import json
    return json.dumps(obj)


def _parse_filters(val: Any) -> Dict[str, Any]:
    """Parse JSON string from DB or return dict if already parsed."""
    import json
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except (json.JSONDecodeError, ValueError):
            return {}
    return {}
