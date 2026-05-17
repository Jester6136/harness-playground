"""Miscellaneous endpoints: /health, /commands, /upload, /reports, /ui."""
from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Header, HTTPException, Request, UploadFile
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    RedirectResponse,
    StreamingResponse,
)
from starlette.concurrency import run_in_threadpool

from harness import tenant
from harness.api.deps import get_user
from harness.config import settings
from harness.extensions.commands import COMMANDS
from harness.persistence.db import healthcheck

log = logging.getLogger(__name__)

router = APIRouter()

_UPLOADS_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"
_STATIC_INDEX = Path(__file__).resolve().parent.parent.parent / "static" / "index.html"
# Where render_ttcp_report writes HTML reports. Resolved once so the
# /reports/{name} endpoint and the tool agree on the same directory.
_REPORTS_DIR = Path(settings.ttcp_report_dir).resolve()


@router.get("/health")
async def health():
    checks: dict[str, Any] = {"status": "ok"}
    checks["postgres"] = "ok" if await healthcheck() else "error"
    return checks


@router.get("/commands")
async def get_commands():
    """Slash command metadata for frontend autocomplete."""
    return {
        "commands": [
            {"name": c.name, "description": c.description, "args": c.args_schema}
            for c in COMMANDS.values()
        ]
    }


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    _user: str = Depends(get_user),
):
    """Accept a file upload, persist it under ./uploads/, return its path.

    PDFs are ALSO mirrored to MinIO ``{ttcp_bucket}/{ttcp_prefix}`` so ad-hoc
    uploads join the offline batch corpus. The MinIO mirror is best-effort —
    a failure there must NOT break the primary (local) upload path, which is
    what `extract_ttcp` reads from. The local filename and the MinIO key
    share the same basename, so one is derivable from the other.
    """
    _UPLOADS_DIR.mkdir(exist_ok=True)
    raw = await file.read()
    ext = Path(file.filename or "upload").suffix or ".bin"
    fname = f"{uuid.uuid4().hex}{ext}"
    dest = _UPLOADS_DIR / fname
    dest.write_bytes(raw)

    minio_key = None
    if ext.lower() == ".pdf":
        try:
            from harness.persistence.minio_store import put_ttcp_object
            minio_key = put_ttcp_object(fname, raw, content_type="application/pdf")
        except Exception:
            log.warning("MinIO mirror failed for %s — local copy still saved", fname,
                        exc_info=True)

    return {"path": str(dest.resolve()), "name": file.filename, "minio_key": minio_key}


@router.get("/files/{key:path}")
async def serve_ttcp_file(
    key: str,
    _user: str = Depends(get_user),
    range_header: str | None = Header(default=None, alias="Range"),
):
    """Stream an object from the TTCP MinIO bucket.

    `key` is the full object key (e.g. ttcp/ttcp-bot/abc.pdf). MinIO isn't
    publicly reachable, so this endpoint proxies it: the API server can reach
    MinIO, clients reach the API. Guarded to the TTCP prefix so it can't be
    used to read arbitrary bucket objects.

    Streamed in 256KB chunks off the event loop (TTCP PDFs run to 500MB / 600+
    pages — buffering the whole blob would stall the server and spike RAM).
    The browser's `Range` header is forwarded to MinIO so the PDF viewer can
    open a 600-page file instantly and fetch only the pages it needs.
    """
    if ".." in key or not key.startswith(tenant.ttcp_prefix()):
        raise HTTPException(status_code=400, detail="invalid key")
    try:
        from harness.persistence.minio_store import open_ttcp_object
        obj = await run_in_threadpool(open_ttcp_object, key, byte_range=range_header)
    except Exception:
        log.warning("could not fetch MinIO object %s", key, exc_info=True)
        raise HTTPException(status_code=404, detail="file not found")

    body = obj["body"]
    filename = key.rsplit("/", 1)[-1] or "file.pdf"
    headers = {
        "Content-Disposition": f'inline; filename="{filename}"',
        "Accept-Ranges": "bytes",
        "Content-Length": str(obj["length"]),
    }
    if obj["content_range"]:
        headers["Content-Range"] = obj["content_range"]

    _CHUNK = 256 * 1024

    async def _iter():
        try:
            while True:
                chunk = await run_in_threadpool(body.read, _CHUNK)
                if not chunk:
                    break
                yield chunk
        finally:
            body.close()

    return StreamingResponse(
        _iter(),
        status_code=obj["status"],
        media_type="application/pdf",
        headers=headers,
    )


@router.get("/reports/{name}", response_class=FileResponse)
async def get_report(name: str, _user: str = Depends(get_user)):
    """Serve a generated TTCP HTML report by file name.

    `render_ttcp_report` writes `reports/<id>.html`; this endpoint hands it
    back so web users open it directly and the Telegram bot can fetch it to
    re-send as a document. No auth: reports contain only already-extracted
    public-document data, and the file name is an unguessable-enough slug.
    """
    # Path-traversal guard: only a bare filename, must stay inside _REPORTS_DIR.
    if "/" in name or "\\" in name or name.startswith("."):
        raise HTTPException(status_code=400, detail="invalid report name")
    target = (_REPORTS_DIR / name).resolve()
    if target.parent != _REPORTS_DIR or not target.is_file():
        raise HTTPException(status_code=404, detail="report not found")
    return FileResponse(target, media_type="text/html", filename=name)


@router.get("/ui", response_class=HTMLResponse, include_in_schema=False)
async def ui(request: Request):
    # Hard auth-gate the UI page itself so unauthenticated users get a clean
    # redirect to /login (rather than seeing the SPA fail every fetch with 401).
    from harness.auth import COOKIE_NAME, read_session
    if not read_session(request.cookies.get(COOKIE_NAME)):
        return RedirectResponse("/login?next=/ui", status_code=303)
    return HTMLResponse(_STATIC_INDEX.read_text())
