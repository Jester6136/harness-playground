"""Telegram handlers — Milestone 1: text in → SSE consume → single final text.

No streaming edits, no HITL resume, no media yet. tool_call / tool_result /
interrupt events are surfaced inline so we can see them during development —
Milestones 2–4 will polish each into proper UX.
"""
from __future__ import annotations

import json
import logging

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from channels._common.sse_client import stream_sse
from channels._common.thread_map import map_telegram
from channels.telegram.settings import settings

log = logging.getLogger(__name__)

_MAX_TG_CHARS = 4000  # Conservative — real cap 4096 but Markdown adds overhead.
_TOOL_RESULT_PREVIEW = 200


def _split_for_telegram(text: str) -> list[str]:
    return [text[i:i + _MAX_TG_CHARS] for i in range(0, len(text), _MAX_TG_CHARS)] or [text]


async def on_start(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if msg:
        await msg.reply_text(
            "Xin chào! Tôi là bot harness-playground. Gửi tin nhắn để bắt đầu.\n"
            "Lệnh: /start — hiển thị help này."
        )


async def on_message(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not (msg and msg.text and chat and user):
        return

    agent_user, session_id = map_telegram(chat.id, user.id)
    await chat.send_action(ChatAction.TYPING)

    pieces: list[str] = []
    notices: list[str] = []
    interrupted = False

    url = f"{settings.agent_api_url.rstrip('/')}/chat/stream"
    headers = {settings.agent_api_user_header: agent_user}
    body = {"session_id": session_id, "message": msg.text}

    try:
        async for event, raw in stream_sse(url, json=body, headers=headers):
            try:
                payload = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                log.warning("Non-JSON SSE data for event=%s: %r", event, raw[:120])
                continue

            if event == "token":
                pieces.append(payload.get("content", ""))
            elif event == "message":
                # Direct slash-command result (already final).
                pieces.append(payload.get("content", ""))
            elif event == "tool_call":
                args_short = json.dumps(payload.get("args", {}), ensure_ascii=False)
                if len(args_short) > 160:
                    args_short = args_short[:160] + "…"
                notices.append(f"⚙️ {payload.get('tool')}({args_short})")
            elif event == "tool_result":
                content = payload.get("content", "")
                if len(content) > _TOOL_RESULT_PREVIEW:
                    content = content[:_TOOL_RESULT_PREVIEW] + f"… ({len(content)} chars)"
                notices.append(f"📦 {payload.get('tool')} → {content}")
            elif event == "thinking":
                log.debug("thinking: %s", str(payload.get("content", ""))[:200])
            elif event == "interrupt":
                interrupted = True
                notices.append(
                    f"⏸️ Cần approval: {payload.get('tool')} — chưa wire (Milestone 3)."
                )
            elif event == "session_cleared":
                notices.append("🗑️ Session đã được xoá.")
            elif event == "done":
                break
    except Exception as exc:
        log.exception("SSE stream failed")
        await msg.reply_text(f"⚠️ Lỗi gọi agent: {exc}")
        return

    final = "".join(pieces).strip()
    parts: list[str] = []
    if notices:
        parts.append("\n".join(notices))
    if final:
        parts.append(final)
    elif interrupted:
        parts.append("⏸️ Đang chờ approval — Milestone 3 sẽ render nút bấm.")
    elif not notices:
        parts.append("(no response)")

    out = "\n\n".join(parts)
    for chunk in _split_for_telegram(out):
        await msg.reply_text(chunk)
