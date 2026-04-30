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
    """
    command = COMMANDS.get(cmd)
    if command is None:
        return "direct", f"Unknown command: /{cmd}. Type /help for available commands."

    if command.handler == "direct" and command.fn:
        if asyncio.iscoroutinefunction(command.fn):
            result = await command.fn(args)
        else:
            result = command.fn(args)
        return "direct", str(result)

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


@register_command("clear", "Clear the current session (use via UI or delete endpoint)", handler="direct")
def _cmd_clear(args: str) -> str:
    return "To clear a session, use DELETE /threads/{user}/{session} or start a new session."


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
