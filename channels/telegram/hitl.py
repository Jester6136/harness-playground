"""HITL approval state — in-memory per-bot-process.

Each pending approval batch (one or more interrupt events from a single SSE
stream) gets a monotonic int id. The id is embedded in inline-keyboard
`callback_data` so we can look up the batch when the user clicks. We use an
int (not a UUID) to stay well under Telegram's 64-byte callback_data limit.

State is lost on bot restart — MVP choice per the architecture review. Migrate
to Redis or Postgres if you need pending approvals to survive deploys.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


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


def render_summary(interrupts: list[dict]) -> str:
    """Human-readable summary of the actions awaiting approval."""
    if len(interrupts) == 1:
        i = interrupts[0]
        import json
        args = json.dumps(i.get("args", {}), ensure_ascii=False)
        if len(args) > 240:
            args = args[:240] + "…"
        return f"⏸️ Cần approval:\n  {i.get('tool')}({args})"

    import json
    lines = ["⏸️ Cần approval:"]
    for n, i in enumerate(interrupts, 1):
        args = json.dumps(i.get("args", {}), ensure_ascii=False)
        if len(args) > 160:
            args = args[:160] + "…"
        lines.append(f"  {n}. {i.get('tool')}({args})")
    lines.append("\nApprove/Deny áp dụng cho TẤT CẢ actions trên.")
    return "\n".join(lines)


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
