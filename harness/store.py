"""Long-term memory store backed by Postgres (or in-memory for dev).

Uses LangGraph's BaseStore API so the agent can remember facts about users
across sessions. Namespace: ("users", user_id).

USE_POSTGRES=true → AsyncPostgresStore (requires langgraph-checkpoint-postgres).
USE_POSTGRES unset  → InMemoryStore (facts lost on restart — dev only).
"""
from __future__ import annotations

from harness.config import POSTGRES_DSN, USE_POSTGRES

_store = None


async def get_store():
    """Lazy-init and return the global store instance."""
    global _store
    if _store is not None:
        return _store

    if USE_POSTGRES:
        from langgraph.store.postgres.aio import AsyncPostgresStore
        _store = AsyncPostgresStore.from_conn_string(POSTGRES_DSN)
        await _store.setup()
    else:
        from langgraph.store.memory import InMemoryStore
        _store = InMemoryStore()

    return _store


async def close_store() -> None:
    global _store
    if _store is not None and hasattr(_store, "close"):
        await _store.close()
    _store = None
