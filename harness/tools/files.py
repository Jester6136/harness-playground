"""Filesystem tools: read, list, write."""
from __future__ import annotations

from pathlib import Path

from langchain_core.tools import tool
from langgraph.types import interrupt

from harness.logging_config import log_tool_call
from harness.utils.paths import resolve_relative_path


@tool
@log_tool_call
def read_file(path: str) -> str:
    """Read a UTF-8 text file from disk and return its contents.

    Paths are relative to the working directory. Files larger than 20K chars
    are truncated to keep the context window bounded.
    """
    text = resolve_relative_path(path).read_text()
    if len(text) > 20_000:
        return text[:20_000] + f"\n\n... [truncated {len(text) - 20_000} chars]"
    return text


@tool
@log_tool_call
def list_dir(path: str = ".") -> str:
    """List entries in a directory. 'd' prefix = directory, 'f' = file."""
    entries = sorted(
        resolve_relative_path(path).iterdir(),
        key=lambda p: (not p.is_dir(), p.name),
    )
    return "\n".join(f"{'d' if p.is_dir() else 'f'} {p.name}" for p in entries)


@tool
@log_tool_call
def write_file(path: str, content: str) -> str:
    """Write text to a file (creates or overwrites). Requires human approval."""
    decision = interrupt({
        "type": "approval",
        "tool": "write_file",
        "args": {"path": path, "bytes": len(content)},
    })
    if decision != "approve":
        return "ERROR: denied by user"
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return f"wrote {len(content)} bytes to {p}"
