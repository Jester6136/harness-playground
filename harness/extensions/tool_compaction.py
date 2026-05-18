"""Semantic tool-output compaction middleware.

deepagents' built-in ContextEditingMiddleware (wired in harness.agent) replaces
old tool outputs with a fixed ``[cleared]`` placeholder once a token threshold
is crossed — robust, but the model loses *what the tool did*. This middleware
adds the hermes-agent idea (`agent/context_compressor._summarize_tool_result`):
replace stale large tool results with a short, structure-aware stub like

    ⟦compacted aggregate_ttcp⟧ 1.8 KB · 42 phần tử

so the model still knows which tool ran and roughly what came back.

Design choices (this machine has no runtime — correctness is by construction,
not by test):

* Mirrors the EXACT idiom of LangChain's ContextEditingMiddleware:
  ``deepcopy(list(request.messages))`` → rewrite ``ToolMessage`` via
  ``model_copy(update=...)`` → ``handler(request.override(messages=...))``.
  No permanent state mutation (wrap_model_call deep-copies).
* Triggers on *age*, not tokens: the last ``keep`` tool results are always
  verbatim; older ones are stubbed every call. Deterministic and idempotent
  (stubs carry a sentinel and are skipped on re-entry), so it composes with
  ContextEditingMiddleware regardless of middleware order — both only ever
  shrink old ToolMessages, so whichever runs first the other no-ops.
* Tool-AGNOSTIC: the stub is derived from the result's generic shape (JSON
  list → element count, JSON dict → top-level keys, else → text head). No
  per-tool table to maintain — a new tool added to ALL_TOOLS gets a sensible
  stub for free, matching this project's "register once, nothing else"
  convention. Parsing is guarded; _stub never raises into the agent loop.
"""
from __future__ import annotations

import json
from copy import deepcopy

from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.messages import ToolMessage

from harness.config import settings

# Sentinel prefix marking an already-compacted result — used for idempotency
# (never stub a stub) and so the model can recognise elided content.
_MARK = "⟦compacted"  # ⟦compacted <tool>⟧ ...


def _head(text: str, limit: int = 220) -> str:
    """First non-empty line, whitespace-collapsed, truncated to `limit`."""
    for line in text.splitlines():
        line = line.strip()
        if line:
            return line[:limit] + ("…" if len(line) > limit else "")
    return text.strip()[:limit]


def _loads(body: str):
    """json.loads that never raises — returns the object or None."""
    try:
        return json.loads(body)
    except Exception:
        return None


def _shape_summary(body: str) -> str | None:
    """Generic, tool-agnostic outcome line from the result's structure.

    list  → element count   (search/list/aggregate-style tools)
    dict  → top-level keys  (single-record / structured tools)
    other → None, caller falls back to a text head.
    """
    data = _loads(body)
    if isinstance(data, list):
        return f"{len(data)} phần tử"
    if isinstance(data, dict):
        keys = [str(k) for k in data.keys()]
        shown = ", ".join(keys[:6])
        more = f" +{len(keys) - 6}" if len(keys) > 6 else ""
        return f"{len(keys)} khóa: {shown}{more}"
    return None


def _stub(msg: ToolMessage) -> str:
    """hermes-style semantic one-liner for a bulky tool result.

    Uses the result's generic structure; any parse failure / odd shape just
    falls back to a head+size stub, so this can never raise.
    """
    name = msg.name or "tool"
    body = msg.content if isinstance(msg.content, str) else str(msg.content)
    kb = len(body.encode("utf-8", "ignore")) / 1024

    summary = _shape_summary(body)
    if summary:
        return f"{_MARK} {name}⟧ {kb:.1f} KB · {summary}"
    return f"{_MARK} {name}⟧ {kb:.1f} KB elided · head: {_head(body)}"


class SemanticToolCompactionMiddleware(AgentMiddleware):
    """Replace stale, large tool results with structure-aware stubs.

    Keeps the most recent ``settings.context_edit_keep`` tool results intact;
    older ToolMessages whose content exceeds
    ``settings.context_compact_min_chars`` are collapsed to a one-line stub.
    """

    def wrap_model_call(self, request, handler):
        messages = deepcopy(list(request.messages))

        tool_idxs = [
            i for i, m in enumerate(messages) if isinstance(m, ToolMessage)
        ]
        keep = settings.context_edit_keep
        # Protect the most recent `keep` tool results; only stub older ones.
        stale = tool_idxs[:-keep] if keep else tool_idxs
        if keep >= len(tool_idxs):
            stale = []

        min_chars = settings.context_compact_min_chars
        for i in stale:
            m = messages[i]
            content = m.content if isinstance(m.content, str) else str(m.content)
            if content.startswith(_MARK):  # already compacted — idempotent
                continue
            if len(content) < min_chars:  # small result: leave fully readable
                continue
            messages[i] = m.model_copy(
                update={"content": _stub(m), "artifact": None}
            )

        return handler(request.override(messages=messages))
