---
name: add_tool
description: Add a new tool to this harness following the project's @tool conventions. Use when the user asks to extend the agent's capabilities.
---

# Add a new tool to harness-playground

The harness uses LangChain's `@tool` decorator. Type hints become the JSON
schema; the docstring becomes the model-facing description.

## 1. Decide the shape

- **Name**: snake_case `verb_noun` (e.g. `count_lines`, `fetch_url`, `query_database`).
- **Side effects?** Built-in tools that need human approval (`execute`, `write_file`, `edit_file`) are
  already covered by `interrupt_on=` in `harness/agent.py`. For a brand-new custom tool with
  side effects, add its name to the `HITL_TOOLS` dict in `harness/agent.py`.
- **Output size?** If unbounded, truncate inside the function. Large outputs blow up the context window.

## 2. Pick the right location

| Scope | Where it goes |
|---|---|
| Generic, used across many skills | `harness/tools/` — pick the most fitting domain file (`vision.py`, `memory.py`) or create a new one, then add to `ALL_TOOLS` in `harness/tools/__init__.py` |
| Specific to one skill | New `*.py` file in `skills/<skill_name>/` (auto-imported by skill loader) |

## 3. Write the tool

```python
from langchain_core.tools import tool

@tool
def my_new_tool(arg1: str, arg2: int = 10) -> str:
    """One-line description shown to the model.

    Longer body explaining when to use it, what it returns, and
    any constraints the model should know about.
    """
    # implementation
    return result
```

## 4. Register & verify

- For generic tools in `harness/tools/`, add to `ALL_TOOLS` in `harness/tools/__init__.py`.
- For skill-local tools, no registration needed — the skill loader auto-imports any `@tool`-decorated callables it finds in the skill folder.
- Run `python main.py "use the new <tool_name> to ..."` and watch the trace.

You do NOT need to edit `harness/agent.py` unless the new tool needs HITL approval. Both the agent and skill loader pick up new tools automatically.
