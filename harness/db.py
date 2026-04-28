"""Async PostgreSQL connection pool (used by FastAPI + AsyncPostgresSaver).

Usage:
    pool = await get_pool()           # lazy-init, cached globally
    async with pool.acquire() as conn:
        await conn.fetch("SELECT 1")

Call close_pool() on app shutdown.
"""
import asyncpg

from harness.config import POSTGRES_DSN

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(POSTGRES_DSN, min_size=2, max_size=20)
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def healthcheck() -> bool:
    """Return True if Postgres is reachable."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return True
    except Exception:
        return False
