"""Reusable async MongoDB collection wrapper (Motor).

One `MongoStore` instance corresponds to one (db, collection) pair. Multiple
stores in the same process share a single `AsyncIOMotorClient` — Motor pools
sockets internally, so this is cheap.

Caller picks the collection name; this class only knows about the standard
CRUD + text-search operations the harness tools need. Connection is lazy and
closed by `close_mongo()` (call from app shutdown).
"""
from __future__ import annotations

import logging
import re
from typing import Any

from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorCollection,
)

from harness.config import settings

log = logging.getLogger(__name__)

_client: AsyncIOMotorClient | None = None


def _redact(uri: str) -> str:
    """Mask user:pass in a Mongo URI for log output."""
    return re.sub(r"://[^/@]*@", "://<redacted>@", uri)


def _get_client() -> AsyncIOMotorClient:
    """Lazy-init the shared Motor client. Safe to call from any coroutine."""
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(
            settings.mongo_uri,
            serverSelectionTimeoutMS=5000,
            uuidRepresentation="standard",
        )
        log.info("MongoDB client initialised: %s", _redact(settings.mongo_uri))
    return _client


async def close_mongo() -> None:
    """Close the shared client. Idempotent."""
    global _client
    if _client is not None:
        _client.close()
        _client = None


def _stringify_id(doc: dict | None) -> dict | None:
    """Mongo `_id` is an ObjectId — JSON-serialise it as str so tool callers
    (which `json.dumps` the result) don't blow up."""
    if doc is not None and "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc


class MongoStore:
    """Async CRUD + text-search wrapper around a single collection."""

    def __init__(self, db_name: str, collection: str) -> None:
        self._db_name = db_name
        self._collection_name = collection

    @property
    def _coll(self) -> AsyncIOMotorCollection:
        return _get_client()[self._db_name][self._collection_name]

    # ── core CRUD ───────────────────────────────────────────────────────────

    async def insert_one(self, doc: dict) -> str:
        result = await self._coll.insert_one(doc)
        return str(result.inserted_id)

    async def upsert_one(self, key_filter: dict, doc: dict) -> dict[str, Any]:
        """Match by `key_filter`, replace the matched doc with `doc` (or insert).

        Returns `{matched, modified, upserted_id}` so callers can tell whether
        this was a fresh insert or an overwrite.
        """
        result = await self._coll.replace_one(key_filter, doc, upsert=True)
        return {
            "matched": result.matched_count,
            "modified": result.modified_count,
            "upserted_id": str(result.upserted_id) if result.upserted_id else None,
        }

    async def find_one(self, filter: dict) -> dict | None:
        return _stringify_id(await self._coll.find_one(filter))

    async def find_many(self, filter: dict, *, limit: int = 50) -> list[dict]:
        cursor = self._coll.find(filter).limit(limit)
        return [_stringify_id(d) async for d in cursor]

    async def update_one(self, filter: dict, set_fields: dict) -> dict[str, Any]:
        """Apply a `$set` update to one matched doc. Returns counts."""
        result = await self._coll.update_one(filter, {"$set": set_fields})
        return {"matched": result.matched_count, "modified": result.modified_count}

    async def delete_one(self, filter: dict) -> int:
        result = await self._coll.delete_one(filter)
        return result.deleted_count

    # ── text search ─────────────────────────────────────────────────────────

    async def text_search(self, query: str, *, limit: int = 20) -> list[dict]:
        """`$text` search, sorted by relevance. Requires a text index on the
        target fields — call `ensure_text_index(...)` once at startup."""
        cursor = (
            self._coll.find(
                {"$text": {"$search": query}},
                {"score": {"$meta": "textScore"}},
            )
            .sort([("score", {"$meta": "textScore"})])
            .limit(limit)
        )
        return [_stringify_id(d) async for d in cursor]

    async def ensure_text_index(
        self,
        fields: list[str],
        *,
        name: str = "text_idx",
        default_language: str = "none",
    ) -> None:
        """Idempotent: create a text index over `fields` if not already present.

        `default_language="none"` disables stemming — important for Vietnamese
        where Mongo's English stemmer would mangle accented words.
        """
        spec = [(f, "text") for f in fields]
        try:
            await self._coll.create_index(spec, name=name, default_language=default_language)
        except Exception as exc:
            # Common: index already exists with the same spec — driver raises
            # OperationFailure with codeName "IndexOptionsConflict" only when
            # spec differs. Log and continue.
            log.debug("ensure_text_index(%s): %s", name, exc)

    # ── housekeeping ────────────────────────────────────────────────────────

    async def count(self, filter: dict | None = None) -> int:
        return await self._coll.count_documents(filter or {})
