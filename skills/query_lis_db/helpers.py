"""Skill-local tools for the `query_lis_db` skill.

Three tools, one per parametric SQL template in `queries.py`. All input is
bound via psycopg `%s` placeholders — no string formatting of user input
into SQL. The connection pool lives in `harness.persistence.lis_db` so it
can be shared with slash commands (e.g. /status).
"""
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


async def _run_and_format(sql: str, params: tuple) -> str:
    try:
        rows = await run_query(sql, params, row_cap=_ROW_CAP)
    except Exception as exc:
        return json.dumps(
            {"error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False
        )
    return json.dumps(
        {"rows": rows, "count": len(rows), "capped": len(rows) >= _ROW_CAP},
        ensure_ascii=False,
        default=str,
    )


@tool
@log_tool_call
def lookup_gcn_by_so_hieu(so_hieu_gcn: str) -> str:
    """Tra cứu Giấy chứng nhận quyền sử dụng đất theo số hiệu GCN.

    Trả về JSON gồm thông tin chủ sở hữu (cá nhân / tổ chức), thửa đất
    (số tờ bản đồ, số thửa, diện tích, địa chỉ, xã), mục đích sử dụng,
    tài sản trên đất (nhà, công trình xây dựng), sơ đồ và file scan hồ sơ.
    """
    return run_async(_run_and_format(GET_GCN_BY_SO_HIEU, (so_hieu_gcn,)))


@tool
@log_tool_call
def lookup_gcn_by_giay_to_dinh_danh(so_giay_to: str) -> str:
    """Tra cứu các GCN gắn với một số giấy tờ định danh của chủ sở hữu.

    `so_giay_to` là số CMND, CCCD, hộ chiếu, mã số thuế tổ chức...
    Trả về danh sách các GCN mà người/tổ chức đó đứng tên, kèm thông tin
    thửa đất, mục đích sử dụng, hồ sơ quét.
    """
    return run_async(_run_and_format(GET_GCN_BY_GIAY_TO_DINH_DANH, (so_giay_to,)))


@tool
@log_tool_call
def check_don_dang_ky(don_dang_ky_id: str) -> str:
    """Lấy snapshot đầy đủ một Đơn đăng ký theo id (UUID).

    Trả về JSON 1 row với các nhóm con quan trọng:
      - phapNhanSdds:    danh sách pháp nhân sử dụng đất (chủ sở hữu)
      - thuaDats:        danh sách thửa đất
      - daMdsdds:        danh sách mục đích sử dụng đất
      - giayChungNhans:  danh sách Giấy chứng nhận liên quan

    Đơn được coi là "khoẻ" / "đầy đủ" khi cả 4 nhóm trên đều có ít nhất 1
    phần tử. Nhóm nào rỗng → đơn thiếu thông tin, cần bổ sung.
    """
    return run_async(_run_and_format(CHECK_DON_DANG_KY, (don_dang_ky_id,)))
