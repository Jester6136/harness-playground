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

The agent uses **deepagents' StateBackend** by default (no filesystem access). Set `ALLOW_FILESYSTEM=true` to grant deepagents' built-in fs tools real host access via `FilesystemPermission` — see [Filesystem access](#filesystem-access).

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

### Adding a main-agent tool

Add a `@tool`-decorated function under `harness/tools/`, then register it in `harness/tools/__init__.py` → `ALL_TOOLS`. The system prompt's tool listing is generated from `ALL_TOOLS` at agent build time — **no prompt edit required**.

```python
# harness/tools/my_domain.py
from langchain_core.tools import tool

@tool
def query_postgres(sql: str) -> str:
    """Run a read-only SQL query against the application database."""
    ...

# harness/tools/__init__.py  →  add query_postgres to ALL_TOOLS
```

The first line of the docstring becomes the prompt summary; the model sees the full docstring in the tool schema. To override the summary explicitly, attach a hint:

```python
@tool(metadata={"prompt_hint": "use for SQL on the app DB; read-only"})
def query_postgres(sql: str) -> str: ...
```

To require human approval before the tool runs, mark it as HITL:

```python
@tool(metadata={"hitl": True})
def drop_table(name: str) -> str: ...
```

The agent collects HITL flags from tool metadata at build time, plus deepagents' built-in `execute` listed in `_BUILTIN_HITL` in `harness/agent.py`.

### GCN database (MongoDB)

`harness/tools/gcn_db.py` ships 5 tools backed by MongoDB for storing the output of `extract_gcn`:

| Tool | HITL | Purpose |
|---|---|---|
| `save_gcn(gcn_json)` | ✅ | Upsert a GCN keyed by `Số phát hành giấy chứng nhận` |
| `update_gcn(so_hieu, updates_json)` | ✅ | `$set` specific fields via dotted-key dict |
| `delete_gcn(so_hieu)` | ✅ | Remove by số hiệu |
| `find_gcn(so_hieu)` | — | Exact lookup by số hiệu |
| `search_gcn(query, limit)` | — | Full-text search across owner name, address, GCN number |

`MongoStore` ([harness/persistence/mongo.py](harness/persistence/mongo.py)) is the reusable wrapper — use it to back other collections (just instantiate with a different `collection` name). Connection is lazy and closed via the FastAPI lifespan; the text index is created idempotently on first use.

Configure with `MONGO_URI` and `MONGO_DB_NAME` in `.env` (defaults to `mongodb://localhost:27017` / `harness`). docker-compose spins up a `mongo:7` service on port 27017.

**Demo flow showcasing HITL + multi-tool agent:**
1. User sends a GCN PDF over Telegram → agent calls `extract_gcn` → JSON.
2. Agent calls `save_gcn(json)` → bot shows `[✅ Approve] [❌ Deny]` keyboard.
3. Approve → record stored. Later: "Tìm GCN số CH00123" → `find_gcn` → result.
4. "Xoá GCN CH00123" → `delete_gcn` → another HITL prompt → confirm → deleted.

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
- Skills automatically inherit the "no filesystem" restriction via a base prompt prepended by the loader. The restriction is lifted globally when the deployment sets `ALLOW_FILESYSTEM=true` (see [Filesystem access](#filesystem-access)).
- Skill-specific tools go in `helpers.py`; tools shared across skills go in `harness/tools/ALL_TOOLS`.
- Skills receive `ALL_TOOLS` (global custom tools) plus their own `helpers.py` tools.

### Built-in skill: `query_lis_db`

Looks up Vietnamese land-information records (Giấy chứng nhận / thửa đất / đơn đăng ký) in the external `geohub_lis` Postgres. Three parametric lookups:

| Tool | By |
|---|---|
| `lookup_gcn_by_so_hieu(so_hieu_gcn)` | GCN serial number |
| `lookup_gcn_by_giay_to_dinh_danh(so_giay_to)` | Owner ID document (CMND/CCCD/MST) |
| `check_don_dang_ky(don_dang_ky_id)` | Đơn đăng ký UUID |

Configure via `.env`:

```
LIS_DB_HOST=192.168.20.10
LIS_DB_PORT=5432
LIS_DB_NAME=geohub_lis
LIS_DB_USER=lis_readonly      # recommended: read-only role, NOT a superuser
LIS_DB_PASSWORD=...
```

Connection pool is lazy + lock-guarded; queries are read-only via psycopg parametric binding (`%s`) — safe against SQL injection. Output is capped at 50 rows per call.

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
| `/status <id>` | Sức khoẻ chi tiết Đơn đăng ký — kiểm tra cả 4 nhóm (phapNhanSdds, thuaDats, daMdsdds, giayChungNhans) lẫn các trường con quan trọng (giấy tờ định danh chủ sở hữu, kích thước thửa đất, file scan trong GCN…); báo từng item thiếu gì để bổ sung |

Add commands in `harness/extensions/commands.py` via `@register_command`.

## HITL (Human-in-the-loop)

deepagents' `execute` tool is listed in `_BUILTIN_HITL` in `harness/agent.py`. Custom tools opt in via `metadata={"hitl": True}` on the `@tool` decorator — `_collect_hitl()` merges both sources at build time and feeds them to deepagents' `interrupt_on=`. The stream emits an `interrupt` SSE event; the frontend renders an Approve / Deny dialog. On user action, POST to `/threads/{user}:{session}/runs/resume` with `{"resume": "approve" | "deny"}`.

See [`docs/API.md`](docs/API.md) for the full HITL protocol.

## Filesystem access

By default the agent runs **without** filesystem access — deepagents' built-in fs tools are gated by its own permissions system.

To enable real filesystem access for the host server, set:

```
ALLOW_FILESYSTEM=true
```

When enabled, `make_agent()` swaps the default `StateBackend` (in-memory) for `FilesystemBackend(virtual_mode=False)` and grants matching `FilesystemPermission` rules. Both pieces are required: the backend tells the fs tools where to read/write, and the permissions list gates access. The harness does not add prompt-level instructions for these tools — deepagents' built-in tool schemas describe them and its permission middleware enforces approval semantics.

For a sandboxed setup, use `virtual_mode=True` with a `root_dir` (blocks `..` and `~`), or compose deny rules in the permissions list — see [`harness/agent.py`](harness/agent.py) and [deepagents backends docs](https://docs.langchain.com/oss/python/deepagents/backends).

**Security:** this gives the LLM real read/write on the host. Only enable inside a sandbox (container, restricted user, chrooted volume mount). Do not enable on a shared multi-tenant server.

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
```
