"""Miscellaneous endpoints: /health, /commands, /upload, /reports, /ui."""
from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

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


# NOTE: there is deliberately no /files proxy endpoint. TTCP PDFs run to
# 500MB / 600+ pages — piping them through the web app would saturate its
# bandwidth and stall the SPA for everyone. `get_ttcp_file` hands the browser
# a presigned MinIO URL instead, so MinIO serves the bytes directly.


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
