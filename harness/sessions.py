"""Per-user, per-session state management on top of LangGraph checkpointers.

LangGraph identifies a conversation by `thread_id`. We use the convention
`<user>:<session>` so one SQLite file can serve many users with logical
isolation.

For production multi-tenancy, replace SqliteSaver with PostgresSaver and put
real auth in front of it — this module is the educational baseline.
"""
import sqlite3
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver

DB_PATH = Path(__file__).resolve().parent.parent / "sessions.db"


def make_checkpointer() -> SqliteSaver:
    """SQLite-backed checkpointer. Conversations persist across restarts."""
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()  # idempotent; ensures tables exist
    return saver


def thread_id(user: str, session: str) -> str:
    """Compose the LangGraph thread_id from user + session names."""
    return f"{user}:{session}"


# ---------------------------------------------------------------------------
# Admin queries — read directly from the SqliteSaver tables.
# (For Postgres or other backends, the DB shape changes; adapt as needed.)
# ---------------------------------------------------------------------------

def _all_thread_ids() -> list[str]:
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(str(DB_PATH))
    try:
        rows = conn.execute(
            "SELECT DISTINCT thread_id FROM checkpoints"
        ).fetchall()
    except sqlite3.OperationalError:
        rows = []  # table not yet created
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
    if not DB_PATH.exists():
        return
    tid = thread_id(user, session)
    conn = sqlite3.connect(str(DB_PATH))
    try:
        for table in ("checkpoints", "writes"):
            try:
                conn.execute(f"DELETE FROM {table} WHERE thread_id = ?", (tid,))
            except sqlite3.OperationalError:
                pass  # table may not exist yet
        conn.commit()
    finally:
        conn.close()
