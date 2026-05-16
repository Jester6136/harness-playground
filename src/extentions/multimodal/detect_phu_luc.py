"""Phát hiện điểm bắt đầu PHỤ LỤC trong kết luận thanh tra dài.

Bài toán: một PDF thanh tra có thể 600+ trang / 500MB nhưng chỉ ~20-30 trang
đầu là nội dung chính (kết luận, nhận xét, kiến nghị), phần còn lại là phụ lục
/ biểu mẫu / bảng kê đính kèm. Nếu nhồi cả 600 trang vào model trích xuất thì
vừa chậm vừa tốn ngữ cảnh vô ích.

Cách làm ở đây:

  1. Quét TUẦN TỰ từ đầu tài liệu theo từng cụm `chunk_size` trang (mặc định
     50 — đúng như yêu cầu). Render ảnh ở DPI thấp (chỉ cần đọc tiêu đề, không
     cần nét để trích xuất) → rẻ và nhanh.
  2. Mỗi cụm hỏi model: trang đầu tiên thuộc phụ lục là trang thứ mấy trong
     cụm? (hoặc null nếu cả cụm vẫn là nội dung chính). Ranh giới chính→phụ lục
     là đơn điệu nên gặp cụm đầu tiên có phụ lục là dừng — thường chỉ tốn 1
     lần gọi vì ranh giới nằm ngay ~30 trang đầu.
  3. Cắt PDF, chỉ giữ các trang [0, boundary) rồi trả về để feed vào
     `process_pdf` (ttcp_inference).

Tách riêng module này để vừa gọi được độc lập (CLI test) vừa cắm vào pipeline
trích xuất / batch.
"""
from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Cho phép chạy trực tiếp `python src/extentions/multimodal/detect_phu_luc.py`
# vẫn resolve được `src.*` (giống ttcp_inference.py).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

load_dotenv()

import litellm

litellm.turn_off_message_logging = True
litellm.suppress_logs = True
logging.getLogger("LiteLLM").setLevel(logging.CRITICAL)

import pypdfium2 as pdfium
from litellm import acompletion

from src.extentions.multimodal.make import (
    PDF_RENDER_EXECUTOR,
    get_pdf_page_count,
    render_pages_chunk,
)

log = logging.getLogger("detect_phu_luc")

VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://192.168.120.12:2900/v1")
VLLM_MODEL_NAME = os.getenv("VLLM_MODEL_NAME", "cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit")
VLLM_API_KEY = os.getenv("VLLM_API_KEY", "EMPTY")

# Mặc định theo yêu cầu: 50 trang / lần detect. Render nhẹ — chỉ cần đọc được
# tiêu đề "PHỤ LỤC" / "Biểu số", không cần độ nét để trích xuất số liệu.
DETECT_CHUNK_SIZE = int(os.getenv("PHU_LUC_CHUNK_SIZE", "50"))
DETECT_DPI = int(os.getenv("PHU_LUC_DPI", "100"))
DETECT_MAX_IMG = int(os.getenv("PHU_LUC_MAX_IMG", "1000"))


_DETECT_SYSTEM = """Bạn là bộ phân loại trang của văn bản KẾT LUẬN THANH TRA Việt Nam.

Phân biệt 2 loại trang:
- "Nội dung chính": phần mở đầu, căn cứ, kết quả thanh tra, nhận xét – đánh giá,
  kết luận, KIẾN NGHỊ xử lý, nơi nhận, chữ ký, con dấu. Là văn bản tường thuật
  hành chính liền mạch.
- "Phụ lục": phần ĐÍNH KÈM SAU nội dung chính — các biểu mẫu, bảng kê, danh
  sách, tổng hợp số liệu chi tiết. Dấu hiệu: tiêu đề "PHỤ LỤC", "Phụ lục số",
  "Biểu số", "Mẫu số", "Danh sách ...", hoặc cả trang là bảng số liệu/danh
  sách dài, không còn là văn bản tường thuật của kết luận.

Ranh giới chỉ chuyển MỘT chiều: nội dung chính trước, phụ lục sau."""

_DETECT_USER = """Dưới đây là {n} ảnh trang LIÊN TIẾP, đánh số 1..{n} đúng theo \
thứ tự xuất hiện.

Hãy tìm ảnh ĐẦU TIÊN (số nhỏ nhất) bắt đầu phần PHỤ LỤC / biểu mẫu đính kèm \
— tức trang mà từ đó trở đi không còn là văn bản tường thuật của kết luận \
thanh tra nữa.

Chỉ trả về JSON, không giải thích:
{{"phu_luc_bat_dau_o_anh": <số nguyên 1..{n}, hoặc null nếu CẢ {n} trang vẫn là nội dung chính>}}"""


def _b64_image_block(img_b64: str) -> dict:
    return {
        "type": "image_url",
        "image_url": {"url": f"data:image/png;base64,{img_b64}"},
    }


def _render_chunk(tmp_path: str, page_indices: list[int]) -> list[str]:
    """Render một cụm trang (raw, không xoay) ở DPI thấp → list base64 PNG.

    Bỏ qua orientation-correction để nhanh: việc nhận diện tiêu đề "PHỤ LỤC"
    không cần ảnh chuẩn hướng như khi trích xuất số liệu.
    """
    args = (tmp_path, page_indices, DETECT_DPI, DETECT_MAX_IMG)
    pairs = PDF_RENDER_EXECUTOR.submit(render_pages_chunk, args).result()
    pairs.sort(key=lambda x: x[0])
    return [b64 for _, b64 in pairs]


async def _ask_appendix_ordinal(images_b64: list[str]) -> int | None:
    """Hỏi model: trang phụ lục đầu tiên là ảnh thứ mấy (1-based) trong cụm?
    Trả None nếu cả cụm vẫn là nội dung chính (hoặc model trả không hợp lệ)."""
    n = len(images_b64)
    resp = await acompletion(
        model=f"openai/{VLLM_MODEL_NAME}",
        api_base=VLLM_BASE_URL,
        api_key=VLLM_API_KEY,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _DETECT_SYSTEM},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _DETECT_USER.format(n=n)},
                    *[_b64_image_block(b) for b in images_b64],
                ],
            },
        ],
    )
    raw = resp.choices[0].message.content
    try:
        val = json.loads(raw).get("phu_luc_bat_dau_o_anh")
    except (json.JSONDecodeError, TypeError, AttributeError):
        log.warning("detect: model trả về không phải JSON hợp lệ: %r", raw)
        return None
    if val is None:
        return None
    try:
        ordinal = int(val)
    except (TypeError, ValueError):
        return None
    if 1 <= ordinal <= n:
        return ordinal
    return None  # ngoài khoảng → coi như không có


async def detect_appendix_start(
    pdf_path: str,
    chunk_size: int = DETECT_CHUNK_SIZE,
) -> int | None:
    """Trả về chỉ số trang (0-based) bắt đầu phụ lục, hoặc None nếu không có
    phụ lục (toàn bộ tài liệu là nội dung chính).

    Quét tuần tự từng cụm `chunk_size` trang từ đầu; dừng ngay cụm đầu tiên
    phát hiện phụ lục (ranh giới đơn điệu nên không cần quét tiếp).
    """
    num_pages = PDF_RENDER_EXECUTOR.submit(get_pdf_page_count, pdf_path).result()
    if num_pages <= 0:
        return None

    for start in range(0, num_pages, chunk_size):
        page_indices = list(range(start, min(start + chunk_size, num_pages)))
        images = await asyncio.get_running_loop().run_in_executor(
            None, _render_chunk, pdf_path, page_indices
        )
        ordinal = await _ask_appendix_ordinal(images)
        log.info(
            "detect: trang %d-%d → %s",
            page_indices[0],
            page_indices[-1],
            f"phụ lục bắt đầu ở trang {start + ordinal - 1}" if ordinal else "toàn nội dung chính",
        )
        if ordinal is not None:
            return start + ordinal - 1  # ordinal 1-based trong cụm → page 0-based
    return None


def split_main_content(pdf_path: str, boundary: int | None) -> io.BytesIO:
    """Tạo PDF mới chỉ gồm các trang [0, boundary) (phần nội dung chính).

    `boundary` None hoặc <=0 → trả nguyên tài liệu (không phát hiện phụ lục).
    """
    src = pdfium.PdfDocument(pdf_path)
    try:
        total = len(src)
        if not boundary or boundary <= 0 or boundary >= total:
            # Không có phụ lục (hoặc ranh giới vô lý) → giữ nguyên tài liệu.
            with open(pdf_path, "rb") as f:
                return io.BytesIO(f.read())
        dst = pdfium.PdfDocument.new()
        dst.import_pages(src, list(range(0, boundary)))
        buf = io.BytesIO()
        dst.save(buf)
        buf.seek(0)
        return buf
    finally:
        src.close()


async def prepare_main_pdf(pdf_path: str, chunk_size: int = DETECT_CHUNK_SIZE):
    """Tiện ích 1 bước: detect phụ lục → cắt → trả (BytesIO, info).

    `info` = {"total": N, "boundary": idx|None, "kept": số trang giữ lại}.
    Cắm trước `process_pdf` để chỉ trích xuất phần nội dung chính.
    """
    total = PDF_RENDER_EXECUTOR.submit(get_pdf_page_count, pdf_path).result()
    boundary = await detect_appendix_start(pdf_path, chunk_size=chunk_size)
    trimmed = split_main_content(pdf_path, boundary)
    kept = boundary if (boundary and 0 < boundary < total) else total
    return trimmed, {"total": total, "boundary": boundary, "kept": kept}


async def _main():
    if len(sys.argv) < 2:
        print("Cách dùng: python src/extentions/multimodal/detect_phu_luc.py <file.pdf> [chunk_size]")
        return
    pdf_path = sys.argv[1]
    chunk = int(sys.argv[2]) if len(sys.argv) > 2 else DETECT_CHUNK_SIZE
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    _, info = await prepare_main_pdf(pdf_path, chunk_size=chunk)
    print(f"\n{'=' * 40}")
    print(f"File        : {pdf_path}")
    print(f"Tổng số trang: {info['total']}")
    if info["boundary"] is None:
        print("Phụ lục     : KHÔNG phát hiện → giữ toàn bộ")
    else:
        print(f"Phụ lục bắt đầu ở trang (0-based): {info['boundary']}")
    print(f"Giữ lại để trích xuất: {info['kept']} trang đầu")


if __name__ == "__main__":
    asyncio.run(_main())
