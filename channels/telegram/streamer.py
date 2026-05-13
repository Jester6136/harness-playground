"""Edit-in-place token streamer for Telegram.

One instance per agent response. Caller pushes tokens (`push_token`), side
events (`commit_then_send` for tool_call notices, interrupt placeholders, etc.),
and finally `finish` to drop the cursor on the last edit.

Behaviour mirrors Hermes-Agent's `stream_consumer.py` + `platforms/telegram.py`
edit loop, adapted to consume our SSE event types. See ./NOTICE for attribution.

Design choices that differ from Hermes:
- We don't try to render thinking blocks inline (caller decides whether to
  surface them).
- We always commit the current streaming message before showing a side notice,
  so visual order matches the SSE timeline.
- We don't implement "fresh_final" (send final as a new message) — caller can
  achieve the same by calling `finish()` then `commit_then_send()`.
"""
from __future__ import annotations

import asyncio
import logging
import time

from telegram import Message
from telegram.constants import ChatAction
from telegram.error import RetryAfter, TimedOut

from channels._common.stream_buffer import StreamBuffer
from channels.telegram.text_utils import truncate_utf16, utf16_len

log = logging.getLogger(__name__)

# Telegram's hard cap is 4096 UTF-16 units; we leave headroom for the cursor
# glyph and for the chance that the very last token would otherwise be split
# mid-codepoint.
_HARD_CAP_UNITS = 4000
_CURSOR = " ▉"
_CURSOR_UNITS = utf16_len(_CURSOR)

# Adaptive backoff bounds for RetryAfter (flood control) responses.
_BACKOFF_FACTOR = 2.0
_BACKOFF_CAP = 10.0


class TelegramStreamer:
    """Owns the lifecycle of one streaming AI response inside a chat."""

    def __init__(self, chat) -> None:
        self.chat = chat
        self.buffer = StreamBuffer()
        # The currently-editing placeholder message; None if not started or
        # already committed and waiting for the next token to begin a new one.
        self._msg: Message | None = None
        # Text already displayed in `_msg` (without the trailing cursor).
        self._committed_text: str = ""

    # ── public API ──────────────────────────────────────────────────────────

    async def push_token(self, text: str) -> None:
        """Accumulate a token; flush to Telegram if the buffer policy says so."""
        if not text:
            return
        self.buffer.push(text)
        if self.buffer.should_flush(time.monotonic()):
            await self._flush()

    async def commit_then_send(self, notice: str) -> None:
        """Finalize the current streaming message, then send `notice` as a new one.

        Use for tool_call / tool_result / interrupt placeholders that should
        appear inline in the chat timeline without being overwritten by later
        token edits.
        """
        await self._drain_and_finalize()
        if notice:
            await self.chat.send_message(notice)

    async def finish(self) -> None:
        """Drain any remaining buffered tokens and drop the cursor."""
        await self._drain_and_finalize()

    # ── internals ───────────────────────────────────────────────────────────

    async def _flush(self) -> None:
        chunk = self.buffer.take(time.monotonic())
        if not chunk:
            return
        await self._append_to_current(chunk, with_cursor=True)

    async def _drain_and_finalize(self) -> None:
        if self.buffer.pending:
            chunk = self.buffer.take(time.monotonic())
            await self._append_to_current(chunk, with_cursor=False)
        elif self._msg is not None and self._committed_text.endswith(_CURSOR):
            # Cursor is sitting on the message but no new text — strip it.
            await self._set_message_text(self._committed_text[: -len(_CURSOR)])
        # Either way we're done with this message — next token starts a fresh one.
        self._msg = None
        self._committed_text = ""

    async def _append_to_current(self, chunk: str, *, with_cursor: bool) -> None:
        """Render `committed_text + chunk` into the current message, handling
        the 4096-UTF-16-unit cap by overflowing into new messages."""
        remaining = chunk
        while remaining:
            if self._msg is None:
                # Start a fresh message. Typing indicator while it's empty.
                await self._show_typing()
                head, remaining = self._fit_into_new(remaining, with_cursor)
                self._msg = await self.chat.send_message(head + (_CURSOR if with_cursor and remaining == "" else ""))
                self._committed_text = head + (_CURSOR if with_cursor and remaining == "" else "")
                if remaining:
                    # New message overflowed already — finalize and loop.
                    await self._set_message_text(head)
                    self._msg = None
                    self._committed_text = ""
                continue

            current = self._strip_cursor(self._committed_text)
            available = _HARD_CAP_UNITS - utf16_len(current) - (_CURSOR_UNITS if with_cursor else 0)
            if available <= 0:
                # Current message is full — commit without cursor and start a new one.
                await self._set_message_text(current)
                self._msg = None
                self._committed_text = ""
                continue

            head, tail = truncate_utf16(remaining, available)
            new_text = current + head + (_CURSOR if with_cursor and not tail else "")
            await self._set_message_text(new_text)
            self._committed_text = new_text
            remaining = tail
            if tail:
                # Overflowed — finalize and loop into a fresh message.
                await self._set_message_text(current + head)
                self._msg = None
                self._committed_text = ""

    def _fit_into_new(self, text: str, with_cursor: bool) -> tuple[str, str]:
        cap = _HARD_CAP_UNITS - (_CURSOR_UNITS if with_cursor else 0)
        return truncate_utf16(text, cap)

    @staticmethod
    def _strip_cursor(text: str) -> str:
        return text[: -len(_CURSOR)] if text.endswith(_CURSOR) else text

    async def _set_message_text(self, text: str) -> None:
        """edit_message_text with RetryAfter-aware backoff."""
        if self._msg is None:
            return
        try:
            await self._msg.edit_text(text)
        except RetryAfter as exc:
            wait = float(getattr(exc, "retry_after", 1.0))
            self.buffer.widen_interval(_BACKOFF_FACTOR, _BACKOFF_CAP)
            log.warning(
                "Telegram flood control: sleeping %.1fs, edit_interval → %.1fs",
                wait, self.buffer.interval,
            )
            await asyncio.sleep(wait)
            try:
                await self._msg.edit_text(text)
            except Exception:
                log.exception("edit_text retry failed; dropping update")
        except TimedOut:
            log.warning("edit_text timed out; dropping update")
        except Exception as exc:
            # Common harmless case: "message is not modified" when whitespace
            # round-trips identically. Log and move on.
            msg = str(exc).lower()
            if "not modified" in msg:
                return
            log.exception("edit_text failed: %s", exc)

    async def _show_typing(self) -> None:
        try:
            await self.chat.send_action(ChatAction.TYPING)
        except Exception:
            pass
