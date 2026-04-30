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


# Lightweight count of the 4 required groups for an Đơn đăng ký. Used by /status
# to give a deterministic completeness ("sức khoẻ") report without invoking the
# agent loop.
_STATUS_SQL = """
SELECT
    EXISTS(SELECT 1 FROM lis.don_dang_ky WHERE id = %(id)s) AS exists,
    (SELECT COUNT(*) FROM lis.phap_nhan_sdd_don_dang_ky
     WHERE don_dang_ky_id = %(id)s AND phap_nhan_sdd_id IS NOT NULL) AS phap_nhan_count,
    (SELECT COUNT(*) FROM lis.dang_ky_thua
     WHERE don_dang_ky_id = %(id)s AND thua_dat_id IS NOT NULL) AS thua_count,
    (SELECT COUNT(*) FROM lis.dang_ky_thua
     WHERE don_dang_ky_id = %(id)s AND da_mdsdd_id IS NOT NULL) AS mdsdd_count,
    (SELECT COUNT(*) FROM lis.phap_nhan_sdd_don_dang_ky
     WHERE don_dang_ky_id = %(id)s AND giay_chung_nhan_id IS NOT NULL) AS gcn_count
"""


@register_command(
    "status",
    "Kiểm tra sức khoẻ (4 nhóm bắt buộc) của một Đơn đăng ký theo id",
    handler="direct",
    args_schema={"id": "str — UUID đơn đăng ký"},
)
async def _cmd_status(args: str) -> str:
    don_id = args.strip()
    if not don_id:
        return "Cú pháp: `/status <don_dang_ky_id>`"

    from harness.persistence.lis_db import run_query

    try:
        rows = await run_query(_STATUS_SQL, {"id": don_id}, row_cap=1)
    except Exception as exc:
        return f"❌ Lỗi DB: `{type(exc).__name__}: {exc}`"

    if not rows:
        return f"❌ Không truy vấn được. Kiểm tra lại id: `{don_id}`."

    r = rows[0]
    if not r.get("exists"):
        return f"❌ Không tồn tại đơn đăng ký id `{don_id}`."

    groups = [
        ("phapNhanSdds (chủ sở hữu)",     int(r["phap_nhan_count"])),
        ("thuaDats (thửa đất)",           int(r["thua_count"])),
        ("daMdsdds (mục đích sử dụng)",   int(r["mdsdd_count"])),
        ("giayChungNhans (GCN liên quan)", int(r["gcn_count"])),
    ]
    missing = [name for name, c in groups if c == 0]

    lines = [f"**Sức khoẻ đơn đăng ký** `{don_id}`\n"]
    for name, count in groups:
        mark = "✓" if count > 0 else "✗"
        lines.append(f"  {mark} {name}: **{count}**")

    if not missing:
        lines.append("\n→ **ĐẦY ĐỦ**. Đơn có cả 4 nhóm dữ liệu bắt buộc.")
    else:
        lines.append(
            f"\n→ **THIẾU {len(missing)}/4 nhóm**: "
            + ", ".join(f"`{m}`" for m in missing)
            + ". Cần bổ sung."
        )
    return "\n".join(lines)
