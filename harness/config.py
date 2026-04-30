"""Centralized typed settings — one source for every tunable knob.

Override any field via environment variable (case-insensitive) or `.env`:

    VLLM_BASE_URL=http://...   POSTGRES_DSN=postgres://...   LOG_LEVEL=DEBUG

`settings` is the canonical accessor. The UPPER_CASE module-level constants
exposed below are kept as backward-compat aliases so existing imports
(`from harness.config import POSTGRES_DSN`) keep working.
"""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # vLLM (OpenAI-compatible API endpoint)
    vllm_base_url: str = "http://192.168.120.11:2900/v1"
    vllm_model_name: str = "cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit"
    vllm_api_key: str = "EMPTY"
    temperature: float = 0.2

    # Reasoning ("thinking") — only some served models support this. When True,
    # we pass `chat_template_kwargs.enable_thinking=True` via OpenAI extra_body.
    # Reasoning tokens stream as `event: thinking` (separate from `event: token`).
    enable_thinking: bool = False

    # Postgres (checkpointer + long-term store)
    postgres_dsn: str = "postgresql://harness:harness@localhost:5432/harness"

    # Logging
    log_level: str = "INFO"
    log_file: str = "logs/harness.json"


settings = Settings()

# Back-compat aliases — UPPER_CASE module-level constants kept so legacy
# imports continue to work without modification.
VLLM_BASE_URL = settings.vllm_base_url
VLLM_MODEL_NAME = settings.vllm_model_name
VLLM_API_KEY = settings.vllm_api_key
TEMPERATURE = settings.temperature
POSTGRES_DSN = settings.postgres_dsn

# Skills directory — each SKILL.md (or top-level .md) becomes a deepagents
# subagent at startup.
SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"


def get_instructions() -> str:
    """Build the system prompt."""
    return """You are a helpful assistant.

You do NOT have access to the local filesystem. Never call ls, read_file,
write_file, edit_file, glob, or grep — these tools are not connected to any
real filesystem and will return empty results.

Tools available to you:
  - write_todos    — break down multi-step work into tracked tasks
  - task           — delegate to a specialized sub-agent (skills)
  - execute        — run a shell command (requires human approval; prefer skills over raw shell)
  - analyze_image  — describe an image or PDF via the vision model
  - remember_about_user / recall_user_context — persist and retrieve per-user facts

When the user's request matches a sub-agent's description, use `task` to
delegate — the sub-agent runs with its own context and returns a concise result.
Otherwise act directly. Be concise. Stop calling tools once you have enough
information to answer."""
