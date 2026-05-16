"""Display titles for chat sessions (sidebar labels).

Stored separately from the LangGraph checkpointer (Postgres) because:
  - The session's stable identifier is the thread_id; we never want to
    change it (Postgres rows are keyed on it).
  - The display title is mutable (auto-generated from the first message,
    can be renamed by the user later).
  - One small Mongo collection, indexed for sidebar listing.

Doc shape: ``{_id: "<user>:<session>", title: str, updated_at: datetime}``.
"""
from __future__ import annotations

from datetime import datetime, timezone

from pymongo import DESCENDING, MongoClient

from harness.config import settings

_COLLECTION = "session_titles"
_client: MongoClient | None = None


def _coll():
    global _client
    if _client is None:
        _client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=5000)
    coll = _client[settings.mongo_db_name][_COLLECTION]
    # Cheap: createIndex is idempotent.
    coll.create_index([("updated_at", DESCENDING)])
    return coll


def _now() -> datetime:
    return datetime.now(timezone.utc)


def set_title(thread_id: str, title: str) -> None:
    """Upsert a title for a thread (truncates to 120 chars defensively)."""
    title = (title or "").strip()[:120]
    if not title:
        return
    _coll().update_one(
        {"_id": thread_id},
        {"$set": {"title": title, "updated_at": _now()}},
        upsert=True,
    )


def set_title_if_missing(thread_id: str, title: str) -> None:
    """Only writes if no title exists yet — for the auto-derived first-message
    title, so a later manual rename via :func:`set_title` is not overwritten
    by a subsequent run that misdetects "first message".

    No upsert: relies on :func:`touch` having created the doc at request start
    (avoids DuplicateKeyError if a stale title doc survives a manual cleanup).
    """
    title = (title or "").strip()[:120]
    if not title:
        return
    _coll().update_one(
        {"_id": thread_id, "title": {"$exists": False}},
        {"$set": {"title": title, "updated_at": _now()}},
    )


def get_titles_for_user(user_id: str) -> dict[str, dict]:
    """Return ``{session_id: {title, updated_at}}`` for one user.

    Returns ALL of the user's titled sessions; caller filters/joins against
    the Postgres-derived session list.
    """
    prefix = f"{user_id}:"
    out: dict[str, dict] = {}
    for d in _coll().find({"_id": {"$regex": f"^{prefix}"}}):
        sid = d["_id"][len(prefix):]
        out[sid] = {
            "title": d.get("title", ""),
            "updated_at": d.get("updated_at"),
        }
    return out


def delete_title(thread_id: str) -> None:
    _coll().delete_one({"_id": thread_id})


def touch(thread_id: str) -> None:
    """Bump ``updated_at`` (for sidebar "most recent on top" ordering).
    Creates the doc if it doesn't exist yet (no title field — that's set by
    :func:`set_title_if_missing` after the first user message)."""
    _coll().update_one(
        {"_id": thread_id},
        {"$set": {"updated_at": _now()}},
        upsert=True,
    )
