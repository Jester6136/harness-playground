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


def presign_ttcp_object(key: str, *, expires: int = 3600) -> str:
    """Return a time-limited URL the **browser fetches straight from MinIO**.

    The harness API must never proxy these files: a Thanh tra PDF runs to
    500MB / 600+ pages and piping it through the web app would saturate its
    bandwidth and stall the SPA for everyone. Instead the API just *signs* a
    URL (pure crypto, no network call) and MinIO serves the bytes directly —
    the same pattern DataLens already uses for its document links.

    `key` is the full object key. `expires` is the TTL in seconds (default 1h).
    Raises only on misconfiguration (missing creds), not on a missing object.
    """
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": tenant.ttcp_bucket(), "Key": key},
        ExpiresIn=expires,
    )
