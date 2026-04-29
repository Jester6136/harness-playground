"""Bridge async coroutines into sync code (e.g., LangChain @tool functions)."""
from __future__ import annotations

import asyncio
import concurrent.futures
from typing import Coroutine, TypeVar

T = TypeVar("T")


def run_async(coro: Coroutine) -> T:
    """Execute a coroutine from sync code, even when a loop is already running.

    LangChain tool functions are sync, but our memory store is async-only.
    asyncio.run() refuses to start a new loop inside a running one, so we
    delegate to a worker thread in that case.
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        return asyncio.run(coro)

    if loop.is_running():
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    return loop.run_until_complete(coro)
