"""Helpers for turning image/PDF files into LangChain message content.

These are utility functions used by the analyze_image tool and the API upload
handler. They convert local file paths into base64 data URIs so the VLM can
process them without a public URL.
"""
from __future__ import annotations

import base64
import mimetypes
from pathlib import Path


def image_path_to_content(path: str | Path) -> dict:
    """Return a LangChain image_url content block from a local image file."""
    p = Path(path)
    mime, _ = mimetypes.guess_type(str(p))
    if not mime or not mime.startswith("image/"):
        mime = "image/jpeg"
    data = base64.b64encode(p.read_bytes()).decode()
    return {
        "type": "image_url",
        "image_url": {"url": f"data:{mime};base64,{data}"},
    }


def pdf_to_image_contents(path: str | Path, dpi: int = 150) -> list[dict]:
    """Convert a PDF to a list of image_url content blocks (one per page).

    Requires `pdf2image` + poppler. Falls back gracefully if not installed.
    """
    try:
        from pdf2image import convert_from_path
    except ImportError:
        return []

    pages = convert_from_path(str(path), dpi=dpi)
    results = []
    for page in pages:
        import io
        buf = io.BytesIO()
        page.save(buf, format="JPEG")
        data = base64.b64encode(buf.getvalue()).decode()
        results.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{data}"},
        })
    return results


def file_to_contents(path: str | Path) -> list[dict]:
    """Auto-detect file type and return a list of content blocks.

    - Images: one block.
    - PDFs: one block per page.
    - Anything else: empty list (unsupported).
    """
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".pdf":
        return pdf_to_image_contents(p)
    return [image_path_to_content(p)]
