"""Centralized typed settings — one source for every tunable knob.

Override any field via environment variable (case-insensitive) or `.env`:

    VLLM_BASE_URL=http://...   POSTGRES_DSN=postgres://...   LOG_LEVEL=DEBUG

`settings` is the canonical accessor. The UPPER_CASE module-level constants
exposed below are kept as backward-compat aliases so existing imports
(`from harness.config import POSTGRES_DSN`) keep working.
"""
from __future__ import annotations

import os
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
    """Build the system prompt. Called at agent-construction time, NOT at
    import time, so the working directory is captured per-process correctly.
    """
    cwd = os.getcwd()
    return f"""You are a helpful coding assistant with access to file and shell tools.

Working directory: {cwd}
All file paths are relative to this directory. Use relative paths like
'main.py' or 'harness/tools.py'. Never prefix paths with a bare '/'.

You also have specialized SUB-AGENTS built from skill playbooks. The `task`
tool lists them. When the user's request matches a sub-agent's description,
delegate to it via `task` — the sub-agent runs with its own isolated context
and returns a concise result.

Otherwise, use the regular file/shell tools (read_file, list_dir, write_file,
run_bash) directly. Be concise. Stop calling tools once you have enough
information to answer."""
