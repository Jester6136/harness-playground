"""Telegram bot entry — Milestone 1: echo bot + SSE bridge.

Run:
    python -m channels.telegram.bot

Requires TELEGRAM_BOT_TOKEN in .env (or the environment). The agent must be
reachable at AGENT_API_URL (default http://localhost:8000) — start it first
with `python main.py --serve`.
"""
from __future__ import annotations

import logging

from telegram.ext import Application, CommandHandler, MessageHandler, filters

from channels.telegram.handlers import on_message, on_start
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
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

    log.info("Telegram bot starting (long-poll). Agent API → %s", settings.agent_api_url)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
