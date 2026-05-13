"""Skill-local tools for the `query_lis_db` skill."""
from __future__ import annotations

import json

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


async def _run_query(sql: str, params: tuple) -> str:
    try:
        rows = await run_query(sql, params, row_cap=_ROW_CAP)
    except Exception as exc:
        return json.dumps(
            {"error": "db_error", "message": f"{type(exc).__name__}: {exc}"},
            ensure_ascii=False,
        )
    return json.dumps(
        {"rows": rows, "count": len(rows), "capped": len(rows) >= _ROW_CAP},
        ensure_ascii=False,
        default=str,
    )


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
    """Lấy snapshot đầy đủ một Đơn đăng ký theo id (UUID)."""
    return run_async(_run_query(CHECK_DON_DANG_KY, (don_dang_ky_id,)))
