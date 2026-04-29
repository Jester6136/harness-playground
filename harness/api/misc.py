"""Miscellaneous endpoints: /health, /commands, /upload, /ui."""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import HTMLResponse

from harness.api.deps import get_user
from harness.extensions.commands import COMMANDS
from harness.persistence.db import healthcheck

router = APIRouter()

_UPLOADS_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"
_STATIC_INDEX = Path(__file__).resolve().parent.parent.parent / "static" / "index.html"


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


@router.get("/ui", response_class=HTMLResponse, include_in_schema=False)
async def ui():
    return HTMLResponse(_STATIC_INDEX.read_text())
