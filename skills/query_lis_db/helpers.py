"""Skill-local tools for the `query_lis_db` skill."""
from __future__ import annotations

from pathlib import Path

from langchain_core.tools import tool

from harness.logging_config import log_tool_call
from harness.persistence.lis_db import run_query
from harness.utils.async_utils import run_async

from harness.persistence.lis_queries import (
    CHECK_DON_DANG_KY,
    GET_GCN_BY_GIAY_TO_DINH_DANH,
    GET_GCN_BY_SO_HIEU,
)

_ROW_CAP = 50
_REFERENCE_DIR = Path(__file__).parent / "reference"


async def _run_query(sql: str, params: tuple) -> str:
    try:
        rows = await run_query(sql, params, row_cap=_ROW_CAP)
    except Exception as exc:
        return f"Lỗi DB: {type(exc).__name__}: {exc}"
    return str(rows)


@tool
@log_tool_call
def lookup_gcn_by_so_hieu(so_hieu_gcn: str) -> str:
    """Tra cứu Giấy chứng nhận quyền sử dụng đất theo số hiệu GCN."""
    return run_async(_run_query(GET_GCN_BY_SO_HIEU, (so_hieu_gcn,)))


@tool
@log_tool_call
def lookup_gcn_by_giay_to_dinh_danh(so_giay_to: str) -> str:
    """Tra cứu các GCN gắn với một số giấy tờ định danh của chủ sở hữu."""
    return run_async(_run_query(GET_GCN_BY_GIAY_TO_DINH_DANH, (so_giay_to,)))


@tool
@log_tool_call
def check_don_dang_ky(don_dang_ky_id: str) -> str:
    """Lấy thông tin tổng hợp một Đơn đăng ký theo id (UUID)."""
    output = run_async(_run_query(CHECK_DON_DANG_KY, (don_dang_ky_id,)))
    print(f"  [check_don_dang_ky] {output}")
    return output


@tool
@log_tool_call
def lis_schema_doc(topic: str) -> str:
    """Trả schema reference của 1 query trong query_lis_db."""
    if topic == "index":
        topics = sorted(p.stem for p in _REFERENCE_DIR.glob("*.md"))
        return "Topic có sẵn:\n" + "\n".join(f"  - {t}" for t in topics)
    path = _REFERENCE_DIR / f"{topic}.md"
    if not path.exists():
        return (
            f"ERROR: không có doc cho topic '{topic}'. "
            f"Gọi `lis_schema_doc(topic='index')` để xem danh sách."
        )
    return path.read_text(encoding="utf-8")