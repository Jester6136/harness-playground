"""Render a TTCP doc into the standard 'Bảng tóm tắt Kết luận thanh tra' HTML.

Best-effort mapping from the CURRENT `extract_ttcp` schema. The report
template (xem ``vi_du_mau_PhuTho``) cần vài field schema chưa có:

  - thông tin chung: ngày công bố, ngày kết thúc thanh tra, hình thức thanh tra
  - vi phạm[]: hậu quả (riêng), nguyên nhân, kiến nghị per-violation 3 loại

Những ô đó render thành "—" / "Không nêu trong văn bản" — KHÔNG bịa.

`kiến nghị xử lý` cấp document (schema CÓ, nhưng không gắn được vào từng
dòng Bảng II) được render thành Mục III riêng, nên không mất dữ liệu đã
extract. Khi nào schema thêm kiến nghị per-violation thì Bảng II tự đầy.
"""
from __future__ import annotations

import html
import json
import logging
import re
from datetime import datetime
from pathlib import Path

from langchain_core.tools import tool

from harness.config import settings
from harness.logging_config import log_tool_call
from harness.persistence.mongo import MongoStore

log = logging.getLogger(__name__)

_store = MongoStore(db_name=settings.mongo_db_name, collection=settings.ttcp_collection)

# Same nested path used by ttcp_db — content lives under `result`.
_P_SO_VB = "result.thông tin chung.số văn bản"

_DASH = "—"
_NOT_STATED = "Không nêu trong văn bản"


# ── small helpers ──────────────────────────────────────────────────────────


def _esc(v: object) -> str:
    """HTML-escape a scalar; empty/None → em-dash."""
    s = "" if v is None else str(v)
    s = s.strip()
    return html.escape(s) if s else _DASH


def _esc_or(v: object, fallback: str) -> str:
    s = "" if v is None else str(v).strip()
    return html.escape(s) if s else fallback


def _join(v: object) -> str:
    """Render a list as '; '-joined text, or pass a scalar through."""
    if isinstance(v, list):
        items = [str(x).strip() for x in v if str(x).strip()]
        return html.escape("; ".join(items)) if items else _DASH
    return _esc(v)


def _num(v: object) -> str:
    """Format a numeric giá trị with thousands separators, else em-dash."""
    if isinstance(v, (int, float)):
        return f"{v:,.0f}".replace(",", ".")
    return _DASH


def _safe_filename(so_van_ban: str) -> str:
    """'636/TB-TTCP' → '636_TB-TTCP' — slug for the output file name."""
    slug = re.sub(r"[^\w\-.]+", "_", so_van_ban.strip()) or "ttcp"
    return slug.strip("_")


# ── section renderers ──────────────────────────────────────────────────────


def _info_table(tic: dict) -> str:
    """Bảng thông tin chung. Rows mirror the report template; fields the
    schema doesn't carry render as em-dash."""
    so_vb = tic.get("số văn bản", "")
    loai = tic.get("loại văn bản", "")
    qd_kl = f"{loai} {so_vb}".strip() if loai or so_vb else ""
    nguoi_ky = tic.get("người ký", "")
    chuc_vu = tic.get("chức vụ người ký", "")
    nguoi = f"{chuc_vu}: {nguoi_ky}".strip(": ") if (nguoi_ky or chuc_vu) else ""

    cells = [
        ("Tên cuộc thanh tra", _esc(tic.get("nội dung thanh tra")),
         "Quyết định / Kết luận", _esc_or(qd_kl, _DASH),
         "Ngày ban hành", _esc(tic.get("ngày ban hành"))),
        ("Nội dung thanh tra", _esc(tic.get("nội dung thanh tra")),
         "Đối tượng thanh tra", _esc(tic.get("đối tượng thanh tra")),
         "Thời kỳ thanh tra", _esc(tic.get("thời kỳ thanh tra"))),
        ("Người ký / Chức vụ", _esc_or(nguoi, _DASH),
         "Ngày công bố KL", _DASH,
         "Ngày kết thúc thanh tra", _DASH),
        ("Đơn vị chủ trì", _esc(tic.get("cơ quan ban hành")),
         "Hình thức thanh tra", _DASH,
         "Lĩnh vực", _join(tic.get("lĩnh vực"))),
    ]
    rows = "\n".join(
        f"""    <tr>
      <td class="label">{l1}</td><td class="value">{v1}</td>
      <td class="label">{l2}</td><td class="value">{v2}</td>
      <td class="label">{l3}</td><td class="value">{v3}</td>
    </tr>"""
        for l1, v1, l2, v2, l3, v3 in cells
    )
    return f'  <table class="info-table">\n{rows}\n  </table>'


def _narrative(vi_pham: list) -> str:
    """Mục I — Trích lược vi phạm (dạng văn xuôi)."""
    if not vi_pham:
        return '  <div class="narrative-wrap"><div class="narrative-item">'\
               f'{_NOT_STATED}.</div></div>'
    items = []
    for i, v in enumerate(vi_pham, 1):
        if not isinstance(v, dict):
            continue
        # hậu quả: schema không có field riêng → dùng "mô tả" (gần nhất).
        hau_qua = v.get("mô tả") or ""
        items.append(f"""    <div class="narrative-item">
      <span class="num">{i}.</span>
      <span class="lbl">Hành vi vi phạm:</span> {_esc(v.get("hành vi vi phạm"))} —
      <span class="lbl">Điều khoản:</span> {_esc(v.get("căn cứ vi phạm"))} —
      <span class="lbl">Hậu quả:</span> {_esc_or(hau_qua, _NOT_STATED)};
      <span class="lbl">Trách nhiệm thuộc về:</span> {_esc(v.get("trách nhiệm"))};
      <span class="lbl">Kiến nghị:</span> {_NOT_STATED};
      <span class="lbl">Nguyên nhân:</span> {_NOT_STATED}.
    </div>""")
    return '  <div class="narrative-wrap">\n' + "\n".join(items) + "\n  </div>"


def _detail_table(vi_pham: list) -> str:
    """Mục II — Bảng chi tiết vi phạm.

    Cột 'Kiến nghị xử lý' (Hình sự / Hành chính / Kinh tế) là per-violation —
    schema hiện chỉ có flag `dấu hiệu tội phạm`, nên cột Hình sự suy ra từ
    flag đó; Hành chính / Kinh tế để em-dash (xem Mục III cho kiến nghị chung).
    """
    body_rows = []
    for i, v in enumerate(vi_pham or [], 1):
        if not isinstance(v, dict):
            continue
        hau_qua = v.get("mô tả") or ""
        gt = v.get("giá trị triệu đồng")
        if isinstance(gt, (int, float)):
            hau_qua = f"{hau_qua} (Giá trị: {_num(gt)} triệu đồng)".strip()
        hinh_su = (
            "Có dấu hiệu tội phạm — kiến nghị chuyển cơ quan điều tra"
            if v.get("dấu hiệu tội phạm") is True else _DASH
        )
        body_rows.append(f"""        <tr>
          <td class="stt">{i}</td>
          <td><strong>{_esc(v.get("đối tượng vi phạm"))}</strong></td>
          <td>{_esc(v.get("hành vi vi phạm"))}</td>
          <td class="law">{_esc(v.get("căn cứ vi phạm"))}</td>
          <td class="consequence">{_esc_or(hau_qua, _NOT_STATED)}</td>
          <td>{_esc(v.get("trách nhiệm"))}</td>
          <td class="recommend">{hinh_su}</td>
          <td class="recommend">{_DASH}</td>
          <td class="recommend">{_DASH}</td>
        </tr>""")
    body = "\n".join(body_rows) or (
        '        <tr><td colspan="9" class="stt">' + _NOT_STATED + "</td></tr>"
    )
    return f"""  <div class="main-table-wrap">
    <table class="main-table">
      <thead>
        <tr>
          <th rowspan="2">STT</th>
          <th rowspan="2">Đối tượng vi phạm</th>
          <th rowspan="2">Hành vi vi phạm</th>
          <th rowspan="2">Điều khoản vi phạm</th>
          <th rowspan="2">Hậu quả định tính/định lượng</th>
          <th rowspan="2">Trách nhiệm</th>
          <th colspan="3">Kiến nghị xử lý</th>
        </tr>
        <tr>
          <th class="sub-th">Hình sự</th>
          <th class="sub-th">Hành chính</th>
          <th class="sub-th">Kinh tế</th>
        </tr>
      </thead>
      <tbody>
{body}
      </tbody>
    </table>
  </div>"""


def _recommendations(kien_nghi: dict) -> str:
    """Mục III — Kiến nghị xử lý (chung, cấp document).

    Đây là dữ liệu schema CÓ nhưng Bảng II không đặt được vào từng dòng.
    Render thành danh sách để không mất thông tin.
    """
    if not isinstance(kien_nghi, dict):
        return ""
    blocks = []
    labels = [
        ("chính sách", "Về cơ chế, chính sách, pháp luật"),
        ("kinh tế", "Về kinh tế (thu hồi, truy thu, hoàn trả)"),
        ("trách nhiệm", "Về kiểm điểm, xử lý trách nhiệm"),
    ]
    for key, label in labels:
        items = kien_nghi.get(key) or []
        if not isinstance(items, list) or not items:
            continue
        lis = "\n".join(f"        <li>{_esc(x)}</li>" for x in items if str(x).strip())
        if lis:
            blocks.append(
                f'    <div class="narrative-item">'
                f'<span class="lbl">{label}:</span>\n      <ul>\n{lis}\n      </ul>\n    </div>'
            )
    # hình sự: list of objects
    hinh_su = kien_nghi.get("hình sự") or []
    if isinstance(hinh_su, list) and hinh_su:
        lis = []
        for h in hinh_su:
            if not isinstance(h, dict):
                continue
            parts = [
                _esc_or(h.get("nội dung"), ""),
                f"(cơ quan nhận: {_esc(h.get('cơ quan nhận'))})" if h.get("cơ quan nhận") else "",
                f"— tình trạng: {_esc(h.get('tình trạng'))}" if h.get("tình trạng") else "",
            ]
            line = " ".join(p for p in parts if p)
            if line:
                lis.append(f"        <li>{line}</li>")
        if lis:
            blocks.append(
                '    <div class="narrative-item">'
                '<span class="lbl">Về hình sự (chuyển cơ quan điều tra):</span>\n'
                "      <ul>\n" + "\n".join(lis) + "\n      </ul>\n    </div>"
            )
    if not blocks:
        return ""
    return (
        '  <div class="section-title">III. Kiến nghị xử lý (chung)</div>\n'
        '  <div class="narrative-wrap">\n' + "\n".join(blocks) + "\n  </div>"
    )


# ── full-page assembly ─────────────────────────────────────────────────────

_CSS = """  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Times New Roman', Times, serif; background: #f4f6f9; color: #1f2937; line-height: 1.5; padding: 20px; }
  .container { max-width: 1400px; margin: 0 auto; }
  .doc-title { text-align: center; font-size: 18px; font-weight: 700; margin-bottom: 16px; text-transform: uppercase; color: #111; letter-spacing: 0.5px; }
  .doc-sub { text-align: center; font-size: 12px; color: #6b7280; margin-bottom: 16px; }
  .section-title { font-size: 15px; font-weight: 700; color: #1f3864; margin: 28px 0 12px 0; padding-bottom: 6px; border-bottom: 2px solid #1f3864; text-transform: uppercase; }
  .info-table { width: 100%; border-collapse: collapse; margin-bottom: 24px; background: white; box-shadow: 0 2px 4px rgba(0,0,0,0.05); font-size: 13px; }
  .info-table td { border: 1px solid #1f2937; padding: 10px 12px; vertical-align: top; }
  .info-table .label { font-weight: 700; background: #f3f4f6; width: 14%; }
  .info-table .value { width: 19.33%; background: white; }
  .main-table-wrap { background: white; border-radius: 8px; border: 1px solid #e5e7eb; overflow-x: auto; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
  table.main-table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
  table.main-table th, table.main-table td { border: 1px solid #1f2937; padding: 8px 10px; vertical-align: top; text-align: left; }
  table.main-table thead th { background: #1f3864; color: white; font-weight: 700; text-align: center; vertical-align: middle; }
  table.main-table thead .sub-th { background: #4472c4; }
  table.main-table tbody tr:nth-child(even) td { background: #f9fafb; }
  table.main-table td.stt { text-align: center; font-weight: 700; width: 40px; }
  table.main-table td.law { font-style: italic; color: #1f2937; font-size: 12px; }
  table.main-table td.consequence { color: #1f2937; }
  table.main-table td.recommend { font-size: 12px; }
  .narrative-wrap { background: white; border-radius: 8px; border: 1px solid #e5e7eb; padding: 24px 28px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); font-size: 14px; line-height: 1.75; }
  .narrative-item { margin-bottom: 18px; padding-bottom: 14px; border-bottom: 1px dashed #d1d5db; text-align: justify; }
  .narrative-item:last-child { margin-bottom: 0; padding-bottom: 0; border-bottom: none; }
  .narrative-item .num { font-weight: 700; color: #1f3864; margin-right: 4px; }
  .narrative-item .lbl { font-weight: 700; color: #1f3864; }
  .narrative-item ul { margin: 6px 0 0 22px; }
  @media print { body { background: white; padding: 0; } .main-table-wrap, .narrative-wrap { border: none; box-shadow: none; } .narrative-item { page-break-inside: avoid; } }
  @media (max-width: 768px) { body { padding: 10px; } .info-table .label { width: 30%; } .info-table .value { width: auto; display: block; } table.main-table { font-size: 11px; } .narrative-wrap { padding: 16px; } }"""


def _build_html(doc: dict) -> str:
    result = doc.get("result", {}) or {}
    tic = result.get("thông tin chung", {}) or {}
    vi_pham = result.get("vi phạm", []) or []
    kien_nghi = result.get("kiến nghị xử lý", {}) or {}

    so_vb = tic.get("số văn bản", "") or "(không rõ số văn bản)"
    generated = datetime.now().strftime("%d/%m/%Y %H:%M")

    section3 = _recommendations(kien_nghi)
    section3_block = f"\n{section3}\n" if section3 else "\n"

    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Bảng tóm tắt Kết luận thanh tra - {html.escape(so_vb)}</title>
<style>
{_CSS}
</style>
</head>
<body>
<div class="container">

  <div class="doc-title">Bảng tóm tắt nội dung Kết luận thanh tra</div>
  <div class="doc-sub">Số văn bản: {html.escape(so_vb)} · Tạo lúc {generated} · Nguồn: trích xuất tự động</div>

{_info_table(tic)}

  <div class="section-title">I. Trích lược vi phạm</div>
{_narrative(vi_pham)}

  <div class="section-title">II. Bảng chi tiết vi phạm</div>
{_detail_table(vi_pham)}
{section3_block}</div>
</body>
</html>
"""


# ── the tool ───────────────────────────────────────────────────────────────


@tool
@log_tool_call
def render_ttcp_report(so_van_ban: str) -> str:
    """Sinh báo cáo HTML 'Bảng tóm tắt Kết luận thanh tra' từ doc trong DB.

    Tra kết luận theo số văn bản (vd '636/TB-TTCP'), render ra file HTML
    theo template chuẩn: bảng thông tin chung, Mục I (trích lược vi phạm),
    Mục II (bảng chi tiết vi phạm), Mục III (kiến nghị xử lý chung).

    Mapping best-effort từ schema hiện tại — một số ô (ngày công bố, hình
    thức thanh tra, kiến nghị per-vi-phạm) schema chưa có sẽ để "—" /
    "Không nêu trong văn bản", KHÔNG bịa.

    Trả về JSON `{path, số văn bản, số vi phạm}` — `path` là file HTML đã ghi
    (mở bằng trình duyệt hoặc gửi cho user). Lỗi → `{error, message}`.
    """
    try:
        doc = _store.find_one({"status": "done", _P_SO_VB: so_van_ban})
        if not doc:
            return json.dumps(
                {"error": "not_found",
                 "message": f"không tìm thấy kết luận số '{so_van_ban}' (status=done) trong DB"},
                ensure_ascii=False,
            )

        html_text = _build_html(doc)

        out_dir = Path(settings.ttcp_report_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{_safe_filename(so_van_ban)}.html"
        out_path.write_text(html_text, encoding="utf-8")

        vi_pham = (doc.get("result", {}) or {}).get("vi phạm", []) or []
        return json.dumps(
            {
                "path": str(out_path.resolve()),
                "số văn bản": so_van_ban,
                "số vi phạm": len(vi_pham),
            },
            ensure_ascii=False,
        )
    except Exception as exc:
        log.exception("render_ttcp_report failed")
        return json.dumps({"error": "render_error", "message": str(exc)}, ensure_ascii=False)


render_ttcp_report.metadata = {
    "prompt_hint": (
        "Sinh báo cáo HTML 'Bảng tóm tắt Kết luận thanh tra' từ 1 kết luận "
        "trong DB (read-only). Dùng khi user muốn xuất / xem báo cáo / bảng "
        "tóm tắt của 1 số văn bản cụ thể. Trả về path file HTML."
    ),
}
