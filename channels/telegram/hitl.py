"""HITL approval state — in-memory per-bot-process.

Each pending approval batch (one or more interrupt events from a single SSE
stream) gets a monotonic int id. The id is embedded in inline-keyboard
`callback_data` so we can look up the batch when the user clicks. We use an
int (not a UUID) to stay well under Telegram's 64-byte callback_data limit.

State is lost on bot restart — MVP choice per the architecture review. Migrate
to Redis or Postgres if you need pending approvals to survive deploys.

HITL output is intentionally NOT truncated: the user is making a decision and
must see the full action. Long args are split across multiple messages, then
a short final message carries the keyboard.
"""
from __future__ import annotations

import itertools
import json
from dataclasses import dataclass, field
from typing import Iterator

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from channels.telegram.text_utils import truncate_utf16


@dataclass
class PendingApproval:
    chat_id: int
    thread_id: str            # raw thread_id for POST /threads/{tid}/runs/resume
    interrupts: list[dict] = field(default_factory=list)
    # The message_id of the keyboard we sent, so we can edit it on click to
    # disable buttons and show the chosen outcome.
    keyboard_message_id: int | None = None


class ApprovalRegistry:
    def __init__(self) -> None:
        self._counter = itertools.count(1)
        self._store: dict[int, PendingApproval] = {}

    def add(self, p: PendingApproval) -> int:
        approval_id = next(self._counter)
        self._store[approval_id] = p
        return approval_id

    def get(self, approval_id: int) -> PendingApproval | None:
        return self._store.get(approval_id)

    def pop(self, approval_id: int) -> PendingApproval | None:
        return self._store.pop(approval_id, None)


# Module-level singleton — one process, one registry.
REGISTRY = ApprovalRegistry()


def build_keyboard(approval_id: int) -> InlineKeyboardMarkup:
    """Two-button keyboard: approve / deny. Applies to ALL interrupts in the batch.

    The harness `/runs/resume` endpoint accepts a single decision string that
    is fanned out across every action_request in the batch (see
    `_build_resume_command` in harness/api/chat.py).
    """
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Approve", callback_data=f"hitl:{approval_id}:approve"),
        InlineKeyboardButton("❌ Deny",    callback_data=f"hitl:{approval_id}:deny"),
    ]])


# Telegram hard cap is 4096 UTF-16 units; reserve headroom for continuation
# markers and the chance the last char is a surrogate.
_CHUNK_UNITS = 3900


def _maybe_unfold(args: dict) -> dict:
    """Parse string args that look like JSON and substitute the parsed tree.

    Tools like `save_gcn(gcn_json: str)` receive a stringified JSON blob —
    pretty-printing it as a string leaves the user staring at backslash-
    escaped quotes. Unfolding gives a readable nested tree instead.
    """
    out: dict = {}
    for k, v in args.items():
        if isinstance(v, str) and len(v) > 80 and v.lstrip().startswith(("{", "[")):
            try:
                out[k] = json.loads(v)
                continue
            except (json.JSONDecodeError, ValueError):
                pass
        out[k] = v
    return out


def render_full_details(interrupts: list[dict]) -> Iterator[str]:
    """Yield Telegram-safe chunks describing every pending action, IN FULL.

    No truncation — args are JSON-pretty-printed and split into <=3900-UTF-16
    chunks if needed. Caller sends each yielded string as a separate message
    BEFORE the keyboard message, so the user sees the full action and decides
    last.
    """
    multi = len(interrupts) > 1
    for n, intr in enumerate(interrupts, 1):
        tool = intr.get("tool", "?")
        args = _maybe_unfold(intr.get("args", {}))
        args_pretty = json.dumps(args, ensure_ascii=False, indent=2)
        header = f"⏸️ Action {n}/{len(interrupts)} — {tool}" if multi else f"⏸️ Sắp chạy: {tool}"
        body = f"{header}\n\n{args_pretty}"

        remaining = body
        first = True
        while remaining:
            head, tail = truncate_utf16(remaining, _CHUNK_UNITS)
            yield head if first else f"…(tiếp)\n{head}"
            remaining = tail
            first = False


def render_decision_prompt(interrupts: list[dict]) -> str:
    """Short text for the keyboard message — sits below the detail messages."""
    if len(interrupts) == 1:
        return "Approve action trên?"
    return f"Approve TẤT CẢ {len(interrupts)} actions trên?"


def parse_callback(data: str) -> tuple[int, str] | None:
    """Parse `hitl:{id}:{approve|deny}` callback_data. Returns None if not ours."""
    if not data or not data.startswith("hitl:"):
        return None
    try:
        _, sid, decision = data.split(":", 2)
        if decision not in {"approve", "deny"}:
            return None
        return int(sid), decision
    except (ValueError, AttributeError):
        return None
