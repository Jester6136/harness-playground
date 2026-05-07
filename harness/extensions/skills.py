"""Skill discovery + loading.

Skills v2 layout (preferred):
    skills/<name>/SKILL.md       ← required: frontmatter + body (system prompt)
    skills/<name>/*.py           ← optional: @tool-decorated functions only this skill needs
    skills/<name>/<anything>     ← optional resources (templates, references) — read by tools

Backward-compat:
    skills/<name>.md             ← still loaded as a flat skill (no helper tools possible)

Folder skills take precedence over flat .md with the same name.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

from harness.config import SKILLS_DIR
from harness.tools import ALL_TOOLS


# ---------------------------------------------------------------------------
# Frontmatter parser — moved here so harness/agent.py stays small.
# Tiny YAML-ish reader; avoids a PyYAML dep for this single use case.
# ---------------------------------------------------------------------------

def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Parse `--- key: value ---` header. Returns (meta, body)."""
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


# ---------------------------------------------------------------------------
# Skill-specific tool loading
# ---------------------------------------------------------------------------

def _is_langchain_tool(obj: Any) -> bool:
    """Loose duck-typing check for objects produced by `langchain_core.tools.tool`."""
    return hasattr(obj, "name") and hasattr(obj, "description") and hasattr(obj, "invoke")


def _import_helpers(skill_dir: Path) -> list[Any]:
    """Import every `*.py` file (not starting with _) in `skill_dir` and harvest @tool objects."""
    tools: list[Any] = []
    for py_file in sorted(skill_dir.glob("*.py")):
        if py_file.name.startswith("_"):
            continue
        module_name = f"skills.{skill_dir.name}.{py_file.stem}"
        spec = importlib.util.spec_from_file_location(module_name, py_file)
        if not spec or not spec.loader:
            continue
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        for attr_name in dir(module):
            if attr_name.startswith("_"):
                continue
            attr = getattr(module, attr_name)
            if _is_langchain_tool(attr):
                tools.append(attr)
    return tools


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _make_subagent_spec(name: str, description: str, body: str, extra_tools: list[Any]) -> dict:
    return {
        "name": name,
        "description": description,
        "system_prompt": body.strip(),
        "tools": ALL_TOOLS + extra_tools,
    }


def load_skills() -> list[dict]:
    """Discover skills under SKILLS_DIR and build deepagents subagent specs.

    Order:
      1. Folder layout `skills/<name>/SKILL.md` (preferred; can have skill-local @tool helpers).
      2. Flat layout `skills/<name>.md` (backward-compat; only if name not already taken).
    """
    if not SKILLS_DIR.exists():
        return []

    specs: list[dict] = []
    seen: set[str] = set()

    # Folder layout
    for child in sorted(SKILLS_DIR.iterdir()):
        if not child.is_dir():
            continue
        skill_md = child / "SKILL.md"
        if not skill_md.exists():
            continue
        meta, body = parse_frontmatter(skill_md.read_text())
        name = meta.get("name", child.name)
        if name in seen:
            continue
        seen.add(name)
        extra_tools = _import_helpers(child)
        specs.append(_make_subagent_spec(name, meta.get("description", ""), body, extra_tools))

    # Flat backward-compat layout
    for path in sorted(SKILLS_DIR.glob("*.md")):
        meta, body = parse_frontmatter(path.read_text())
        name = meta.get("name", path.stem)
        if name in seen:
            continue
        seen.add(name)
        specs.append(_make_subagent_spec(name, meta.get("description", ""), body, []))

    return specs
