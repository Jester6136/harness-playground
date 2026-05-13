"""Tools for persisting Vietnamese land certificates (GCN) in MongoDB.

The schema is whatever `extract_gcn` produces — see
`src/extentions/multimodal/prompt.py`. The natural key is
`Đăng ký.Giấy chứng nhận.Số phát hành giấy chứng nhận` (số hiệu GCN).

Write/delete/update are HITL-gated (`metadata["hitl"] = True`) so the user
must approve every mutation through the channel UI (Telegram inline keyboard
or web UI). Read tools are intentionally NOT gated — searches should feel
instant.
"""
from __future__ import annotations

import json
import logging

from langchain_core.tools import tool

from harness.config import settings
from harness.logging_config import log_tool_call
from harness.persistence.mongo import MongoStore
from harness.utils.async_utils import run_async

log = logging.getLogger(__name__)

# Top-level "flat" key the DB indexes and filters on. Decoupled from the
# nested schema produced by extract_gcn so we don't break when the model
# (or a prompt change) shifts where the GCN number lives in the tree.
_FLAT_KEY = "_so_hieu_gcn"

# extract_gcn's prompt is inconsistent: body says "Số phát hành" but the
# canonical schema at the bottom of the prompt says "Số phát hành giấy chứng
# nhận". Accept both. Add more aliases here if more variants appear.
_GCN_NUMBER_KEYS = {
    "Số phát hành giấy chứng nhận",
    "Số phát hành",
}

_INDEX_FIELDS = [
    _FLAT_KEY,
    "Đăng ký.Giấy chứng nhận.Số phát hành giấy chứng nhận",
    "Đăng ký.Giấy chứng nhận.Số phát hành",
    "Đăng ký.Giấy chứng nhận.Số vào sổ",
    "Đăng ký.Chủ sử dụng.Tên chủ",
    "Đăng ký.Chủ sử dụng.Địa chỉ",
    "Đăng ký.Thửa đất.Địa chỉ",
]

_store = MongoStore(db_name=settings.mongo_db_name, collection="gcn")


def _find_first(obj: object, key_names: set[str]) -> str:
    """DFS for the first non-empty string value under any key in `key_names`.

    Tolerant of both object- and array-shaped `Đăng ký`, missing branches, and
    arbitrary nesting depth. Returns "" if nothing matches.
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in key_names and isinstance(v, str) and v.strip():
                return v.strip()
        for v in obj.values():
            found = _find_first(v, key_names)
            if found:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _find_first(item, key_names)
            if found:
                return found
    return ""


def _extract_so_hieu(gcn: dict) -> str:
    """Pull số hiệu GCN from anywhere in the doc, schema-agnostic."""
    return _find_first(gcn, _GCN_NUMBER_KEYS)


# ── write tools (HITL) ─────────────────────────────────────────────────────


@tool
@log_tool_call
def save_gcn(gcn_json: str) -> str:
    """Lưu GCN đã trích xuất vào MongoDB (upsert theo số hiệu GCN).

    `gcn_json` là chuỗi JSON từ tool `extract_gcn` — copy nguyên văn vào đây.
    Nếu số hiệu trùng với record có sẵn → ghi đè (extract mới chính xác hơn).
    Trả về JSON `{"so_hieu_gcn": str, "matched": int, "modified": int,
    "upserted_id": str|null}`.
    """
    try:
        gcn = json.loads(gcn_json)
    except json.JSONDecodeError as exc:
        return json.dumps({"error": "invalid_json", "message": str(exc)}, ensure_ascii=False)

    so_hieu = _extract_so_hieu(gcn)
    if not so_hieu:
        return json.dumps(
            {"error": "missing_key",
             "message": (
                 "không tìm thấy 'Số phát hành (giấy chứng nhận)' trong JSON "
                 "— extract lại từ ảnh/PDF rồi thử save_gcn lần nữa."
             )},
            ensure_ascii=False,
        )

    # Stamp the flat key into the doc so queries don't need to know the nested
    # path. Idempotent — overwrites whatever was there before.
    gcn[_FLAT_KEY] = so_hieu

    async def _do():
        await _store.ensure_text_index(_INDEX_FIELDS, name="gcn_text_idx")
        return await _store.upsert_one({_FLAT_KEY: so_hieu}, gcn)

    try:
        result = run_async(_do())
        return json.dumps({"so_hieu_gcn": so_hieu, **result}, ensure_ascii=False)
    except Exception as exc:
        log.exception("save_gcn failed")
        return json.dumps({"error": "db_error", "message": str(exc)}, ensure_ascii=False)


@tool
@log_tool_call
def update_gcn(so_hieu_gcn: str, updates_json: str) -> str:
    """Cập nhật field cụ thể của GCN (theo số hiệu).

    `updates_json` là JSON object dùng dotted-key — ví dụ:
    `{"Đăng ký.Chủ sử dụng.0.Địa chỉ": "Số 1, Quận 1, TP HCM"}`. Mỗi key sẽ
    được apply qua `$set`. Trả về `{"matched": int, "modified": int}`.
    """
    try:
        updates = json.loads(updates_json)
    except json.JSONDecodeError as exc:
        return json.dumps({"error": "invalid_json", "message": str(exc)}, ensure_ascii=False)
    if not isinstance(updates, dict) or not updates:
        return json.dumps({"error": "empty_updates"}, ensure_ascii=False)

    async def _do():
        return await _store.update_one({_FLAT_KEY: so_hieu_gcn}, updates)

    try:
        result = run_async(_do())
        return json.dumps({"so_hieu_gcn": so_hieu_gcn, **result}, ensure_ascii=False)
    except Exception as exc:
        log.exception("update_gcn failed")
        return json.dumps({"error": "db_error", "message": str(exc)}, ensure_ascii=False)


@tool
@log_tool_call
def delete_gcn(so_hieu_gcn: str) -> str:
    """Xoá GCN khỏi DB theo số hiệu. Không khôi phục được.

    Trả về `{"deleted": int}` — 0 nếu không tìm thấy.
    """
    async def _do():
        return await _store.delete_one({_FLAT_KEY: so_hieu_gcn})

    try:
        deleted = run_async(_do())
        return json.dumps({"so_hieu_gcn": so_hieu_gcn, "deleted": deleted}, ensure_ascii=False)
    except Exception as exc:
        log.exception("delete_gcn failed")
        return json.dumps({"error": "db_error", "message": str(exc)}, ensure_ascii=False)


# ── read tools (no HITL) ───────────────────────────────────────────────────


@tool
@log_tool_call
def find_gcn(so_hieu_gcn: str) -> str:
    """Tra cứu GCN theo số hiệu. Trả về JSON đầy đủ hoặc `{}` nếu không thấy."""
    async def _do():
        return await _store.find_one({_FLAT_KEY: so_hieu_gcn})

    try:
        doc = run_async(_do())
        return json.dumps(doc or {}, ensure_ascii=False, default=str)
    except Exception as exc:
        log.exception("find_gcn failed")
        return json.dumps({"error": "db_error", "message": str(exc)}, ensure_ascii=False)


@tool
@log_tool_call
def search_gcn(query: str, limit: int = 10) -> str:
    """Full-text search GCN theo tên chủ, địa chỉ, số hiệu, số vào sổ.

    Tìm kiếm relevance-ranked qua text index của MongoDB (tự tạo nếu chưa có).
    Trả về `{"hits": [...], "count": N}` với mỗi hit là GCN đầy đủ.
    """
    async def _do():
        await _store.ensure_text_index(_INDEX_FIELDS, name="gcn_text_idx")
        return await _store.text_search(query, limit=limit)

    try:
        docs = run_async(_do())
        return json.dumps({"hits": docs, "count": len(docs)}, ensure_ascii=False, default=str)
    except Exception as exc:
        log.exception("search_gcn failed")
        return json.dumps({"error": "db_error", "message": str(exc)}, ensure_ascii=False)


# ── tool metadata: HITL gating + prompt hints ──────────────────────────────


save_gcn.metadata = {
    "hitl": True,
    "prompt_hint": (
        "Lưu GCN đã trích xuất vào DB (cần approval). Dùng SAU extract_gcn — "
        "truyền nguyên chuỗi JSON từ extract_gcn vào, không reformat."
    ),
}
update_gcn.metadata = {
    "hitl": True,
    "prompt_hint": "Cập nhật field GCN theo số hiệu (cần approval).",
}
delete_gcn.metadata = {
    "hitl": True,
    "prompt_hint": "Xoá GCN khỏi DB (cần approval, không khôi phục được).",
}
find_gcn.metadata = {
    "prompt_hint": "Tra cứu GCN theo số hiệu chính xác (read-only).",
}
search_gcn.metadata = {
    "prompt_hint": "Full-text search GCN theo tên chủ / địa chỉ / số hiệu (read-only).",
}
