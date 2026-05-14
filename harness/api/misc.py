"""Miscellaneous endpoints: /health, /commands, /upload, /ui."""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from harness.api.deps import get_user
from harness.config import settings
from harness.extensions.commands import COMMANDS
from harness.persistence.db import healthcheck

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
    """Accept a file upload, persist it under ./uploads/, return its path."""
    _UPLOADS_DIR.mkdir(exist_ok=True)
    ext = Path(file.filename or "upload").suffix or ".bin"
    fname = f"{uuid.uuid4().hex}{ext}"
    dest = _UPLOADS_DIR / fname
    dest.write_bytes(await file.read())
    return {"path": str(dest.resolve()), "name": file.filename}


@router.get("/reports/{name}", response_class=FileResponse)
async def get_report(name: str):
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
async def ui():
    return HTMLResponse(_STATIC_INDEX.read_text())
