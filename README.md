# harness-playground

A production-ready LLM agent harness built on **LangGraph** + **deepagents**, serving a local vLLM model over a REST + SSE HTTP API.

Features: token streaming · multi-user sessions (PostgreSQL) · HITL approval via interrupts · skill sub-agents · pipeline mode (structured output) · slash commands · multimodal input (image / PDF) · long-term memory · demo web UI.

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
│   ├── multimodal.py         ← image / PDF → message content
│   ├── logging_config.py     ← structured JSON logging + @log_tool_call
│   ├── eval.py               ← YAML eval runner (python -m harness.eval)
│   ├── api/                  ← FastAPI app split by concern
│   │   ├── __init__.py       ←   app + lifespan + router wiring
│   │   ├── chat.py           ←   /chat/stream + resume
│   │   ├── threads.py        ←   /threads/* (list, history, delete)
│   │   ├── pipelines.py      ←   /pipelines + auto-mounted /api/{name}
│   │   ├── misc.py           ←   /health, /commands, /upload, /ui
│   │   ├── streaming.py      ←   SSE event_stream() helper
│   │   └── deps.py           ←   shared FastAPI deps (X-User-Id)
│   ├── persistence/          ← Postgres-backed state
│   │   ├── checkpoints.py    ←   PostgresSaver + session admin
│   │   ├── store.py          ←   long-term memory (LangGraph Store)
│   │   └── db.py             ←   healthcheck
│   ├── tools/                ← @tool functions, one module per domain
│   │   ├── files.py          ←   read_file, list_dir, write_file
│   │   ├── shell.py          ←   run_bash + denylist
│   │   ├── vision.py         ←   analyze_image (VLM)
│   │   └── memory.py         ←   remember/recall_user_context
│   ├── extensions/           ← agent plug-in mechanisms
│   │   ├── commands.py       ←   slash command dispatcher
│   │   ├── pipelines.py      ←   pipeline registry + run_pipeline
│   │   └── skills.py         ←   skill loader (folder-based SKILL.md)
│   └── utils/                ← cross-cutting helpers (no I/O, no state)
│       ├── async_utils.py    ←   run_async() bridge
│       └── paths.py          ←   resolve_relative_path()
├── skills/
│   ├── summarize_codebase/SKILL.md
│   ├── find_secrets/SKILL.md
│   └── add_tool/SKILL.md
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
```

Copy `.env.example` and adjust as needed.

## Run

### CLI mode (one-shot)

```bash
python main.py "summarize this codebase"
python main.py --user alice --session research "scan for secrets"
python main.py --user alice --session research "what did you find?"  # remembers
```

HITL: when the agent calls `write_file` or `run_bash`, the CLI prompts `y/N`.

Session admin:

```bash
python main.py --list-users
python main.py --list-sessions --user alice
python main.py --delete-session --user alice --session research
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

Defined under `harness/tools/` (one module per domain) with `@tool`. All tools are exported as `ALL_TOOLS` from the package.

| Tool | Description |
|---|---|
| `read_file` | Read a UTF-8 file from disk |
| `list_dir` | List directory contents |
| `write_file` | Write/overwrite a file (requires HITL approval) |
| `run_bash` | Run a shell command (requires HITL approval) |
| `analyze_image` | Describe an image or PDF using the vision model |
| `remember_about_user` | Persist a key-value fact to long-term memory |
| `recall_user_context` | Retrieve all remembered facts for the current user |

### Adding a tool

```python
# harness/tools/files.py (or a new module)
@tool
def count_words(path: str) -> str:
    """Count words in a text file."""
    return f"{len(Path(path).read_text().split())} words"

# Then export it from harness/tools/__init__.py and add to ALL_TOOLS.
```

The docstring becomes the model-facing description; type hints become the JSON schema.

## Skills (sub-agents)

Each skill is a sub-agent with its own system prompt, invoked via the built-in `task` tool.

Structure:
```
skills/
└── my_skill/
    ├── SKILL.md       ← required: YAML frontmatter (name, description) + prompt body
    └── helpers.py     ← optional: extra @tool functions available only to this skill
```

`SKILL.md` format:
```markdown
---
name: my_skill
description: One-line summary the model uses to decide when to delegate here.
---

## Playbook
1. Do this first.
2. Then this.
3. Return results in this format.
```

Drop the folder in `skills/` and restart — the skill appears automatically.

## Pipelines (structured output)

Register in `harness/extensions/pipelines.py`:

```python
@register_pipeline
class SummarizeText(Pipeline):
    name = "summarize_text"
    description = "Summarize text into a structured report."
    # define input_model, output_model (Pydantic), system_prompt
```

Each pipeline gets a `POST /api/{name}` endpoint with input/output validated by Pydantic.

## Slash commands

Handled before reaching the agent — zero LLM cost.

| Command | Description |
|---|---|
| `/help` | List all available commands |
| `/clear` | Info on clearing a session |
| `/list-skills` | Show loaded skill sub-agents |

Add commands in `harness/extensions/commands.py` via `@register_command`.

## HITL (Human-in-the-loop)

`write_file` and `run_bash` call `langgraph.types.interrupt()` before executing. The stream emits an `interrupt` SSE event; the frontend renders an Approve / Deny dialog. On user action, POST to `/threads/{user}:{session}/runs/resume`.

See [`docs/API.md`](docs/API.md) for the full HITL protocol.

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
```

YAML format:

```yaml
name: basic_hello
input: "say hello"
expected_contains: "hello"
```
