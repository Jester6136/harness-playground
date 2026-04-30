# harness-playground

A production-ready LLM agent harness built on **LangGraph** + **deepagents**, serving a local vLLM model over a REST + SSE HTTP API.

Features: token streaming · multi-user sessions (PostgreSQL) · HITL approval via interrupts · skill sub-agents · pipeline mode (structured output) · slash commands · multimodal input (image / PDF) · long-term memory · demo web UI · reasoning/thinking toggle.

## Architecture

deepagents is used as the **orchestration layer**: it wires up the LangGraph agent loop, skill sub-agent routing (`task`), HITL interrupts (`interrupt_on=`), and checkpointing integration. The agent runs with `StateBackend` (in-memory state) — it does **not** access the host filesystem. Domain capabilities live in custom tools and skills.

## Layout

```
harness-playground/
├── main.py                   ← CLI entry-point; --serve launches FastAPI
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
├── static/
│   └── index.html            ← Demo UI served at GET /ui
├── harness/
│   ├── config.py             ← pydantic Settings (vLLM, Postgres, logs) + system prompt
│   ├── agent.py              ← make_agent() factory
│   ├── llm.py                ← ChatOpenAI factory + thinking toggle
│   ├── multimodal.py         ← image / PDF → message content
│   ├── logging_config.py     ← structured JSON logging + @log_tool_call
│   ├── eval.py               ← YAML eval runner (python -m harness.eval)
│   ├── api/                  ← FastAPI app split by concern
│   │   ├── __init__.py       ←   app + lifespan + router wiring
│   │   ├── chat.py           ←   /chat/stream + /runs/resume
│   │   ├── threads.py        ←   /threads/* (list, history, delete)
│   │   ├── pipelines.py      ←   /pipelines + auto-mounted /api/{name}
│   │   ├── misc.py           ←   /health, /commands, /upload, /ui
│   │   ├── streaming.py      ←   SSE event_stream() helper
│   │   └── deps.py           ←   shared FastAPI deps (X-User-Id)
│   ├── persistence/          ← Postgres-backed state
│   │   ├── checkpoints.py    ←   PostgresSaver + session admin
│   │   ├── store.py          ←   long-term memory (LangGraph Store)
│   │   └── db.py             ←   healthcheck
│   ├── tools/                ← custom @tool functions
│   │   ├── vision.py         ←   analyze_image (VLM)
│   │   └── memory.py         ←   remember/recall_user_context
│   ├── extensions/           ← agent plug-in mechanisms
│   │   ├── commands.py       ←   slash command dispatcher
│   │   ├── pipelines.py      ←   pipeline registry + run_pipeline
│   │   └── skills.py         ←   skill loader (folder-based SKILL.md)
│   └── utils/                ← cross-cutting helpers (no I/O, no state)
│       ├── async_utils.py    ←   run_async() bridge
│       └── paths.py          ←   resolve_relative_path()
├── skills/                   ← drop a <name>/SKILL.md here to add a sub-agent skill
├── evals/                    ← YAML test cases (python -m harness.eval)
└── docs/
    └── API.md                ← Full REST + SSE contract for frontend teams
```

## Prerequisites

**vLLM** — must be running with tool calling enabled:

```bash
vllm serve cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit \
    --port 2900 \
    --enable-auto-tool-choice \
    --tool-call-parser hermes
```

**PostgreSQL** — used for both session checkpoints and long-term memory:

```bash
# Quick local instance via Docker:
docker run -d --name pg \
  -e POSTGRES_USER=harness -e POSTGRES_PASSWORD=harness -e POSTGRES_DB=harness \
  -p 5432:5432 postgres:16-alpine

# Or bring up the full stack (Postgres + harness-api):
docker compose up -d
```

## Setup

```bash
pip install -e .
```

Key environment variables (defaults work for the local Docker stack above):

```
VLLM_BASE_URL=http://192.168.120.11:2900/v1
VLLM_MODEL_NAME=cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit
POSTGRES_DSN=postgresql://harness:harness@localhost:5432/harness
ENABLE_THINKING=false   # set true if model supports reasoning tokens
```

Copy `.env.example` and adjust as needed.

## Run

### CLI mode (one-shot)

```bash
python main.py "hello, what can you do?"
python main.py --user alice --session s1 "remember my name is Alice"
python main.py --user alice --session s1 "what is my name?"   # recalls from memory
```

HITL: when the agent calls `execute`, the CLI prompts `y/N` before running the command.

Session admin:

```bash
python main.py --list-users
python main.py --list-sessions --user alice
python main.py --delete-session --user alice --session s1
```

### API server mode

```bash
python main.py --serve          # FastAPI on http://localhost:8000
# or
uvicorn harness.api:app --reload
```

**Demo UI:** open `http://localhost:8000/ui`

Full REST + SSE API documented in [`docs/API.md`](docs/API.md).

```bash
# Quick smoke test
curl http://localhost:8000/health

curl -N -X POST http://localhost:8000/chat/stream \
  -H "Content-Type: application/json" \
  -H "X-User-Id: alice" \
  -d '{"session_id": "main", "message": "hello"}'
```

## Demo UI (`/ui`)

Single-page HTML served from `static/index.html` — no build step needed.

- **Real-time token streaming** with markdown + syntax highlighting rendered as tokens arrive
- **Tool call / result blocks** — see every tool the agent invokes
- **HITL approval** — Approve / Deny dialog when the agent needs shell access
- **File attachment** — attach images or PDFs; the agent calls `analyze_image` automatically
- **Sessions sidebar** — create, switch, and delete sessions per user
- **Slash command autocomplete** — type `/` to see available commands
- **Pipelines tab** — run structured-output pipelines with auto-generated forms

## Tools

The agent uses **deepagents' StateBackend** (no filesystem access). Filesystem tools built into deepagents (`ls`, `read_file`, `write_file`, `edit_file`, `glob`, `grep`) are explicitly disabled in the system prompt — they would return empty results and are not relevant to this harness' use cases.

**Active deepagents built-ins:**

| Tool | Description |
|---|---|
| `write_todos` | Break down multi-step work into tracked tasks |
| `task` | Delegate to a skill sub-agent |
| `execute` | Run a shell command (HITL approval required) |

**Custom tools** (defined in `harness/tools/`):

| Tool | Description |
|---|---|
| `analyze_image` | Describe an image or PDF using the vision model |
| `remember_about_user` | Persist a key-value fact to long-term memory |
| `recall_user_context` | Retrieve all remembered facts for the current user |

### Adding a main-agent tool

Add a `@tool`-decorated function to an appropriate module under `harness/tools/`, then register it in `harness/tools/__init__.py` → `ALL_TOOLS`. Finally, add its name and description to the "Tools available to you" list in `harness/config.py` → `get_instructions()` so the model knows to use it.

```python
# harness/tools/my_domain.py
from langchain_core.tools import tool

@tool
def query_postgres(sql: str) -> str:
    """Run a read-only SQL query against the application database."""
    ...

# harness/tools/__init__.py  →  add query_postgres to ALL_TOOLS
# harness/config.py get_instructions()  →  add to tool list in prompt
```

## Skills (sub-agents)

Drop a folder under `skills/` and restart — the skill is picked up automatically. No changes needed to the main system prompt or any loader code.

```
skills/
└── my_skill/
    ├── SKILL.md       ← required: YAML frontmatter (name, description) + prompt body
    └── helpers.py     ← optional: @tool functions available only to this skill
```

`SKILL.md` format:

```markdown
---
name: query_postgres
description: Query the application PostgreSQL database and return structured results.
---

## When to use
When the user asks about data in the database.

## Steps
1. Use `query_postgres` to run the appropriate SQL.
2. Format results as a table or list.
3. If the request is ambiguous, ask which table or schema to look at.
```

**Notes:**
- The `description` field is what the main agent reads to decide when to delegate — write it as a clear one-liner.
- Skills automatically inherit the "no filesystem" restriction via a base prompt prepended by the loader.
- Skill-specific tools go in `helpers.py`; tools shared across skills go in `harness/tools/ALL_TOOLS`.
- Skills receive `ALL_TOOLS` (global custom tools) plus their own `helpers.py` tools.

## Pipelines (structured output)

Register in `harness/extensions/pipelines.py`:

```python
@register_pipeline
class SummarizeText(Pipeline):
    name = "summarize_text"
    description = "Summarize text into a structured report."
    # define input_model, output_model (Pydantic), system_prompt
```

Each pipeline gets a `POST /api/{name}` endpoint with input/output validated by Pydantic. Pipelines always run with `enable_thinking=False` regardless of the global setting.

## Slash commands

Handled before reaching the agent — zero LLM cost.

| Command | Description |
|---|---|
| `/help` | List all available commands |
| `/clear` | Info on clearing a session |
| `/list-skills` | Show loaded skill sub-agents |

Add commands in `harness/extensions/commands.py` via `@register_command`.

## HITL (Human-in-the-loop)

`execute` (and `write_file`, `edit_file` if used) are listed in `HITL_TOOLS` in `harness/agent.py`, wired via deepagents' native `interrupt_on=` mechanism. The stream emits an `interrupt` SSE event; the frontend renders an Approve / Deny dialog. On user action, POST to `/threads/{user}:{session}/runs/resume` with `{"resume": "approve" | "deny"}`.

See [`docs/API.md`](docs/API.md) for the full HITL protocol.

## Reasoning / thinking

Set `ENABLE_THINKING=true` (or `enable_thinking = true` in `.env`) when the served model supports reasoning tokens (e.g. Gemma thinking checkpoints). The model streams its chain-of-thought as `thinking` SSE events before the final answer.

Toggle per-process by passing `enable_thinking=True/False` to `make_agent()` or `make_llm()`.

## Long-term memory

The agent can persist facts across sessions per user:

- `remember_about_user(key, value)` — writes to Postgres store
- `recall_user_context()` — reads all facts for the current user

Facts survive server restarts. Namespace is `("users", <user_id>)`.

## Multimodal input

Attach an image or PDF in the UI — it uploads via `POST /upload`, and the file path is embedded in the message. The agent automatically calls `analyze_image`, which sends the file to the vision model (same vLLM endpoint).

Supported: JPEG, PNG, GIF, WebP, PDF.

## Deployment

```bash
docker compose up -d
```

Services: `postgres` + `harness-api`. Set env vars in a `.env` file (see `.env.example`).

Healthcheck: `GET /health` returns `{"status": "ok", "postgres": "ok"}`.

## Evaluation

```bash
python -m harness.eval              # run all cases in evals/
python -m harness.eval --filter hi  # filter by name pattern
python -m harness.eval --json       # JSON report
```

YAML format:

```yaml
- name: smoke_hello
  input: "say hello"
  expected:
    contains: "hello"          # case-insensitive substring

- name: uses_memory
  input: "use the memory tool"
  expected:
    tool_called: remember_about_user   # assert a specific tool was called
```
