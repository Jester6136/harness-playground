"""Builds the deep agent — wires LLM + tools + skill-based subagents.

deepagents is used as orchestration layer: agent loop, skill routing (task),
HITL (interrupt_on=), and checkpointing. By default the agent runs with
StateBackend (no host filesystem access); set ALLOW_FILESYSTEM=true to grant
deepagents' built-in fs tools real access via FilesystemPermission. Domain
capabilities live in custom tools and skills.
"""
from deepagents import create_deep_agent, FilesystemPermission
from deepagents.backends import FilesystemBackend
from deepagents.middleware.subagents import GENERAL_PURPOSE_SUBAGENT
from langchain.agents.middleware.context_editing import (
    ClearToolUsesEdit,
    ContextEditingMiddleware,
)

from harness.config import get_instructions, settings
from harness.extensions.skills import load_skills
from harness.extensions.tool_compaction import SemanticToolCompactionMiddleware
from harness.llm import make_llm
from harness.tools import ALL_TOOLS

# HITL gating for deepagents' built-in tools (we don't own these objects, so
# we can't tag them via metadata — list them by name here). Filesystem tools
# are gated by deepagents itself via `permissions=FilesystemPermission`.
_BUILTIN_HITL = {"execute"}


def _collect_hitl(*tool_lists) -> dict[str, bool]:
    """Build the deepagents `interrupt_on` dict.

    Picks up every tool whose `metadata={"hitl": True}` was set on the @tool
    decorator, plus the deepagents built-ins in `_BUILTIN_HITL`. To mark a
    custom tool as HITL, decorate it with `@tool(..., metadata={"hitl": True})`.
    """
    hitl = {name: True for name in _BUILTIN_HITL}
    for tools in tool_lists:
        for t in tools:
            if (getattr(t, "metadata", None) or {}).get("hitl"):
                hitl[t.name] = True
    return hitl

# deepagents auto-injects a "general-purpose" subagent with an aggressive
# default description ("use it for all tasks"). We override it with a
# restrained description so the model doesn't delegate simple questions.
# Spread the original spec to inherit all required fields (system_prompt, etc.),
# then override only the description so the model doesn't delegate simple tasks.
_GP_SUBAGENT_OVERRIDE: dict = {
    **GENERAL_PURPOSE_SUBAGENT,
    "description": (
        "General-purpose sub-agent for genuinely complex, multi-step tasks "
        "that require isolated context (e.g. long research chains, iterative "
        "refinement across many steps). Do NOT use for simple questions, "
        "single-step tasks, or anything you can answer directly."
    ),
}


def _context_editing_middleware() -> ContextEditingMiddleware:
    """Clear stale tool outputs before they overflow the context window.

    deepagents always wires a SummarizationMiddleware, but a custom vLLM model
    name has no LangChain profile so it falls back to a fixed 170k-token
    trigger — unreachable when vLLM serves a smaller --max-model-len, meaning
    the summarizer never fires and the model hard-overflows first. The dominant
    pressure here is large tool results (find_ttcp full doc, aggregate_ttcp
    tables, LIS rows, analyze_image output), not long chat. This Anthropic-style
    clear-tool-uses middleware replaces old tool outputs with a placeholder once
    prompt tokens cross a fraction of the REAL context window, keeping the most
    recent `keep` results verbatim. Sized from settings.max_model_len so it
    actually triggers; SummarizationMiddleware stays as a rarely-hit backstop.
    Runs via wrap_model_call (deep-copies messages — no permanent state mutation),
    so it composes safely with deepagents' own middleware regardless of order.
    """
    trigger = int(settings.max_model_len * settings.context_edit_trigger_fraction)
    return ContextEditingMiddleware(
        edits=[
            ClearToolUsesEdit(
                trigger=trigger,
                keep=settings.context_edit_keep,
                clear_tool_inputs=False,  # keep call args — small, and aid recall
            ),
        ],
    )


def make_agent(checkpointer=None, store=None, enable_thinking: bool | None = None):
    """Returns a compiled LangGraph agent ready to invoke or stream.

    Pass a checkpointer (e.g. from harness.persistence.checkpoints.make_checkpointer())
    to persist conversation state per thread_id. Without one the agent is
    stateless across runs.

    `enable_thinking` controls model reasoning. None → use settings default.
    """
    skills = load_skills()
    # _GP_SUBAGENT_OVERRIDE must come last so its name matches the auto-inject
    # guard and suppresses deepagents' default GP description.
    subagents = skills + [_GP_SUBAGENT_OVERRIDE]
    skill_tools = [t for s in skills for t in s.get("tools", [])]

    # When ALLOW_FILESYSTEM=true, swap in deepagents' real-host backend AND
    # grant matching permissions. Two pieces are required: the backend tells
    # the fs tools where to read/write (default StateBackend = in-memory state,
    # which is why `ls("/")` returns []), and the permissions list gates
    # access. SECURITY: virtual_mode=False allows any host path — only enable
    # in sandboxed deployments (container, restricted user). For narrower
    # scopes, set virtual_mode=True with a root_dir, or use deny rules.
    kwargs: dict = {}
    if settings.allow_filesystem:
        kwargs["backend"] = FilesystemBackend(virtual_mode=False)
        kwargs["permissions"] = [
            FilesystemPermission(
                operations=["read", "write"],
                paths=["/**"],
                mode="allow",
            ),
        ]

    return create_deep_agent(
        tools=ALL_TOOLS,
        system_prompt=get_instructions(ALL_TOOLS, skills),
        model=make_llm(enable_thinking=enable_thinking),
        subagents=subagents,
        middleware=[
            SemanticToolCompactionMiddleware(),
            _context_editing_middleware(),
        ],
        interrupt_on=_collect_hitl(ALL_TOOLS, skill_tools),
        checkpointer=checkpointer,
        store=store,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Module-level export consumed by `langgraph-cli` (`langgraph dev` / `up`).
# The CLI injects its own checkpointer + thread management at the API layer,
# so we don't pass our own here. For self-hosted production with persistent
# storage, configure `store` / `checkpointer` in langgraph.json or deploy
# to LangGraph Platform.
# ---------------------------------------------------------------------------
graph = make_agent()
