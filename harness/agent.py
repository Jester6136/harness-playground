"""Builds the deep agent — wires LLM + tools + skill-based subagents.

deepagents ships built-in tools (write_todos, ls, read_file, write_file,
edit_file, glob, grep, execute, task) and a native HITL approval mechanism
via `interrupt_on=`. We only add tools it doesn't have.
"""
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend

from harness.config import get_instructions
from harness.extensions.skills import load_skills
from harness.llm import make_llm
from harness.tools import ALL_TOOLS

# Built-in tools that should pause for human approval. Same protocol
# (LangGraph `interrupt`) as before — the API streams `event: interrupt`
# and resumes via /threads/.../runs/resume; the CLI prompts y/N.
HITL_TOOLS = {
    "execute": True,
    "write_file": True,
    "edit_file": True,
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
    return create_deep_agent(
        tools=ALL_TOOLS,
        system_prompt=get_instructions(),
        model=make_llm(enable_thinking=enable_thinking),
        subagents=load_skills(),
        backend=FilesystemBackend(),
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
