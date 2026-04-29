"""Long-term memory store backed by Postgres (LangGraph Store API).

Uses namespace ("users", user_id) to persist facts about users across sessions.
"""
from __future__ import annotations

import asyncio

from langgraph.store.postgres.aio import AsyncPostgresStore
from psycopg import AsyncConnection

from harness.config import POSTGRES_DSN

_store: AsyncPostgresStore | None = None
_store_lock = asyncio.Lock()


async def get_store() -> AsyncPostgresStore:
    """Lazy-init and return the global async Postgres store.

    Lock + double-check guards against two concurrent first-callers each
    spawning their own Postgres connection.
    """
    global _store
    if _store is not None:
        return _store

    async with _store_lock:
        if _store is not None:
            return _store
        conn = await AsyncConnection.connect(
            POSTGRES_DSN, autocommit=True, prepare_threshold=0
        )
        store = AsyncPostgresStore(conn)
        await store.setup()
        _store = store
    return _store


async def close_store() -> None:
    global _store
    if _store is not None and hasattr(_store, "conn"):
        try:
            await _store.conn.close()
        except Exception:
            pass
    _store = None
