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

from pydantic import Field
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

    # Context window of the SERVED vLLM model. deepagents always wires a
    # SummarizationMiddleware, but for a custom model name LangChain has no
    # profile, so it falls back to a fixed 170k-token trigger — unreachable
    # when vLLM serves a smaller context, i.e. the summarizer never fires and
    # the model hard-overflows first. We add ContextEditingMiddleware and size
    # it from this value, so it MUST match vLLM's --max-model-len (set in .env).
    max_model_len: int = 32768
    # Clear old tool outputs once prompt tokens exceed this fraction of
    # max_model_len. Tool-result bloat (full TTCP docs, aggregate tables, LIS
    # rows, analyze_image output) is the real context pressure here, not chat
    # length — so we clear well before the (dead) summarization trigger.
    context_edit_trigger_fraction: float = 0.6
    # Number of most-recent tool results kept verbatim (never cleared).
    context_edit_keep: int = 4
    # Tool results shorter than this (chars) are left untouched by the
    # semantic compactor — small outputs cost little and stay fully readable.
    context_compact_min_chars: int = 600

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
    datalens_url: str = "http://192.168.120.12:37001"
    datalens_chatbot_code: str = "bags_code"
    datalens_timeout: float = 60.0

    # MongoDB — used by harness.tools.ttcp_db (TTCP CRUD + full-text + aggregate).
    # Connection is lazy; only initialised when a TTCP tool is first invoked.
    # ``ttcp_collection`` matches the offline batch (extention_/ttcp_batch) so
    # the agent sees the same docs the extractor wrote.
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db_name: str = "datalens"
    ttcp_collection: str = "ttcp-extracted"
    # Where render_ttcp_report writes generated HTML reports (relative to CWD
    # unless absolute). Created on first use.
    ttcp_report_dir: str = "reports"

    # MinIO / S3 — the /upload endpoint mirrors uploaded PDFs into the TTCP
    # corpus bucket (datalens-data/ttcp/ttcp-bot/) so ad-hoc uploads join the
    # offline batch corpus. validation_alias reuses the SAME env var names the
    # batch (extention_/ttcp_batch) already reads — one set of MinIO config.
    minio_endpoint: str = Field("http://192.168.120.12:9002", validation_alias="ENDPOINT_URL_MINIO")
    minio_access_key: str = Field("", validation_alias="AWS_ACCESS_KEY_ID_MINIO")
    minio_secret_key: str = Field("", validation_alias="AWS_SECRET_ACCESS_KEY_MINIO")
    ttcp_bucket: str = Field("datalens-data", validation_alias="TTCP_BUCKET")
    ttcp_prefix: str = Field("ttcp/ttcp-bot/", validation_alias="TTCP_PREFIX")

    # Downstream sync webhook — after any write to the TTCP collection
    # (save/update/delete tools, or a batch run that produced new docs) we
    # POST here so the user's other apps re-sync their own DB. Best-effort:
    # a failure is logged and swallowed, never blocks/breaks the write.
    # Empty string disables the hook.
    ttcp_sync_url: str = "http://192.168.120.11:8000/import/ttcp"
    ttcp_sync_timeout: float = 10.0

    # Logging
    log_level: str = "INFO"
    log_file: str = "logs/harness.json"

    # Filesystem access for deepagents' built-in fs tools. DEFAULT FALSE —
    # when true, the agent runs with `permissions=FilesystemPermission`.
    # SECURITY: enabling this gives the LLM real access to the host filesystem.
    # Combine with sandboxing (container, restricted user) for production use.
    allow_filesystem: bool = False


settings = Settings()

# Back-compat aliases — UPPER_CASE module-level constants kept so legacy
# imports continue to work without modification.
VLLM_BASE_URL = settings.vllm_base_url
VLLM_MODEL_NAME = settings.vllm_model_name
VLLM_API_KEY = settings.vllm_api_key
TEMPERATURE = settings.temperature
POSTGRES_DSN = settings.postgres_dsn

if settings.allow_filesystem:
    DODGE_SYSTEM_ACCESS = """You do NOT have access to the local filesystem. Never call ls, read_file,
    write_file, edit_file, glob, or grep — these tools are not connected to any
    real filesystem and will return empty results."""
else:
    DODGE_SYSTEM_ACCESS = """"""

os.environ["OPENAI_API_KEY"] = settings.vllm_api_key

# Skills directory — each SKILL.md (or top-level .md) becomes a deepagents
# subagent at startup.
SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"


def _summarize_tool(t) -> str:
    """One-line summary for the prompt's tool listing.

    Prefers `metadata['prompt_hint']` if the tool author set one (lets them
    override the docstring without rewriting it). Otherwise uses the first
    non-empty line of the tool description.
    """
    hint = (getattr(t, "metadata", None) or {}).get("prompt_hint")
    if hint:
        return hint.strip()
    desc = (getattr(t, "description", "") or "").strip()
    return desc.split("\n", 1)[0].strip() if desc else ""


def get_instructions(tools: list | None = None, skills: list[dict] | None = None) -> str:
    """Build the system prompt.

    The tool listing is generated from the actual tool objects so adding/renaming
    a tool only requires registering it in `ALL_TOOLS` — no prompt edit needed.
    Skills are listed by name+description so the model knows when to delegate
    via `task`. With no skills loaded, `task` is disabled in the prompt.
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

    tool_lines = [
        "  - write_todos: break down multi-step work into tracked tasks",
        "  - execute: run a shell command (requires human approval)",
    ]
    for t in tools or []:
        summary = _summarize_tool(t)
        tool_lines.append(f"  - {t.name}: {summary}" if summary else f"  - {t.name}")
    tools_section = "Other tools available:\n" + "\n".join(tool_lines)

    return f"""You are a helpful assistant built by AI researchers at AI Academy VN.

{DODGE_SYSTEM_ACCESS}

{task_section}

{tools_section}

For tools whose summary is brief, consult the full tool schema (description,
arguments) before calling — that is the authoritative source for usage rules,
output format, and citation conventions.

Answer simple questions directly without calling any tools. Be concise."""
