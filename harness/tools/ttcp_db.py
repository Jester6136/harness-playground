"""Tools cho kho kết luận thanh tra (TTCP) trong MongoDB.

Schema do `extract_ttcp` sinh ra (xem ``src/extentions/multimodal/prompt.py``):

  - ``thông tin chung``: số văn bản, loại, ngày ban hành, cơ quan, người ký,
    đối tượng, lĩnh vực[], thời kỳ, nội dung, văn bản liên quan[]
  - ``vi phạm[]``: stt, nhóm, đối tượng vi phạm, hành vi vi phạm, mô tả,
    căn cứ pháp luật, giá trị triệu đồng, trách nhiệm, dấu hiệu tội phạm
  - ``kiến nghị xử lý``: chính sách[], kinh tế[], trách nhiệm[],
    hình sự[{nội dung, cơ quan nhận, hành vi, giá trị, tình trạng}]

Cùng collection với offline batch (``extention_/ttcp_batch``) — agent đọc
nguyên kho mà batch đã extract. Một số doc do batch ghi sẽ KHÔNG có
``_so_van_ban`` flat key (batch dùng object-key MinIO làm ``_id``), nên các
tool ở đây fallback sang nested path ``thông tin chung.số văn bản``.

Read tools open; save/update/delete HITL-gated qua ``metadata["hitl"]``.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.tools import tool

from harness.config import settings
from harness.logging_config import log_tool_call
from harness.persistence.mongo import MongoStore

log = logging.getLogger(__name__)

# Top-level flat key — saved by `save_ttcp`. Decoupled from the nested schema
# so a prompt tweak that shifts where "số văn bản" lives doesn't break point
# lookup. Batch-written rows won't have this field; we fall back to the
# nested path in `find_ttcp` / `update_ttcp` / `delete_ttcp`.
_FLAT_KEY = "_so_van_ban"

# Field-path constants — one place to retarget if the extractor prompt moves
# something. Mongo handles UTF-8 keys (spaces, dấu) just fine.
P_SO_VB = "thông tin chung.số văn bản"
P_NGAY = "thông tin chung.ngày ban hành"
P_CO_QUAN = "thông tin chung.cơ quan ban hành"
P_NGUOI_KY = "thông tin chung.người ký"
P_DOI_TUONG = "thông tin chung.đối tượng thanh tra"
P_LINH_VUC = "thông tin chung.lĩnh vực"
P_DAU_HIEU = "vi phạm.dấu hiệu tội phạm"

# Fields included in the text index (`$text` search). Ordered by likely
# relevance: số văn bản first → exact-id hits float to the top.
_INDEX_FIELDS = [
    _FLAT_KEY,
    P_SO_VB,
    P_DOI_TUONG,
    P_CO_QUAN,
    P_NGUOI_KY,
    "vi phạm.hành vi vi phạm",
    "vi phạm.mô tả",
    "vi phạm.trách nhiệm",
    "vi phạm.đối tượng vi phạm",
    "kiến nghị xử lý.chính sách",
    "kiến nghị xử lý.kinh tế",
    "kiến nghị xử lý.trách nhiệm",
    "kiến nghị xử lý.hình sự.nội dung",
]

_store = MongoStore(
    db_name=settings.mongo_db_name,
    collection=settings.ttcp_collection,
)


# ── helpers ────────────────────────────────────────────────────────────────


def _find_first_str(obj: Any, keys: set[str]) -> str:
    """DFS for the first non-empty string value under any of `keys`.

    Mirrors the helper that lived in the old gcn_db — used to be schema-
    agnostic. Here we still need it because batch-written docs may not have
    the flat ``_so_van_ban`` key.
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


def _id_filter(so_van_ban: str) -> dict:
    """Match either the flat key (agent-written) or nested path (batch-written)."""
    return {"$or": [{_FLAT_KEY: so_van_ban}, {P_SO_VB: so_van_ban}]}


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
    """Compose a Mongo filter from optional structured constraints."""
    f: dict = {}
    if linh_vuc:
        # Mongo array-contains: { field: value } matches if any element equals.
        f[P_LINH_VUC] = linh_vuc
    if co_quan:
        f[P_CO_QUAN] = {"$regex": co_quan, "$options": "i"}
    if nguoi_ky:
        f[P_NGUOI_KY] = {"$regex": nguoi_ky, "$options": "i"}
    if doi_tuong:
        f[P_DOI_TUONG] = {"$regex": doi_tuong, "$options": "i"}
    if year_from or year_to:
        # ngày ban hành is stored as ISO string ("YYYY-MM-DD") per the prompt,
        # so lexical compare works for full-year ranges.
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
    """Parse a tri-state string flag ('true' / 'false' / '') → bool | None.

    @tool prefers concrete defaults over Optional[bool]; a string with "" =
    "not set" lets the model express three states without an extra arg.
    """
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
    tic = doc.get("thông tin chung", {}) or {}
    vi_pham = doc.get("vi phạm", []) or []
    total_value = 0
    for v in vi_pham:
        gt = v.get("giá trị triệu đồng") if isinstance(v, dict) else None
        if isinstance(gt, (int, float)):
            total_value += gt
    so_vb = tic.get("số văn bản") or doc.get(_FLAT_KEY, "")
    return {
        "số văn bản": so_vb,
        "loại văn bản": tic.get("loại văn bản", ""),
        "ngày ban hành": tic.get("ngày ban hành", ""),
        "cơ quan": tic.get("cơ quan ban hành", ""),
        "người ký": tic.get("người ký", ""),
        "đối tượng": tic.get("đối tượng thanh tra", ""),
        "lĩnh vực": tic.get("lĩnh vực", []),
        "số vi phạm": len(vi_pham),
        "tổng giá trị (triệu đồng)": total_value,
        "có dấu hiệu tội phạm": any(
            isinstance(v, dict) and v.get("dấu hiệu tội phạm") is True for v in vi_pham
        ),
    }


# ── read tools (no HITL) ───────────────────────────────────────────────────


@tool
@log_tool_call
def find_ttcp(so_van_ban: str) -> str:
    """Tra cứu kết luận thanh tra theo số văn bản (vd '2280/TB-TTCP').

    Trả về JSON đầy đủ của 1 kết luận hoặc `{}` nếu không thấy. Doc có thể
    lớn (50-200KB) — chỉ gọi khi user muốn xem chi tiết; với câu hỏi tổng
    quát, ưu tiên `search_ttcp` / `list_ttcp`.
    """
    try:
        doc = _store.find_one(_id_filter(so_van_ban))
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
    """
    try:
        _store.ensure_text_index(_INDEX_FIELDS, name="ttcp_text_idx")
        docs = _store.text_search(query, limit=limit)
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

    Dùng cho "có bao nhiêu…" / "tổng số…". Không filter → đếm toàn bộ DB.
    KHÔNG dùng `search_ttcp` để đếm (text search cần từ ngữ thật).
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


# Group-by dispatch table for aggregate_ttcp. Each entry knows whether the
# pipeline needs an extra ``$unwind`` to make the group key scalar.
_AGG_GROUP_BY: dict[str, dict] = {
    "linh_vuc":     {"unwind": "$thông tin chung.lĩnh vực", "field": "$thông tin chung.lĩnh vực"},
    "co_quan":      {"field": "$thông tin chung.cơ quan ban hành"},
    "nguoi_ky":     {"field": "$thông tin chung.người ký"},
    "year":         {"field": {"$substr": ["$thông tin chung.ngày ban hành", 0, 4]}},
    "nhom_vi_pham": {"unwind_vipham": True, "field": "$vi phạm.nhóm"},
    "hanh_vi":      {"unwind_vipham": True, "field": "$vi phạm.hành vi vi phạm"},
}

_AGG_METRIC: dict[str, dict] = {
    "count":     {"agg": {"$sum": 1},                                  "needs_vipham": False},
    "sum_value": {"agg": {"$sum": "$vi phạm.giá trị triệu đồng"},      "needs_vipham": True},
    "avg_value": {"agg": {"$avg": "$vi phạm.giá trị triệu đồng"},      "needs_vipham": True},
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

    pipeline: list[dict] = []
    if f:
        pipeline.append({"$match": f})
    # Unwind vi phạm if metric (sum/avg of giá trị) OR group_by needs it.
    if m["needs_vipham"] or g.get("unwind_vipham"):
        pipeline.append({"$unwind": "$vi phạm"})
    # Unwind a non-vi-phạm array group field (e.g. lĩnh vực).
    if "unwind" in g:
        pipeline.append({"$unwind": g["unwind"]})

    pipeline += [
        {"$group": {"_id": g["field"], "value": m["agg"]}},
        # Drop empty buckets — extractor uses "" for missing string fields.
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

    `ttcp_json` là chuỗi JSON từ tool `extract_ttcp` — copy nguyên văn vào
    đây, không reformat. Nếu số văn bản trùng → ghi đè (extract mới chính
    xác hơn). Trả về `{số văn bản, matched, modified, upserted_id}`.
    """
    try:
        doc = json.loads(ttcp_json)
    except json.JSONDecodeError as exc:
        return json.dumps({"error": "invalid_json", "message": str(exc)}, ensure_ascii=False)

    so_vb = _find_first_str(doc, {"số văn bản"})
    if not so_vb:
        return json.dumps({
            "error": "missing_key",
            "message": (
                "không tìm thấy 'số văn bản' trong JSON — extract lại từ "
                "ảnh/PDF rồi thử save_ttcp lần nữa."
            ),
        }, ensure_ascii=False)

    # Stamp flat key for cheap point-lookup. Idempotent.
    doc[_FLAT_KEY] = so_vb

    try:
        _store.ensure_text_index(_INDEX_FIELDS, name="ttcp_text_idx")
        result = _store.upsert_one({_FLAT_KEY: so_vb}, doc)
        return json.dumps({"số văn bản": so_vb, **result}, ensure_ascii=False)
    except Exception as exc:
        log.exception("save_ttcp failed")
        return json.dumps({"error": "db_error", "message": str(exc)}, ensure_ascii=False)


@tool
@log_tool_call
def update_ttcp(so_van_ban: str, updates_json: str) -> str:
    """Cập nhật field cụ thể của kết luận (theo số văn bản).

    `updates_json` dùng dotted-key — vd:
    `{"thông tin chung.người ký": "Nguyễn Văn A"}` hoặc
    `{"vi phạm.0.giá trị triệu đồng": 1500}`.
    Mỗi key apply qua `$set`. Trả về `{matched, modified}`.
    """
    try:
        updates = json.loads(updates_json)
    except json.JSONDecodeError as exc:
        return json.dumps({"error": "invalid_json", "message": str(exc)}, ensure_ascii=False)
    if not isinstance(updates, dict) or not updates:
        return json.dumps({"error": "empty_updates"}, ensure_ascii=False)
    try:
        result = _store.update_one(_id_filter(so_van_ban), updates)
        return json.dumps({"số văn bản": so_van_ban, **result}, ensure_ascii=False)
    except Exception as exc:
        log.exception("update_ttcp failed")
        return json.dumps({"error": "db_error", "message": str(exc)}, ensure_ascii=False)


@tool
@log_tool_call
def delete_ttcp(so_van_ban: str) -> str:
    """Xoá kết luận khỏi DB theo số văn bản. Không khôi phục được.

    Lưu ý: batch sẽ KHÔNG tự tạo lại doc đã xoá (vì _id batch dùng là
    object-key MinIO). Để re-extract, dùng `extention_/ttcp_batch
    --retry-failed` hoặc reset doc trực tiếp trong mongo. Trả về `{deleted}`.
    """
    try:
        deleted = _store.delete_one(_id_filter(so_van_ban))
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
        "Tra cứu 1 kết luận theo số văn bản (read-only, trả về full doc — có thể lớn)."
    ),
}
search_ttcp.metadata = {
    "prompt_hint": (
        "Full-text search kết luận theo nội dung vi phạm / kiến nghị / đối tượng "
        "(read-only). Trả tóm tắt, không full doc."
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
