"""All tunable knobs in one place. Override with environment variables."""
import os
from pathlib import Path

# vLLM serves an OpenAI-compatible API. Any string works as api_key.
VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://192.168.120.11:2900/v1")
VLLM_MODEL_NAME = os.getenv("VLLM_MODEL_NAME", "cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit")
VLLM_API_KEY = os.getenv("VLLM_API_KEY", "EMPTY")

TEMPERATURE = 0.2

# PostgreSQL DSN for checkpointer + store.
# Set POSTGRES_DSN env var to enable; falls back to SQLite when unset.
POSTGRES_DSN = os.getenv(
    "POSTGRES_DSN",
    "postgresql://harness:harness@localhost:5432/harness",
)
USE_POSTGRES = os.getenv("USE_POSTGRES", "false").lower() in ("1", "true", "yes")

# Skills directory — each .md file becomes a deepagents subagent at startup.
SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"

INSTRUCTIONS = """You are a helpful coding assistant with access to file and shell tools.

You also have specialized SUB-AGENTS built from skill playbooks. The `task`
tool lists them. When the user's request matches a sub-agent's description,
delegate to it via `task` — the sub-agent runs with its own isolated context
and returns a concise result.

Otherwise, use the regular file/shell tools (read_file, list_dir, write_file,
run_bash) directly. Be concise. Stop calling tools once you have enough
information to answer."""
