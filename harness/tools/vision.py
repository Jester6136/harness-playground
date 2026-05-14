"""Vision tools — analyze images / PDFs, and extract Vietnamese kết luận thanh tra (TTCP).

The multimodal preprocessing (PDF render + page-orientation correction)
delegates to `src.extentions.multimodal.make.pdf_to_corrected_images`, which
uses pypdfium2 + an ONNX orientation detector to feed the VLM upright pages.
"""
from __future__ import annotations

import base64
import io
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from PIL import Image

from harness.llm import make_llm
from harness.logging_config import log_tool_call
from src.extentions.multimodal.make import pdf_to_corrected_images
from src.extentions.multimodal.prompt import ttcp_extract_prompt, ttcp_system_prompt


_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}


def _image_to_b64_png(path: Path) -> str:
    img = Image.open(path).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _file_to_image_blocks(path: str | Path) -> list[dict]:
    """Turn an image or PDF file into a list of LangChain image_url content blocks."""
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".pdf":
        with open(p, "rb") as f:
            pdf_bytesio = io.BytesIO(f.read())
        b64s = pdf_to_corrected_images(pdf_bytesio)
    elif suffix in _IMAGE_SUFFIXES:
        b64s = [_image_to_b64_png(p)]
    else:
        return []
    return [
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b}"}}
        for b in b64s
    ]


@tool
@log_tool_call
def analyze_image(path: str, question: str = "Describe this image in detail.") -> str:
    """General-purpose image with the vision model.

    Use this for free-form questions about photos, scanned documents, charts,
    diagrams, etc. Supports JPEG, PNG, GIF, WebP, BMP and PDF (pages are
    rendered and auto-rotated to upright before being sent).

    DO NOT use this for Vietnamese kết luận thanh tra (thông báo / quyết định
    của Thanh tra Chính phủ) — call `extract_ttcp(path)` instead, which
    returns a canonical JSON schema. Routing the wrong tool wastes tokens
    and gives unstructured output.
    """
    blocks = _file_to_image_blocks(path)
    if not blocks:
        return f"ERROR: unsupported or unreadable file: {path}"

    vlm = make_llm()
    msg = HumanMessage(content=[{"type": "text", "text": question}] + blocks)
    # callbacks=[] keeps inner VLM tokens out of the outer SSE stream.
    response = vlm.invoke([msg], config={"callbacks": []})
    return response.content


@tool
@log_tool_call
def extract_ttcp(path: str) -> str:
    """Trích xuất PDF kết luận / thông báo thanh tra (TTCP) sang JSON.

    Dùng tool này cho mọi loại văn bản của Thanh tra Chính phủ: kết luận
    thanh tra, thông báo kết luận thanh tra, quyết định xử phạt. Đưa về cấu
    trúc JSON gồm 3 khối: `thông tin chung`, `vi phạm[]`, `kiến nghị xử lý`.
    Không rút gọn — giữ đầy đủ số liệu, mô tả, căn cứ pháp luật.
    """
    blocks = _file_to_image_blocks(path)
    if not blocks:
        return f"ERROR: unsupported or unreadable file: {path}"

    vlm = make_llm(temperature=0.0).bind(response_format={"type": "json_object"})
    messages = [
        SystemMessage(content=ttcp_system_prompt),
        HumanMessage(content=[{"type": "text", "text": ttcp_extract_prompt}] + blocks),
    ]
    response = vlm.invoke(messages, config={"callbacks": []})
    return response.content


# ── prompt hints ──────────────────────────────────────────────────────────

analyze_image.metadata = {
    "prompt_hint": (
        "General image/PDF Q&A. KHÔNG dùng cho kết luận thanh tra — gọi "
        "extract_ttcp thay vì cái này."
    ),
}
extract_ttcp.metadata = {
    "prompt_hint": (
        "BẮT BUỘC dùng (không phải analyze_image) khi file là văn bản thanh tra "
        "(kết luận / thông báo / quyết định của Thanh tra Chính phủ). Trả về "
        "JSON với 'thông tin chung', 'vi phạm', 'kiến nghị xử lý'."
    ),
}
