"""PostgreSQL connectivity utilities.

Uses psycopg (psycopg3) — same driver as langgraph-checkpoint-postgres.
"""
from psycopg import AsyncConnection

from harness.config import POSTGRES_DSN


async def healthcheck() -> bool:
    """Return True if Postgres is reachable."""
    try:
        conn = await AsyncConnection.connect(POSTGRES_DSN)
        await conn.execute("SELECT 1")
        await conn.close()
        return True
    except Exception:
        return False
