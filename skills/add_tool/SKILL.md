---
name: add_tool
description: Add a new tool to this harness following the project's @tool conventions. Use when the user asks to extend the agent's capabilities.
---

# Add a new tool to harness-playground

The harness uses LangChain's `@tool` decorator. Type hints become the JSON
schema; the docstring becomes the model-facing description.

## 1. Decide the shape

- **Name**: snake_case `verb_noun` (e.g. `count_lines`, `fetch_url`, `query_database`).
- **Side effects?** If yes (writes, network, shell, mutating DB), require human approval via
  `langgraph.types.interrupt(...)` — see how `run_bash` and `write_file` do it in `harness/tools.py`.
- **Output size?** If unbounded, truncate inside the function. Large outputs blow up the context window.

## 2. Pick the right location

| Scope | Where it goes |
|---|---|
| Generic, used across many skills | `harness/tools.py`, append to `ALL_TOOLS` at bottom |
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

For tools with side effects:

```python
from langgraph.types import interrupt

@tool
def dangerous_action(target: str) -> str:
    """Mutates external state. Asks for human approval first."""
    decision = interrupt({"type": "approval", "tool": "dangerous_action", "target": target})
    if decision != "approve":
        return "ERROR: denied by user"
    # ... actually do the thing
    return "done"
```

## 4. Register & verify

- For generic tools, append to the `ALL_TOOLS` list at the bottom of `harness/tools.py`.
- For skill-local tools, no registration needed — the skill loader auto-imports any `@tool`-decorated callables it finds in the skill folder.
- Run `python main.py "use the new <tool_name> to ..."` and watch the trace.

You do NOT need to edit `harness/agent.py` or any loader code. Both pick up new tools automatically.
