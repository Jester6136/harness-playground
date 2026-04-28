"""Long-term memory store backed by Postgres (LangGraph Store API).

Uses namespace ("users", user_id) to persist facts about users across sessions.

Requires: langgraph-checkpoint-postgres + psycopg[binary]
"""
from __future__ import annotations

from harness.config import POSTGRES_DSN

_store = None


async def get_store():
    """Lazy-init and return the global async Postgres store."""
    global _store
    if _store is not None:
        return _store

    from psycopg import AsyncConnection
    from langgraph.store.postgres.aio import AsyncPostgresStore

    conn = await AsyncConnection.connect(
        POSTGRES_DSN, autocommit=True, prepare_threshold=0
    )
    _store = AsyncPostgresStore(conn)
    await _store.setup()
    return _store


async def close_store() -> None:
    global _store
    if _store is not None and hasattr(_store, "conn"):
        try:
            await _store.conn.close()
        except Exception:
            pass
    _store = None
