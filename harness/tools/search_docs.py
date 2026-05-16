"""Search internal documents via the DataLens ReAct retriever.

DataLens already runs its own ReAct loop (decompose → hybrid search → rerank),
so this tool is a thin HTTP client. We hand the agent the ranked passages and
let it synthesize the answer. See docs/DATALENS_API.md for the wire contract.
"""
from __future__ import annotations

import json

import httpx
from langchain_core.tools import tool

from harness import tenant
from harness.config import settings
from harness.logging_config import log_tool_call
from harness.utils.async_utils import run_async


async def _retrieve(query: str) -> str:
    chatbot_code = tenant.datalens_chatbot_code()
    if not chatbot_code:
        return json.dumps(
            {"error": "config_missing", "message": "DATALENS_CHATBOT_CODE is not set."},
            ensure_ascii=False,
        )

    payload = {
        "query": query,
        "chatbot_code": chatbot_code,
        "allowed_ids": None,
        "history": [],
    }
    url = f"{settings.datalens_url.rstrip('/')}/retrieve/react/"

    try:
        async with httpx.AsyncClient(timeout=settings.datalens_timeout) as client:
            r = await client.post(url, json=payload)
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPStatusError as exc:
        return json.dumps(
            {"error": "http_error", "status": exc.response.status_code,
             "message": exc.response.text[:500]},
            ensure_ascii=False,
        )
    except Exception as exc:
        return json.dumps(
            {"error": "request_failed", "message": f"{type(exc).__name__}: {exc}"},
            ensure_ascii=False,
        )

    return json.dumps(data, ensure_ascii=False, default=str)


@tool
@log_tool_call
def search_internal_docs(query: str) -> str:
    """Tra cứu kho tri thức nội bộ (DataLens) bằng câu hỏi tự nhiên.

    Dùng khi user hỏi về quy trình, chính sách, tài liệu nội bộ — bất cứ thứ
    gì có thể nằm trong tài liệu của tổ chức. KHÔNG dùng cho tra cứu định danh
    cụ thể (GCN, đơn đăng ký) — đã có skill `query_lis_db` lo việc đó.

    Tham số `query` nên là câu hỏi đầy đủ ngữ cảnh (vd. "Quy trình duyệt
    thanh toán nội bộ?"), không phải keyword rời rạc. Với câu hỏi follow-up
    mơ hồ (vd. "còn cái kia?"), tự viết lại thành câu đầy đủ trước khi gọi.

    Trả về JSON `{"ranked_contexts": [...], "count": N, "elapsed_ms": ms}`.
    Mỗi context gồm: `text` (nội dung chunk), `document_name` (tên file),
    `pages` (số trang), `score`, và `presigned_url` (link MinIO TTL 1h, có
    thể null).

    QUY TẮC TRẢ LỜI:
    1. Tổng hợp câu trả lời CHỈ từ `text` của các chunk. Không bịa.
    2. **Bắt buộc trích nguồn** ngay sau mỗi ý/đoạn lấy từ chunk, dùng
       Markdown link tới `presigned_url` + anchor `#page=N` (N = `pages[0]`):
         `[document_name (tr. X-Y)](presigned_url#page=X)`
       Nếu `presigned_url` là null thì chỉ ghi `(document_name, tr. X-Y)`.
    3. Nếu nhiều chunk cùng đóng góp, cite lần lượt từng nguồn ở chỗ liên quan
       — không gộp cuối bài.
    4. `count: 0` → trả lời "Không tìm thấy nội dung phù hợp trong kho tri
       thức nội bộ." Không cố đoán.
    5. Có lỗi (`error` field) → báo lỗi ngắn gọn, không retry.
    """
    return run_async(_retrieve(query))
