"""PostgreSQL connectivity utilities.

Uses psycopg (psycopg3) — same driver as langgraph-checkpoint-postgres.
"""
from harness.config import POSTGRES_DSN


async def healthcheck() -> bool:
    """Return True if Postgres is reachable."""
    try:
        from psycopg import AsyncConnection
        conn = await AsyncConnection.connect(POSTGRES_DSN)
        await conn.execute("SELECT 1")
        await conn.close()
        return True
    except Exception:
        return False
