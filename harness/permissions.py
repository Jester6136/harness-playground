"""Permission policy — the gate between the model's *requests* and actual *execution*.

The model can ask to do anything; this layer decides what actually runs.
Three outcomes for any tool call:
  - allowed silently (read-only stuff)
  - allowed after the human types 'y' (approval-required tools)
  - denied outright (denylist patterns)
"""
from .tools import Tool

# Substrings that should never run, even with approval.
HARD_DENYLIST = (
    "rm -rf /",
    "mkfs",
    ":(){ :|:& };:",   # classic fork bomb
    "dd if=/dev/zero of=/dev/",
)


def check(tool: Tool, args: dict) -> tuple[bool, str | None]:
    """Returns (allowed, reason_if_denied)."""
    # 1. Hard denylist for shell commands
    if tool.name == "run_bash":
        cmd = args.get("command", "")
        for pattern in HARD_DENYLIST:
            if pattern in cmd:
                return False, f"command matches denylist pattern {pattern!r}"

    # 2. Approval gate
    if tool.requires_approval:
        prompt = f"\n  [approve?] {tool.name}({args})  [y/N]: "
        if input(prompt).strip().lower() != "y":
            return False, "denied by user"

    return True, None
