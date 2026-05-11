"""Map (platform, chat, user) → agent (user_id, session_id).

The agent's `thread_id` is `f"{user_id}:{session_id}"` (see
harness.persistence.checkpoints.thread_id). Each channel decides the mapping
policy — group chats can share state among members or stay per-user.
"""
from __future__ import annotations


def map_telegram(chat_id: int, user_id: int) -> tuple[str, str]:
    """Return `(agent_user_id, agent_session_id)` for a Telegram update.

    Policy: one session per Telegram chat (so a group chat shares state among
    its members), keyed by chat_id. The Telegram user_id becomes the agent's
    user_id, prefixed to avoid colliding with other channels' user namespaces.
    """
    return f"tg:{user_id}", f"tg-chat:{chat_id}"
