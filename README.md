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

## Sub-agents and compaction (the two scaling layers)

Both are wired in. Together they let the agent run for many iterations
without exploding the context window.

### Sub-agents — `spawn_agent` tool

The model can spin up a child agent with **isolated context**. The child
runs its own loop, calls its own tools, and returns one final string. The
parent's history grows by exactly one message no matter how many iterations
the child uses internally.

```
parent context:    [system, user, ..., spawn_agent("research X"), "X is Y"]
                                                                  ↑ one string back
child context:     [system, "research X", read, list, read, ...]  ← gone after return
```

Use it when a sub-task would otherwise produce dozens of intermediate tool
calls that aren't relevant to the parent's reasoning. Recursion is bounded
by `MAX_AGENT_DEPTH` in [config.py](harness/config.py).

### Compaction — automatic, before every LLM call

`harness/compaction.py` estimates total tokens; once they exceed
`COMPACT_THRESHOLD_TOKENS`, it asks the model to summarize the *middle* of
the conversation, replacing many old turns with one short summary message.
The system prompt, original user task, and last `KEEP_RECENT_TURNS` messages
are always preserved verbatim.

```
before:  [system, user, A1, T1, A2, T2, A3, T3, A4, T4, A5, T5]   ~6500 tok
after:   [system, user, "[summary of A1..A3]", A4, T4, A5, T5]    ~1800 tok
```

Tune the trigger and retention in [config.py](harness/config.py).

## What's still NOT in here (further next steps)

- **Streaming**: output appears at the end of each turn, not token-by-token.
- **Persistence**: every run starts fresh. Save `messages` to disk to resume.
- **Parallel tool calls**: tool calls within one turn run sequentially. Could `asyncio.gather` them.
- **Evals**: no test harness for measuring agent quality on a fixed task set.
- **Real tokenizer**: compaction uses a char/4 estimate. Swap in `tiktoken` or the model's tokenizer for accuracy.

These are the layers a production harness adds on top of the core loop.

## File: `mini_harness.py`

The single-file ~120-line version from the earlier conversation. Keep it
around as a reference point — it does the same thing in one file with no
abstractions, so you can see the difference between "minimal" and
"structured".
