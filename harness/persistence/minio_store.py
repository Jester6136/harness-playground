"""Thin MinIO/S3 client for mirroring uploaded files into the TTCP corpus.

The `/upload` endpoint calls `put_ttcp_object` to push uploaded PDFs into
``s3://{ttcp_bucket}/{ttcp_prefix}`` — the same location the offline batch
(``extention_/ttcp_batch``) lists from — so ad-hoc uploads become part of
the corpus the batch processes.

Lazy singleton boto3 client (thread-safe once created). MinIO config is
shared with the batch via the same env vars (see harness.config).
"""
from __future__ import annotations

import logging
from functools import lru_cache

import boto3
from botocore.config import Config

from harness import tenant
from harness.config import settings

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _client():
    return boto3.client(
        "s3",
        endpoint_url=settings.minio_endpoint,
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        config=Config(signature_version="s3v4", retries={"max_attempts": 3}),
    )


def put_ttcp_object(
    key_suffix: str,
    data: bytes,
    *,
    content_type: str = "application/pdf",
) -> str:
    """Upload `data` to ``s3://{ttcp_bucket}/{ttcp_prefix}{key_suffix}``.

    Returns the full object key on success. Raises on failure — the caller
    (the /upload endpoint) treats the MinIO mirror as best-effort and must
    not let a failure here break the primary local-save path.
    """
    # Normalise the prefix: exactly one trailing slash, so a misconfigured
    # TTCP_PREFIX without "/" doesn't produce keys like "ttcp/ttcp-botX.pdf".
    prefix = tenant.ttcp_prefix().rstrip("/") + "/"
    key = f"{prefix}{key_suffix}"
    bucket = tenant.ttcp_bucket()
    _client().put_object(
        Bucket=bucket,
        Key=key,
        Body=data,
        ContentType=content_type,
    )
    log.info("mirrored upload to MinIO: s3://%s/%s", bucket, key)
    return key


def get_ttcp_object(key: str) -> bytes:
    """Download an object's bytes fully into memory by full object key.

    Kept for callers that genuinely need the whole blob. The /files endpoint
    does NOT use this — TTCP PDFs run to 500MB / 600+ pages, so it streams
    via `open_ttcp_object` instead. Raises on missing object / transport error.
    """
    resp = _client().get_object(Bucket=tenant.ttcp_bucket(), Key=key)
    return resp["Body"].read()


def open_ttcp_object(key: str, *, byte_range: str | None = None) -> dict:
    """Open an object for *streaming* (no full-buffer read).

    Returns ``{body, length, total, content_range, status}`` where ``body`` is
    a botocore StreamingBody the caller must read in chunks and close. A
    500MB / 600-page Thanh tra PDF must never be slurped into RAM nor block
    the event loop while a single client downloads it.

    `byte_range` (the raw HTTP ``Range`` header, e.g. ``bytes=0-1048575``) is
    passed straight through to S3 so the browser PDF viewer can fetch one page
    of a 600-page file without pulling the whole object; when honoured, S3
    answers with ``ContentRange`` and we report HTTP 206.
    """
    kwargs: dict = {"Bucket": tenant.ttcp_bucket(), "Key": key}
    if byte_range:
        kwargs["Range"] = byte_range
    resp = _client().get_object(**kwargs)
    content_range = resp.get("ContentRange")
    return {
        "body": resp["Body"],
        "length": resp["ContentLength"],   # bytes in THIS response
        "content_range": content_range,
        "status": 206 if content_range else 200,
    }
