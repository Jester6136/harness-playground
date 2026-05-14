"""Thin httpx wrapper for the harness `/upload` endpoint.

Channels POST file bytes here and get back the server-side absolute path
(which they embed into the chat message so the agent's vision/extraction
tools can open it directly) plus the MinIO key when the file was mirrored
to the TTCP corpus bucket.
"""
from __future__ import annotations

import httpx


async def upload_bytes(
    *,
    api_url: str,
    data: bytes,
    filename: str,
    headers: dict | None = None,
    timeout: float = 120.0,
) -> dict:
    """POST `data` (raw bytes) as multipart to `{api_url}/upload`.

    Returns the full JSON payload: `{path, name, minio_key}`. `path` is the
    absolute path the API persisted the file to (what extraction tools read);
    `minio_key` is the MinIO object key if the file was mirrored to the TTCP
    corpus bucket (PDFs only), else None. Raises on HTTP errors — caller
    decides whether to surface or retry.
    """
    files = {"file": (filename, data)}
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(
            f"{api_url.rstrip('/')}/upload",
            files=files,
            headers=headers or {},
        )
        r.raise_for_status()
        return r.json()
