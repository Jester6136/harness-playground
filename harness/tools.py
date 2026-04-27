"""Tools = the model's interface to the outside world.

Each tool has two halves:
  - SCHEMA   (sent to the model, tells it the tool exists and its arg shape)
  - EXECUTE  (runs in this process when the model calls the tool)

Tools are kept in a REGISTRY so the loop and permission layer can look them
up by name. To add a new tool, define a function and call `register(Tool(...))`
at the bottom of this file.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]      # JSON Schema describing the args
    execute: Callable[[dict], str]  # runs the tool, returns a string
    requires_approval: bool = False  # if True, permissions.py will prompt the user


REGISTRY: dict[str, Tool] = {}


def register(tool: Tool) -> None:
    REGISTRY[tool.name] = tool


def schemas() -> list[dict]:
    """Return all tool schemas in the OpenAI tool-calling format."""
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            },
        }
        for t in REGISTRY.values()
    ]


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def _read_file(args: dict) -> str:
    path = Path(args["path"])
    text = path.read_text()
    # Truncate huge files so one bad read can't blow up the context window.
    if len(text) > 20_000:
        return text[:20_000] + f"\n\n... [truncated {len(text) - 20_000} chars]"
    return text


def _list_dir(args: dict) -> str:
    path = Path(args.get("path", "."))
    entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name))
    return "\n".join(f"{'d' if p.is_dir() else 'f'} {p.name}" for p in entries)


def _write_file(args: dict) -> str:
    path = Path(args["path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(args["content"])
    return f"wrote {len(args['content'])} bytes to {path}"


def _run_bash(args: dict) -> str:
    result = subprocess.run(
        args["command"],
        shell=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return (
        f"exit_code: {result.returncode}\n"
        f"--- stdout ---\n{result.stdout}"
        f"--- stderr ---\n{result.stderr}"
    )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

register(Tool(
    name="read_file",
    description="Read a UTF-8 text file from disk and return its contents.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file."},
        },
        "required": ["path"],
    },
    execute=_read_file,
))

register(Tool(
    name="list_dir",
    description="List entries in a directory. Prefix 'd' = dir, 'f' = file.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Directory path. Defaults to current dir."},
        },
    },
    execute=_list_dir,
))

register(Tool(
    name="write_file",
    description="Write text to a file (creates or overwrites). Requires user approval.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
        },
        "required": ["path", "content"],
    },
    execute=_write_file,
    requires_approval=True,
))

register(Tool(
    name="run_bash",
    description="Run a shell command and return stdout/stderr. Requires user approval.",
    parameters={
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Shell command to execute."},
        },
        "required": ["command"],
    },
    execute=_run_bash,
    requires_approval=True,
))


# ---------------------------------------------------------------------------
# Skills — a meta-tool that loads a procedural playbook into context on demand.
# Skills are markdown files under ./skills/ with YAML-style frontmatter:
#     ---
#     name: my_skill
#     description: one-line summary the model uses to pick this skill
#     ---
#     # body: step-by-step instructions the model should follow
# ---------------------------------------------------------------------------

SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Tiny YAML-ish parser for `--- key: value ---` frontmatter."""
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    meta: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, text[end + 5:]


def _list_skills() -> list[tuple[str, str]]:
    """Returns [(name, description), ...] for all skills found on disk."""
    if not SKILLS_DIR.exists():
        return []
    out = []
    for path in sorted(SKILLS_DIR.glob("*.md")):
        meta, _ = _parse_frontmatter(path.read_text())
        out.append((meta.get("name", path.stem), meta.get("description", "")))
    return out


def _build_invoke_skill_description() -> str:
    skills = _list_skills()
    if not skills:
        return "Load a procedural skill into context. (No skills currently available.)"
    lines = [
        "Load a procedural skill (a recipe for a class of tasks) into context.",
        "Call this BEFORE doing the task itself when one of the skills below matches.",
        "Available skills:",
    ]
    for name, desc in skills:
        lines.append(f"  - {name}: {desc}")
    return "\n".join(lines)


def _invoke_skill(args: dict) -> str:
    name = args["name"]
    path = SKILLS_DIR / f"{name}.md"
    if not path.exists():
        available = [n for n, _ in _list_skills()]
        return f"ERROR: unknown skill {name!r}. Available: {available}"
    _, body = _parse_frontmatter(path.read_text())
    return body


register(Tool(
    name="invoke_skill",
    description=_build_invoke_skill_description(),
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Name of the skill to load."},
        },
        "required": ["name"],
    },
    execute=_invoke_skill,
))


# ---------------------------------------------------------------------------
# Sub-agent — a tool whose executor runs another full agent loop in isolation.
#
# The sub-agent gets its OWN `messages` list (fresh system prompt, fresh user
# task). Only its final string is returned to the parent. So the parent's
# context grows by exactly one tool result, no matter how many iterations
# the sub-agent runs internally.
#
# Use cases:
#   - deep research that would otherwise generate dozens of intermediate
#     tool calls in the main conversation
#   - parallel exploration ("look at branch A while I look at branch B")
#   - bounding the blast radius when running risky/experimental skills
# ---------------------------------------------------------------------------

def _spawn_agent(args: dict) -> str:
    # Lazy imports break the circular dependency: loop.py imports tools.py
    # at startup, and we don't want tools.py importing loop.py back at startup.
    from .client import make_client
    from .loop import run

    return run(make_client(), args["task"])


register(Tool(
    name="spawn_agent",
    description=(
        "Spawn a sub-agent with its own isolated context to handle a sub-task. "
        "The sub-agent's full conversation does NOT pollute the main context — "
        "only its final answer comes back as one string. Use for: deep research, "
        "parallel exploration, sub-tasks that would otherwise generate many "
        "intermediate tool calls. The sub-agent has access to all the same "
        "tools (including invoke_skill) but starts with NO memory of the "
        "parent conversation, so the task description MUST be self-contained."
    ),
    parameters={
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "Self-contained task description for the sub-agent.",
            },
        },
        "required": ["task"],
    },
    execute=_spawn_agent,
))
