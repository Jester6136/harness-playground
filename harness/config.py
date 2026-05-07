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

    # Reasoning ("thinking") — only some served models support this. When True,
    # we pass `chat_template_kwargs.enable_thinking=True` via OpenAI extra_body.
    # Reasoning tokens stream as `event: thinking` (separate from `event: token`).
    enable_thinking: bool = False

    # Postgres (checkpointer + long-term store)
    postgres_dsn: str = "postgresql://harness:harness@localhost:5432/harness"

    # External LIS Postgres (geohub_lis) — used by skills/query_lis_db.
    # Required: set LIS_DB_PASSWORD via .env. Read-only role recommended.
    lis_db_host: str = "192.168.20.10"
    lis_db_port: int = 5432
    lis_db_name: str = "geohub_lis"
    lis_db_user: str = "postgres"
    lis_db_password: str = ""

    @property
    def lis_db_dsn(self) -> str:
        return (
            f"postgresql://{self.lis_db_user}:{self.lis_db_password}"
            f"@{self.lis_db_host}:{self.lis_db_port}/{self.lis_db_name}"
            f"?connect_timeout=5"
        )

    # DataLens internal-docs retriever — used by tools/search_docs.
    # POST {datalens_url}/retrieve/react/ with {query, chatbot_code, ...}.
    datalens_url: str = "http://118.70.52.237:37001"
    datalens_chatbot_code: str = "bags_code"
    datalens_timeout: float = 60.0

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

os.environ["OPENAI_API_KEY"] = settings.vllm_api_key

# Skills directory — each SKILL.md (or top-level .md) becomes a deepagents
# subagent at startup.
SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"


def get_instructions(skills: list[dict] | None = None) -> str:
    """Build the system prompt.

    Pass the loaded skill specs so the prompt lists exactly which sub-agents
    exist and when to use them. When no skills are loaded, `task` is disabled.
    """
    if skills:
        skill_lines = "\n".join(
            f"  - {s['name']}: {s['description']}" for s in skills
        )
        task_section = (
            "Available skills — delegate via `task` ONLY for these:\n"
            + skill_lines
            + "\n\nDo NOT use `task` for anything outside this list."
        )
    else:
        task_section = (
            "No skills are loaded. Do NOT call `task` — there are no sub-agents. "
            "Answer directly."
        )

    return f"""You are a helpful assistant built by AI researchers at AI Academy VN.

You do NOT have access to the local filesystem. Never call ls, read_file,
write_file, edit_file, glob, or grep — these tools are not connected to any
real filesystem and will return empty results.

{task_section}

Other tools available:
  - write_todos          — break down multi-step work into tracked tasks
  - execute              — run a shell command (requires human approval)
  - analyze_image        — describe an image or PDF via the vision model
  - search_internal_docs — search the internal knowledge base (DataLens). Use
                           when the user asks about internal policies,
                           processes, documents, or anything that would live
                           in company docs. Returns ranked passages with
                           presigned_url. ALWAYS cite each fact with a
                           Markdown link of the form
                           `[document_name (tr. X-Y)](presigned_url#page=X)`
                           inline, right after the sentence it supports.
                           If presigned_url is null, fall back to plain
                           `(document_name, tr. X-Y)`.
  - remember_about_user / recall_user_context — persist and retrieve per-user facts

Answer simple questions directly without calling any tools. Be concise."""
