"""Search internal documents via the DataLens ReAct retriever.

DataLens already runs its own ReAct loop (decompose → hybrid search → rerank),
so this tool is a thin HTTP client. We hand the agent the ranked passages and
let it synthesize the answer. See docs/DATALENS_API.md for the wire contract.
"""
from __future__ import annotations

import json

import httpx
from langchain_core.tools import tool

from harness.config import settings
from harness.logging_config import log_tool_call
from harness.utils.async_utils import run_async


async def _retrieve(query: str) -> str:
    if not settings.datalens_chatbot_code:
        return json.dumps(
            {"error": "config_missing", "message": "DATALENS_CHATBOT_CODE is not set."},
            ensure_ascii=False,
        )

    payload = {
        "query": query,
        "chatbot_code": settings.datalens_chatbot_code,
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
    Mỗi context có `text`, `document_name`, `pages`, `score`. Khi trả lời
    user, hãy tổng hợp từ `text` và trích nguồn theo `document_name` + `pages`.
    `count: 0` = KB không có nội dung khớp — nói thẳng "không tìm thấy".
    """
    return run_async(_retrieve(query))
