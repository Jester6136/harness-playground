"""Builds the deep agent — wires LLM + tools + skill-based subagents.

deepagents is used as orchestration layer: agent loop, skill routing (task),
HITL (interrupt_on=), and checkpointing. The agent runs with StateBackend —
no local filesystem access. Domain capabilities live in custom tools and skills.
"""
from deepagents import create_deep_agent

from harness.config import get_instructions
from harness.extensions.skills import load_skills
from harness.llm import make_llm
from harness.tools import ALL_TOOLS

# Tools that pause for human approval before executing.
HITL_TOOLS = {
    "execute": True,
    "write_file": True,
    "edit_file": True,
}

# deepagents auto-injects a "general-purpose" subagent with an aggressive
# default description ("use it for all tasks"). We override it with a
# restrained description so the model doesn't delegate simple questions.
_GP_SUBAGENT_OVERRIDE: dict = {
    "name": "general-purpose",
    "description": (
        "General-purpose sub-agent for genuinely complex, multi-step tasks "
        "that require isolated context (e.g. long research chains, iterative "
        "refinement across many steps). Do NOT use for simple questions, "
        "single-step tasks, or anything you can answer directly."
    ),
}


def make_agent(checkpointer=None, store=None, enable_thinking: bool | None = None):
    """Returns a compiled LangGraph agent ready to invoke or stream.

    Pass a checkpointer (e.g. from harness.persistence.checkpoints.make_checkpointer())
    to persist conversation state per thread_id. Without one the agent is
    stateless across runs.

    Pass a store (e.g. from harness.persistence.store.get_store()) to enable long-term
    memory tools (remember_about_user, recall_user_context).

    `enable_thinking` controls model reasoning. None → use settings default.
    """
    skills = load_skills()
    # _GP_SUBAGENT_OVERRIDE must come last so its name matches the auto-inject
    # guard and suppresses deepagents' default GP description.
    subagents = skills + [_GP_SUBAGENT_OVERRIDE]
    return create_deep_agent(
        tools=ALL_TOOLS,
        system_prompt=get_instructions(skills),
        model=make_llm(enable_thinking=enable_thinking),
        subagents=subagents,
        interrupt_on=HITL_TOOLS,
        checkpointer=checkpointer,
        store=store,
    )


# ---------------------------------------------------------------------------
# Module-level export consumed by `langgraph-cli` (`langgraph dev` / `up`).
# The CLI injects its own checkpointer + thread management at the API layer,
# so we don't pass our own here. For self-hosted production with persistent
# storage, configure `store` / `checkpointer` in langgraph.json or deploy
# to LangGraph Platform.
# ---------------------------------------------------------------------------
graph = make_agent()
