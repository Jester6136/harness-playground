"""Render a TTCP doc into the standard 'Bảng tóm tắt Kết luận thanh tra' HTML.

Best-effort mapping from the CURRENT `extract_ttcp` schema. The report
template (xem ``template-ttcp.html``) cần vài field schema chưa có:

  - thông tin chung: ngày công bố, ngày kết thúc thanh tra, hình thức thanh tra
  - vi phạm[]: hậu quả (riêng), nguyên nhân, kiến nghị per-violation 3 loại

Những ô đó render thành "—" / "Không nêu trong văn bản" — KHÔNG bịa.

`kiến nghị xử lý` cấp document (schema CÓ, nhưng không gắn được vào từng
dòng Bảng II) được render thành Mục III riêng, style khớp template, nên
không mất dữ liệu đã extract. Khi schema thêm kiến nghị per-violation thì
Bảng II tự đầy.

Style: bản template-ttcp.html — Tailwind (CDN), CSS scoped trong
`.tt-report-container`, nhận diện Thanh tra Chính phủ.
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


def _info_cell(label: str, value: str, *, full: bool = False, span2: bool = False) -> str:
    """One cell of the compact info-grid.

    `full` → spans the whole row (4 columns on desktop), with a red left
    border for the lead "Tên / Nội dung thanh tra" entry. `span2` → spans
    2 of 4 columns (used for Người ký, Lĩnh vực).
    """
    classes = "info-cell"
    if full:
        classes += " full"
    style_attr = ' style="grid-column: span 2 / span 2;"' if (span2 and not full) else ""
    return f"""            <div class="{classes}"{style_attr}>
              <span class="info-label">{label}</span>
              <p class="info-value">{value}</p>
            </div>"""


def _info_section(tic: dict) -> str:
    """Bảng thông tin chung — compact 4-column grid (template mới).

    Chỉ giữ những trường thường xuyên có giá trị: Tên/Nội dung, Quyết định,
    Ngày ban hành, Đơn vị chủ trì, Đối tượng, Người ký, Lĩnh vực. Các field
    schema có nhưng template gọn không hiển thị (ngày công bố, ngày kết
    thúc, hình thức, thời kỳ) vẫn lưu trong DB — render nội tuyến nếu sau
    này cần.
    """
    so_vb = tic.get("số văn bản", "")
    loai = tic.get("loại văn bản", "")
    qd_kl = f"{loai} {so_vb}".strip() if (loai or so_vb) else ""

    nguoi_ky = (tic.get("người ký") or "").strip()
    chuc_vu = (tic.get("chức vụ người ký") or "").strip()
    if chuc_vu and nguoi_ky:
        nguoi_html = f'{_esc(chuc_vu)} <span class="text-gray-500">({_esc(nguoi_ky)})</span>'
    elif chuc_vu:
        nguoi_html = _esc(chuc_vu)
    elif nguoi_ky:
        nguoi_html = _esc(nguoi_ky)
    else:
        nguoi_html = _DASH

    # Fall back to "cơ quan ban hành" if "đơn vị chủ trì" missing (v1 docs).
    don_vi_chu_tri = tic.get("đơn vị chủ trì") or tic.get("cơ quan ban hành", "")

    cells = [
        _info_cell("Tên / Nội dung thanh tra", _esc(tic.get("nội dung thanh tra")), full=True),
        _info_cell("Quyết định / Kết luận", _esc_or(qd_kl, _DASH)),
        _info_cell("Ngày ban hành", _esc(tic.get("ngày ban hành"))),
        _info_cell("Đơn vị chủ trì", _esc(don_vi_chu_tri)),
        _info_cell("Đối tượng", _esc(tic.get("đối tượng thanh tra"))),
        _info_cell("Người ký", nguoi_html, span2=True),
        _info_cell("Lĩnh vực", _join(tic.get("lĩnh vực")), span2=True),
    ]
    return f"""        <section class="mb-8">
          <h2 class="section-header text-base">Thông tin chung về cuộc thanh tra</h2>
          <div class="info-grid">
{chr(10).join(cells)}
          </div>
        </section>"""


def _rec_line(label: str, tag_class: str, text: str, *, money: bool = False) -> str:
    """One labelled recommendation line inside a card's `.rec-block`.

    `tag_class` ∈ {tag-admin, tag-eco, tag-crim}. `money=True` styles the
    text red+bold (used for Kinh tế lines with money figures).
    """
    text_cls = "rec-text eco-money" if money else "rec-text"
    return (
        f'                <p class="rec-line">'
        f'<span class="rec-tag {tag_class}">{label}</span>'
        f'<span class="{text_cls}">{html.escape(text.strip())}</span></p>'
    )


def _narrative_section(vi_pham: list) -> str:
    """Mục I — Trích lược vi phạm (cards compact).

    Mỗi card gồm: badge STT, dòng "Hành vi:", dòng meta italic (Điều khoản /
    Hậu quả / Nguyên nhân), và một `rec-block` ở dưới với các tag pill
    (Hành chính / Kinh tế / Hình sự) — chỉ hiển thị tag nào có nội dung.
    """
    if not vi_pham:
        body = (
            '          <div class="flex items-start gap-4 p-4 bg-white border '
            f'border-gray-200 rounded-md shadow-sm"><p class="text-sm text-gray-500">'
            f'{_NOT_STATED}.</p></div>'
        )
        return f"""        <section class="mb-10">
          <h2 class="section-header text-base">I. Trích lược vi phạm</h2>
          <div class="grid grid-cols-1 gap-4">
{body}
          </div>
        </section>"""

    cards = []
    for i, v in enumerate(vi_pham, 1):
        if not isinstance(v, dict):
            continue
        nghiem_trong = v.get("dấu hiệu tội phạm") is True
        hanh_vi = _esc(v.get("hành vi vi phạm"))
        dieu_khoan = (v.get("căn cứ vi phạm") or "").strip()
        # v2: dedicated "hậu quả" field; v1 fallback to "mô tả".
        hau_qua = (v.get("hậu quả") or v.get("mô tả") or "").strip()
        nguyen_nhan = (v.get("nguyên nhân") or "").strip()
        meta_parts = []
        if dieu_khoan:
            meta_parts.append(f"Điều khoản: {html.escape(dieu_khoan)}")
        if hau_qua:
            meta_parts.append(f"Hậu quả: {html.escape(hau_qua)}")
        if nguyen_nhan:
            meta_parts.append(f"Nguyên nhân: {html.escape(nguyen_nhan)}")
        meta = " | ".join(meta_parts) if meta_parts else f"Hậu quả: {_NOT_STATED}."

        # Per-violation kiến nghị → rec-block tag lines.
        kn = v.get("kiến nghị") if isinstance(v.get("kiến nghị"), dict) else {}
        hc_text = (kn.get("hành chính") or "").strip()
        kt_text = (kn.get("kinh tế") or "").strip()
        hs_text = (kn.get("hình sự") or "").strip()
        # v1 fallback: derive Hình sự from the dấu hiệu tội phạm flag.
        if not hs_text and nghiem_trong:
            hs_text = "Nếu phát hiện dấu hiệu vi phạm hình sự thì chuyển cơ quan điều tra"

        rec_lines = []
        if hc_text:
            rec_lines.append(_rec_line("Hành chính", "tag-admin", hc_text))
        if kt_text:
            rec_lines.append(_rec_line("Kinh tế", "tag-eco", kt_text, money=True))
        if hs_text:
            rec_lines.append(_rec_line("Hình sự", "tag-crim", hs_text))

        rec_block = ""
        if rec_lines:
            rec_block = (
                '\n              <div class="rec-block">\n'
                '                <span class="rec-title">Kiến nghị xử lý</span>\n'
                + "\n".join(rec_lines)
                + "\n              </div>"
            )

        cards.append(f"""          <div class="flex items-start gap-4 p-4 bg-white border border-gray-200 rounded-md shadow-sm hover:border-[#a3171e] transition-colors">
            <span class="flex-shrink-0 w-8 h-8 flex items-center justify-center bg-[#fef2f2] text-[#a3171e] font-bold rounded-full text-sm border border-[#fca5a5]">{i}</span>
            <div class="space-y-1">
              <p class="text-sm text-gray-800"><span class="font-bold text-[#8a1319]">Hành vi:</span> {hanh_vi}</p>
              <p class="text-[13px] text-gray-500 italic">{meta}</p>{rec_block}
            </div>
          </div>""")

    return f"""        <section class="mb-10">
          <h2 class="section-header text-base">I. Trích lược vi phạm</h2>
          <div class="grid grid-cols-1 gap-4">
{chr(10).join(cards)}
          </div>
        </section>"""


def _kn_cell(value: str, *, accent: str) -> str:
    """One cell of the Kiến nghị column trio. `accent` ∈ {hinh_su, hanh_chinh,
    kinh_te} styles the text to match the rest of the row when filled."""
    v = (value or "").strip()
    if not v:
        return '<td class="empty-dash">—</td>'
    cls = {
        "hinh_su": "text-[#a3171e] font-bold text-[13px]",
        "hanh_chinh": "font-medium text-[13px]",
        "kinh_te": "text-[#8a1319] font-bold text-[13px]",
    }[accent]
    return f'<td class="{cls}">{html.escape(v)}</td>'


def _detail_table(vi_pham: list) -> str:
    """Mục II — Bảng chi tiết vi phạm.

    Cột 'Kiến nghị xử lý' (Hình sự / Hành chính / Kinh tế) đọc trực tiếp từ
    `v["kiến nghị"]` của schema v2. Với doc v1 còn lại (chưa re-extract):
    cột Hình sự fallback suy từ flag `dấu hiệu tội phạm`; Hành chính / Kinh
    tế giữ em-dash (Mục III sẽ hiển thị kiến nghị chung).
    """
    rows = []
    for i, v in enumerate(vi_pham or [], 1):
        if not isinstance(v, dict):
            continue
        nghiem_trong = v.get("dấu hiệu tội phạm") is True
        # v2: dedicated "hậu quả"; v1 fallback to "mô tả".
        hau_qua = (v.get("hậu quả") or v.get("mô tả") or "").strip()
        gt = v.get("giá trị triệu đồng")
        if isinstance(gt, (int, float)):
            hau_qua = f"{hau_qua} (Giá trị: {_num(gt)} triệu đồng)".strip()

        # v2: per-violation kiến nghị; v1: derive Hình sự from flag, others "—".
        kn = v.get("kiến nghị") if isinstance(v.get("kiến nghị"), dict) else {}
        hs_text = kn.get("hình sự", "")
        hc_text = kn.get("hành chính", "")
        kt_text = kn.get("kinh tế", "")
        if not hs_text and nghiem_trong:
            hs_text = "Có dấu hiệu tội phạm — kiến nghị chuyển cơ quan điều tra"

        tr_cls = ' class="bg-red-50/40 hover:bg-red-100"' if nghiem_trong else ""
        stt_cls = "text-[#a3171e]" if nghiem_trong else "text-gray-500"
        rows.append(f"""                <tr{tr_cls}>
                  <td class="text-center font-bold {stt_cls}">{i}</td>
                  <td><strong>{_esc(v.get("đối tượng vi phạm"))}</strong></td>
                  <td>{_esc(v.get("hành vi vi phạm"))}</td>
                  <td class="italic text-[13px] text-gray-600">{_esc(v.get("căn cứ vi phạm"))}</td>
                  <td>{_esc_or(hau_qua, _NOT_STATED)}</td>
                  <td>{_esc(v.get("trách nhiệm"))}</td>
                  {_kn_cell(hs_text, accent="hinh_su")}
                  {_kn_cell(hc_text, accent="hanh_chinh")}
                  {_kn_cell(kt_text, accent="kinh_te")}
                </tr>""")
    body = "\n".join(rows) or (
        '                <tr><td colspan="9" class="empty-dash">' + _NOT_STATED + "</td></tr>"
    )
    return f"""        <section class="mb-14">
          <h2 class="section-header text-base">II. Bảng chi tiết vi phạm</h2>
          <div class="table-container">
            <table class="v-table">
              <thead>
                <tr>
                  <th rowspan="2" class="w-12 border-r border-[#9c151b]">STT</th>
                  <th rowspan="2" class="w-[12%] border-r border-[#9c151b]">Đối tượng vi phạm</th>
                  <th rowspan="2" class="w-[22%] border-r border-[#9c151b]">Hành vi vi phạm</th>
                  <th rowspan="2" class="w-[12%] border-r border-[#9c151b]">Điều khoản vi phạm</th>
                  <th rowspan="2" class="w-[15%] border-r border-[#9c151b]">Hậu quả định tính/định lượng</th>
                  <th rowspan="2" class="w-[12%] border-r border-[#9c151b]">Trách nhiệm</th>
                  <th colspan="3" class="border-b-gold uppercase tracking-wider text-[0.8rem]">Kiến nghị xử lý</th>
                </tr>
                <tr>
                  <th class="sub-th w-[8%] border-r border-[#c4252e]">Hình sự</th>
                  <th class="sub-th w-[10%] border-r border-[#c4252e]">Hành chính</th>
                  <th class="sub-th w-[9%]">Kinh tế</th>
                </tr>
              </thead>
              <tbody>
{body}
              </tbody>
            </table>
          </div>
        </section>"""


def _recommendations_section(kien_nghi: dict) -> str:
    """Mục III — Kiến nghị xử lý (chung, cấp document).

    Dữ liệu schema CÓ nhưng Bảng II không đặt được vào từng dòng. Render
    thành cards khớp style template để không mất thông tin.
    """
    if not isinstance(kien_nghi, dict):
        return ""
    cards = []
    labels = [
        ("chính sách", "Về cơ chế, chính sách, pháp luật"),
        ("kinh tế", "Về kinh tế (thu hồi, truy thu, hoàn trả)"),
        ("trách nhiệm", "Về kiểm điểm, xử lý trách nhiệm"),
    ]
    for key, label in labels:
        items = kien_nghi.get(key) or []
        if not isinstance(items, list) or not items:
            continue
        lis = "\n".join(
            f"              <li>{_esc(x)}</li>" for x in items if str(x).strip()
        )
        if lis:
            cards.append(f"""          <div class="p-4 bg-white border border-gray-200 rounded-md shadow-sm">
            <p class="font-bold text-[#8a1319] text-sm mb-2">{label}</p>
            <ul class="list-disc pl-5 space-y-1 text-sm text-gray-800">
{lis}
            </ul>
          </div>""")

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
                lis.append(f"              <li>{line}</li>")
        if lis:
            cards.append(f"""          <div class="p-4 bg-red-50 border border-red-300 rounded-md shadow-sm">
            <p class="font-bold text-red-700 text-sm mb-2">Về hình sự (chuyển cơ quan điều tra)</p>
            <ul class="list-disc pl-5 space-y-1 text-sm text-gray-900">
{chr(10).join(lis)}
            </ul>
          </div>""")

    if not cards:
        return ""
    return f"""        <section class="mb-6">
          <h2 class="section-header text-base">III. Kiến nghị xử lý (chung)</h2>
          <div class="grid grid-cols-1 gap-4">
{chr(10).join(cards)}
          </div>
        </section>"""


# ── CSS (scoped under .tt-report-container — từ template-ttcp.html) ─────────

_CSS = """        .tt-report-container {
            --tt-red: #a3171e;
            --tt-red-dark: #8a1319;
            --tt-gold: #d4af37;
            --tt-text: #333333;
            --tt-border: #e2e8f0;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            color: var(--tt-text);
            line-height: 1.6;
        }
        .tt-report-container .table-container {
            overflow-x: auto;
            border-radius: 6px;
            box-shadow: 0 4px 15px -3px rgba(0, 0, 0, 0.08);
            background: white;
            border: 1px solid var(--tt-border);
        }
        .tt-report-container .v-table {
            width: 100%;
            border-collapse: collapse;
            min-width: 1250px;
        }
        .tt-report-container .v-table th,
        .tt-report-container .v-table td {
            border: 1px solid var(--tt-border);
        }
        .tt-report-container .v-table thead {
            border-top: 4px solid var(--tt-gold);
        }
        .tt-report-container .v-table thead th {
            background-color: var(--tt-red-dark);
            color: #ffffff;
            text-align: center;
            vertical-align: middle;
            padding: 0.875rem 0.5rem;
            font-weight: 600;
            font-size: 0.85rem;
            line-height: 1.4;
        }
        .tt-report-container .v-table thead th.sub-th {
            background-color: #b72028;
            font-weight: 500;
            border-color: #9c151b;
        }
        .tt-report-container .v-table thead th.border-b-gold {
            border-bottom: 1px solid #d66468;
        }
        .tt-report-container .v-table tbody td {
            padding: 0.875rem 1rem;
            vertical-align: top;
            font-size: 0.875rem;
            color: #1e293b;
        }
        .tt-report-container .v-table tbody tr:nth-child(even) {
            background-color: #fafafa;
        }
        .tt-report-container .v-table tbody tr:hover {
            background-color: #fef2f2;
        }
        .tt-report-container .section-header {
            border-bottom: 2px solid var(--tt-red);
            margin-bottom: 1.5rem;
            padding-bottom: 0.5rem;
            color: var(--tt-red);
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.025em;
            display: flex;
            align-items: center;
        }
        .tt-report-container .section-header::before {
            content: '';
            display: inline-block;
            width: 6px;
            height: 1.2rem;
            background-color: var(--tt-gold);
            margin-right: 10px;
        }
        .tt-report-container .empty-dash {
            text-align: center;
            color: #cbd5e1;
            font-weight: bold;
        }
        /* === Compact info block === */
        .tt-report-container .info-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.5rem;
            background: #f8fafc;
            border: 1px solid var(--tt-border);
            border-radius: 8px;
            padding: 0.875rem;
        }
        @media (min-width: 768px) {
            .tt-report-container .info-grid {
                grid-template-columns: repeat(4, minmax(0, 1fr));
            }
        }
        .tt-report-container .info-cell {
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 5px;
            padding: 0.55rem 0.75rem;
        }
        .tt-report-container .info-cell.full {
            grid-column: 1 / -1;
            border-left: 3px solid var(--tt-red);
        }
        .tt-report-container .info-label {
            font-size: 0.65rem;
            font-weight: 700;
            color: var(--tt-red);
            text-transform: uppercase;
            letter-spacing: 0.04em;
            margin-bottom: 0.15rem;
            display: block;
        }
        .tt-report-container .info-value {
            font-size: 0.8rem;
            color: #1f2937;
            line-height: 1.45;
        }
        .tt-report-container .info-cell.full .info-value {
            font-size: 0.85rem;
            line-height: 1.55;
        }
        /* === Recommendation block trong phần I === */
        .tt-report-container .rec-block {
            margin-top: 0.5rem;
            padding: 0.55rem 0.7rem;
            background: #fff8f1;
            border-left: 3px solid #d4af37;
            border-radius: 4px;
        }
        .tt-report-container .rec-title {
            font-size: 0.7rem;
            font-weight: 700;
            color: #8a1319;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            margin-bottom: 0.25rem;
            display: block;
        }
        .tt-report-container .rec-line {
            font-size: 0.8rem;
            color: #1f2937;
            line-height: 1.45;
            margin: 0.1rem 0;
            display: flex;
            align-items: flex-start;
            gap: 0.4rem;
        }
        .tt-report-container .rec-tag {
            flex-shrink: 0;
            display: inline-block;
            font-size: 0.65rem;
            font-weight: 700;
            padding: 0.1rem 0.45rem;
            border-radius: 3px;
            text-transform: uppercase;
            letter-spacing: 0.03em;
            line-height: 1.4;
            white-space: nowrap;
        }
        .tt-report-container .rec-tag.tag-admin {
            background: #dbeafe;
            color: #1e40af;
        }
        .tt-report-container .rec-tag.tag-eco {
            background: #fee2e2;
            color: #8a1319;
        }
        .tt-report-container .rec-tag.tag-crim {
            background: #fef3c7;
            color: #92400e;
        }
        .tt-report-container .rec-text {
            flex: 1;
        }
        .tt-report-container .rec-text.eco-money {
            font-weight: 600;
            color: #8a1319;
        }
        @media print {
            .tt-report-container .no-print { display: none !important; }
            .tt-report-container { padding: 0 !important; background: white !important; }
            .tt-report-container .v-table thead th { background-color: var(--tt-red-dark) !important; color: white !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
            .tt-report-container .v-table thead th.sub-th { background-color: #b72028 !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
            .tt-report-container .v-table tbody tr:nth-child(even) { background-color: #fafafa !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
            .tt-report-container .section-header { color: var(--tt-red) !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
            .tt-report-container .info-grid { background: #f8fafc !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
        }"""


_PRINT_BUTTON_SVG = (
    '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">'
    '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" '
    'd="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 '
    "2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 "
    '2 0 00-2 2v4h10z"></path></svg>'
)


# ── full-page assembly ─────────────────────────────────────────────────────


def _build_html(doc: dict) -> str:
    result = doc.get("result", {}) or {}
    tic = result.get("thông tin chung", {}) or {}
    vi_pham = result.get("vi phạm", []) or []
    kien_nghi = result.get("kiến nghị xử lý", {}) or {}

    so_vb = tic.get("số văn bản", "") or "(không rõ số văn bản)"
    generated = datetime.now().strftime("%d/%m/%Y")

    info = _info_section(tic)
    narrative = _narrative_section(vi_pham)
    detail = _detail_table(vi_pham)
    recommendations = _recommendations_section(kien_nghi)

    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Bảng tóm tắt Kết luận thanh tra - {html.escape(so_vb)}</title>
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
{_CSS}
</style>
</head>
<body class="bg-transparent m-0 p-0">

  <div class="tt-report-container antialiased w-full h-full p-2 md:p-6 bg-transparent">
    <div class="max-w-[1400px] mx-auto bg-white shadow-lg border border-gray-200 rounded-lg overflow-hidden">

      <header class="bg-gradient-to-b from-[#a3171e] to-[#8a1319] text-white p-6 md:p-8 flex flex-col items-center text-center relative border-b-4 border-[#d4af37]">
        <img src="https://upload.wikimedia.org/wikipedia/commons/a/a3/Emblem_of_Vietnam.svg" alt="Quốc huy Việt Nam" class="w-16 md:w-20 mb-3 drop-shadow-lg">
        <h1 class="text-lg md:text-xl lg:text-2xl font-bold uppercase tracking-wide text-[#f8e5ad]">
          Bảng Tóm Tắt Nội Dung Kết Luận Thanh Tra
        </h1>
        <p class="mt-2 text-white/80 text-sm font-medium">Số văn bản: {html.escape(so_vb)}</p>
      </header>

      <main class="p-6 md:p-8">
{info}

{narrative}

{detail}

{recommendations}
      </main>

      <footer class="bg-[#f8fafc] p-6 border-t border-gray-200 text-center no-print rounded-b-lg">
        <button onclick="window.focus(); window.print();" class="bg-[#a3171e] hover:bg-[#8a1319] text-white font-bold py-2.5 px-8 rounded shadow transition-all inline-flex items-center gap-2 border-b-4 border-[#7a1015] active:border-b-0 active:translate-y-1">
          {_PRINT_BUTTON_SVG}
          In / Xuất PDF báo cáo
        </button>
        <p class="mt-4 text-[11px] text-gray-500 uppercase tracking-widest font-semibold">
          Tài liệu lưu hành nội bộ — Tạo tự động lúc {generated}
        </p>
      </footer>

    </div>
  </div>

</body>
</html>
"""


# ── the tool ───────────────────────────────────────────────────────────────


@tool
@log_tool_call
def render_ttcp_report(so_van_ban: str) -> str:
    """Sinh báo cáo HTML 'Bảng tóm tắt Kết luận thanh tra' từ doc trong DB.

    Tra kết luận theo số văn bản (vd '636/TB-TTCP'), render ra file HTML
    theo template chuẩn (nhận diện Thanh tra Chính phủ): bảng thông tin
    chung, Mục I (trích lược vi phạm), Mục II (bảng chi tiết vi phạm),
    Mục III (kiến nghị xử lý chung).

    Mapping best-effort từ schema hiện tại — một số ô (ngày công bố, hình
    thức thanh tra, kiến nghị per-vi-phạm) schema chưa có sẽ để "—" /
    "Không nêu trong văn bản", KHÔNG bịa.

    Trả về JSON `{report_id, url, filename, caption, số văn bản, số vi phạm}`:
      - `url` là đường dẫn tương đối `/reports/<id>.html` do harness API serve
        (KHÔNG phải path filesystem — đừng bịa path tuyệt đối).
      - Web UI: link mở trực tiếp. Telegram: bot tự đính kèm file.
    Lỗi → `{error, message}`.
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

        report_id = _safe_filename(so_van_ban)
        out_dir = Path(settings.ttcp_report_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{report_id}.html").write_text(html_text, encoding="utf-8")

        vi_pham = (doc.get("result", {}) or {}).get("vi phạm", []) or []
        return json.dumps(
            {
                "report_id": report_id,
                "url": f"/reports/{report_id}.html",
                "filename": f"{report_id}.html",
                "caption": f"📄 Báo cáo tóm tắt — {so_van_ban} ({len(vi_pham)} vi phạm)",
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
        "tóm tắt của 1 số văn bản cụ thể. Trả về URL file HTML."
    ),
}
