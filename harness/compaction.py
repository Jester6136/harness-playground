"""Context compaction — keep `messages` from growing forever.

Why this exists: every iteration appends to `messages`, and every iteration
sends the FULL list back to the LLM. After ~20 iterations with a few big
file reads, the prompt balloons to 30K+ tokens — slow, expensive, and
eventually exceeds the context window.

Strategy: when total tokens cross a threshold, replace the MIDDLE of the
conversation with a single LLM-generated summary. Keep:
  - the system prompt (always),
  - the original user task (so the goal isn't lost),
  - the most recent K turns verbatim (so the model has fresh detail).

    [system, user, A1, T1, A2, T2, A3, T3, A4, T4, A5, T5]
                   └────────── compacted ──────────┘
    becomes:
    [system, user, summary, A4, T4, A5, T5]
"""
from openai import OpenAI

from . import observability as obs
from .config import COMPACT_THRESHOLD_TOKENS, KEEP_RECENT_TURNS, VLLM_MODEL_NAME


def estimate_tokens(messages: list[dict]) -> int:
    """Rough char-based estimate (~4 chars per token).

    Real harnesses use tiktoken or the model's actual tokenizer; this is
    fine for triggering compaction, where exact precision doesn't matter.
    """
    total = 0
    for m in messages:
        c = m.get("content")
        if isinstance(c, str):
            total += len(c)
        for tc in m.get("tool_calls", []) or []:
            total += len(tc["function"]["arguments"])
    return total // 4


def maybe_compact(messages: list[dict], client: OpenAI) -> list[dict]:
    """Return a possibly-compacted messages list. No-op below threshold."""
    tokens = estimate_tokens(messages)
    if tokens < COMPACT_THRESHOLD_TOKENS:
        return messages

    # Need: system + user + at least one message to compact + K recent turns.
    if len(messages) < 2 + 1 + KEEP_RECENT_TURNS:
        return messages

    head = messages[:2]
    tail = messages[-KEEP_RECENT_TURNS:]
    middle = messages[2:-KEEP_RECENT_TURNS]

    # IMPORTANT: an "tool" message at the start of tail would be orphaned
    # because its matching assistant tool_call is about to be summarized away.
    # Drop those leading tool messages — the API rejects orphan tool replies.
    while tail and tail[0]["role"] == "tool":
        tail = tail[1:]

    if not middle:
        return messages

    obs.banner(f"compacting {len(middle)} msgs (~{tokens} tok → summary)")

    transcript = _render(middle)
    response = client.chat.completions.create(
        model=VLLM_MODEL_NAME,
        messages=[
            {"role": "system", "content": (
                "You compact agent conversation history. Summarize the transcript "
                "below in under 200 words as terse bullets. Focus on: facts gathered, "
                "files read with key findings, decisions made, current task progress. "
                "Do not invent details."
            )},
            {"role": "user", "content": transcript},
        ],
        temperature=0.0,
    )
    summary = response.choices[0].message.content or "(empty summary)"

    summary_msg = {
        "role": "assistant",
        "content": f"[earlier turns compacted]\n{summary}",
    }
    return head + [summary_msg] + tail


def _render(messages: list[dict]) -> str:
    """Flatten messages into a plain transcript for the summarizer to read."""
    lines = []
    for m in messages:
        role = m["role"]
        if role == "tool":
            lines.append(f"[tool result] {m.get('content', '')}")
        elif role == "assistant":
            for tc in m.get("tool_calls", []) or []:
                lines.append(
                    f"[assistant calls] {tc['function']['name']}({tc['function']['arguments']})"
                )
            if m.get("content"):
                lines.append(f"[assistant] {m['content']}")
        else:
            lines.append(f"[{role}] {m.get('content', '')}")
    return "\n".join(lines)
