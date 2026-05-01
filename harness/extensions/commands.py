"""Slash command dispatcher.

Commands are registered via @register_command. When a message starts with '/',
the API (harness/api.py) parses it and dispatches to the handler instead of
passing it to the agent.

Handler types:
  "direct"   — sync/async function, result streamed as a single AI message.
  "agent"    — pre-filled message sent to the full agent (still streams SSE).
  "pipeline" — calls a registered pipeline (T2.2), returns structured JSON.

Example registration:
    @register_command(
        name="help",
        description="List available commands",
        handler="direct",
    )
    async def cmd_help(args: str) -> str:
        ...

GET /commands returns the metadata for frontend autocomplete.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable

from harness.extensions.skills import load_skills


@dataclass
class Command:
    name: str
    description: str
    handler: str  # "direct" | "agent" | "pipeline"
    fn: Callable[..., Any] | None = None
    pipeline_name: str | None = None
    skill_name: str | None = None
    args_schema: dict = field(default_factory=dict)


COMMANDS: dict[str, Command] = {}


def register_command(
    name: str,
    description: str,
    handler: str = "direct",
    pipeline_name: str | None = None,
    skill_name: str | None = None,
    args_schema: dict | None = None,
):
    """Decorator to register a slash command."""
    def decorator(fn: Callable) -> Callable:
        COMMANDS[name] = Command(
            name=name,
            description=description,
            handler=handler,
            fn=fn,
            pipeline_name=pipeline_name,
            skill_name=skill_name,
            args_schema=args_schema or {},
        )
        return fn
    return decorator


def parse_command(message: str) -> tuple[str, str] | None:
    """If message starts with '/', return (command_name, args_string). Else None."""
    if not message.startswith("/"):
        return None
    parts = message[1:].split(None, 1)
    cmd = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""
    return cmd, args


async def dispatch(cmd: str, args: str) -> tuple[str, str]:
    """Dispatch a slash command. Returns (handler_type, result_or_prompt).

    For 'direct': result is the string to stream back.
    For 'agent': result is the message to send to the agent.
    For 'pipeline': result is the pipeline name (api.py calls the pipeline).
    For 'clear': caller must delete the current session, then display result string.
    """
    command = COMMANDS.get(cmd)
    if command is None:
        return "direct", f"Unknown command: /{cmd}. Type /help for available commands."

    if command.handler in ("direct", "clear") and command.fn:
        if asyncio.iscoroutinefunction(command.fn):
            result = await command.fn(args)
        else:
            result = command.fn(args)
        return command.handler, str(result)

    if command.handler == "agent":
        if command.fn:
            if asyncio.iscoroutinefunction(command.fn):
                prompt = await command.fn(args)
            else:
                prompt = command.fn(args)
            return "agent", str(prompt)
        return "agent", args

    if command.handler == "pipeline":
        return "pipeline", command.pipeline_name or cmd

    return "direct", f"/{cmd} is registered but has no handler."


# ---------------------------------------------------------------------------
# Built-in commands
# ---------------------------------------------------------------------------

@register_command("help", "List all available slash commands")
def _cmd_help(args: str) -> str:
    lines = ["**Available commands:**\n"]
    for c in sorted(COMMANDS.values(), key=lambda x: x.name):
        lines.append(f"  `/{c.name}` — {c.description}")
    return "\n".join(lines)


@register_command("clear", "Xoá toàn bộ lịch sử của session hiện tại", handler="clear")
def _cmd_clear(args: str) -> str:
    return "Đã xoá lịch sử session."


@register_command("list-skills", "List all loaded skill sub-agents", handler="direct")
def _cmd_list_skills(args: str) -> str:
    skills = load_skills()
    if not skills:
        return "No skills loaded."
    lines = ["**Loaded skills:**\n"]
    for s in skills:
        lines.append(f"  `{s['name']}` — {s['description']}")
    return "\n".join(lines)


_LOAI_DOI_TUONG = {
    1: ("caNhan", "Cá nhân"),
    2: ("toChuc", "Tổ chức"),
    3: ("hoGiaDinh", "Hộ gia đình"),
    4: ("voChong", "Vợ chồng"),
    5: ("congDongDanCu", "Cộng đồng dân cư"),
}


def _maybe_json(val):
    """psycopg may return `json` columns as raw strings (vs `jsonb` auto-decoded).
    Decode to native list/dict if needed; pass through if already parsed."""
    if isinstance(val, str):
        import json
        try:
            return json.loads(val)
        except json.JSONDecodeError:
            return None
    return val


def _audit_phap_nhan(pn: dict) -> tuple[str, list[str]]:
    issues: list[str] = []
    loai_raw = pn.get("loaiDoiTuong")
    try:
        loai = int(loai_raw) if loai_raw is not None else None
    except (TypeError, ValueError):
        loai = None
    key, label = _LOAI_DOI_TUONG.get(loai, (None, f"loại không rõ ({loai_raw})"))
    if key is None:
        issues.append("loaiDoiTuong không hợp lệ")
        return label, issues

    nested = pn.get(key)
    if not nested:
        issues.append(f"thiếu chi tiết {label}")
        return label, issues

    if key == "hoGiaDinh":
        chu_ho = nested.get("chuHo") or {}
        if not chu_ho:
            issues.append("thiếu thông tin chủ hộ")
        gtpn = (chu_ho.get("giayToPhapNhan") or [])
        name = chu_ho.get("hoTen") or "?"
    elif key == "voChong":
        n1 = nested.get("nguoiThuNhat") or {}
        n2 = nested.get("nguoiThuHai") or {}
        if not n1:
            issues.append("thiếu người thứ nhất")
        if not n2:
            issues.append("thiếu người thứ hai")
        gtpn = (n1.get("giayToPhapNhan") or []) + (n2.get("giayToPhapNhan") or [])
        name = f"{n1.get('hoTen','?')} & {n2.get('hoTen','?')}"
    else:
        gtpn = nested.get("giayToPhapNhan") or []
        name = (
            nested.get("hoTen")
            or nested.get("tenToChuc")
            or nested.get("tenCongDong")
            or "?"
        )

    if not gtpn:
        issues.append("thiếu giấy tờ định danh (CMND/CCCD/MST/hộ chiếu)")
    return f"{label} — {name}", issues


def _audit_thua_dat(td: dict) -> tuple[str, list[str]]:
    issues: list[str] = []
    for field, label in (
        ("soHieuToBanDo", "số tờ bản đồ"),
        ("soThuTuThua", "số thứ tự thửa"),
        ("dienTich", "diện tích"),
        ("diaChi", "địa chỉ"),
    ):
        if td.get(field) in (None, "", 0):
            issues.append(f"thiếu {label}")
    desc = f"tờ {td.get('soHieuToBanDo','?')}, thửa {td.get('soThuTuThua','?')}"
    return desc, issues


def _audit_mdsdd(m: dict) -> tuple[str, list[str]]:
    issues: list[str] = []
    loai_mdsdd = m.get("loaiMdsdd")
    if not loai_mdsdd:
        issues.append("thiếu loại mục đích")
    if m.get("dienTich") in (None, 0):
        issues.append("thiếu diện tích")
    if m.get("thoiHanSuDung") in (None, "") and not m.get("thoiHanSuDungLauDai"):
        issues.append("thiếu thời hạn sử dụng")
    desc = (loai_mdsdd or {}).get("tenMucDich") or "?"
    return desc, issues


def _audit_gcn(g: dict) -> tuple[str, list[str]]:
    issues: list[str] = []
    for field, label in (
        ("soHieuGcn", "số hiệu"),
        ("soVaoSo", "số vào sổ"),
        ("ngayVaoSo", "ngày vào sổ"),
        ("tenNguoiKy", "người ký"),
    ):
        if not g.get(field):
            issues.append(f"thiếu {label}")
    hsq = g.get("hoSoQuets") or []
    if not hsq:
        issues.append("thiếu hồ sơ quét")
    else:
        empty = [i + 1 for i, h in enumerate(hsq) if not (h.get("papers") or [])]
        if empty:
            issues.append(
                f"hồ sơ quét #{','.join(map(str,empty))} thiếu file scan"
            )
    return g.get("soHieuGcn") or "?", issues


@register_command(
    "status",
    "Sức khoẻ chi tiết của Đơn đăng ký theo id (4 nhóm + sub-fields)",
    handler="direct",
    args_schema={"id": "str — UUID đơn đăng ký"},
)
async def _cmd_status(args: str) -> str:
    don_id = args.strip()
    if not don_id:
        return "Cú pháp: `/status <don_dang_ky_id>`"

    from harness.persistence.lis_db import run_query
    from harness.persistence.lis_queries import CHECK_DON_DANG_KY

    try:
        rows = await run_query(CHECK_DON_DANG_KY, (don_id,), row_cap=1)
    except Exception as exc:
        return f"❌ Lỗi DB: `{type(exc).__name__}: {exc}`"
    if not rows:
        return f"❌ Không tìm thấy đơn đăng ký id `{don_id}`."

    r = rows[0]
    sections = (
        ("Pháp nhân (chủ sở hữu)",     _maybe_json(r.get("phapNhanSdds")),    _audit_phap_nhan),
        ("Thửa đất",                   _maybe_json(r.get("thuaDats")),         _audit_thua_dat),
        ("Mục đích sử dụng đất",       _maybe_json(r.get("daMdsdds")),         _audit_mdsdd),
        ("Giấy chứng nhận",            _maybe_json(r.get("giayChungNhans")),   _audit_gcn),
    )

    lines = [f"**Sức khoẻ đơn đăng ký** `{don_id}`\n"]
    overall_missing: list[str] = []

    for title, items, auditor in sections:
        items = items or []
        lines.append(f"### {title} ({len(items)})")
        if not items:
            lines.append("  ✗ **không có dữ liệu — cần bổ sung**")
            overall_missing.append(f"{title} (rỗng)")
            lines.append("")
            continue
        for i, item in enumerate(items, 1):
            desc, issues = auditor(item)
            if issues:
                lines.append(f"  ✗ #{i} {desc}")
                for iss in issues:
                    lines.append(f"      • {iss}")
                overall_missing.append(f"{title} #{i}")
            else:
                lines.append(f"  ✓ #{i} {desc}")
        lines.append("")

    if not overall_missing:
        lines.append("→ **ĐẦY ĐỦ**. Cả 4 nhóm và các trường chính đều có dữ liệu.")
    else:
        lines.append(
            f"→ **THIẾU CHI TIẾT** ({len(overall_missing)} item): "
            + ", ".join(f"`{m}`" for m in overall_missing)
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# GCN lookup commands — flat snake_case rows, dedup by entity id.
# ---------------------------------------------------------------------------

def _fmt_date(val) -> str:
    if val is None:
        return "?"
    from datetime import date, datetime
    if isinstance(val, (date, datetime)):
        return val.strftime("%d/%m/%Y")
    return str(val)


def _fmt_area(val) -> str:
    if val is None:
        return "?"
    try:
        return f"{float(val):,.1f} m²".replace(",", ".")
    except (TypeError, ValueError):
        return str(val)


def _format_gcn_rows(rows: list[dict]) -> str:
    """Render flat rows (1 GCN, multiple JOINs) into Markdown."""
    r0 = rows[0]
    lines: list[str] = []

    lines.append(f"**GCN: {r0.get('so_hieu_gcn', '?')}**")
    meta = [str(v) for v in (r0.get("loai_gcn"), r0.get("tinh_trang_gcn")) if v]
    if meta:
        lines.append(" | ".join(meta))
    if r0.get("so_ho_so_goc"):
        lines.append(f"Hồ sơ gốc: {r0['so_ho_so_goc']}")
    if r0.get("so_vao_so"):
        lines.append(f"Vào sổ: {r0['so_vao_so']} ngày {_fmt_date(r0.get('ngay_vao_so'))}")
    if r0.get("ten_nguoi_ky"):
        lines.append(f"Người ký: {r0['ten_nguoi_ky']}")

    seen_pn:    dict[str, dict] = {}
    seen_td:    dict[str, dict] = {}
    seen_nha:   dict[str, dict] = {}
    seen_ctxd:  dict[str, dict] = {}
    seen_paper: dict[str, dict] = {}
    for row in rows:
        for key, store in (
            ("phap_nhan_id", seen_pn),
            ("thua_dat_id",  seen_td),
            ("nha_id",       seen_nha),
            ("ctxd_id",      seen_ctxd),
        ):
            v = row.get(key)
            if v and v not in store:
                store[v] = row
        fp = row.get("file_scan_path")
        if fp and fp not in seen_paper:
            seen_paper[fp] = row

    if seen_pn:
        lines.append(f"\n**Chủ sở hữu ({len(seen_pn)}):**")
        for row in seen_pn.values():
            if row.get("loai_doi_tuong") == 1:
                lines.append(
                    f"  Cá nhân: **{row.get('ho_ten') or '?'}**"
                    + (f" | sinh {_fmt_date(row['ngay_sinh'])}" if row.get("ngay_sinh") else "")
                    + (f" | {row['dia_chi_chu']}" if row.get("dia_chi_chu") else "")
                )
            elif row.get("loai_doi_tuong") == 2:
                lines.append(
                    f"  Tổ chức: **{row.get('ten_to_chuc') or '?'}**"
                    + (f" | MSDN: {row['ma_so_doanh_nghiep']}" if row.get("ma_so_doanh_nghiep") else "")
                )

    if seen_td:
        lines.append(f"\n**Thửa đất ({len(seen_td)}):**")
        for row in seen_td.values():
            desc = f"  Tờ {row.get('so_hieu_to_ban_do','?')}, thửa {row.get('so_thu_tu_thua','?')}"
            if row.get("dien_tich"):
                desc += f" — {_fmt_area(row['dien_tich'])}"
            if row.get("muc_dich_su_dung"):
                desc += f" | {row['muc_dich_su_dung']}"
            location = ", ".join(filter(None, [row.get("dia_chi_thua_dat"), row.get("ten_xa")]))
            if location:
                desc += f" | {location}"
            lines.append(desc)

    if seen_nha:
        lines.append(f"\n**Nhà ({len(seen_nha)}):**")
        for row in seen_nha.values():
            parts = []
            if row.get("so_tang"): parts.append(f"{row['so_tang']} tầng")
            if row.get("dien_tich_san"): parts.append(f"sàn {_fmt_area(row['dien_tich_san'])}")
            if row.get("ket_cau_nha"): parts.append(row["ket_cau_nha"])
            if row.get("nam_xay_dung"): parts.append(f"XD {row['nam_xay_dung']}")
            lines.append(f"  Số {row.get('so_nha','?')}" + (f" ({', '.join(parts)})" if parts else ""))

    if seen_ctxd:
        lines.append(f"\n**Công trình XD ({len(seen_ctxd)}):**")
        for row in seen_ctxd.values():
            desc = f"  {row.get('ten_cong_trinh','?')}"
            if row.get("dt_ctxd"): desc += f" ({_fmt_area(row['dt_ctxd'])})"
            lines.append(desc)

    if seen_paper:
        lines.append(f"\n**File scan ({len(seen_paper)}):**")
        for row in seen_paper.values():
            lines.append(f"  {row.get('file_scan_name') or row['file_scan_path']}")

    return "\n".join(lines)


def _format_giay_to_rows(rows: list[dict]) -> str:
    """Render rows from lookup_gcn_by_giay_to_dinh_danh."""
    r0 = rows[0]
    lines = [f"**Chủ sở hữu: {r0.get('ten_chu') or '?'}**"]
    gt_parts = [r0.get("so_giay_to") or "?"]
    if r0.get("loai_giay_to"): gt_parts.append(r0["loai_giay_to"])
    if r0.get("ngay_cap"): gt_parts.append(f"cấp {_fmt_date(r0['ngay_cap'])}")
    if r0.get("noi_cap"): gt_parts.append(f"tại {r0['noi_cap']}")
    lines.append("Giấy tờ: " + " | ".join(gt_parts))

    seen_gcn:    dict[str, dict]       = {}
    gcn_td_keys: dict[str, set[tuple]] = {}
    gcn_tds:     dict[str, list[dict]] = {}

    for row in rows:
        gid = row.get("gcn_id")
        if not gid:
            continue
        if gid not in seen_gcn:
            seen_gcn[gid] = row
            gcn_td_keys[gid] = set()
            gcn_tds[gid] = []
        td_key = (row.get("so_hieu_to_ban_do"), row.get("so_thu_tu_thua"))
        if any(v is not None for v in td_key) and td_key not in gcn_td_keys[gid]:
            gcn_td_keys[gid].add(td_key)
            gcn_tds[gid].append(row)

    lines.append(f"\n**Tìm thấy {len(seen_gcn)} GCN:**")
    for i, (gid, row) in enumerate(seen_gcn.items(), 1):
        hdr = f"\n**{i}. GCN {row.get('so_hieu_gcn','?')}**"
        if row.get("tinh_trang_gcn"): hdr += f" — {row['tinh_trang_gcn']}"
        lines.append(hdr)
        if row.get("loai_gcn"): lines.append(f"   Loại: {row['loai_gcn']}")
        for td in gcn_tds[gid]:
            desc = f"   Thửa: tờ {td.get('so_hieu_to_ban_do','?')}, thửa {td.get('so_thu_tu_thua','?')}"
            if td.get("dien_tich"): desc += f" — {_fmt_area(td['dien_tich'])}"
            if td.get("muc_dich_su_dung"): desc += f" | {td['muc_dich_su_dung']}"
            lines.append(desc)

    return "\n".join(lines)


@register_command(
    "sohieu",
    "Tra cứu GCN theo số hiệu (vd. /sohieu CH 00123)",
    handler="direct",
    args_schema={"so_hieu_gcn": "str — số hiệu GCN"},
)
async def _cmd_sohieu(args: str) -> str:
    so_hieu = args.strip()
    if not so_hieu:
        return "Cú pháp: `/sohieu <so_hieu_gcn>`"

    from harness.persistence.lis_db import run_query
    from harness.persistence.lis_queries import GET_GCN_BY_SO_HIEU

    try:
        rows = await run_query(GET_GCN_BY_SO_HIEU, (so_hieu,), row_cap=50)
    except Exception as exc:
        return f"❌ Lỗi DB: `{type(exc).__name__}: {exc}`"
    if not rows:
        return f"❌ Không tìm thấy GCN với số hiệu `{so_hieu}`."
    return _format_gcn_rows(rows)


@register_command(
    "giayto",
    "Tra cứu GCN theo số giấy tờ chủ sở hữu (CMND/CCCD)",
    handler="direct",
    args_schema={"so_giay_to": "str — số CMND/CCCD"},
)
async def _cmd_giayto(args: str) -> str:
    so_gt = args.strip()
    if not so_gt:
        return "Cú pháp: `/giayto <so_giay_to>`"

    from harness.persistence.lis_db import run_query
    from harness.persistence.lis_queries import GET_GCN_BY_GIAY_TO_DINH_DANH

    try:
        rows = await run_query(GET_GCN_BY_GIAY_TO_DINH_DANH, (so_gt,), row_cap=50)
    except Exception as exc:
        return f"❌ Lỗi DB: `{type(exc).__name__}: {exc}`"
    if not rows:
        return f"❌ Không tìm thấy GCN nào với số giấy tờ `{so_gt}`."
    return _format_giay_to_rows(rows)
