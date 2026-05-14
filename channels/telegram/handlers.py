"""Telegram handlers — Milestone 3: HITL + slash commands.

Flow per message:
  1. POST /chat/stream and consume SSE into a TelegramStreamer (M2 behaviour).
  2. `interrupt` events accumulate in a PendingApproval; when the stream
     closes with at least one interrupt, render a single inline-keyboard
     message ("Approve / Deny") covering the whole batch.
  3. On callback: edit the keyboard message to reflect the choice, POST
     /threads/{tid}/runs/resume, then consume the resumed SSE with a FRESH
     streamer so the new output lands in a new message.

Slash commands: `/start` is bot-local (welcome text). Any other `/cmd args`
is forwarded verbatim as a chat message — the harness API parses it via
`parse_command` and dispatches accordingly.
"""
from __future__ import annotations

import json
import logging
from typing import AsyncIterator

import httpx
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from channels._common.sse_client import stream_sse
from channels._common.thread_map import map_telegram
from channels._common.upload_client import upload_bytes
from channels.telegram.hitl import (
    REGISTRY,
    PendingApproval,
    build_keyboard,
    parse_callback,
    render_decision_prompt,
    render_full_details,
)
from channels.telegram.settings import settings
from channels.telegram.streamer import TelegramStreamer

log = logging.getLogger(__name__)

_TOOL_RESULT_PREVIEW = 200


# ── public handlers ────────────────────────────────────────────────────────


async def on_start(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if msg:
        await msg.reply_text(
            "Xin chào! Tôi là bot harness-playground. Gửi tin nhắn để bắt đầu.\n"
            "Slash commands của agent (`/help`, `/clear`, `/list-skills`, …) "
            "cũng dùng được — gõ thẳng như trong web UI."
        )


async def on_message(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Plain text → forward to /chat/stream."""
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not (msg and msg.text and chat and user):
        return

    agent_user, session_id = map_telegram(chat.id, user.id)
    await chat.send_action(ChatAction.TYPING)

    streamer = TelegramStreamer(chat)
    url = f"{settings.agent_api_url.rstrip('/')}/chat/stream"
    body = {"session_id": session_id, "message": msg.text}
    headers = {settings.agent_api_user_header: agent_user}

    await _consume_into_streamer(
        chat=chat,
        thread_id=_thread_id(agent_user, session_id),
        streamer=streamer,
        sse=stream_sse(url, json=body, headers=headers),
    )


async def on_slash_forward(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Catch-all for `/<anything>` other than `/start` — forward to the agent.

    Telegram strips the leading `/` automatically when populating `message.text`?
    No — it keeps it. We forward as-is. The harness `parse_command` re-parses.
    """
    # `on_message` already handles arbitrary text; reuse it.
    await on_message(update, _ctx)


async def on_media(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Photo / document → upload to /upload → embed path in chat message.

    Telegram delivers an album as N separate updates; for M4 we treat each as
    its own conversation turn. Add media-group debouncing later if needed.
    """
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not (msg and chat and user):
        return

    file_obj, filename = _pick_telegram_file(msg)
    if file_obj is None:
        await msg.reply_text("⚠️ Loại media này chưa hỗ trợ.")
        return

    agent_user, session_id = map_telegram(chat.id, user.id)
    await chat.send_action(ChatAction.UPLOAD_DOCUMENT)

    # Telegram → bytes.
    try:
        tg_file = await file_obj.get_file()
        data = bytes(await tg_file.download_as_bytearray())
    except Exception as exc:
        log.exception("download from Telegram failed")
        await msg.reply_text(f"⚠️ Không tải được file từ Telegram: {exc}")
        return

    # Bytes → harness /upload → {path, name, minio_key} on the API host.
    api_headers = {settings.agent_api_user_header: agent_user}
    try:
        upload = await upload_bytes(
            api_url=settings.agent_api_url,
            data=data,
            filename=filename,
            headers=api_headers,
        )
    except Exception as exc:
        log.exception("upload to agent failed")
        await msg.reply_text(f"⚠️ Lỗi upload lên agent: {exc}")
        return
    path = upload["path"]
    # The /upload endpoint already mirrored PDFs to MinIO; extract_ttcp will
    # derive the MinIO key from the path and stamp it into the result JSON
    # automatically, so we don't need to expose anything extra to the agent.

    # Embed the path the same way the web UI does — but neutral on tool choice,
    # so the model picks `extract_ttcp` vs `analyze_image` based on the file.
    caption = (msg.caption or "").strip()
    if not caption:
        caption = (
            "Hãy xử lý file đính kèm (extract_ttcp nếu là văn bản thanh tra, "
            "otherwise analyze_image)."
        )
    body_msg = f"[Attached file at: {path}]\n\n{caption}"

    # Same SSE consume path as text messages.
    streamer = TelegramStreamer(chat)
    url = f"{settings.agent_api_url.rstrip('/')}/chat/stream"
    body = {"session_id": session_id, "message": body_msg}
    await _consume_into_streamer(
        chat=chat,
        thread_id=_thread_id(agent_user, session_id),
        streamer=streamer,
        sse=stream_sse(url, json=body, headers=api_headers),
    )


async def on_callback_query(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Inline-keyboard click — Approve / Deny on a HITL batch."""
    cq = update.callback_query
    if cq is None or cq.data is None:
        return

    parsed = parse_callback(cq.data)
    if parsed is None:
        await cq.answer("Unknown action")
        return
    approval_id, decision = parsed

    pending = REGISTRY.pop(approval_id)
    if pending is None:
        await cq.answer("Approval đã hết hạn hoặc đã được xử lý.", show_alert=True)
        try:
            await cq.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        return

    # Acknowledge the click and freeze the keyboard.
    await cq.answer("✅ Approved" if decision == "approve" else "❌ Denied")
    marker = "✅ Đã approve" if decision == "approve" else "❌ Đã deny"
    try:
        await cq.edit_message_text(
            text=(cq.message.text or "") + f"\n\n{marker}",
            reply_markup=None,
        )
    except Exception:
        log.warning("could not edit keyboard message %s", cq.message.message_id if cq.message else "?")

    # POST resume and consume the continuation. Use a FRESH streamer so the
    # post-resume output starts in a new visible message.
    chat = update.effective_chat
    if chat is None:
        return
    streamer = TelegramStreamer(chat)
    url = f"{settings.agent_api_url.rstrip('/')}/threads/{pending.thread_id}/runs/resume"
    body = {"resume": decision}
    # The user-id header is required by the API gateway dep; reuse the same
    # mapping. We stored the thread_id, derive the user from it (format is
    # `<user>:<session>` — see harness.persistence.checkpoints.thread_id).
    agent_user = pending.thread_id.split(":", 1)[0]
    headers = {settings.agent_api_user_header: agent_user}

    await _consume_into_streamer(
        chat=chat,
        thread_id=pending.thread_id,
        streamer=streamer,
        sse=stream_sse(url, json=body, headers=headers),
    )


# ── core SSE consumer ──────────────────────────────────────────────────────


async def _consume_into_streamer(
    *,
    chat,
    thread_id: str,
    streamer: TelegramStreamer,
    sse: AsyncIterator[tuple[str, str]],
) -> None:
    """Consume one SSE stream end-to-end. On `interrupt`, collect the batch
    and render a keyboard once the stream closes. On any other event, push
    into the streamer."""
    pending_interrupts: list[dict] = []

    try:
        async for event, raw in sse:
            try:
                payload = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                log.warning("Non-JSON SSE data for event=%s: %r", event, raw[:120])
                continue

            if event == "token":
                await streamer.push_token(payload.get("content", ""))
            elif event == "message":
                await streamer.push_token(payload.get("content", ""))
            elif event == "tool_call":
                if settings.verbose_tools:
                    await streamer.commit_then_send(_fmt_tool_call(payload))
                else:
                    # Quiet mode — keep typing indicator alive so the chat
                    # doesn't look frozen during long tool runs.
                    await chat.send_action(ChatAction.TYPING)
            elif event == "tool_result":
                # Some tools produce a file (render_ttcp_report) — deliver it
                # as a Telegram document instead of leaking a server path.
                sent_file = await _maybe_send_tool_file(chat, payload)
                if settings.verbose_tools:
                    await streamer.commit_then_send(_fmt_tool_result(payload))
                elif not sent_file:
                    # Always surface tool failures — silent errors break trust.
                    err = _tool_result_error(payload)
                    if err:
                        await streamer.commit_then_send(
                            f"⚠️ {payload.get('tool', '?')}: {err}"
                        )
                    else:
                        await chat.send_action(ChatAction.TYPING)
            elif event == "thinking":
                log.debug("thinking: %s", str(payload.get("content", ""))[:200])
            elif event == "interrupt":
                pending_interrupts.append(payload)
            elif event == "session_cleared":
                await streamer.commit_then_send("🗑️ Session đã được xoá.")
            elif event == "done":
                break
    except Exception as exc:
        log.exception("SSE stream failed")
        await streamer.finish()
        await chat.send_message(f"⚠️ Lỗi gọi agent: {exc}")
        return

    await streamer.finish()

    if pending_interrupts:
        await _register_and_render_approval(chat, thread_id, pending_interrupts)


async def _register_and_render_approval(chat, thread_id: str, interrupts: list[dict]) -> None:
    pending = PendingApproval(chat_id=chat.id, thread_id=thread_id, interrupts=interrupts)
    approval_id = REGISTRY.add(pending)

    # Send the full action detail(s) first — possibly across multiple messages
    # when args are huge (e.g. save_ttcp(ttcp_json=<50KB>)). NO truncation: the
    # user is making a decision and must see exactly what will run.
    for chunk in render_full_details(interrupts):
        await chat.send_message(chunk)

    # Then a short message carrying the keyboard, so the buttons sit right
    # under the last thing the user read.
    msg = await chat.send_message(
        render_decision_prompt(interrupts),
        reply_markup=build_keyboard(approval_id),
    )
    pending.keyboard_message_id = msg.message_id


# ── helpers ────────────────────────────────────────────────────────────────


def _thread_id(user: str, session: str) -> str:
    """Mirror harness.persistence.checkpoints.thread_id without importing it
    (channels/ stays decoupled from harness/)."""
    return f"{user}:{session}"


def _pick_telegram_file(msg):
    """Return `(File, filename)` for a photo or document message, else `(None, None)`.

    Photos: take the largest `PhotoSize` (Telegram pre-renders multiple sizes).
    Documents: keep the original filename when present so the harness can pick
    the right tool by extension (`.pdf` → extract_ttcp / analyze_image PDF path).
    """
    if msg.photo:
        ph = msg.photo[-1]
        return ph, f"{ph.file_unique_id}.jpg"
    if msg.document:
        d = msg.document
        return d, d.file_name or f"{d.file_unique_id}.bin"
    return None, None


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


def _tool_result_error(payload: dict) -> str | None:
    """If a tool_result's content is an error-JSON, return the human message.

    Tools in this harness use a `{"error": "...", "message": "..."}` shape
    when something goes wrong (see harness/tools/*.py). Anything else is
    treated as success and stays hidden in quiet mode.
    """
    content = payload.get("content", "") or ""
    try:
        d = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return None
    if isinstance(d, dict) and "error" in d:
        return str(d.get("message") or d.get("error") or "tool error")
    return None


# Tools whose JSON result carries `{url, filename, caption, ...}` — the file is
# fetched from the harness API and delivered as a Telegram document. Add more
# file-producing tools here as they appear.
_FILE_TOOLS = {"render_ttcp_report", "get_ttcp_file"}


async def _maybe_send_tool_file(chat, payload: dict) -> bool:
    """If `payload` is a successful file-producing tool result, fetch the file
    from the harness API and send it to the chat as a document.

    The tool result must carry `{url, filename}` (and optionally `caption`).
    `url` is API-relative — the bot resolves it against `agent_api_url`, so
    the user never needs to reach the API or MinIO directly.

    Returns True if a document (or a stand-in error message) was sent, so the
    caller can skip the quiet-mode typing/error fallback. Returns False for
    non-file tools and for error results (let the normal error path show them).
    """
    if payload.get("tool") not in _FILE_TOOLS:
        return False
    try:
        data = json.loads(payload.get("content", "") or "")
    except (json.JSONDecodeError, TypeError):
        return False
    if not isinstance(data, dict) or "url" not in data:
        return False  # error result → normal error path handles it

    url = f"{settings.agent_api_url.rstrip('/')}{data['url']}"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(url)
            r.raise_for_status()
            file_bytes = r.content
    except Exception as exc:
        log.warning("could not fetch tool file %s: %s", url, exc)
        await chat.send_message(f"⚠️ Tạo file xong nhưng không tải được: {exc}")
        return True

    filename = data.get("filename") or "file"
    caption = data.get("caption") or "📎 File"
    await chat.send_document(
        document=file_bytes,
        filename=filename,
        caption=caption,
    )
    return True
