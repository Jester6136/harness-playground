"""Minimal async SSE client over httpx.

Yields `(event_name, data_str)` tuples per SSE chunk. Multi-line `data:`
fields are joined with `\n` per the SSE spec; comments (`:` prefix) and
unrecognised fields are ignored.

We don't pull in `httpx-sse` because the protocol is small and our needs
(POST + iter_lines) are well-served by httpx alone.
"""
from __future__ import annotations

from typing import AsyncIterator

import httpx


async def stream_sse(
    url: str,
    *,
    json: dict,
    headers: dict | None = None,
    timeout: float = 600.0,
) -> AsyncIterator[tuple[str, str]]:
    """POST `json` to `url` and yield (event_name, data) per SSE event.

    Defaults the event name to "message" (per spec) when the server omits the
    `event:` field. The caller is responsible for `json.loads` on `data` and
    for terminating early on `done` / errors — this function only stops when
    the upstream stream closes.
    """
    merged_headers = {"Accept": "text/event-stream", **(headers or {})}

    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream("POST", url, json=json, headers=merged_headers) as resp:
            resp.raise_for_status()

            event_name = "message"
            data_lines: list[str] = []

            async for raw in resp.aiter_lines():
                if raw == "":
                    if data_lines:
                        yield event_name, "\n".join(data_lines)
                    event_name = "message"
                    data_lines = []
                    continue

                if raw.startswith(":"):
                    # Comment / keep-alive ping.
                    continue
                if raw.startswith("event:"):
                    event_name = raw[6:].strip()
                elif raw.startswith("data:"):
                    # Per spec a single leading space after the colon is stripped.
                    data_lines.append(raw[5:].lstrip(" "))
                # id:/retry: ignored — we don't reconnect from a Last-Event-ID yet.

            # Flush any trailing event without a blank line.
            if data_lines:
                yield event_name, "\n".join(data_lines)
