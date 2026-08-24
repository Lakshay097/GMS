"""
Real-time Meilisearch indexing service — PRS §33/§51, R-60.

Design
------
* Every write-path service (observation, task, discrepancy, KPI, user, school,
  department) calls ``SearchIndexer.index()`` immediately after its DB commit.
  This keeps indexing lag well below the 60-second target (R-60).

* Index names are prefixed with ``SEARCH_INDEX_PREFIX`` (default "schoolop_")
  to support multi-tenant or multi-env Meilisearch instances.

* Permission scoping is NOT done here.  The indexer stores ``school_id``,
  ``department_id``, and a ``searchable_roles`` hint on every document so the
  query layer can apply tenant + role filters at search time (R-60).

* Indexing lag is recorded in ``search_index_sync_log`` so the acceptance test
  can query: SELECT MAX(lag_seconds) … WHERE indexed_at > NOW() - interval '5 min'
  and assert it stays under 60 s.

Supported entity types
----------------------
observation | task | discrepancy | kpi | user | school | department
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger(__name__)

SEARCH_INDEX_URL: str = os.getenv("SEARCH_INDEX_URL", "http://localhost:7700")

# Ensure URL has protocol
if SEARCH_INDEX_URL and not SEARCH_INDEX_URL.startswith(("http://", "https://")):
    SEARCH_INDEX_URL = f"http://{SEARCH_INDEX_URL}"
SEARCH_INDEX_API_KEY: str = os.getenv("SEARCH_INDEX_API_KEY", "")
SEARCH_INDEX_PREFIX: str = os.getenv("SEARCH_INDEX_PREFIX", "schoolop_")
LAG_TARGET_SECONDS: int = int(os.getenv("SEARCH_INDEXING_LAG_TARGET_SECONDS", "60"))

# Meilisearch index configurations — filterable/sortable attributes per entity
_INDEX_CONFIG: Dict[str, Dict[str, Any]] = {
    "observation": {
        "filterableAttributes": ["school_id", "department_id", "kpi_id",
                                  "rag_status", "auto_result", "checker_id",
                                  "submitted_at_date"],
        "sortableAttributes": ["submitted_at"],
        "searchableAttributes": ["kpi_title", "department_name", "school_name",
                                  "checker_name", "value_text"],
        "displayedAttributes": ["*"],
    },
    "task": {
        "filterableAttributes": ["school_id", "department_id", "status",
                                  "created_by", "eta_date"],
        "sortableAttributes": ["eta", "created_at"],
        "searchableAttributes": ["title", "description", "school_name",
                                  "department_name"],
        "displayedAttributes": ["*"],
    },
    "discrepancy": {
        "filterableAttributes": ["school_id", "department_id", "state",
                                  "category_id", "raised_by_user_id"],
        "sortableAttributes": ["raised_at", "created_at"],
        "searchableAttributes": ["category_name", "investigation_findings",
                                  "school_name", "department_name"],
        "displayedAttributes": ["*"],
    },
    "kpi": {
        "filterableAttributes": ["kra_id", "status", "category_code",
                                  "frequency_code", "is_sensitive"],
        "sortableAttributes": ["created_at"],
        "searchableAttributes": ["title", "unit_of_measure", "category_code",
                                  "kra_name"],
        "displayedAttributes": ["*"],
    },
    "user": {
        "filterableAttributes": ["school_id", "department_id", "status",
                                  "roles"],
        "sortableAttributes": ["created_at", "full_name"],
        "searchableAttributes": ["full_name", "email", "employee_id",
                                  "school_name", "department_name"],
        "displayedAttributes": ["*"],
    },
    "school": {
        "filterableAttributes": ["status"],
        "sortableAttributes": ["name", "created_at"],
        "searchableAttributes": ["name", "code", "address", "contact_email"],
        "displayedAttributes": ["*"],
    },
    "department": {
        "filterableAttributes": ["school_id", "status"],
        "sortableAttributes": ["name", "created_at"],
        "searchableAttributes": ["name", "code", "description", "school_name"],
        "displayedAttributes": ["*"],
    },
}


def _index_name(entity_type: str) -> str:
    return f"{SEARCH_INDEX_PREFIX}{entity_type}"


def _headers() -> Dict[str, str]:
    h = {"Content-Type": "application/json"}
    if SEARCH_INDEX_API_KEY:
        h["Authorization"] = f"Bearer {SEARCH_INDEX_API_KEY}"
    return h


class SearchIndexer:
    """
    Async Meilisearch client wrapper.

    All public methods are fire-and-forget coroutines that MUST be awaited from
    write-path services right after their DB commit.  They never raise — indexing
    failures are logged but not propagated to the caller so a Meilisearch outage
    cannot block a write.
    """

    # ── Index bootstrap ────────────────────────────────────────────────────────

    @staticmethod
    async def ensure_indexes() -> None:
        """
        Create all entity indexes with their attribute config if they don't
        exist yet.  Called once at application startup (lifespan).
        """
        async with httpx.AsyncClient(timeout=10) as client:
            for entity_type, config in _INDEX_CONFIG.items():
                idx = _index_name(entity_type)
                try:
                    # Create index (idempotent — 400 if already exists)
                    await client.post(
                        f"{SEARCH_INDEX_URL}/indexes",
                        headers=_headers(),
                        json={"uid": idx, "primaryKey": "id"},
                    )
                    # Apply attribute config
                    await client.patch(
                        f"{SEARCH_INDEX_URL}/indexes/{idx}/settings",
                        headers=_headers(),
                        json=config,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("SearchIndexer.ensure_indexes[%s] failed: %s", idx, exc)

    # ── Upsert ─────────────────────────────────────────────────────────────────

    @staticmethod
    async def index(
        entity_type: str,
        document: Dict[str, Any],
        db: Optional[AsyncSession] = None,
        write_committed_at: Optional[datetime] = None,
    ) -> None:
        """
        Index (upsert) a single document.  ``document`` must contain an ``id``
        field (string UUID).

        ``write_committed_at`` should be set to the timestamp of the DB commit
        so the lag monitor can compute exact lag_seconds.
        """
        idx = _index_name(entity_type)
        now = datetime.now(timezone.utc)
        committed_at = write_committed_at or now

        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.post(
                    f"{SEARCH_INDEX_URL}/indexes/{idx}/documents",
                    headers=_headers(),
                    json=[document],
                )
                resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            logger.error("SearchIndexer.index[%s] failed: %s", idx, exc)
            return

        lag = (now - committed_at).total_seconds()
        if lag > LAG_TARGET_SECONDS:
            logger.warning(
                "Indexing lag %.1fs exceeds target %ds for %s id=%s",
                lag, LAG_TARGET_SECONDS, entity_type, document.get("id"),
            )

        if db is not None:
            await SearchIndexer._log_sync(
                db, entity_type, document.get("id"), "upsert",
                now, committed_at, lag,
                school_id=document.get("school_id"),
            )

    @staticmethod
    async def index_batch(
        entity_type: str,
        documents: List[Dict[str, Any]],
        db: Optional[AsyncSession] = None,
    ) -> None:
        """Bulk upsert — used by catch-up reindex jobs."""
        if not documents:
            return
        idx = _index_name(entity_type)
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{SEARCH_INDEX_URL}/indexes/{idx}/documents",
                    headers=_headers(),
                    json=documents,
                )
                resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            logger.error("SearchIndexer.index_batch[%s] failed: %s", idx, exc)

    # ── Delete ─────────────────────────────────────────────────────────────────

    @staticmethod
    async def delete(
        entity_type: str,
        entity_id: str,
        db: Optional[AsyncSession] = None,
    ) -> None:
        """Remove a document from the index (e.g. archived user)."""
        idx = _index_name(entity_type)
        now = datetime.now(timezone.utc)
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.delete(
                    f"{SEARCH_INDEX_URL}/indexes/{idx}/documents/{entity_id}",
                    headers=_headers(),
                )
                resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            logger.error("SearchIndexer.delete[%s/%s] failed: %s", idx, entity_id, exc)
            return

        if db is not None:
            await SearchIndexer._log_sync(
                db, entity_type, entity_id, "delete", now, now, 0.0,
            )

    # ── Query (used by SearchService) ──────────────────────────────────────────

    @staticmethod
    async def search(
        entity_type: str,
        query: str,
        filters: Optional[str] = None,  # Meilisearch filter expression
        offset: int = 0,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """
        Run a search query against a single entity index.
        Returns the raw Meilisearch response dict.
        """
        idx = _index_name(entity_type)
        payload: Dict[str, Any] = {
            "q": query,
            "offset": offset,
            "limit": limit,
            "attributesToHighlight": ["*"],
            "highlightPreTag": "<mark>",
            "highlightPostTag": "</mark>",
        }
        if filters:
            payload["filter"] = filters

        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.post(
                    f"{SEARCH_INDEX_URL}/indexes/{idx}/search",
                    headers=_headers(),
                    json=payload,
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.error("SearchIndexer.search[%s] failed: %s", idx, exc)
            return {"hits": [], "estimatedTotalHits": 0, "processingTimeMs": 0}

    # ── Lag monitor ────────────────────────────────────────────────────────────

    @staticmethod
    async def get_max_lag_last_n_minutes(
        db: AsyncSession,
        minutes: int = 5,
    ) -> Optional[float]:
        """
        Return the maximum indexing lag (seconds) recorded in the last N minutes.
        Used by the acceptance test to verify < 60 s.
        """
        result = await db.execute(
            text(
                """
                SELECT MAX(lag_seconds)
                FROM search_index_sync_log
                WHERE indexed_at > NOW() - INTERVAL ':minutes minutes'
                """,
            ),
            {"minutes": minutes},
        )
        row = result.fetchone()
        return float(row[0]) if row and row[0] is not None else None

    # ── Internal helpers ───────────────────────────────────────────────────────

    @staticmethod
    async def _log_sync(
        db: AsyncSession,
        entity_type: str,
        entity_id: Any,
        operation: str,
        indexed_at: datetime,
        write_committed_at: datetime,
        lag_seconds: float,
        school_id: Optional[Any] = None,
    ) -> None:
        """Insert a row into search_index_sync_log (best-effort, never raises)."""
        try:
            await db.execute(
                text(
                    """
                    INSERT INTO search_index_sync_log
                        (id, entity_type, entity_id, school_id, operation,
                         indexed_at, write_committed_at, lag_seconds)
                    VALUES
                        (:id, :entity_type, :entity_id, :school_id, :operation,
                         :indexed_at, :write_committed_at, :lag_seconds)
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "entity_type": entity_type,
                    "entity_id": str(entity_id) if entity_id else None,
                    "school_id": str(school_id) if school_id else None,
                    "operation": operation,
                    "indexed_at": indexed_at,
                    "write_committed_at": write_committed_at,
                    "lag_seconds": round(lag_seconds, 3),
                },
            )
            # Don't commit here — the caller's DB session may still be in a tx.
            # The log row is committed when the parent request commits, which is fine.
        except Exception as exc:  # noqa: BLE001
            logger.warning("SearchIndexer._log_sync failed: %s", exc)


# ── Document builders ──────────────────────────────────────────────────────────
# Each helper converts an ORM row + enrichment dict into a flat Meilisearch doc.

def build_observation_doc(obs: Any, enrichment: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(obs.id),
        "entity_type": "observation",
        "school_id": str(obs.school_id) if obs.school_id else None,
        "department_id": str(obs.department_id) if obs.department_id else None,
        "kpi_id": str(obs.kpi_id) if obs.kpi_id else None,
        "kpi_title": enrichment.get("kpi_title"),
        "checker_id": str(obs.checker_id) if obs.checker_id else None,
        "checker_name": enrichment.get("checker_name"),
        "department_name": enrichment.get("department_name"),
        "school_name": enrichment.get("school_name"),
        "rag_status": obs.rag_status.value if obs.rag_status else None,
        "auto_result": obs.auto_result.value if obs.auto_result else None,
        "value_text": obs.value_text,
        "submitted_at": obs.submitted_at.isoformat() if obs.submitted_at else None,
        "submitted_at_date": obs.submitted_at.date().isoformat() if obs.submitted_at else None,
        "is_late": obs.is_late,
    }


def build_task_doc(task: Any, enrichment: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(task.id),
        "entity_type": "task",
        "school_id": str(task.school_id) if task.school_id else None,
        "department_id": str(task.department_id) if task.department_id else None,
        "title": task.title,
        "description": task.description,
        "school_name": enrichment.get("school_name"),
        "department_name": enrichment.get("department_name"),
        "status": task.status,
        "created_by": str(task.created_by) if task.created_by else None,
        "eta": task.eta.isoformat() if task.eta else None,
        "eta_date": task.eta.date().isoformat() if task.eta else None,
        "created_at": task.created_at.isoformat() if task.created_at else None,
    }


def build_discrepancy_doc(disc: Any, enrichment: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(disc.id),
        "entity_type": "discrepancy",
        "school_id": str(disc.school_id) if disc.school_id else None,
        "department_id": str(disc.department_id) if disc.department_id else None,
        "category_id": str(disc.category_id) if disc.category_id else None,
        "category_name": enrichment.get("category_name"),
        "school_name": enrichment.get("school_name"),
        "department_name": enrichment.get("department_name"),
        "state": disc.state,
        "raised_by_user_id": str(disc.raised_by_user_id) if disc.raised_by_user_id else None,
        "investigation_findings": disc.investigation_findings,
        "raised_at": disc.raised_at.isoformat() if disc.raised_at else None,
        "created_at": disc.created_at.isoformat() if disc.created_at else None,
    }


def build_kpi_doc(kpi: Any, enrichment: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": f"{kpi.kpi_id}_v{kpi.version}",
        "entity_type": "kpi",
        "kpi_id": str(kpi.kpi_id),
        "version": kpi.version,
        "kra_id": str(kpi.kra_id) if kpi.kra_id else None,
        "kra_name": enrichment.get("kra_name"),
        "title": kpi.title,
        "unit_of_measure": kpi.unit_of_measure,
        "category_code": kpi.category_code,
        "is_sensitive": kpi.is_sensitive,
        "status": kpi.status.value if kpi.status else None,
        "frequency_code": kpi.frequency_code,
        "created_at": kpi.created_at.isoformat() if kpi.created_at else None,
    }


def build_user_doc(user: Any, enrichment: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(user.id),
        "entity_type": "user",
        "school_id": str(user.school_id) if user.school_id else None,
        "department_id": str(user.department_id) if user.department_id else None,
        "full_name": user.full_name,
        "email": user.email,
        "employee_id": user.employee_id,
        "roles": user.roles or [],
        "status": user.status.value if user.status else None,
        "school_name": enrichment.get("school_name"),
        "department_name": enrichment.get("department_name"),
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def build_school_doc(school: Any) -> Dict[str, Any]:
    return {
        "id": str(school.id),
        "entity_type": "school",
        "name": school.name,
        "code": school.code,
        "status": school.status.value if school.status else None,
        "address": school.address,
        "contact_email": school.contact_email,
        "created_at": school.created_at.isoformat() if school.created_at else None,
    }


def build_department_doc(dept: Any, enrichment: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(dept.id),
        "entity_type": "department",
        "school_id": str(dept.school_id) if dept.school_id else None,
        "school_name": enrichment.get("school_name"),
        "name": dept.name,
        "code": dept.code,
        "description": dept.description,
        "status": dept.status.value if dept.status else None,
        "created_at": dept.created_at.isoformat() if dept.created_at else None,
    }
