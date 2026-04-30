"""Shared connection pool for the external `geohub_lis` Postgres.

Used by `skills/query_lis_db/` (bot tool surface) and
`harness/extensions/commands.py` (the /status slash command). Single source
of truth so both code paths reuse the same pool + DSN logic.
"""
from __future__ import annotations

import asyncio

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from harness.config import settings

_pool: AsyncConnectionPool | None = None
_pool_lock = asyncio.Lock()


async def get_pool() -> AsyncConnectionPool:
    """Lazy-init and return the global geohub_lis pool."""
    global _pool
    if _pool is not None:
        return _pool
    async with _pool_lock:
        if _pool is not None:
            return _pool
        pool = AsyncConnectionPool(
            conninfo=settings.lis_db_dsn,
            min_size=1,
            max_size=4,
            kwargs={"autocommit": True, "row_factory": dict_row},
            open=False,
        )
        await pool.open()
        _pool = pool
    return _pool


async def run_query(sql: str, params: tuple | dict, row_cap: int = 50) -> list[dict]:
    """Execute a parametric SELECT and return up to `row_cap` rows as dicts.

    Raises on any database error — caller handles formatting.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(sql, params)
        return await cur.fetchmany(row_cap)


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        try:
            await _pool.close()
        except Exception:
            pass
    _pool = None
