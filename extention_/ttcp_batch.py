"""Batch extract TTCP PDFs from MinIO → ``process_pdf`` → MongoDB.

Một entrypoint duy nhất: liệt kê toàn bộ PDF dưới
``s3://${TTCP_BUCKET}/${TTCP_PREFIX}``, upsert thành rows ``pending`` trong
``${MONGO_DB_NAME}.${TTCP_COLLECTION}``, rồi extract song song và lưu kết quả.

Run (từ project root)::

    python extention_/ttcp_batch.py
    # hoặc tương đương:
    python -m extention_.ttcp_batch

Idempotent — chạy lại an toàn. Lệnh tự reap rows ``running`` đã stale, retry
``error`` cho tới ``TTCP_MAX_ATTEMPTS`` lần, và bump version khi
``TTCP_VERSION`` tăng (kết quả cũ được archive vào ``history``).

Status machine
--------------
- ``pending``  — đã thấy ở MinIO, chưa chạy.
- ``running``  — worker đang giữ (``worker_id`` + ``claimed_at``).
- ``done``     — xong, ``result`` chứa JSON.
- ``error``    — lần gần nhất fail, ``attempts`` < ``max_attempts`` → claim lại.
- ``dead``     — hết quota retry, dừng tự động — reset thủ công nếu muốn.
- ``skipped``  — đánh dấu bỏ qua, không bao giờ claim.
- (``stale``)  — không phải status thật; reaper coi ``running`` quá lâu là stale
                  và reset về ``pending``.

ENV
---
- ``ENDPOINT_URL_MINIO``, ``AWS_ACCESS_KEY_ID_MINIO``, ``AWS_SECRET_ACCESS_KEY_MINIO``
- ``TTCP_BUCKET`` (default ``datalens-data``), ``TTCP_PREFIX`` (default ``ttcp/ttcp-bot/``)
- ``MONGO_URI``, ``MONGO_DB_NAME`` (default ``datalens``), ``TTCP_COLLECTION`` (default ``ttcp-extracted``)
- ``TTCP_BATCH_CONCURRENCY`` (default 40) — số file luôn-luôn-in-flight
- ``TTCP_TIMEOUT_SEC`` (default 800) — hard timeout per file
- ``TTCP_MAX_ATTEMPTS`` (default 3)
- ``TTCP_STALE_AFTER_SEC`` (default 900) — reaper threshold; nên ≥ TIMEOUT_SEC
- ``TTCP_VERSION`` (default 1) — bump để force rerun
- ``ENABLE_THINKING`` (default false) — snapshot vào doc khi chạy
"""
from __future__ import annotations

import argparse
import asyncio
import functools
import io
import json
import logging
import os
import socket
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# Make ``python extention_/ttcp_batch.py`` work the same as ``python -m
# extention_.ttcp_batch`` — direct-script execution doesn't put the project
# root on sys.path, so the ``src.extentions.…`` import below would fail.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import boto3
from botocore.config import Config
from dotenv import load_dotenv
from pymongo import ASCENDING, MongoClient, ReturnDocument
from tqdm import tqdm

load_dotenv()

# ttcp_inference reads ENABLE_THINKING at module-import time, so we import
# AFTER load_dotenv() to make sure .env values are visible to it.
from src.extentions.multimodal.ttcp_inference import process_pdf  # noqa: E402

log = logging.getLogger("ttcp_batch")

# ── config (env-driven) ────────────────────────────────────────────────────

MINIO_ENDPOINT = os.getenv("ENDPOINT_URL_MINIO", "http://192.168.120.12:9002")
MINIO_KEY = os.getenv("AWS_ACCESS_KEY_ID_MINIO", "")
MINIO_SECRET = os.getenv("AWS_SECRET_ACCESS_KEY_MINIO", "")
BUCKET = os.getenv("TTCP_BUCKET", "datalens-data")
PREFIX = os.getenv("TTCP_PREFIX", "ttcp/ttcp-bot/")

MONGO_URI = os.getenv("MONGO_URI", "mongodb://admin:password@192.168.120.12:27017")
MONGO_DB = os.getenv("MONGO_DB_NAME", "datalens")
MONGO_COLL = os.getenv("TTCP_COLLECTION", "ttcp-extracted")

CONCURRENCY = int(os.getenv("TTCP_BATCH_CONCURRENCY", "40"))
MAX_ATTEMPTS = int(os.getenv("TTCP_MAX_ATTEMPTS", "3"))
# Per-file budget for download + process_pdf. Anything slower is killed and
# the row goes back to ``error`` so it can be retried (or marked dead) later.
TIMEOUT_SEC = int(os.getenv("TTCP_TIMEOUT_SEC", "800"))
STALE_AFTER_SEC = int(os.getenv("TTCP_STALE_AFTER_SEC", "900"))
VERSION = int(os.getenv("TTCP_VERSION", "1"))
THINKING = os.getenv("ENABLE_THINKING", "false").strip().lower() == "true"

WORKER_ID = f"{socket.gethostname()}-{os.getpid()}"


# ── clients (lazy module singletons) ───────────────────────────────────────

_s3_client = None
_mongo_client: MongoClient | None = None


def s3():
    """Boto3 S3 client. Thread-safe per boto3 docs once created."""
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client(
            "s3",
            endpoint_url=MINIO_ENDPOINT,
            aws_access_key_id=MINIO_KEY,
            aws_secret_access_key=MINIO_SECRET,
            config=Config(
                signature_version="s3v4",
                retries={"max_attempts": 3},
                # botocore mặc định chỉ 10 HTTP connection → với _IO_POOL
                # (CONCURRENCY+8) tải MinIO song song sẽ bị "connection pool is
                # full, discarding connection". Cho khớp mức song song.
                max_pool_connections=CONCURRENCY + 8,
            ),
        )
    return _s3_client


def coll():
    """MongoDB collection — single MongoClient reused (pool inside)."""
    global _mongo_client
    if _mongo_client is None:
        _mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    return _mongo_client[MONGO_DB][MONGO_COLL]


# Dedicated thread pool for blocking I/O (S3 download + Mongo claim/mark).
# `asyncio.to_thread` shares ONE small default pool (min(32, cpu+4)); with
# CONCURRENCY≈40, slow downloads there starve the scheduler's claim_one calls
# → the in-flight pool drains then refills in waves. A pool sized to
# CONCURRENCY + headroom keeps claims/marks from queueing behind downloads so
# the pool stays full and vLLM gets a steady request stream.
_IO_POOL = ThreadPoolExecutor(
    max_workers=CONCURRENCY + 8, thread_name_prefix="ttcp-io"
)


async def _io(fn, *args):
    """Run a blocking fn on the dedicated I/O pool (not the shared default)."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_IO_POOL, functools.partial(fn, *args))


def ensure_indexes() -> None:
    """Indexes used by claim_one()'s filter+sort and stats aggregation."""
    c = coll()
    c.create_index([("status", ASCENDING), ("attempts", ASCENDING)], name="status_attempts")
    c.create_index([("claimed_at", ASCENDING)], name="claimed_at")


def now() -> datetime:
    return datetime.now(timezone.utc)


# ── phase 1: discover MinIO objects → upsert pending rows ──────────────────


def sync_index() -> dict:
    """List MinIO PDFs and upsert into mongo as ``pending``.

    Idempotent. Three outcomes per object:
      - new key → insert ``status="pending"``.
      - existing key, ``version`` < current VERSION & ``status="done"`` →
        archive old ``result`` into ``history[]``, reset to ``pending``.
      - else → leave untouched (running/done/error/dead/skipped all kept).
    """
    c = coll()
    paginator = s3().get_paginator("list_objects_v2")

    seen = new = bumped = 0
    for page in paginator.paginate(Bucket=BUCKET, Prefix=PREFIX):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if not key.lower().endswith(".pdf"):
                continue
            seen += 1
            doc = c.find_one(
                {"_id": key},
                {"version": 1, "status": 1, "result": 1, "thinking": 1},
            )
            if doc is None:
                c.insert_one({
                    "_id": key,
                    "bucket": BUCKET,
                    "etag": obj.get("ETag", "").strip('"'),
                    "size": obj.get("Size"),
                    "last_modified": obj.get("LastModified"),
                    "status": "pending",
                    "version": VERSION,
                    "thinking": THINKING,
                    "attempts": 0,
                    "max_attempts": MAX_ATTEMPTS,
                    "worker_id": None,
                    "claimed_at": None,
                    "started_at": None,
                    "finished_at": None,
                    "last_error": None,
                    "result": None,
                    "history": [],
                    "created_at": now(),
                    "updated_at": now(),
                })
                new += 1
            elif doc.get("version", 1) < VERSION and doc.get("status") == "done":
                c.update_one(
                    {"_id": key},
                    {
                        "$push": {"history": {
                            "version": doc.get("version"),
                            "thinking": doc.get("thinking"),
                            "result": doc.get("result"),
                            "archived_at": now(),
                        }},
                        "$set": {
                            "status": "pending",
                            "version": VERSION,
                            "thinking": THINKING,
                            "attempts": 0,
                            "worker_id": None,
                            "claimed_at": None,
                            "started_at": None,
                            "finished_at": None,
                            "last_error": None,
                            "result": None,
                            "updated_at": now(),
                        },
                    },
                )
                bumped += 1

    return {"seen": seen, "new": new, "bumped": bumped}


# ── reaper: running > STALE_AFTER_SEC → pending ────────────────────────────


def reap_stale() -> int:
    cutoff = datetime.fromtimestamp(now().timestamp() - STALE_AFTER_SEC, tz=timezone.utc)
    res = coll().update_many(
        {"status": "running", "claimed_at": {"$lt": cutoff}},
        {"$set": {
            "status": "pending",
            "worker_id": None,
            "claimed_at": None,
            "updated_at": now(),
        }},
    )
    return res.modified_count


# ── claim + mark transitions ───────────────────────────────────────────────


def claim_one() -> Optional[dict]:
    """Atomically pick one pending / retry-eligible error row.

    ``attempts`` is incremented on claim so a worker crash before mark_done()
    still consumes one retry budget — prevents tight infinite-retry loops.
    """
    return coll().find_one_and_update(
        {"$or": [
            {"status": "pending"},
            {"status": "error", "attempts": {"$lt": MAX_ATTEMPTS}},
        ]},
        {
            "$set": {
                "status": "running",
                "worker_id": WORKER_ID,
                "claimed_at": now(),
                "started_at": now(),
                "updated_at": now(),
            },
            "$inc": {"attempts": 1},
        },
        sort=[("attempts", ASCENDING), ("_id", ASCENDING)],
        return_document=ReturnDocument.AFTER,
    )


def mark_done(key: str, result: Any) -> None:
    coll().update_one(
        {"_id": key},
        {"$set": {
            "status": "done",
            "result": result,
            "last_error": None,
            "finished_at": now(),
            "updated_at": now(),
        }},
    )


def mark_error(key: str, err: str, attempts: int) -> None:
    final = "dead" if attempts >= MAX_ATTEMPTS else "error"
    coll().update_one(
        {"_id": key},
        {"$set": {
            "status": final,
            "last_error": err[:2000],
            "finished_at": now(),
            "updated_at": now(),
        }},
    )


def reset_failed(include_dead: bool = True) -> int:
    """Reset ``error`` (and optionally ``dead``) rows back to ``pending``.

    Use this when MAX_ATTEMPTS got hit (e.g. all 1/1 timeouts) and rows are
    stuck as ``dead`` so claim_one() ignores them. Clears ``attempts`` so
    they get a full retry budget again. Triggered by ``--retry-failed``.
    """
    statuses = ["error"] + (["dead"] if include_dead else [])
    res = coll().update_many(
        {"status": {"$in": statuses}},
        {"$set": {
            "status": "pending",
            "attempts": 0,
            "worker_id": None,
            "claimed_at": None,
            "started_at": None,
            "finished_at": None,
            "last_error": None,
            "updated_at": now(),
        }},
    )
    return res.modified_count


def count_workload() -> int:
    """Rows that ``claim_one()`` will eventually pick up — used for tqdm total."""
    return coll().count_documents({"$or": [
        {"status": "pending"},
        {"status": "error", "attempts": {"$lt": MAX_ATTEMPTS}},
    ]})


# ── async work loop ────────────────────────────────────────────────────────


async def _download(key: str) -> io.BytesIO:
    def _do() -> io.BytesIO:
        buf = io.BytesIO()
        s3().download_fileobj(BUCKET, key, buf)
        buf.seek(0)
        return buf
    return await _io(_do)


async def _extract(key: str) -> Any:
    """Download + extract; returns the parsed-JSON result (or ``{"_raw": str}``
    if the model output isn't valid JSON for some reason)."""
    pdf_bytes = await _download(key)
    raw = await process_pdf(pdf_bytes)
    try:
        return json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError):
        return {"_raw": raw}


async def _process_one(doc: dict) -> bool:
    """Returns True on success, False on error/timeout. Never raises.

    Hard timeout via ``asyncio.wait_for`` so a stuck vLLM call can't tie up
    a slot forever — the row falls back to ``error`` and gets retried (or
    promoted to ``dead`` after MAX_ATTEMPTS).
    """
    key = doc["_id"]
    attempts = doc.get("attempts", 1)
    try:
        parsed = await asyncio.wait_for(_extract(key), timeout=TIMEOUT_SEC)
        await _io(mark_done, key, parsed)
        log.info("✓ %s", key)
        return True
    except asyncio.TimeoutError:
        log.warning("⏱ %s timed out >%ds (attempt %d/%d)", key, TIMEOUT_SEC, attempts, MAX_ATTEMPTS)
        await _io(mark_error, key, f"TimeoutError: exceeded {TIMEOUT_SEC}s", attempts)
        return False
    except Exception as exc:
        log.exception("✗ %s (attempt %d/%d)", key, attempts, MAX_ATTEMPTS)
        await _io(mark_error, key, f"{type(exc).__name__}: {exc}", attempts)
        return False


async def run_loop() -> dict:
    """Top-up scheduler: keep ≤ CONCURRENCY tasks in flight until claim_one
    returns None AND nothing is in flight. tqdm tracks throughput; counters
    in postfix show running done/error breakdown."""
    tasks: set[asyncio.Task] = set()
    counters = {"done": 0, "error": 0}

    initial = await _io(count_workload)
    pbar = tqdm(total=initial, desc="extract", unit="pdf", dynamic_ncols=True)

    async def _refill() -> int:
        """Claim up to the number of free slots IN PARALLEL and start them.
        Parallel claim (vs the old one-at-a-time await) refills freed slots
        immediately so ~CONCURRENCY files stay in flight → vLLM keeps a steady
        request stream instead of running in waves. Returns #started."""
        free = CONCURRENCY - len(tasks)
        if free <= 0:
            return 0
        docs = await asyncio.gather(*(_io(claim_one) for _ in range(free)))
        started = 0
        for doc in docs:
            if doc is not None:
                tasks.add(asyncio.create_task(_process_one(doc)))
                started += 1
        return started

    # Retries re-enter the workload after a fail, so the real total can grow
    # beyond `initial`. We bump total whenever the pool is refilled.
    try:
        while True:
            await _refill()
            if not tasks:
                break  # drained: nothing claimable, nothing in flight

            done, pending = await asyncio.wait(
                tasks, return_when=asyncio.FIRST_COMPLETED
            )
            tasks = set(pending)  # robust: rebuild from what's still running
            for d in done:
                try:
                    ok = d.result()
                except Exception:
                    # _process_one should never raise; defensive bucket.
                    ok = False
                counters["done" if ok else "error"] += 1
                pbar.update(1)
            # Keep total honest if retries pushed us past initial estimate.
            if pbar.n > pbar.total:
                pbar.total = pbar.n + len(tasks)
            pbar.set_postfix(counters, refresh=False)
    finally:
        pbar.close()
        _IO_POOL.shutdown(wait=False, cancel_futures=True)

    return counters


def stats() -> dict:
    pipeline = [{"$group": {"_id": "$status", "n": {"$sum": 1}}}]
    return {r["_id"]: r["n"] for r in coll().aggregate(pipeline)}


# ── entrypoint ─────────────────────────────────────────────────────────────


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="TTCP batch extractor (MinIO → vLLM → Mongo)")
    p.add_argument(
        "--retry-failed", action="store_true",
        help="Reset error+dead rows to pending before processing (clears attempts).",
    )
    p.add_argument(
        "--retry-errors-only", action="store_true",
        help="Like --retry-failed but skip 'dead' rows (only retries 'error').",
    )
    p.add_argument(
        "--stats-only", action="store_true",
        help="Print status breakdown and exit. No MinIO listing, no extraction.",
    )
    return p.parse_args()


async def main() -> None:
    args = _parse_args()
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    log.info(
        "worker=%s bucket=%s prefix=%s db=%s coll=%s concurrency=%d timeout=%ds thinking=%s version=%d",
        WORKER_ID, BUCKET, PREFIX, MONGO_DB, MONGO_COLL, CONCURRENCY, TIMEOUT_SEC, THINKING, VERSION,
    )

    ensure_indexes()  # also creates the Mongo client once (single-thread)
    s3()               # pre-warm the boto3 client before parallel downloads
                       # race-create it (40 concurrent _io calls at startup).

    if args.stats_only:
        log.info("stats: %s", await asyncio.to_thread(stats))
        return

    if args.retry_failed or args.retry_errors_only:
        n = await asyncio.to_thread(reset_failed, not args.retry_errors_only)
        log.info("reset %d failed rows → pending", n)

    s = await asyncio.to_thread(sync_index)
    log.info("sync_index: %s", s)

    reaped = await asyncio.to_thread(reap_stale)
    if reaped:
        log.info("reaped %d stale running rows", reaped)

    t0 = time.monotonic()
    res = await run_loop()
    elapsed = time.monotonic() - t0
    log.info("run_loop done in %.1fs: %s", elapsed, res)
    log.info("final stats: %s", await asyncio.to_thread(stats))

    # Trigger downstream sync ONCE if this run produced new docs — firing per
    # mark_done would hammer the sync endpoint with hundreds of POSTs. block=True
    # because the process is about to exit (a daemon thread would be killed
    # before the request completes).
    if res.get("done"):
        from harness.persistence.sync_hook import notify_ttcp_sync
        await asyncio.to_thread(notify_ttcp_sync, "batch", block=True)


if __name__ == "__main__":
    asyncio.run(main())
