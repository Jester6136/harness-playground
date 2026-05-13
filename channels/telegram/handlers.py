"""Telegram handlers — Milestone 2: streaming edit-in-place.

Flow per message:
  1. POST /chat/stream and consume SSE.
  2. `token` events → TelegramStreamer.push_token (edits the latest message).
  3. `tool_call` / `tool_result` / `interrupt` → commit the current streaming
     message and send the notice as a fresh message, so timeline order matches.
  4. `done` → finalize (drop cursor).
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
from channels.telegram.streamer import TelegramStreamer

log = logging.getLogger(__name__)

_TOOL_RESULT_PREVIEW = 200


async def on_start(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if msg:
        await msg.reply_text(
            "Xin chào! Tôi là bot harness-playground. Gửi tin nhắn để bắt đầu."
        )


def _fmt_tool_call(payload: dict) -> str:
    tool = payload.get("tool", "?")
    args = json.dumps(payload.get("args", {}), ensure_ascii=False)
    if len(args) > 160:
        args = args[:160] + "…"
    return f"⚙️ {tool}({args})"


def _fmt_tool_result(payload: dict) -> str:
    tool = payload.get("tool", "?")
    content = payload.get("content", "") or ""
    if len(content) > _TOOL_RESULT_PREVIEW:
        content = content[:_TOOL_RESULT_PREVIEW] + f"… ({len(content)} chars)"
    return f"📦 {tool} → {content}"


async def on_message(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not (msg and msg.text and chat and user):
        return

    agent_user, session_id = map_telegram(chat.id, user.id)
    await chat.send_action(ChatAction.TYPING)

    url = f"{settings.agent_api_url.rstrip('/')}/chat/stream"
    headers = {settings.agent_api_user_header: agent_user}
    body = {"session_id": session_id, "message": msg.text}

    streamer = TelegramStreamer(chat)

    try:
        async for event, raw in stream_sse(url, json=body, headers=headers):
            try:
                payload = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                log.warning("Non-JSON SSE data for event=%s: %r", event, raw[:120])
                continue

            if event == "token":
                await streamer.push_token(payload.get("content", ""))
            elif event == "message":
                # Direct slash-command result — push as one chunk, no cursor games.
                await streamer.push_token(payload.get("content", ""))
            elif event == "tool_call":
                await streamer.commit_then_send(_fmt_tool_call(payload))
            elif event == "tool_result":
                await streamer.commit_then_send(_fmt_tool_result(payload))
            elif event == "thinking":
                # Logged-only in M2; M3+ may surface as a separate "spoiler" msg.
                log.debug("thinking: %s", str(payload.get("content", ""))[:200])
            elif event == "interrupt":
                await streamer.commit_then_send(
                    f"⏸️ Cần approval: {payload.get('tool')} — chưa wire (Milestone 3)."
                )
            elif event == "session_cleared":
                await streamer.commit_then_send("🗑️ Session đã được xoá.")
            elif event == "done":
                break
    except Exception as exc:
        log.exception("SSE stream failed")
        await streamer.finish()
        await msg.reply_text(f"⚠️ Lỗi gọi agent: {exc}")
        return

    await streamer.finish()
