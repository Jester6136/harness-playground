"""Per-user, per-session state management on top of LangGraph checkpointers.

LangGraph identifies a conversation by `thread_id`. We use the convention
`<user>:<session>` so one database can serve many users with logical isolation.

Backend selection (set USE_POSTGRES=true to enable Postgres):
  - Postgres (production): AsyncPostgresSaver via psycopg3.
  - SQLite (dev/default): SqliteSaver via sqlite3.

Sync helpers (list_users, list_sessions, delete_session) are provided for
the CLI. The async checkpointer is used by the FastAPI app (T1.4).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from harness.config import POSTGRES_DSN, USE_POSTGRES

# ---------------------------------------------------------------------------
# Thread-id convention
# ---------------------------------------------------------------------------

def thread_id(user: str, session: str) -> str:
    """Compose the LangGraph thread_id from user + session names."""
    return f"{user}:{session}"


# ---------------------------------------------------------------------------
# Checkpointer factories
# ---------------------------------------------------------------------------

def make_checkpointer():
    """Return a sync checkpointer (SqliteSaver or PostgresSaver).

    Used by the CLI (main.py). FastAPI uses make_async_checkpointer() instead.
    """
    if USE_POSTGRES:
        from psycopg import Connection
        from langgraph.checkpoint.postgres import PostgresSaver

        conn = Connection.connect(
            POSTGRES_DSN,
            autocommit=True,
            prepare_threshold=0,
        )
        saver = PostgresSaver(conn)
        saver.setup()
        return saver
    else:
        _DB_PATH = Path(__file__).resolve().parent.parent / "sessions.db"
        conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
        from langgraph.checkpoint.sqlite import SqliteSaver
        saver = SqliteSaver(conn)
        saver.setup()
        return saver


async def make_async_checkpointer():
    """Return an async checkpointer (AsyncPostgresSaver or AsyncSqliteSaver).

    Used by the FastAPI app. Caller is responsible for lifecycle (setup/close).
    """
    if USE_POSTGRES:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        checkpointer = AsyncPostgresSaver.from_conn_string(POSTGRES_DSN)
        await checkpointer.setup()
        return checkpointer
    else:
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        _DB_PATH = Path(__file__).resolve().parent.parent / "sessions.db"
        checkpointer = AsyncSqliteSaver.from_conn_string(str(_DB_PATH))
        await checkpointer.setup()
        return checkpointer


# ---------------------------------------------------------------------------
# Admin queries (SQLite only — Postgres variant reads from pg tables directly)
# ---------------------------------------------------------------------------

def _sqlite_path() -> Path:
    return Path(__file__).resolve().parent.parent / "sessions.db"


def _all_thread_ids() -> list[str]:
    if USE_POSTGRES:
        # For Postgres, query the checkpoints table via psycopg.
        try:
            from psycopg import Connection
            with Connection.connect(POSTGRES_DSN, autocommit=True) as conn:
                rows = conn.execute(
                    "SELECT DISTINCT thread_id FROM checkpoints"
                ).fetchall()
            return [r[0] for r in rows]
        except Exception:
            return []
    else:
        db = _sqlite_path()
        if not db.exists():
            return []
        conn = sqlite3.connect(str(db))
        try:
            rows = conn.execute(
                "SELECT DISTINCT thread_id FROM checkpoints"
            ).fetchall()
        except sqlite3.OperationalError:
            rows = []
        finally:
            conn.close()
        return [r[0] for r in rows]


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
    if USE_POSTGRES:
        try:
            from psycopg import Connection
            with Connection.connect(POSTGRES_DSN, autocommit=True) as conn:
                for table in ("checkpoints", "checkpoint_writes", "checkpoint_blobs"):
                    try:
                        conn.execute(f"DELETE FROM {table} WHERE thread_id = %s", (tid,))
                    except Exception:
                        pass
        except Exception:
            pass
    else:
        db = _sqlite_path()
        if not db.exists():
            return
        conn = sqlite3.connect(str(db))
        try:
            for table in ("checkpoints", "writes"):
                try:
                    conn.execute(f"DELETE FROM {table} WHERE thread_id = ?", (tid,))
                except sqlite3.OperationalError:
                    pass
            conn.commit()
        finally:
            conn.close()
