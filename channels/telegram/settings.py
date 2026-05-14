"""Telegram bot settings — env-driven, isolated from harness.* config.

Required:
    TELEGRAM_BOT_TOKEN — from @BotFather

Optional:
    AGENT_API_URL          — default http://localhost:8000
    AGENT_API_USER_HEADER  — default X-User-Id (matches harness.api.deps.get_user)
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class TelegramSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    telegram_bot_token: str = ""
    agent_api_url: str = "http://localhost:8000"
    agent_api_user_header: str = "X-User-Id"

    # Show every tool_call / tool_result inline as a notice ("⚙️ tool(args)").
    # Default OFF — chat-as-UI for end users should hide internals; the agent's
    # final text answer is what they care about. Errors are surfaced regardless
    # of this flag so silent tool failures are still visible.
    verbose_tools: bool = False


settings = TelegramSettings()
