"""Vision tools — analyze images / PDFs, and extract Vietnamese land certificates (GCN).

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
from src.extentions.multimodal.prompt import pdf_detect_prompt, system_prompt


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


@tool(metadata={
    "prompt_hint": (
        "general image/PDF Q&A. Do NOT use for Vietnamese Giấy chứng nhận "
        "(GCN / sổ đỏ / sổ hồng / Certificate of Land Use Rights) — those go "
        "to `extract_gcn` for structured JSON extraction."
    ),
})
@log_tool_call
def analyze_image(path: str, question: str = "Describe this image in detail.") -> str:
    """General-purpose image / PDF question answering with the vision model.

    Use this for free-form questions about photos, scanned documents, charts,
    diagrams, etc. Supports JPEG, PNG, GIF, WebP, BMP and PDF (pages are
    rendered and auto-rotated to upright before being sent).

    DO NOT use this for Vietnamese Giấy chứng nhận quyền sử dụng đất (GCN,
    sổ đỏ, sổ hồng) — call `extract_gcn(path)` instead, which returns a
    canonical JSON schema. Routing the wrong tool wastes tokens and gives
    unstructured output.
    """
    blocks = _file_to_image_blocks(path)
    if not blocks:
        return f"ERROR: unsupported or unreadable file: {path}"

    vlm = make_llm()
    msg = HumanMessage(content=[{"type": "text", "text": question}] + blocks)
    # callbacks=[] keeps inner VLM tokens out of the outer SSE stream.
    response = vlm.invoke([msg], config={"callbacks": []})
    return response.content


@tool(metadata={
    "prompt_hint": (
        "ALWAYS use this (not analyze_image) when the file is a Vietnamese "
        "Giấy chứng nhận quyền sử dụng đất (GCN / sổ đỏ / sổ hồng / "
        "Certificate of Land Use Rights). Returns canonical JSON."
    ),
})
@log_tool_call
def extract_gcn(path: str) -> str:
    """Trích xuất Giấy chứng nhận quyền sử dụng đất (GCN) thành JSON có cấu trúc.

    BẮT BUỘC dùng tool này (không phải `analyze_image`) khi file là Giấy chứng
    nhận quyền sử dụng đất / sổ đỏ / sổ hồng / Certificate of Land Use Rights
    của Việt Nam — bất kể user hỏi "tóm tắt", "đọc", "phân tích", hay "trích
    xuất". Tool tự lo định dạng đầu ra.

    Trả về chuỗi JSON theo schema chuẩn dưới gốc `Đăng ký` (Giấy chứng nhận /
    Chủ sử dụng / Thửa đất / Thông tin nhà ở / Biến động). Trường thiếu được
    điền `""` (string) hoặc `[]` (array); không bịa, không tóm tắt, không
    bỏ field — downstream parser cần đầy đủ.
    """
    blocks = _file_to_image_blocks(path)
    if not blocks:
        return f"ERROR: unsupported or unreadable file: {path}"

    vlm = make_llm(temperature=0.0).bind(response_format={"type": "json_object"})
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=[{"type": "text", "text": pdf_detect_prompt}] + blocks),
    ]
    response = vlm.invoke(messages, config={"callbacks": []})
    return response.content
