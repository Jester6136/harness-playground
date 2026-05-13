"""Telegram bot entry — Milestone 3: HITL + slash commands.

Run:
    python -m channels.telegram.bot

Handler stack (registered in `main()`):
  - CommandHandler("start", on_start)         — bot-local welcome
  - CallbackQueryHandler(on_callback_query)   — HITL inline-keyboard clicks
  - MessageHandler(COMMAND, on_slash_forward) — `/clear`, `/help`, … → agent
  - MessageHandler(TEXT,    on_message)       — plain text → agent

Order matters: COMMAND handler must run before generic TEXT (PTB dispatches
the first matching handler per group).
"""
from __future__ import annotations

import logging

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from channels.telegram.handlers import (
    on_callback_query,
    on_media,
    on_message,
    on_slash_forward,
    on_start,
)
from channels.telegram.settings import settings

log = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    if not settings.telegram_bot_token:
        raise SystemExit(
            "TELEGRAM_BOT_TOKEN is not set. Add it to .env (see .env.example)."
        )

    app = Application.builder().token(settings.telegram_bot_token).build()
    app.add_handler(CommandHandler("start", on_start))
    app.add_handler(CallbackQueryHandler(on_callback_query, pattern=r"^hitl:"))
    # Forward any other `/something …` to the agent (harness has its own
    # slash-command parser, see harness/extensions/commands.py).
    app.add_handler(MessageHandler(filters.COMMAND, on_slash_forward))
    # Photo / document → /upload → embed path → /chat/stream (M4).
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, on_media))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

    log.info("Telegram bot starting (long-poll). Agent API → %s", settings.agent_api_url)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
