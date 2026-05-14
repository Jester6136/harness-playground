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
    key = f"{settings.ttcp_prefix}{key_suffix}"
    _client().put_object(
        Bucket=settings.ttcp_bucket,
        Key=key,
        Body=data,
        ContentType=content_type,
    )
    log.info("mirrored upload to MinIO: s3://%s/%s", settings.ttcp_bucket, key)
    return key


def get_ttcp_object(key: str) -> bytes:
    """Download an object's bytes from the TTCP bucket by full object key.

    Raises on a missing object or transport error — the caller (the /files
    endpoint) maps that to a 404. PDFs in this corpus are a few MB, so
    reading fully into memory is fine.
    """
    resp = _client().get_object(Bucket=settings.ttcp_bucket, Key=key)
    return resp["Body"].read()
