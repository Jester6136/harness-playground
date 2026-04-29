"""SSE event generator — translates LangGraph dual-stream into SSE dicts."""
from __future__ import annotations

import json
from typing import Any, AsyncGenerator

from langgraph.types import Command


async def event_stream(
    agent,
    inputs: dict | Command,
    config: dict,
    seen: int,
) -> AsyncGenerator[dict, None]:
    """Yield SSE dicts using dual stream_mode=['messages','values'].

    'messages' mode gives AIMessageChunks for token-by-token streaming.
    'values' mode gives full state snapshots for tool_call/tool_result/interrupt detection.
    """
    current_input = inputs
    while True:
        interrupt_payloads: list[Any] = []
        async for mode, data in agent.astream(
            current_input, config=config, stream_mode=["messages", "values"]
        ):
            if mode == "messages":
                msg, _meta = data
                if getattr(msg, "type", "") == "AIMessageChunk":
                    content = getattr(msg, "content", "") or ""
                    if content:
                        yield {"event": "token", "data": json.dumps({"content": content})}

            elif mode == "values":
                if "__interrupt__" in data:
                    interrupt_payloads = data["__interrupt__"]
                    break
                msgs = data.get("messages", [])
                for msg in msgs[seen:]:
                    t = getattr(msg, "type", "")
                    if t == "ai":
                        for tc in (getattr(msg, "tool_calls", []) or []):
                            yield {
                                "event": "tool_call",
                                "data": json.dumps({"tool": tc["name"], "args": tc["args"]}),
                            }
                    elif t == "tool":
                        yield {
                            "event": "tool_result",
                            "data": json.dumps({
                                "tool": getattr(msg, "name", "?"),
                                "content": getattr(msg, "content", "") or "",
                            }),
                        }
                seen = len(msgs)

        if not interrupt_payloads:
            break

        for intr in interrupt_payloads:
            val = intr.value if hasattr(intr, "value") else intr
            yield {"event": "interrupt", "data": json.dumps(val)}

        return

    yield {"event": "done", "data": "{}"}
