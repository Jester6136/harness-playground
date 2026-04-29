"""Shell execution tool with HITL approval and a hard denylist."""
from __future__ import annotations

import subprocess

from langchain_core.tools import tool
from langgraph.types import interrupt

from harness.logging_config import log_tool_call

# Substrings that must never run, even with approval.
HARD_DENY = ("rm -rf /", "mkfs", ":(){ :|:& };:", "dd if=/dev/zero of=/dev/")


@tool
@log_tool_call
def run_bash(command: str) -> str:
    """Run a shell command and return stdout/stderr. Requires human approval."""
    for danger in HARD_DENY:
        if danger in command:
            return f"ERROR: command matches denylist pattern {danger!r}"
    decision = interrupt({
        "type": "approval",
        "tool": "run_bash",
        "args": {"command": command},
    })
    if decision != "approve":
        return "ERROR: denied by user"
    result = subprocess.run(
        command, shell=True, capture_output=True, text=True, timeout=30
    )
    return (
        f"exit_code: {result.returncode}\n"
        f"--- stdout ---\n{result.stdout}"
        f"--- stderr ---\n{result.stderr}"
    )
