"""Skill-local tools for the `query_lis_db` skill.

Three query tools — each runs a fixed SQL template and returns pre-formatted
Vietnamese text (80% path). The `lis_schema_doc` tool is kept for future
flex/ad-hoc queries (20% path, not yet implemented).
"""
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
from skills.query_lis_db.formatters import (
    format_don_dang_ky,
    format_gcn_by_giay_to_dinh_danh,
    format_gcn_by_so_hieu,
)

_ROW_CAP = 50
_REFERENCE_DIR = Path(__file__).parent / "reference"


async def _run_formatted(sql: str, params: tuple, formatter) -> str:
    try:
        rows = await run_query(sql, params, row_cap=_ROW_CAP)
    except Exception as exc:
        return f"Lỗi DB: {type(exc).__name__}: {exc}"
    return formatter(rows, capped=len(rows) >= _ROW_CAP)


@tool
@log_tool_call
def lookup_gcn_by_so_hieu(so_hieu_gcn: str) -> str:
    """Tra cứu Giấy chứng nhận quyền sử dụng đất theo số hiệu GCN.

    Trả về thông tin đã định dạng: chủ sở hữu, thửa đất, mục đích sử dụng,
    tài sản trên đất (nhà, công trình xây dựng), sơ đồ và file scan hồ sơ.
    """
    return run_async(_run_formatted(GET_GCN_BY_SO_HIEU, (so_hieu_gcn,), format_gcn_by_so_hieu))


@tool
@log_tool_call
def lookup_gcn_by_giay_to_dinh_danh(so_giay_to: str) -> str:
    """Tra cứu các GCN gắn với một số giấy tờ định danh của chủ sở hữu.

    `so_giay_to` là số CMND, CCCD, hộ chiếu, mã số thuế tổ chức...
    Trả về danh sách GCN đứng tên, kèm thông tin thửa đất và mục đích sử dụng.
    """
    return run_async(
        _run_formatted(
            GET_GCN_BY_GIAY_TO_DINH_DANH,
            (so_giay_to,),
            format_gcn_by_giay_to_dinh_danh,
        )
    )


@tool
@log_tool_call
def check_don_dang_ky(don_dang_ky_id: str) -> str:
    """Lấy thông tin tổng hợp một Đơn đăng ký theo id (UUID).

    Hiển thị 4 nhóm: pháp nhân (chủ sở hữu), thửa đất, mục đích sử dụng,
    Giấy chứng nhận liên quan. Dùng `/status <id>` để kiểm tra chi tiết
    từng trường còn thiếu.
    """
    return run_async(
        _run_formatted(CHECK_DON_DANG_KY, (don_dang_ky_id,), format_don_dang_ky)
    )


@tool
@log_tool_call
def lis_schema_doc(topic: str) -> str:
    """Trả schema reference của 1 query trong query_lis_db (dành cho flex queries).

    `topic` = tên tool ("lookup_gcn_by_so_hieu", "lookup_gcn_by_giay_to_dinh_danh",
    "check_don_dang_ky"), "glossary", hoặc "index" để xem danh sách.
    """
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
