"""Skill-local tools for the `query_lis_db` skill.

Connects to the external `geohub_lis` Postgres (separate from the harness's
own Postgres). Pool is lazy + lock-guarded; connection params come from
`harness.config.settings.lis_db_dsn`.

Three tools, one per parametric SQL template in `queries.py`. Each accepts
a single string argument bound via psycopg `%s` placeholder — no string
formatting of user input into SQL.
"""
from __future__ import annotations

import asyncio
import json

from langchain_core.tools import tool
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from harness.config import settings
from harness.logging_config import log_tool_call
from harness.utils.async_utils import run_async

from skills.query_lis_db.queries import (
    CHECK_DON_DANG_KY,
    GET_GCN_BY_GIAY_TO_DINH_DANH,
    GET_GCN_BY_SO_HIEU,
)

_ROW_CAP = 50

_pool: AsyncConnectionPool | None = None
_pool_lock = asyncio.Lock()


async def _get_pool() -> AsyncConnectionPool:
    global _pool
    if _pool is not None:
        return _pool
    async with _pool_lock:
        if _pool is not None:
            return _pool
        pool = AsyncConnectionPool(
            conninfo=settings.lis_db_dsn,
            min_size=1,
            max_size=4,
            kwargs={"autocommit": True, "row_factory": dict_row},
            open=False,
        )
        await pool.open()
        _pool = pool
    return _pool


async def _run(sql: str, params: tuple) -> str:
    try:
        pool = await _get_pool()
        async with pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(sql, params)
            rows = await cur.fetchmany(_ROW_CAP)
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
    return run_async(_run(GET_GCN_BY_SO_HIEU, (so_hieu_gcn,)))


@tool
@log_tool_call
def lookup_gcn_by_giay_to_dinh_danh(so_giay_to: str) -> str:
    """Tra cứu các GCN gắn với một số giấy tờ định danh của chủ sở hữu.

    `so_giay_to` là số CMND, CCCD, hộ chiếu, mã số thuế tổ chức...
    Trả về danh sách các GCN mà người/tổ chức đó đứng tên, kèm thông tin
    thửa đất, mục đích sử dụng, hồ sơ quét.
    """
    return run_async(_run(GET_GCN_BY_GIAY_TO_DINH_DANH, (so_giay_to,)))


@tool
@log_tool_call
def check_don_dang_ky(don_dang_ky_id: str) -> str:
    """Lấy snapshot đầy đủ một Đơn đăng ký theo id (UUID).

    Trả về JSON gồm pháp nhân (cá nhân / hộ gia đình / vợ chồng / tổ chức /
    cộng đồng dân cư), danh sách thửa đất, mục đích sử dụng đất, và các
    GCN liên quan kèm hồ sơ quét.
    """
    return run_async(_run(CHECK_DON_DANG_KY, (don_dang_ky_id,)))
