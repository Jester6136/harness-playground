# PLAN — Strong Base Agent Harness (API-first, self-hosted)

> Living document. Update as work proceeds.

## Context

`harness-playground` đã trải qua nhiều iteration:
1. From-scratch educational harness.
2. Migrate sang `deepagents`/LangGraph.
3. Multi-user/multi-session via SQLite checkpointer.
4. Tích hợp `agent-chat-ui` qua `langgraph dev`.

**Yêu cầu hiện tại:**
- **API-only**: Backend chỉ expose REST + SSE. Web team build app riêng.
- **PostgreSQL throughout**: checkpointer + store. Bỏ SQLite.
- **Skills v2**: cấu trúc thư mục `skills/<name>/SKILL.md` + helpers.
- **Streaming SSE**.
- **Khép kín / self-hosted**: LangSmith optional, off by default.
- **HITL** qua `interrupt()`.
- **Deploy ổn định**: Docker Compose stack hoàn chỉnh.

## Goal

Base harness:
- HTTP API (REST + SSE), Web team build FE riêng.
- Postgres self-hosted (checkpoint + store).
- Skills folder structure (instructions + Python helpers + resources).
- HITL approval qua interrupt-protocol.
- Pipeline mode (single-shot LLM với structured output) song song agent mode.
- Slash command dispatcher (direct/agent/pipeline routing).
- Multimodal input (Gemma 4-26B-A4B-it là VLM).
- `docker compose up`, không SaaS bên ngoài.

## Architecture decisions

| Concern | Decision |
|---|---|
| Frontend | Web team build riêng từ `docs/API.md`. `agent-chat-ui` là demo UI mặc định. |
| Database | 1 Postgres self-hosted, namespaces: checkpoints, store, app. `asyncpg` pool. DSN qua `POSTGRES_DSN`. |
| Observability | stdlib JSON logging → `logs/harness.json`. Token/timing track qua decorator + LangChain callback. LangSmith opt-in. |
| HITL | `langgraph.types.interrupt()` → stream emit `__interrupt__` chunk → FE render dialog → POST `/runs/resume` với `Command(resume=...)`. |
| Skills v2 | `skills/<name>/SKILL.md` + optional `*.py` chứa `@tool` skill-specific. Backward compat với flat `.md` (transition). |

## Tiered roadmap

### Tier 1 — Foundation (deploy-ready)

- **T1.1 Project packaging** — `pyproject.toml` (setuptools), `.gitignore`.
- **T1.2 Postgres infra** — `harness/db.py` (asyncpg pool); rewrite `harness/sessions.py` dùng `AsyncPostgresSaver`.
- **T1.3 HITL via interrupt()** — migrate `_ask()` từ `input()` sang `interrupt()`; CLI handle resume cycle.
- **T1.4 FastAPI + SSE** — `harness/api.py`:
  - `POST /chat/stream`, `GET /threads/{user}`, `GET /threads/{user}/{session}/messages`,
  - `DELETE /threads/{user}/{session}`, `POST /threads/{tid}/runs/resume`,
  - `GET /health`, `GET /commands`.
  - SSE events: `message`, `tool_call`, `tool_result`, `interrupt`, `done`, `error`.
- **T1.5 Multimodal** — `harness/multimodal.py` (image/PDF → message content); `analyze_image` tool; multipart upload.
- **T1.6 Skills v2** — `harness/skills.py` loader (folder + frontmatter + skill-specific tools); migrate 3 skills hiện tại sang folder.

### Tier 2 — Core productization

- **T2.1 Slash command dispatcher** — `harness/commands.py`:
  - `Command` dataclass (`name`, `description`, `args_schema`, `handler` ∈ `direct|agent|pipeline`).
  - `COMMANDS` registry, builtin `/help`, `/clear`, `/list-skills`.
  - API: `GET /commands`; chat stream pre-process detect `/cmd` → dispatch.
- **T2.2 Pipeline mode** — `harness/pipelines.py`:
  - `Pipeline` dataclass dùng `llm.with_structured_output(output_model)`.
  - API tự động sinh `POST /api/{pipeline.name}`.
- **T2.3 Long-term memory** — `harness/store.py` (`AsyncPostgresStore` cùng pool); tools `remember_about_user`, `recall_user_context`; `make_agent(checkpointer=, store=)`.

### Tier 3 — Production polish

- **T3.1 Eval framework** — `harness/eval.py` + `evals/*.yaml`. CLI `python -m harness.eval`.
- **T3.2 Structured logging** — `harness/logging_config.py` JSON formatter; tool wrap decorator; LangChain callback cho token usage.
- **T3.3 Deployment artifacts** — `Dockerfile` (multi-stage, non-root), `docker-compose.yml` (postgres + harness-api + vllm + optional agent-chat-ui), `.env.example`.
- **T3.4 API contract docs** — `docs/API.md` cho Web team.

## File map

```
harness-playground/
├── pyproject.toml                  ← T1.1
├── Dockerfile                      ← T3.3
├── docker-compose.yml              ← T3.3
├── .env.example                    ← T3.3
├── .gitignore                      ← T1.1
├── PLAN.md                         ← THIS
├── README.md
├── main.py                         ← UPDATE T1.3, T1.4, T2.3, T3.2
├── docs/API.md                     ← T3.4
├── harness/
│   ├── agent.py                    ← UPDATE T1.6, T2.3
│   ├── api.py                      ← T1.4, T2.1, T2.2
│   ├── tools.py                    ← UPDATE T1.3, T1.5, T2.3, T3.2
│   ├── commands.py                 ← T2.1
│   ├── pipelines.py                ← T2.2
│   ├── multimodal.py               ← T1.5
│   ├── store.py                    ← T2.3
│   ├── db.py                       ← T1.2
│   ├── sessions.py                 ← REWRITE T1.2
│   ├── skills.py                   ← T1.6
│   ├── eval.py                     ← T3.1
│   └── logging_config.py           ← T3.2
├── skills/
│   ├── summarize_codebase/SKILL.md
│   ├── find_secrets/SKILL.md
│   └── add_tool/SKILL.md
└── evals/*.yaml
```

## Out of scope (defer)

- FE custom dashboard (Web team tự build).
- Auth/JWT verify trong harness (gateway concern, dùng header `X-User-Id`).
- Domain tools Parcel360 (GEOHUB/GEOLIS/DC-VPDK), Map UI, PostGIS, OCR — sau base.
- Vector embedding cho long-term memory — key-value trước.
- LangSmith — opt-in.
- Rate limiting — gateway-level.

## Execution order

| # | Task | Effort | Outcome |
|---|---|---|---|
| 1 | T1.1 | 0.5 ngày | Installable package |
| 2 | T1.6 | 0.5 ngày | Skills v2 |
| 3 | T1.2 | 1 ngày | Postgres |
| 4 | T1.3 | 1 ngày | Web-safe HITL |
| 5 | T1.4 | 1.5 ngày | API endpoints |
| 6 | T1.5 | 1 ngày | VLM image input |
| 7 | T2.1 | 1.5 ngày | Slash commands |
| 8 | T2.2 | 1 ngày | Pipeline APIs |
| 9 | T2.3 | 1.5 ngày | Cross-session memory |
| 10 | T3.4 | 0.5 ngày | API docs |
| 11 | T3.1 | 1 ngày | Eval suite |
| 12 | T3.2 | 1 ngày | Logging |
| 13 | T3.3 | 1 ngày | Docker stack |

**Tổng**: ~12-13 ngày. Milestone trung gian: bước 1-7 (~7 ngày) là backend đủ cho Web team kết nối.

## Verification end-to-end

1. `docker compose up -d` → toàn stack lên.
2. `curl localhost:8000/health` → 200.
3. `curl localhost:8000/commands` → JSON list.
4. Pipeline: `curl -X POST localhost:8000/api/extract_pdf -F file=@cert.pdf` → JSON structured.
5. SSE chat: `curl -N -X POST localhost:8000/chat/stream -H "X-User-Id: alice" -d '{...}'`.
6. HITL: stream emit `interrupt` → POST `/runs/resume` → tool chạy.
7. Long-term: 2 sessions khác user, fact persisted.
8. Skill v2: `skills/word_count/SKILL.md` + `helpers.py` → restart → task tool list có entry mới.
9. Eval: `python -m harness.eval` → pass.
10. Logs: `tail -f logs/harness.json | jq` thấy structured entries.

## Progress log

| Date | Task | Status | Notes |
|---|---|---|---|
| 2026-04-28 | Plan written | ✅ | This file |
| | T1.1 packaging | 🔄 | In progress |
| | T1.6 skills v2 | ⏳ | Pending |
| | T1.2 Postgres | ⏳ | |
| | T1.3 HITL | ⏳ | |
| | T1.4 FastAPI | ⏳ | |
| | T1.5 Multimodal | ⏳ | |
| | T2.1 Commands | ⏳ | |
| | T2.2 Pipelines | ⏳ | |
| | T2.3 Long-term memory | ⏳ | |
| | T3.4 API docs | ⏳ | |
| | T3.1 Eval | ⏳ | |
| | T3.2 Logging | ⏳ | |
| | T3.3 Docker | ⏳ | |
