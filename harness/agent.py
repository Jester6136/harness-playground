"""Builds the deep agent — wires LLM + tools + skill-based subagents.

The whole "harness" is now this one function plus a markdown loader.
The agentic loop, sub-agents, state management, and compaction live inside
deepagents/LangGraph.
"""
from deepagents import create_deep_agent
from langchain_openai import ChatOpenAI

from .config import (
    INSTRUCTIONS,
    SKILLS_DIR,
    TEMPERATURE,
    VLLM_API_KEY,
    VLLM_BASE_URL,
    VLLM_MODEL_NAME,
)
from .tools import ALL_TOOLS


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Tiny YAML-ish parser for `--- key: value ---` skill frontmatter.

    Avoids pulling PyYAML in for this one tiny use case.
    """
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


def _load_skills_as_subagents() -> list[dict]:
    """Each skill .md becomes one deepagents subagent.

    The mapping is direct:
      frontmatter `name`        → subagent name (the model invokes it by this)
      frontmatter `description` → subagent description (model uses to pick it)
      body                      → subagent prompt (the playbook itself)
    """
    if not SKILLS_DIR.exists():
        return []
    out = []
    for path in sorted(SKILLS_DIR.glob("*.md")):
        meta, body = _parse_frontmatter(path.read_text())
        out.append({
            "name": meta.get("name", path.stem),
            "description": meta.get("description", ""),
            "prompt": body.strip(),
            "tools": ALL_TOOLS,  # subagent gets the same toolbox as the main agent
        })
    return out


def make_agent():
    """Returns a compiled LangGraph agent ready to invoke or stream."""
    llm = ChatOpenAI(
        base_url=VLLM_BASE_URL,
        api_key=VLLM_API_KEY,
        model=VLLM_MODEL_NAME,
        temperature=TEMPERATURE,
    )
    return create_deep_agent(
        tools=ALL_TOOLS,
        instructions=INSTRUCTIONS,
        model=llm,
        subagents=_load_skills_as_subagents(),
    )
