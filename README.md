# harness-playground

An agent built on **deepagents** (langchain-ai) talking to a local vLLM model.

This used to be a from-scratch harness (~300 lines: loop, tools, permissions,
compaction, sub-agents). Those concepts are still here — but they're now
provided by the framework, so the codebase is much smaller.

For the from-scratch educational version, see `mini_harness.py` (single-file
~120 lines) or the git history for the full structured version.

## Layout

```
harness-playground/
├── main.py             ← CLI: streams the agent and prints a trace
├── harness/
│   ├── config.py       ← vLLM endpoint, model, system prompt
│   ├── tools.py        ← @tool-decorated Python functions
│   └── agent.py        ← create_deep_agent(...) + skill loading
└── skills/
    ├── summarize_codebase.md
    ├── find_secrets.md
    └── add_tool.md
```

## What deepagents provides (so we don't have to)

| Concern              | Before (handwritten)         | Now (deepagents / LangGraph)            |
|----------------------|------------------------------|------------------------------------------|
| Agentic loop         | `loop.py` (~80 lines)        | LangGraph state machine                  |
| Tool registry        | `tools.py` REGISTRY          | `@tool` decorators, plain list           |
| Sub-agents           | `spawn_agent` tool           | Built-in `task` tool + `subagents` config |
| Skills               | `invoke_skill` + `skills/`   | `subagents` (one per skill .md)          |
| Compaction           | `compaction.py`              | LangGraph state pruning                  |
| Permissions          | `permissions.py` + `input()` | `input()` here; LangGraph supports proper interrupts |
| Observability        | `observability.py`           | `agent.stream()` + LangSmith             |
| Persistence          | (none)                       | LangGraph checkpointers (plug one in)    |

Net: ~300 lines of harness code → ~150 lines, with more features available.

## Setup

```bash
pip install -r requirements.txt
```

Make sure your vLLM server is running with tool calling enabled:

```bash
vllm serve cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit \
    --port 2900 \
    --enable-auto-tool-choice \
    --tool-call-parser hermes
```

## Run

```bash
python main.py "summarize this codebase"
python main.py "use find_secrets to scan this project"
python main.py "spawn a sub-agent to summarize the harness/ directory and another for skills/, then synthesize"
```

Tool approvals (for `write_file` and `run_bash`) prompt on the terminal:
type `y` to allow, anything else to deny.

## Adding a tool

Edit `harness/tools.py`:

```python
@tool
def count_words(path: str) -> str:
    """Count words in a text file."""
    return f"{len(Path(path).read_text().split())} words"

ALL_TOOLS.append(count_words)
```

Docstring becomes the model-facing description; type hints become the JSON
schema. That's it.

## Adding a skill (a sub-agent)

Drop a new `.md` file in `skills/` with frontmatter:

```markdown
---
name: my_skill
description: One-line summary the model uses to decide when to invoke this skill.
---

# Step-by-step playbook
1. Do this first.
2. Then this.
3. Report results in this format.
```

Restart `main.py`. The skill is now a subagent the main agent can invoke
via the built-in `task` tool.

## Multi-user / multi-session

The agent remembers per-`(user, session)` conversations across runs. State
lives in `sessions.db` (SQLite) via LangGraph's `SqliteSaver`.

```bash
# default user, default session
python main.py "what's in this directory?"
python main.py "and what does main.py do?"           # remembers the previous turn

# named user + named session
python main.py --user alice --session research "scan this project for secrets"
python main.py --user alice --session research "summarize what you found"

# alice has another session in parallel — completely isolated
python main.py --user alice --session refactor "list files under harness/"

# bob's sessions don't see alice's
python main.py --user bob --session main "hi"

# admin
python main.py --list-users
python main.py --list-sessions --user alice
python main.py --delete-session --user alice --session research
```

How it works:

- Every run computes `thread_id = "<user>:<session>"` and passes it via
  `config={"configurable": {"thread_id": ...}}`.
- LangGraph's checkpointer auto-loads/saves the full message history per
  thread. The model sees the entire prior conversation every turn — no
  extra plumbing.
- `harness/sessions.py` adds a thin admin layer (list users, list sessions,
  delete) by querying the SQLite tables directly.

For production:
- Swap `SqliteSaver` for `PostgresSaver` (one-liner change in `harness/sessions.py`).
- Put real auth in front so users can't pass arbitrary `--user` ids.
- Consider a separate metadata table for session titles / created-at /
  last-active timestamps.

## What we gave up vs. the handwritten harness

- **Visibility into the loop**: previously you could see compaction triggers,
  sub-agent depth banners, every iteration's token count. With deepagents you
  trust the framework. The `stream()` output gives a tool-by-tool trace, but
  the deeper internals are LangGraph nodes you didn't write.
- **Custom flow**: LangGraph has opinions about state transitions. Exotic
  patterns (agents talking in real time, ad-hoc reasoning loops) are harder.

## What we gained

- **~50% less code to maintain**.
- **Free upgrades**: streaming, persistence, parallel tool calls, LangSmith
  tracing, HITL interrupts — all available by configuring, not coding.
- **Battle-tested primitives**: edge cases the deepagents authors have already
  hit and fixed (tool-call format quirks across providers, message serialization,
  recursion limits, etc.).
