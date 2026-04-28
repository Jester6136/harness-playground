"""Structured JSON logging configuration.

Call setup_logging() once at app startup (main.py / api.py lifespan).

All tool calls are logged automatically via the @log_tool_call decorator.
LLM token usage is tracked via LangChain callback (LLMUsageCallback).

Logs go to:
  - stdout (always)
  - logs/harness.json (if LOG_FILE env var is set, default: logs/harness.json)

Set LOG_LEVEL env var to control verbosity (default: INFO).
Set LANGSMITH_TRACING=true to additionally send traces to LangSmith (opt-in).
"""
from __future__ import annotations

import functools
import logging
import os
import time
from pathlib import Path
from typing import Any, Callable

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FILE = os.getenv("LOG_FILE", "logs/harness.json")


def setup_logging() -> None:
    """Configure root logger with JSON output to stdout + optional file."""
    handlers: list[logging.Handler] = [logging.StreamHandler()]

    log_path = Path(LOG_FILE)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handlers.append(logging.FileHandler(log_path))

    try:
        from pythonjsonlogger import jsonlogger
        formatter = jsonlogger.JsonFormatter(
            fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    except ImportError:
        # Fallback: plain text if python-json-logger not installed.
        formatter = logging.Formatter(
            fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )

    for h in handlers:
        h.setFormatter(formatter)

    logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO), handlers=handlers)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def log_tool_call(fn: Callable) -> Callable:
    """Decorator that logs every tool invocation with timing and result size."""
    logger = logging.getLogger("harness.tools")

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        start = time.monotonic()
        tool_name = getattr(fn, "name", fn.__name__)
        try:
            result = fn(*args, **kwargs)
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.info(
                "tool_call",
                extra={
                    "tool": tool_name,
                    "elapsed_ms": elapsed_ms,
                    "result_len": len(str(result)) if result else 0,
                    "success": True,
                },
            )
            return result
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.error(
                "tool_error",
                extra={
                    "tool": tool_name,
                    "elapsed_ms": elapsed_ms,
                    "error": str(exc),
                    "success": False,
                },
            )
            raise

    return wrapper


class LLMUsageCallback:
    """LangChain callback handler that logs token usage per LLM call."""

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        logger = logging.getLogger("harness.llm")
        try:
            usage = response.llm_output.get("token_usage", {}) if response.llm_output else {}
            logger.info(
                "llm_usage",
                extra={
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0),
                },
            )
        except Exception:
            pass

    # Required by LangChain callback protocol but unused.
    def on_llm_start(self, *args, **kwargs): pass
    def on_llm_error(self, *args, **kwargs): pass
    def on_chain_start(self, *args, **kwargs): pass
    def on_chain_end(self, *args, **kwargs): pass
    def on_chain_error(self, *args, **kwargs): pass
    def on_tool_start(self, *args, **kwargs): pass
    def on_tool_end(self, *args, **kwargs): pass
    def on_tool_error(self, *args, **kwargs): pass
