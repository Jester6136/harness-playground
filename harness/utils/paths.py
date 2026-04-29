"""Path helpers shared across tools."""
from __future__ import annotations

from pathlib import Path


def resolve_relative_path(path: str) -> Path:
    """Resolve a path, recovering from a common LLM mistake of leading slash.

    If the agent passes '/main.py' but the file doesn't exist there, try
    resolving it as relative to CWD (i.e., strip the leading '/').
    """
    p = Path(path)
    if p.is_absolute() and not p.exists():
        stripped = Path(*p.parts[1:])
        candidate = Path.cwd() / stripped
        if candidate.exists():
            return candidate
    return p
