"""Tools as plain Python functions decorated with @tool.

LangChain reads the docstring (becomes the model-facing description) and the
type hints (become the JSON schema). No registry boilerplate needed — just
write a function and add it to ALL_TOOLS.
"""
import subprocess
from pathlib import Path

from langchain_core.tools import tool


@tool
def read_file(path: str) -> str:
    """Read a UTF-8 text file from disk and return its contents.

    Files larger than 20K chars are truncated to keep the context window bounded.
    """
    text = Path(path).read_text()
    if len(text) > 20_000:
        return text[:20_000] + f"\n\n... [truncated {len(text) - 20_000} chars]"
    return text


@tool
def list_dir(path: str = ".") -> str:
    """List entries in a directory. 'd' prefix = directory, 'f' = file."""
    entries = sorted(Path(path).iterdir(), key=lambda p: (not p.is_dir(), p.name))
    return "\n".join(f"{'d' if p.is_dir() else 'f'} {p.name}" for p in entries)


# Substrings that must never run, even with approval.
HARD_DENY = ("rm -rf /", "mkfs", ":(){ :|:& };:", "dd if=/dev/zero of=/dev/")


def _ask(label: str) -> bool:
    """Prompt the human for approval. Returns True iff they typed 'y'.

    For production, replace this with LangGraph's interrupt() so the UI layer
    (chat app, IDE plugin) handles approval rather than blocking on stdin.
    """
    print(f"\n  [approve?] {label}  [y/N]: ", end="", flush=True)
    return input().strip().lower() == "y"


@tool
def write_file(path: str, content: str) -> str:
    """Write text to a file (creates or overwrites). Asks for human approval."""
    if not _ask(f"write_file({path!r}, {len(content)} bytes)"):
        return "ERROR: denied by user"
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return f"wrote {len(content)} bytes to {p}"


@tool
def run_bash(command: str) -> str:
    """Run a shell command and return stdout/stderr. Asks for human approval."""
    for danger in HARD_DENY:
        if danger in command:
            return f"ERROR: command matches denylist pattern {danger!r}"
    if not _ask(f"run_bash({command!r})"):
        return "ERROR: denied by user"
    result = subprocess.run(
        command, shell=True, capture_output=True, text=True, timeout=30
    )
    return (
        f"exit_code: {result.returncode}\n"
        f"--- stdout ---\n{result.stdout}"
        f"--- stderr ---\n{result.stderr}"
    )


ALL_TOOLS = [read_file, list_dir, write_file, run_bash]
