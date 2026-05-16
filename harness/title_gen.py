"""LLM-powered chat title generator (cho sidebar phiên chat).

Gọi 1 lần sau khi tin đầu của phiên kết thúc. Bounded timeout — model chậm/
lỗi → trả "" để caller tự fallback về cắt ngắn tin nhắn (`_derive_title`).
"""
from __future__ import annotations

import asyncio
import logging

from harness.llm import make_llm

log = logging.getLogger(__name__)

_PROMPT = """Tóm tắt câu hỏi/yêu cầu sau của người dùng thành TIÊU ĐỀ \
ngắn 3-6 từ tiếng Việt, viết hoa chữ cái đầu mỗi từ chính.
- KHÔNG dấu chấm cuối, KHÔNG dấu ngoặc kép, KHÔNG kèm giải thích.
- Tập trung vào CHỦ THỂ + HÀNH ĐỘNG (ví dụ: "Tra cứu kết luận 2280", \
"Báo cáo vi phạm VHL", "Tổng hợp kiến nghị 2024").
- Nếu câu quá ngắn/mơ hồ thì giữ nguyên ý chính.

Chỉ trả về ĐÚNG MỘT DÒNG tiêu đề, không gì khác.

Câu hỏi:
{msg}

Tiêu đề:"""


def _clean(t: str) -> str:
    """Bóc lớp rác hay xuất hiện ở đầu/cuối: ngoặc kép, dấu chấm, bullet, ..."""
    t = (t or "").strip()
    if not t:
        return ""
    # Lấy dòng đầu, bỏ dấu liệt kê đầu dòng
    t = t.splitlines()[0].strip().lstrip("-•*0123456789.) ").strip()
    # Bỏ ngoặc kép bao quanh
    t = t.strip("\"'`«»“”‘’ ").strip()
    # Bỏ dấu kết câu thừa
    while t and t[-1] in ".。:;,":
        t = t[:-1].rstrip()
    return t[:120]


async def generate_title(message: str, *, timeout: float = 3.0) -> str:
    """Trả tiêu đề LLM-generated; "" nếu không khả thi (caller tự fallback)."""
    msg = (message or "").strip()[:600]   # giới hạn cho rẻ + nhanh
    if not msg:
        return ""
    try:
        llm = make_llm(enable_thinking=False, temperature=0.3)
        resp = await asyncio.wait_for(
            llm.ainvoke(_PROMPT.format(msg=msg)),
            timeout=timeout,
        )
        return _clean(getattr(resp, "content", "") or "")
    except Exception as exc:   # bao gồm asyncio.TimeoutError, lỗi mạng vLLM, ...
        log.info("title_gen: LLM thất bại (%s) — sẽ dùng fallback", exc)
        return ""
