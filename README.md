# harness-playground

A minimal-but-complete agent harness around a local vLLM model. ~300 lines of
plain Python, no frameworks. Built to teach the concepts.

## Mental model

The model just predicts tokens. The **harness** is everything else:

| Layer | File | Role |
|---|---|---|
| Config | `harness/config.py` | One place for the endpoint, model name, prompts |
| LLM client | `harness/client.py` | Talks to vLLM (OpenAI-compatible API) |
| Tools | `harness/tools.py` | What the model is *allowed to ask for* |
| Permissions | `harness/permissions.py` | What *actually runs* when it asks |
| Observability | `harness/observability.py` | What the human sees as it runs |
| Loop | `harness/loop.py` | Glues everything together |
| Entry | `main.py` | CLI wrapper |

Read them in that order — each file is short and builds on the previous one.

## The loop, in pseudocode

```
loop until done or max_iterations:
    response = LLM(messages, tools=schemas)
    record assistant message in history
    if no tool calls in response:
        return final text
    for each tool call:
        check permission
        execute tool
        record result in history
```

That's it. Everything else is plumbing for that loop.

## Setup

```bash
pip install -r requirements.txt
```

Make sure your vLLM server was started with tool calling enabled, e.g.:

```bash
vllm serve cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit \
    --port 2900 \
    --enable-auto-tool-choice \
    --tool-call-parser hermes
```

(The right `--tool-call-parser` depends on the model's chat template. Check
the vLLM docs for your model.)

## Run

```bash
python main.py "list the files here and explain what mini_harness.py does"
```

You'll see a structured trace of every iteration: assistant text, each tool
call with arguments, the result, and token usage.

## Adding a new tool

Edit `harness/tools.py`:

```python
def _word_count(args: dict) -> str:
    text = Path(args["path"]).read_text()
    return f"{len(text.split())} words"

register(Tool(
    name="word_count",
    description="Count words in a text file.",
    parameters={
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    },
    execute=_word_count,
))
```

The loop picks it up automatically. Set `requires_approval=True` for anything
with side effects.

## Skills

Skills are **procedural playbooks** that live in `skills/*.md` and tell the
model *how* to do a class of task using the existing tools. They are NOT new
tools — they're instructions the model loads on demand via the `invoke_skill`
meta-tool.

```
skills/
├── summarize_codebase.md   ← walk a project and produce a structured summary
├── find_secrets.md         ← grep for hardcoded credentials, triage findings
└── add_tool.md             ← extend this harness with a new tool
```

Each skill is a markdown file with YAML-style frontmatter:

```markdown
---
name: my_skill
description: One-line summary the model uses to decide if this skill applies.
---

# Step-by-step instructions
1. Do this.
2. Then this.
3. Report results in this shape.
```

The `invoke_skill` tool is auto-populated from `skills/`. To add one, drop a
new `.md` file in there — no code changes needed.

**Tools vs. skills, in one line:** tools are the verbs the model can use;
skills are the playbooks for combining those verbs to accomplish a task well.

## What's NOT in here (intentional next steps)

- **Streaming**: output appears at the end of each turn, not token-by-token.
- **Context compaction**: long conversations will eventually exceed the
  context window. Add a summarizer that compresses old turns.
- **Sub-agents**: add a `spawn_agent` tool whose executor calls `loop.run()`
  recursively. That's how Claude Code parallelizes work.
- **Persistence**: every run starts fresh. Save `messages` to disk to resume.
- **Concurrency**: tool calls run sequentially. Could `asyncio.gather` them.
- **Evals**: no test harness for measuring agent quality on a fixed task set.

These are the layers a production harness adds on top of the core loop.

## File: `mini_harness.py`

The single-file ~120-line version from the earlier conversation. Keep it
around as a reference point — it does the same thing in one file with no
abstractions, so you can see the difference between "minimal" and
"structured".
