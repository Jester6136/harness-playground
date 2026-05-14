"""Tools cho kho kết luận thanh tra (TTCP) trong MongoDB.

Schema mongo (do offline batch ``extention_/ttcp_batch`` ghi):

    {
      "_id": "ttcp/ttcp-bot/<file>.pdf",   # MinIO object key
      "status": "done", "version": 2, "thinking": false, "attempts": …,
      "bucket": …, "etag": …, "size": …, "last_modified": …,
      "result": {                          # ← extract_ttcp's JSON sits HERE
        "thông tin chung": { số văn bản, loại, ngày ban hành, hình thức,
                             đơn vị chủ trì, … },
        "vi phạm": [ {
          stt, nhóm, đối tượng vi phạm, hành vi vi phạm, mô tả,
          điều khoản vi phạm, hậu quả, trách nhiệm, nguyên nhân,
          kiến nghị: { hình sự, hành chính, kinh tế },
          giá trị triệu đồng, dấu hiệu tội phạm
        } ]
      }
    }

Kiến nghị xử lý GẮN VỚI TỪNG VI PHẠM (object ``kiến nghị`` trong mỗi phần
tử ``vi phạm``) — không còn khối ``kiến nghị xử lý`` cấp document.

Đó là lý do mọi path query đều bắt đầu bằng ``result.…``. Reads luôn lọc
``status="done"`` để bỏ qua dòng pending / error / dead còn lại trong DB.

Khi user upload PDF mới qua Telegram → ``extract_ttcp`` → ``save_ttcp``, ta
bọc lại JSON vào cùng shape (``{result: parsed, status: "done", …}``) để
một schema duy nhất, và mọi tool sau đều dùng được.

Read tools open; save/update/delete HITL-gated qua ``metadata["hitl"]``.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from langchain_core.tools import tool

from harness.config import settings
from harness.logging_config import log_tool_call
from harness.persistence.mongo import MongoStore

log = logging.getLogger(__name__)

# ── schema-aware constants ─────────────────────────────────────────────────
# Field-path constants — one place to retarget if the extractor prompt moves
# something. All paths are nested under ``result`` (batch shape).
P_RESULT = "result"
P_SO_VB = "result.thông tin chung.số văn bản"
P_NGAY = "result.thông tin chung.ngày ban hành"
P_CO_QUAN = "result.thông tin chung.cơ quan ban hành"
P_NGUOI_KY = "result.thông tin chung.người ký"
P_DOI_TUONG = "result.thông tin chung.đối tượng thanh tra"
P_LINH_VUC = "result.thông tin chung.lĩnh vực"
P_VI_PHAM = "result.vi phạm"
P_DAU_HIEU = "result.vi phạm.dấu hiệu tội phạm"
P_GIA_TRI = "result.vi phạm.giá trị triệu đồng"

# Drop rows the batch hasn't finished — pending/error/dead docs only have
# stubs, not real content. Merged into every read filter.
_DONE_FILTER = {"status": "done"}

# Fields covered by the `$text` index. Name bumped to ``_v3`` because the
# schema changed (kiến nghị moved into vi phạm); the smarter
# `ensure_text_index` drops the stale v2 index automatically.
_INDEX_FIELDS = [
    P_SO_VB,
    P_DOI_TUONG,
    P_CO_QUAN,
    P_NGUOI_KY,
    "result.vi phạm.hành vi vi phạm",
    "result.vi phạm.mô tả",
    "result.vi phạm.điều khoản vi phạm",
    "result.vi phạm.hậu quả",
    "result.vi phạm.trách nhiệm",
    "result.vi phạm.nguyên nhân",
    "result.vi phạm.đối tượng vi phạm",
    "result.vi phạm.kiến nghị.hình sự",
    "result.vi phạm.kiến nghị.hành chính",
    "result.vi phạm.kiến nghị.kinh tế",
]
_INDEX_NAME = "ttcp_text_idx_v3"

_store = MongoStore(
    db_name=settings.mongo_db_name,
    collection=settings.ttcp_collection,
)


# ── helpers ────────────────────────────────────────────────────────────────


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _find_first_str(obj: Any, keys: set[str]) -> str:
    """DFS for the first non-empty string under any of `keys`.

    Used by ``save_ttcp`` to dig số văn bản out of arbitrary extracted JSON
    (no fixed assumption about which branch the prompt put it under).
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in keys and isinstance(v, str) and v.strip():
                return v.strip()
        for v in obj.values():
            r = _find_first_str(v, keys)
            if r:
                return r
    elif isinstance(obj, list):
        for it in obj:
            r = _find_first_str(it, keys)
            if r:
                return r
    return ""


def _so_vb_filter(so_van_ban: str) -> dict:
    """Filter matching a single doc by số văn bản (works for both
    batch-written and agent-saved docs, since both wrap content under
    ``result``)."""
    return {**_DONE_FILTER, P_SO_VB: so_van_ban}


def _merge(*filters: dict) -> dict:
    out: dict = {}
    for f in filters:
        if f:
            out.update(f)
    return out


def _build_filter(
    *,
    linh_vuc: str | None = None,
    co_quan: str | None = None,
    nguoi_ky: str | None = None,
    doi_tuong: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    has_criminal: bool | None = None,
) -> dict:
    """Compose a Mongo filter (already including status=done)."""
    f: dict = dict(_DONE_FILTER)
    if linh_vuc:
        f[P_LINH_VUC] = linh_vuc  # array-contains
    if co_quan:
        f[P_CO_QUAN] = {"$regex": co_quan, "$options": "i"}
    if nguoi_ky:
        f[P_NGUOI_KY] = {"$regex": nguoi_ky, "$options": "i"}
    if doi_tuong:
        f[P_DOI_TUONG] = {"$regex": doi_tuong, "$options": "i"}
    if year_from or year_to:
        # ngày ban hành is YYYY-MM-DD string per the prompt → lex compare works.
        date_range: dict = {}
        if year_from:
            date_range["$gte"] = f"{year_from:04d}-01-01"
        if year_to:
            date_range["$lte"] = f"{year_to:04d}-12-31"
        f[P_NGAY] = date_range
    if has_criminal is True:
        f[P_DAU_HIEU] = True
    elif has_criminal is False:
        f[P_DAU_HIEU] = {"$ne": True}
    return f


def _parse_tri(s: str) -> bool | None:
    """'true'/'false'/'' → bool|None — three-state flag without Optional[bool]."""
    s = (s or "").strip().lower()
    if s == "true":
        return True
    if s == "false":
        return False
    return None


def _summarize(doc: dict) -> dict:
    """Project a full TTCP doc down to a search/list-friendly summary.

    Full docs run 50-200KB — returning N of them in `search_ttcp` would burn
    context fast. The summary preserves the keys a follow-up question can
    pivot on (`số văn bản` for find_ttcp, `lĩnh vực` for filter refinement).
    """
    result = doc.get("result", {}) or {}
    tic = result.get("thông tin chung", {}) or {}
    vi_pham = result.get("vi phạm", []) or []
    total_value = 0
    for v in vi_pham:
        gt = v.get("giá trị triệu đồng") if isinstance(v, dict) else None
        if isinstance(gt, (int, float)):
            total_value += gt
    return {
        "số văn bản": tic.get("số văn bản", ""),
        "loại văn bản": tic.get("loại văn bản", ""),
        "ngày ban hành": tic.get("ngày ban hành", ""),
        "cơ quan": tic.get("cơ quan ban hành", ""),
        "người ký": tic.get("người ký", ""),
        "đối tượng": tic.get("đối tượng thanh tra", ""),
        "lĩnh vực": tic.get("lĩnh vực", []),
        "số vi phạm": len(vi_pham),
        "tổng giá trị": total_value,
        "có dấu hiệu tội phạm": any(
            isinstance(v, dict) and v.get("dấu hiệu tội phạm") is True for v in vi_pham
        ),
    }


# ── read tools (no HITL) ───────────────────────────────────────────────────


@tool
@log_tool_call
def find_ttcp(so_van_ban: str) -> str:
    """Tra cứu kết luận thanh tra theo số văn bản (vd '636/TB-TTCP', '2280/TB-TTCP').

    Trả về JSON đầy đủ của 1 kết luận hoặc `{}` nếu không thấy. Doc có thể
    lớn (50-200KB) — chỉ gọi khi user muốn xem chi tiết; với câu hỏi tổng
    quát, ưu tiên `search_ttcp` / `list_ttcp`.
    """
    try:
        doc = _store.find_one(_so_vb_filter(so_van_ban))
        return json.dumps(doc or {}, ensure_ascii=False, default=str)
    except Exception as exc:
        log.exception("find_ttcp failed")
        return json.dumps({"error": "db_error", "message": str(exc)}, ensure_ascii=False)


@tool
@log_tool_call
def search_ttcp(query: str, limit: int = 10) -> str:
    """Full-text search kết luận thanh tra theo nội dung vi phạm / kiến nghị / đối tượng.

    Tìm relevance-ranked qua `$text` index (tự tạo nếu chưa có). Trả về
    `{hits: [...tóm tắt...], count: N}` — KHÔNG full doc; dùng `find_ttcp`
    để xem chi tiết. Query phải có từ ngữ thật (không match khi rỗng).

    LƯU Ý: text search dở khi query là 1 mã ngắn kiểu '636/TB-TTCP'. Cho
    số văn bản chính xác, dùng `find_ttcp` thay vì search.
    """
    try:
        _store.ensure_text_index(_INDEX_FIELDS, name=_INDEX_NAME)
        # Pre-filter status=done is tricky with text search ranking; we filter
        # client-side because the result set is small (≤ limit).
        docs = [d for d in _store.text_search(query, limit=limit * 2)
                if d.get("status") == "done"][:limit]
        return json.dumps(
            {"hits": [_summarize(d) for d in docs], "count": len(docs)},
            ensure_ascii=False, default=str,
        )
    except Exception as exc:
        log.exception("search_ttcp failed")
        return json.dumps({"error": "db_error", "message": str(exc)}, ensure_ascii=False)


@tool
@log_tool_call
def list_ttcp(
    linh_vuc: str = "",
    co_quan: str = "",
    nguoi_ky: str = "",
    doi_tuong: str = "",
    year_from: int = 0,
    year_to: int = 0,
    has_criminal: str = "",
    limit: int = 20,
) -> str:
    """Lọc kết luận thanh tra theo filter cấu trúc (không cần text query).

    - `linh_vuc`: trùng 1 phần tử mảng (vd "đất đai", "xăng dầu", "đầu tư xây dựng").
    - `co_quan` / `nguoi_ky` / `doi_tuong`: regex case-insensitive (substring).
    - `year_from` / `year_to`: lọc theo `ngày ban hành` (0 = không filter).
    - `has_criminal`: "true" → có dấu hiệu tội phạm, "false" → không, "" → bỏ qua.

    Trả về `{items: [...tóm tắt...], count: N}` — dùng `find_ttcp` để xem chi tiết.
    """
    try:
        f = _build_filter(
            linh_vuc=linh_vuc or None,
            co_quan=co_quan or None,
            nguoi_ky=nguoi_ky or None,
            doi_tuong=doi_tuong or None,
            year_from=year_from or None,
            year_to=year_to or None,
            has_criminal=_parse_tri(has_criminal),
        )
        docs = _store.find_many(f, limit=limit)
        return json.dumps(
            {"items": [_summarize(d) for d in docs], "count": len(docs)},
            ensure_ascii=False, default=str,
        )
    except Exception as exc:
        log.exception("list_ttcp failed")
        return json.dumps({"error": "db_error", "message": str(exc)}, ensure_ascii=False)


@tool
@log_tool_call
def count_ttcp(
    linh_vuc: str = "",
    co_quan: str = "",
    nguoi_ky: str = "",
    doi_tuong: str = "",
    year_from: int = 0,
    year_to: int = 0,
    has_criminal: str = "",
) -> str:
    """Đếm số kết luận thanh tra theo filter (giống `list_ttcp`, không trả nội dung).

    Dùng cho "có bao nhiêu…" / "tổng số…". Không filter → đếm toàn bộ DB
    (chỉ status=done). KHÔNG dùng `search_ttcp` để đếm.
    Trả về `{count: N, filters: {...}}`.
    """
    try:
        f = _build_filter(
            linh_vuc=linh_vuc or None,
            co_quan=co_quan or None,
            nguoi_ky=nguoi_ky or None,
            doi_tuong=doi_tuong or None,
            year_from=year_from or None,
            year_to=year_to or None,
            has_criminal=_parse_tri(has_criminal),
        )
        return json.dumps(
            {"count": _store.count(f), "filters": f},
            ensure_ascii=False, default=str,
        )
    except Exception as exc:
        log.exception("count_ttcp failed")
        return json.dumps({"error": "db_error", "message": str(exc)}, ensure_ascii=False)


# Group-by dispatch — each entry knows whether the pipeline needs extra
# ``$unwind`` to make the group key scalar. All field paths prefixed `result.`.
_AGG_GROUP_BY: dict[str, dict] = {
    "linh_vuc":     {"unwind": "$" + P_LINH_VUC,    "field": "$" + P_LINH_VUC},
    "co_quan":      {"field": "$" + P_CO_QUAN},
    "nguoi_ky":     {"field": "$" + P_NGUOI_KY},
    "year":         {"field": {"$substr": ["$" + P_NGAY, 0, 4]}},
    "nhom_vi_pham": {"unwind_vipham": True, "field": "$result.vi phạm.nhóm"},
    "hanh_vi":      {"unwind_vipham": True, "field": "$result.vi phạm.hành vi vi phạm"},
}

_AGG_METRIC: dict[str, dict] = {
    "count":     {"agg": {"$sum": 1},              "needs_vipham": False},
    "sum_value": {"agg": {"$sum": "$" + P_GIA_TRI}, "needs_vipham": True},
    "avg_value": {"agg": {"$avg": "$" + P_GIA_TRI}, "needs_vipham": True},
}


@tool
@log_tool_call
def aggregate_ttcp(
    group_by: str,
    metric: str = "count",
    linh_vuc: str = "",
    co_quan: str = "",
    year_from: int = 0,
    year_to: int = 0,
    has_criminal: str = "",
    limit: int = 20,
) -> str:
    """Thống kê / aggregate theo nhóm — câu hỏi "phân bố", "top", "tổng theo …".

    `group_by` ∈ {linh_vuc, co_quan, nguoi_ky, year, nhom_vi_pham, hanh_vi}
    `metric`   ∈ {count, sum_value, avg_value}
      - count: số kết luận trong nhóm (số vi phạm nếu group_by là nhom_vi_pham/hanh_vi).
      - sum_value / avg_value: tổng / trung bình "giá trị triệu đồng" — luôn unwind "vi phạm".

    Filters giống `list_ttcp` (linh_vuc, co_quan, year_from/to, has_criminal).
    Ví dụ:
      - aggregate_ttcp("linh_vuc", "count")
            → phân bố kết luận theo lĩnh vực.
      - aggregate_ttcp("year", "sum_value", linh_vuc="đất đai")
            → tổng thiệt hại đất đai theo năm.
      - aggregate_ttcp("co_quan", "count", has_criminal="true")
            → cơ quan nào có nhiều kết luận chuyển CQĐT nhất.

    Trả về `{buckets: [{key, value}, …], group_by, metric}`, sort giảm dần theo value.
    """
    g = _AGG_GROUP_BY.get(group_by)
    if g is None:
        return json.dumps(
            {"error": "bad_group_by", "allowed": list(_AGG_GROUP_BY)},
            ensure_ascii=False,
        )
    m = _AGG_METRIC.get(metric)
    if m is None:
        return json.dumps(
            {"error": "bad_metric", "allowed": list(_AGG_METRIC)},
            ensure_ascii=False,
        )

    f = _build_filter(
        linh_vuc=linh_vuc or None,
        co_quan=co_quan or None,
        year_from=year_from or None,
        year_to=year_to or None,
        has_criminal=_parse_tri(has_criminal),
    )

    pipeline: list[dict] = [{"$match": f}]
    if m["needs_vipham"] or g.get("unwind_vipham"):
        pipeline.append({"$unwind": "$" + P_VI_PHAM})
    if "unwind" in g:
        pipeline.append({"$unwind": g["unwind"]})

    pipeline += [
        {"$group": {"_id": g["field"], "value": m["agg"]}},
        # Drop empty buckets (extractor uses "" / null for missing fields).
        {"$match": {"_id": {"$nin": [None, ""]}}},
        {"$sort": {"value": -1}},
        {"$limit": max(1, min(limit, 200))},
    ]

    try:
        rows = _store.aggregate(pipeline)
        buckets = [{"key": r["_id"], "value": r.get("value")} for r in rows]
        return json.dumps(
            {
                "buckets": buckets,
                "group_by": group_by,
                "metric": metric,
                "total_buckets": len(buckets),
            },
            ensure_ascii=False, default=str,
        )
    except Exception as exc:
        log.exception("aggregate_ttcp failed")
        return json.dumps({"error": "db_error", "message": str(exc)}, ensure_ascii=False)


# ── write tools (HITL) ─────────────────────────────────────────────────────


@tool
@log_tool_call
def save_ttcp(ttcp_json: str) -> str:
    """Lưu kết luận thanh tra đã extract vào DB (upsert theo số văn bản).

    `ttcp_json` là chuỗi JSON từ tool `extract_ttcp` — copy nguyên văn, không
    reformat. Tool sẽ tự bọc lại vào schema chuẩn của batch
    (``{result: parsed, status: "done", source: "agent_upload", …}``) nên
    sau khi save, tất cả tool read khác (find/search/list/aggregate) dùng
    được ngay. Trả về `{số văn bản, matched, modified, upserted_id}`.
    """
    try:
        parsed = json.loads(ttcp_json)
    except json.JSONDecodeError as exc:
        return json.dumps({"error": "invalid_json", "message": str(exc)}, ensure_ascii=False)

    so_vb = _find_first_str(parsed, {"số văn bản"})
    if not so_vb:
        return json.dumps({
            "error": "missing_key",
            "message": (
                "không tìm thấy 'số văn bản' trong JSON — extract lại từ "
                "ảnh/PDF rồi thử save_ttcp lần nữa."
            ),
        }, ensure_ascii=False)

    now = _now()
    doc = {
        # Synthetic _id distinct from batch's MinIO-key _id, so an agent
        # upload doesn't clobber the batch row if both happen to cover the
        # same kết luận.
        "_id": f"agent/{so_vb}",
        "source": "agent_upload",
        "status": "done",
        "version": 1,
        "thinking": False,
        "result": parsed,
        "created_at": now,
        "updated_at": now,
    }

    try:
        _store.ensure_text_index(_INDEX_FIELDS, name=_INDEX_NAME)
        # Upsert by the synthetic id — re-uploads of the same số văn bản
        # overwrite the agent-side doc, batch rows untouched.
        result = _store.upsert_one({"_id": doc["_id"]}, doc)
        return json.dumps({"số văn bản": so_vb, **result}, ensure_ascii=False)
    except Exception as exc:
        log.exception("save_ttcp failed")
        return json.dumps({"error": "db_error", "message": str(exc)}, ensure_ascii=False)


def _prefix_result_keys(updates: dict) -> dict:
    """Auto-prepend ``result.`` to user-supplied dotted keys.

    The agent will pass keys like ``thông tin chung.người ký``. Real path
    in the doc is ``result.thông tin chung.người ký`` — we add the prefix
    unless the key already targets a top-level system field (``status``,
    ``source``, ``version``, etc.) or already starts with ``result.``.
    """
    SYSTEM_FIELDS = {"status", "source", "version", "thinking", "updated_at",
                     "last_error", "attempts"}
    out: dict = {}
    for k, v in updates.items():
        top = k.split(".", 1)[0]
        if k.startswith("result.") or top in SYSTEM_FIELDS:
            out[k] = v
        else:
            out[f"result.{k}"] = v
    return out


@tool
@log_tool_call
def update_ttcp(so_van_ban: str, updates_json: str) -> str:
    """Cập nhật field cụ thể của kết luận (theo số văn bản).

    `updates_json` dùng dotted-key dựa trên schema ``result.*``. Có thể bỏ
    qua tiền tố `result.` — tool tự thêm. Ví dụ:
        `{"thông tin chung.người ký": "Nguyễn Văn A"}`
        `{"vi phạm.0.giá trị triệu đồng": 1500}`
    Trả về `{matched, modified}`. Lưu ý: nếu cùng số văn bản tồn tại 2 doc
    (batch + agent_upload), tool chỉ update doc đầu tiên match.
    """
    try:
        updates = json.loads(updates_json)
    except json.JSONDecodeError as exc:
        return json.dumps({"error": "invalid_json", "message": str(exc)}, ensure_ascii=False)
    if not isinstance(updates, dict) or not updates:
        return json.dumps({"error": "empty_updates"}, ensure_ascii=False)
    try:
        prefixed = _prefix_result_keys(updates)
        prefixed["updated_at"] = _now()
        result = _store.update_one(_so_vb_filter(so_van_ban), prefixed)
        return json.dumps({"số văn bản": so_van_ban, **result}, ensure_ascii=False)
    except Exception as exc:
        log.exception("update_ttcp failed")
        return json.dumps({"error": "db_error", "message": str(exc)}, ensure_ascii=False)


@tool
@log_tool_call
def delete_ttcp(so_van_ban: str) -> str:
    """Xoá kết luận khỏi DB theo số văn bản. Không khôi phục được.

    Lưu ý: nếu doc đến từ batch (``_id`` là object-key MinIO), lần
    ``ttcp_batch sync`` tiếp theo sẽ tạo lại record ``pending`` cho file đó
    (rồi extract lại). Để xoá vĩnh viễn, xoá cả file trên MinIO. Trả về
    `{deleted}`.
    """
    try:
        deleted = _store.delete_one(_so_vb_filter(so_van_ban))
        return json.dumps(
            {"số văn bản": so_van_ban, "deleted": deleted}, ensure_ascii=False,
        )
    except Exception as exc:
        log.exception("delete_ttcp failed")
        return json.dumps({"error": "db_error", "message": str(exc)}, ensure_ascii=False)


# ── tool metadata: HITL + prompt hints ─────────────────────────────────────


save_ttcp.metadata = {
    "hitl": True,
    "prompt_hint": (
        "Lưu kết luận thanh tra đã extract vào DB (cần approval). Dùng SAU "
        "extract_ttcp — truyền nguyên chuỗi JSON từ extract_ttcp vào, không reformat."
    ),
}
update_ttcp.metadata = {
    "hitl": True,
    "prompt_hint": "Cập nhật field kết luận theo số văn bản (cần approval).",
}
delete_ttcp.metadata = {
    "hitl": True,
    "prompt_hint": "Xoá kết luận khỏi DB (cần approval, không khôi phục).",
}
find_ttcp.metadata = {
    "prompt_hint": (
        "Tra cứu 1 kết luận theo số văn bản (read-only, trả full doc — có thể lớn). "
        "Dùng find_ttcp thay vì search_ttcp khi đã biết số văn bản chính xác."
    ),
}
search_ttcp.metadata = {
    "prompt_hint": (
        "Full-text search kết luận theo nội dung vi phạm / kiến nghị / đối tượng "
        "(read-only). Trả tóm tắt, không full doc. KHÔNG dùng để tra số văn bản — "
        "dùng find_ttcp."
    ),
}
list_ttcp.metadata = {
    "prompt_hint": (
        "Lọc kết luận theo lĩnh vực / cơ quan / năm / có dấu hiệu tội phạm "
        "(read-only). Trả tóm tắt."
    ),
}
count_ttcp.metadata = {
    "prompt_hint": (
        "Đếm số kết luận theo filter (read-only). Dùng cho 'có bao nhiêu' / "
        "'tổng số' — KHÔNG dùng search_ttcp để đếm."
    ),
}
aggregate_ttcp.metadata = {
    "prompt_hint": (
        "Aggregate / group-by: thống kê theo lĩnh vực / cơ quan / năm / nhóm "
        "vi phạm / hành vi; metric count | sum_value | avg_value. Dùng cho "
        "'top X', 'phân bố theo Y', 'tổng thiệt hại theo năm'."
    ),
}
