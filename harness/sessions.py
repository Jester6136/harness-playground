"""Per-user, per-session state management on top of LangGraph PostgresSaver.

LangGraph identifies a conversation by `thread_id`. We use the convention
`<user>:<session>` so one database can serve many users with logical isolation.

NOTE: from_conn_string() returns a context manager, not a saver directly.
We create the psycopg connection manually and pass it to the saver instead.
"""
from __future__ import annotations

from harness.config import POSTGRES_DSN


def thread_id(user: str, session: str) -> str:
    """Compose the LangGraph thread_id from user + session names."""
    return f"{user}:{session}"


# ---------------------------------------------------------------------------
# Checkpointer factories
# ---------------------------------------------------------------------------

def make_checkpointer():
    """Sync PostgresSaver for the CLI (main.py).

    Requires psycopg (psycopg3). Install: pip install 'psycopg[binary]'
    """
    from psycopg import Connection
    from langgraph.checkpoint.postgres import PostgresSaver

    conn = Connection.connect(POSTGRES_DSN, autocommit=True, prepare_threshold=0)
    saver = PostgresSaver(conn)
    saver.setup()
    return saver


async def make_async_checkpointer():
    """Async PostgresSaver for the FastAPI app (harness/api.py).

    Requires psycopg (psycopg3). Install: pip install 'psycopg[binary]'
    """
    from psycopg import AsyncConnection
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    conn = await AsyncConnection.connect(
        POSTGRES_DSN, autocommit=True, prepare_threshold=0
    )
    saver = AsyncPostgresSaver(conn)
    await saver.setup()
    return saver


# ---------------------------------------------------------------------------
# Admin queries
# ---------------------------------------------------------------------------

def _all_thread_ids() -> list[str]:
    try:
        from psycopg import Connection
        with Connection.connect(POSTGRES_DSN, autocommit=True) as conn:
            rows = conn.execute(
                "SELECT DISTINCT thread_id FROM checkpoints"
            ).fetchall()
        return [r[0] for r in rows]
    except Exception:
        return []


def list_users() -> list[str]:
    """All distinct user ids that have at least one session."""
    return sorted({
        tid.split(":", 1)[0]
        for tid in _all_thread_ids()
        if ":" in tid
    })


def list_sessions(user: str) -> list[str]:
    """All session ids belonging to a user."""
    prefix = f"{user}:"
    return sorted({
        tid.split(":", 1)[1]
        for tid in _all_thread_ids()
        if tid.startswith(prefix)
    })


def delete_session(user: str, session: str) -> None:
    """Erase a single session's checkpoints and writes."""
    tid = thread_id(user, session)
    try:
        from psycopg import Connection
        with Connection.connect(POSTGRES_DSN, autocommit=True) as conn:
            for table in ("checkpoints", "checkpoint_writes", "checkpoint_blobs"):
                try:
                    conn.execute(
                        f"DELETE FROM {table} WHERE thread_id = %s", (tid,)
                    )
                except Exception:
                    pass
    except Exception:
        pass
