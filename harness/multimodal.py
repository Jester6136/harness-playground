"""Helpers for turning image/PDF files into LangChain message content.

Pipeline:
  1. PDF → render with the fast C-based renderer
     (``src/extentions/pdf_process/pdf_ultra_fast.py``). Falls back to
     ``pdf2image`` if the shared library / module is unavailable.
  2. Image → decode with OpenCV.
  3. Both → batch-detect page orientation with the ONNX MobileNet
     (``src/extentions/rotate_images/dat.py``) and rotate to upright so
     the VLM never sees a sideways/upside-down page.
  4. Re-encode each frame as JPEG and emit ``image_url`` content blocks
     (``data:image/jpeg;base64,...``) — VLMs require a real image MIME,
     and the C renderer outputs raw RGB, so re-encoding is mandatory.
"""
from __future__ import annotations

import base64
import io
import mimetypes
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np


# ── Orientation detector (lazy singleton) ───────────────────────────────────


@lru_cache(maxsize=1)
def _orientation_detector():
    """Return a cached OrientationDetector or None if unavailable."""
    try:
        from src.extentions.rotate_images.dat import OrientationDetector

        return OrientationDetector()
    except Exception:
        return None


def _rotate_to_upright(img_bgr: np.ndarray, angle: int) -> np.ndarray:
    if angle == 90:
        return cv2.rotate(img_bgr, cv2.ROTATE_90_COUNTERCLOCKWISE)
    if angle == 180:
        return cv2.rotate(img_bgr, cv2.ROTATE_180)
    if angle == 270:
        return cv2.rotate(img_bgr, cv2.ROTATE_90_CLOCKWISE)
    return img_bgr


def _autorotate_batch(bgrs: list[np.ndarray]) -> list[np.ndarray]:
    """Detect orientation for a batch of BGR images, rotate to upright."""
    detector = _orientation_detector()
    if detector is None or not bgrs:
        return bgrs
    try:
        streams: list[io.BytesIO] = []
        for bgr in bgrs:
            ok, jpg = cv2.imencode(".jpg", bgr)
            if not ok:
                return bgrs
            streams.append(io.BytesIO(jpg.tobytes()))
        angles = detector.get_orientations_from_images_batch(streams)
        return [_rotate_to_upright(b, int(a)) for b, a in zip(bgrs, angles)]
    except Exception:
        return bgrs


# ── Encoding helpers ────────────────────────────────────────────────────────


def _bgr_to_jpeg(img_bgr: np.ndarray, quality: int = 90) -> bytes:
    ok, buf = cv2.imencode(
        ".jpg", img_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), quality]
    )
    if not ok:
        raise RuntimeError("Failed to encode image as JPEG")
    return buf.tobytes()


def _jpeg_to_content(jpeg: bytes) -> dict:
    data = base64.b64encode(jpeg).decode()
    return {
        "type": "image_url",
        "image_url": {"url": f"data:image/jpeg;base64,{data}"},
    }


def _raw_rgb_to_bgr(b64_str: str, width: int, height: int) -> np.ndarray:
    raw = base64.b64decode(b64_str)
    arr = np.frombuffer(raw, dtype=np.uint8).reshape((height, width, 3))
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)


# ── Public API ──────────────────────────────────────────────────────────────


def image_path_to_content(path: str | Path) -> dict:
    """Return a LangChain image_url content block from a local image file."""
    p = Path(path)
    img = cv2.imread(str(p), cv2.IMREAD_COLOR)
    if img is None:
        # Format OpenCV cannot decode (e.g. HEIC). Pass through raw bytes.
        mime, _ = mimetypes.guess_type(str(p))
        if not mime or not mime.startswith("image/"):
            mime = "image/jpeg"
        data = base64.b64encode(p.read_bytes()).decode()
        return {
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{data}"},
        }

    img = _autorotate_batch([img])[0]
    return _jpeg_to_content(_bgr_to_jpeg(img))


def pdf_to_image_contents(
    path: str | Path,
    dpi: float = 144,
    max_workers: int = 8,
) -> list[dict]:
    """Convert a PDF to a list of image_url content blocks (one per page).

    Uses the fast C-based renderer when available; falls back to
    ``pdf2image`` + poppler. Pages are batch-rotated to upright before
    being re-encoded as JPEG.
    """
    bgrs = _render_pdf(path, dpi=dpi, max_workers=max_workers)
    if not bgrs:
        return []
    bgrs = _autorotate_batch(bgrs)
    return [_jpeg_to_content(_bgr_to_jpeg(b)) for b in bgrs]


def file_to_contents(path: str | Path) -> list[dict]:
    """Auto-detect file type and return a list of content blocks.

    - Images: one block.
    - PDFs: one block per page.
    - Anything else: empty list (unsupported).
    """
    p = Path(path)
    if p.suffix.lower() == ".pdf":
        return pdf_to_image_contents(p)
    return [image_path_to_content(p)]


# ── PDF rendering (fast path + fallback) ────────────────────────────────────


def _render_pdf(
    path: str | Path, dpi: float, max_workers: int
) -> list[np.ndarray]:
    try:
        from src.extentions.pdf_process.pdf_ultra_fast import (
            pdf_to_base64_parallel,
        )
    except Exception:
        return _render_pdf_fallback(path, dpi=dpi)

    try:
        pages = pdf_to_base64_parallel(
            str(path), dpi=dpi, max_workers=max_workers, verbose=False
        )
    except Exception:
        return _render_pdf_fallback(path, dpi=dpi)

    return [_raw_rgb_to_bgr(p["base64"], p["width"], p["height"]) for p in pages]


def _render_pdf_fallback(path: str | Path, dpi: float) -> list[np.ndarray]:
    try:
        from pdf2image import convert_from_path
    except ImportError:
        return []

    pages = convert_from_path(str(path), dpi=int(dpi))
    out: list[np.ndarray] = []
    for page in pages:
        buf = io.BytesIO()
        page.save(buf, format="JPEG")
        bgr = cv2.imdecode(
            np.frombuffer(buf.getvalue(), np.uint8), cv2.IMREAD_COLOR
        )
        if bgr is not None:
            out.append(bgr)
    return out
