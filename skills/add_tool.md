---
name: add_tool
description: Add a new tool to this harness following the project's conventions. Use when the user asks to extend the agent's capabilities.
---

# Add a new tool to harness-playground

1. **Read `harness/tools.py`** to see the existing `Tool` dataclass and `register()` pattern.
2. **Decide the shape** before writing code:
   - Name: snake_case `verb_noun` (e.g. `count_lines`, `fetch_url`).
   - Side effects? If yes (writes, network, shell), set `requires_approval=True`.
   - Output size? If the tool can return a lot of data, truncate inside the executor — uncontrolled output blows up the context window.
3. **Edit `harness/tools.py`** and add two things:
   - A `_my_tool(args: dict) -> str` executor function.
   - A `register(Tool(name=..., description=..., parameters=..., execute=_my_tool))` call.
4. **Verify** by running `python main.py "use the new <tool_name> to ..."`.
5. **Watch the trace** — confirm the tool is called with the right args and returns sensible output.

You do NOT need to edit `loop.py` or `permissions.py`. Both pick up new tools automatically via the `REGISTRY` dict and the `requires_approval` flag.
