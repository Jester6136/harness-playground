"""Long-term memory tools backed by the Postgres store."""
from __future__ import annotations

from langchain_core.tools import tool

from harness.logging_config import log_tool_call
from harness.persistence.store import get_store
from harness.utils.async_utils import run_async

# Thread context (user_id) is not available inside a plain @tool without a
# RunnableConfig. We use a generic namespace; the API layer should inject the
# user via config in a future iteration.
_NAMESPACE = ("users", "default")


@tool
@log_tool_call
def remember_about_user(key: str, value: str) -> str:
    """Persist a fact about the current user in long-term memory.

    Use this to remember information that should survive across sessions, e.g.
    the user's name, role, preferences, or project context. Key should be a
    short snake_case label (e.g. 'name', 'department', 'preferred_language').
    """
    async def _write() -> str:
        store = await get_store()
        await store.aput(_NAMESPACE, key, {"value": value})
        return f"Remembered: {key} = {value!r}"

    try:
        return run_async(_write())
    except Exception as exc:
        return f"ERROR storing memory: {exc}"


@tool
@log_tool_call
def recall_user_context() -> str:
    """Retrieve all facts remembered about the current user from long-term memory.

    Returns a formatted list of key-value pairs. Returns an empty message if
    no facts have been stored yet.
    """
    async def _read() -> str:
        store = await get_store()
        items = await store.asearch(_NAMESPACE)
        if not items:
            return "No facts remembered about this user yet."
        lines = ["**Remembered facts:**"]
        for item in items:
            lines.append(f"  {item.key}: {item.value.get('value', item.value)}")
        return "\n".join(lines)

    try:
        return run_async(_read())
    except Exception as exc:
        return f"ERROR reading memory: {exc}"
