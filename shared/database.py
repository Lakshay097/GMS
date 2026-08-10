"""
Database configuration and connection management for Neon Postgres.

Two engine pools:
  engine             — write-path (transactional): observations, tasks, discrepancies, etc.
                       pool_size=10, max_overflow=20
  read_replica_engine — read-path (reports, dashboards, global search).
                        Reads from DATABASE_READ_REPLICA_URL when set; falls back to the
                        same URL (useful in dev/single-node).  Larger pool because heavy
                        analytical queries hold connections longer.
                        pool_size=5, max_overflow=10

Separation rationale (R-61 / Architecture §14):
  Report and dashboard queries can be seconds-long full-table scans.  Running them on the
  write-path pool starves transactional connections and degrades write latency.  By routing
  all heavy reads through `get_read_db()` (or its `ReadReplicaSession` counterpart) we
  guarantee the write pool is never touched by analytical workloads.

Usage:
  Transactional routes:  Depends(get_db)
  Report/dashboard routes: Depends(get_read_db)
"""
from __future__ import annotations

import os
from urllib.parse import urlparse, parse_qs, urlunparse

from dotenv import load_dotenv
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

load_dotenv()


# ── helpers ────────────────────────────────────────────────────────────────────

def _normalise_url(url: str | None) -> str | None:
    """Convert postgres:// → postgresql+asyncpg:// and strip asyncpg-incompatible params."""
    if not url:
        return url
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)

    parsed = urlparse(url)
    query_params = parse_qs(parsed.query)
    query_params.pop("sslmode", None)
    query_params.pop("channel_binding", None)
    cleaned_query = "&".join(f"{k}={v[0]}" for k, v in query_params.items())
    return urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        cleaned_query,
        parsed.fragment,
    ))


# ── Write-path engine (transactional) ─────────────────────────────────────────

DATABASE_URL: str | None = _normalise_url(os.getenv("DATABASE_URL"))

engine = create_async_engine(
    DATABASE_URL,  # type: ignore[arg-type]
    echo=os.getenv("LOG_LEVEL", "info") == "debug",
    # Transactional pool — kept small so report load cannot exhaust it.
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# ── Read-replica engine (reports / dashboards / search) ───────────────────────
# Falls back to the primary URL in dev/single-node; in production point
# DATABASE_READ_REPLICA_URL at a read replica or a Neon branch.

_READ_URL: str | None = _normalise_url(
    os.getenv("DATABASE_READ_REPLICA_URL") or os.getenv("DATABASE_URL")
)

read_replica_engine = create_async_engine(
    _READ_URL,  # type: ignore[arg-type]
    echo=os.getenv("LOG_LEVEL", "info") == "debug",
    # Larger pool for analytical queries that hold connections longer.
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    # Force read-only at the connection level when a replica is configured.
    # asyncpg connection init: SET default_transaction_read_only = on
    connect_args={"server_settings": {"default_transaction_read_only": "on"}}
    if os.getenv("DATABASE_READ_REPLICA_URL")
    else {},
)

ReadReplicaSessionLocal = async_sessionmaker(
    read_replica_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# ── ORM base ───────────────────────────────────────────────────────────────────

Base = declarative_base()
metadata = MetaData()


# ── FastAPI dependency helpers ─────────────────────────────────────────────────

async def get_db():
    """
    Write-path DB dependency (transactional operations).
    Use for: observations, tasks, discrepancies, users, etc.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_read_db():
    """
    Read-path DB dependency (reports, dashboards, search).

    Routes through read_replica_engine which is either a true read replica
    (DATABASE_READ_REPLICA_URL set) or the primary with a read-only transaction
    flag.  In both cases report queries cannot consume the write-path pool
    (pool_size=10) — they are isolated to the replica pool (pool_size=5).

    Use for: all GET endpoints in dashboards-reports-search module.
    """
    async with ReadReplicaSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# ── Lifecycle helpers ──────────────────────────────────────────────────────────

async def init_db():
    """Initialize database tables (dev only — use Alembic in production)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Dispose both engine pools on shutdown."""
    await engine.dispose()
    await read_replica_engine.dispose()
