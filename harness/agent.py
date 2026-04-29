"""Builds the deep agent — wires LLM + tools + skill-based subagents.

The whole "harness" is now this one function plus the skill loader.
The agentic loop, sub-agents, state management, and compaction live inside
deepagents/LangGraph.
"""
from deepagents import create_deep_agent

from harness.config import get_instructions
from harness.extensions.skills import load_skills
from harness.llm import make_llm
from harness.tools import ALL_TOOLS


def make_agent(checkpointer=None, store=None, enable_thinking: bool | None = None):
    """Returns a compiled LangGraph agent ready to invoke or stream.

    Pass a checkpointer (e.g. from harness.persistence.checkpoints.make_checkpointer())
    to persist conversation state per thread_id. Without one the agent is
    stateless across runs.

    Pass a store (e.g. from harness.persistence.store.get_store()) to enable long-term
    memory tools (remember_about_user, recall_user_context).

    `enable_thinking` controls model reasoning. None → use settings default.
    """
    return create_deep_agent(
        tools=ALL_TOOLS,
        system_prompt=get_instructions(),
        model=make_llm(enable_thinking=enable_thinking),
        subagents=load_skills(),
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
