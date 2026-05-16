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
# tiêu đề / khối chữ ký, không cần độ nét để trích xuất số liệu.
DETECT_CHUNK_SIZE = int(os.getenv("PHU_LUC_CHUNK_SIZE", "50"))
DETECT_DPI = int(os.getenv("PHU_LUC_DPI", "110"))
DETECT_MAX_IMG = int(os.getenv("PHU_LUC_MAX_IMG", "1100"))
# Đệm an toàn: giữ thêm N trang sau ranh giới phát hiện được. Cắt HỤT (mất nội
# dung chính) là lỗi chết người; cắt THỪA chỉ chậm hơn chút. Mặc định 0 vì
# cách neo theo khối ký đã khá chắc; tăng nếu thấy còn bị hụt.
DETECT_SAFETY_PAGES = int(os.getenv("PHU_LUC_SAFETY_PAGES", "0"))


_DETECT_SYSTEM = """Bạn phân tích bố cục văn bản KẾT LUẬN THANH TRA Việt Nam.

Một bộ hồ sơ gồm 2 phần, theo thứ tự cố định:
1. NỘI DUNG CHÍNH: công văn ban hành + bản kết luận thanh tra (mở đầu, căn cứ,
   kết quả, nhận xét, KIẾN NGHỊ xử lý). Phần này KẾT THÚC bằng KHỐI KÝ của bản
   kết luận: chức danh người ký (vd "TỔNG THANH TRA", "PHÓ TỔNG THANH TRA",
   "KT. TỔNG THANH TRA", "CHÁNH THANH TRA TỈNH"...), chữ ký, con dấu, và mục
   "Nơi nhận:". TRONG phần này có thể CÓ bảng/biểu số liệu minh hoạ — chúng
   VẪN là nội dung chính, KHÔNG phải phụ lục.
2. PHỤ LỤC: các biểu mẫu, bảng kê, danh sách, tổng hợp số liệu ĐÍNH KÈM SAU
   khối ký kết luận. Thường có tiêu đề trang "PHỤ LỤC", "Phụ lục số ...",
   "Biểu số ...", "Mẫu số ...", hoặc cả trang là bảng/danh sách dài.

QUY TẮC QUAN TRỌNG:
- TRANG TRẮNG hoặc gần như trống (không chữ, hoặc chỉ vài dòng vô nghĩa, trang
  ngăn cách) KHÔNG phải ranh giới. Bỏ qua, coi như tiếp nối phần xung quanh.
- Bảng/biểu nằm TRƯỚC khối ký kết luận = vẫn nội dung chính.
- Ranh giới THẬT = ngay SAU khối ký + "Nơi nhận" của bản kết luận thanh tra
  (KHÔNG phải chữ ký của công văn ban hành ở đầu hồ sơ).
- Câu kiểu "...chi tiết tại Phụ lục 01 kèm theo" nằm trong văn bản tường thuật
  chỉ là LỜI DẪN, KHÔNG phải trang phụ lục thật."""

_DETECT_USER = """Các ảnh kèm dưới đây là những trang LIÊN TIẾP của hồ sơ, mỗi \
ảnh có nhãn "=== Trang <số> ===" ngay trước nó (số trang tuyệt đối trong hồ sơ).

Xác định ranh giới nội dung chính → phụ lục:
- "trang_ket_thuc_ket_luan": số trang chứa KHỐI KÝ + "Nơi nhận" CUỐI CÙNG của
  bản kết luận thanh tra (trang cuối của nội dung chính). null nếu không thấy.
- "trang_phu_luc_dau_tien": số trang ĐẦU TIÊN thực sự thuộc phụ lục (tiêu đề
  trang là "PHỤ LỤC"/"Phụ lục số"/"Biểu số"/"Mẫu số", hoặc trang bảng/danh
  sách đính kèm SAU khối ký). Bỏ qua trang trắng. null nếu chưa sang phụ lục.

Suy luận ngắn gọn rồi CHỈ trả JSON:
{"ly_do": "<1-2 câu căn cứ>", "trang_ket_thuc_ket_luan": <số hoặc null>, "trang_phu_luc_dau_tien": <số hoặc null>}"""


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


def _coerce_page(val, valid: set[int]) -> int | None:
    """Ép giá trị model trả về thành số trang hợp lệ nằm trong cụm, hoặc None."""
    if val is None:
        return None
    try:
        p = int(val)
    except (TypeError, ValueError):
        return None
    return p if p in valid else None


async def _ask_boundary(page_indices: list[int], images_b64: list[str]) -> int | None:
    """Hỏi model điểm kết thúc kết luận + trang phụ lục đầu trong cụm này.

    Trả về chỉ số trang (0-based, tuyệt đối) BẮT ĐẦU phụ lục, hoặc None nếu
    cụm này vẫn toàn nội dung chính / không xác định được.

    Mỗi ảnh được gán nhãn "=== Trang <n> ===" để model trả số trang tuyệt đối
    (đỡ đếm sai khi 50 ảnh). Lấy mốc neo theo KHỐI KÝ kết luận; chọn ranh giới
    LỚN HƠN giữa các tín hiệu — cắt hụt làm mất nội dung chính, cắt thừa chỉ
    chậm hơn.
    """
    valid = set(page_indices)
    content: list[dict] = [{"type": "text", "text": _DETECT_USER}]
    for pidx, b64 in zip(page_indices, images_b64):
        content.append({"type": "text", "text": f"=== Trang {pidx} ==="})
        content.append(_b64_image_block(b64))

    resp = await acompletion(
        model=f"openai/{VLLM_MODEL_NAME}",
        api_base=VLLM_BASE_URL,
        api_key=VLLM_API_KEY,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _DETECT_SYSTEM},
            {"role": "user", "content": content},
        ],
    )
    raw = resp.choices[0].message.content
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        log.warning("detect: model trả về không phải JSON hợp lệ: %r", raw)
        return None

    ket_thuc = _coerce_page(data.get("trang_ket_thuc_ket_luan"), valid)
    phu_luc = _coerce_page(data.get("trang_phu_luc_dau_tien"), valid)
    # log.info("detect: lý do = %s", str(data.get("ly_do", ""))[:300])

    candidates: list[int] = []
    if ket_thuc is not None:
        candidates.append(ket_thuc + 1)  # phụ lục bắt đầu NGAY SAU khối ký
    if phu_luc is not None:
        candidates.append(phu_luc)
    if not candidates:
        return None
    # Thiên về GIỮ NHIỀU HƠN: lấy mốc lớn hơn để tránh cắt hụt nội dung chính.
    return max(candidates)


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
        boundary = await _ask_boundary(page_indices, images)
        log.info(
            "detect: trang %d-%d → %s",
            page_indices[0],
            page_indices[-1],
            f"phụ lục bắt đầu ở trang {boundary}" if boundary is not None
            else "toàn nội dung chính",
        )
        if boundary is not None:
            # Đệm an toàn + chặn biên: luôn giữ tối thiểu trang 0, không vượt
            # quá tổng số trang.
            boundary = min(max(boundary + DETECT_SAFETY_PAGES, 1), num_pages)
            return boundary
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


# Cờ tắt toàn cục — đặt PHU_LUC_ENABLED=false để bỏ qua detect (debug/so sánh).
PHU_LUC_ENABLED = os.getenv("PHU_LUC_ENABLED", "true").strip().lower() == "true"


async def prepare_main_pdf_bytes(
    data, chunk_size: int = DETECT_CHUNK_SIZE
) -> tuple[io.BytesIO, dict]:
    """Như `prepare_main_pdf` nhưng nhận bytes / BytesIO (nguồn từ MinIO,
    file đọc sẵn...). Tự ghi temp file vì PDFium thao tác theo đường dẫn.

    An toàn tuyệt đối cho pipeline trích xuất: mọi lỗi detect/cắt đều nuốt và
    trả về PDF GỐC nguyên vẹn — không bao giờ làm hỏng/đứng quá trình extract.
    Trả (BytesIO sẵn sàng feed process_pdf, info-dict).
    """
    raw = data.getvalue() if isinstance(data, io.BytesIO) else bytes(data)

    if not PHU_LUC_ENABLED:
        return io.BytesIO(raw), {"total": None, "boundary": None,
                                 "kept": None, "skipped": "disabled"}

    import tempfile

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(raw)
            tmp.flush()
            tmp_path = tmp.name
        trimmed, info = await prepare_main_pdf(tmp_path, chunk_size=chunk_size)
        return trimmed, info
    except Exception as exc:  # detect/cắt hỏng → giữ nguyên bản gốc
        log.warning("detect: bỏ qua trim do lỗi (%s) — dùng PDF gốc", exc)
        return io.BytesIO(raw), {"total": None, "boundary": None,
                                 "kept": None, "error": str(exc)}
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


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
