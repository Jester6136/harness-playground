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
import time
from pathlib import Path
from typing import Any, Callable

from harness.config import settings

LOG_LEVEL = settings.log_level.upper()
LOG_FILE = settings.log_file


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
    """Decorator that logs every tool invocation with timing and result size.

    At DEBUG level also logs the full result content (formatter output) so you
    can compare it against what the sub-agent LLM eventually generates.
    """
    logger = logging.getLogger("harness.tools")

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        start = time.monotonic()
        tool_name = getattr(fn, "name", fn.__name__)
        try:
            result = fn(*args, **kwargs)
            elapsed_ms = int((time.monotonic() - start) * 1000)
            extra: dict = {
                "tool": tool_name,
                "elapsed_ms": elapsed_ms,
                "result_len": len(str(result)) if result else 0,
                "success": True,
            }
            if logger.isEnabledFor(logging.DEBUG) and result:
                extra["result_content"] = str(result)[:2000]
            logger.info("tool_call", extra=extra)
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


class FlowTraceCallback:
    """LangChain callback that traces the full agent flow at DEBUG level.

    Shows each LLM call's input messages and generated output — the key
    insight is comparing ToolMessage content (formatter output) against the
    AIMessage the sub-agent LLM generates right after.

    Enable: set LOG_LEVEL=DEBUG (or LOG_LEVEL=debug in .env).

    Log fields:
      harness.trace / llm_input_msg  — each message fed into one LLM call
      harness.trace / llm_output     — what the LLM generated
      harness.trace / tool_start     — tool invocation input (LangChain layer)
      harness.trace / tool_end       — tool invocation output (LangChain layer)
    """

    _logger = logging.getLogger("harness.trace")

    # ------------------------------------------------------------------ #
    # LLM messages in / out
    # ------------------------------------------------------------------ #

    def on_chat_model_start(
        self, serialized: Any, messages: list, **kwargs: Any
    ) -> None:
        if not self._logger.isEnabledFor(logging.DEBUG):
            return
        model_name = (serialized or {}).get("name", "?")
        run_id = str(kwargs.get("run_id", ""))
        for msg_list in messages:
            for msg in msg_list:
                msg_type = type(msg).__name__          # HumanMessage / AIMessage / ToolMessage / SystemMessage
                content = getattr(msg, "content", "") or ""
                tool_name = getattr(msg, "name", "") or ""
                tool_calls = [
                    tc.get("name") for tc in (getattr(msg, "tool_calls", []) or [])
                ]
                self._logger.debug(
                    "llm_input_msg",
                    extra={
                        "run_id": run_id,
                        "model": model_name,
                        "msg_type": msg_type,
                        "tool_name": tool_name,        # for ToolMessage: which tool produced this
                        "tool_calls": tool_calls,      # for AIMessage: which tools it's calling
                        "content_len": len(content),
                        "content_preview": content[:600],
                    },
                )

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        logger = logging.getLogger("harness.llm")
        # Token usage (same as LLMUsageCallback)
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

        if not self._logger.isEnabledFor(logging.DEBUG):
            return
        run_id = str(kwargs.get("run_id", ""))
        try:
            for gen_list in (response.generations or []):
                for gen in gen_list:
                    msg = getattr(gen, "message", None)
                    content = getattr(msg, "content", "") or "" if msg else ""
                    tool_calls = [
                        tc.get("name") for tc in (getattr(msg, "tool_calls", []) or [])
                    ] if msg else []
                    self._logger.debug(
                        "llm_output",
                        extra={
                            "run_id": run_id,
                            "content_len": len(content),
                            "content_preview": content[:600],
                            "tool_calls": tool_calls,
                        },
                    )
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # Tool start / end (LangChain layer — fires for @tool decorated fns)
    # ------------------------------------------------------------------ #

    def on_tool_start(
        self, serialized: Any, input_str: str, **kwargs: Any
    ) -> None:
        if not self._logger.isEnabledFor(logging.DEBUG):
            return
        self._logger.debug(
            "tool_start",
            extra={
                "tool": (serialized or {}).get("name", "?"),
                "input": str(input_str)[:300],
            },
        )

    def on_tool_end(self, output: Any, **kwargs: Any) -> None:
        if not self._logger.isEnabledFor(logging.DEBUG):
            return
        out_str = str(output) if output is not None else ""
        self._logger.debug(
            "tool_end",
            extra={
                "output_len": len(out_str),
                "output_preview": out_str[:600],
            },
        )

    # ------------------------------------------------------------------ #
    # Required no-ops
    # ------------------------------------------------------------------ #
    def on_llm_start(self, *a, **kw): pass
    def on_llm_error(self, *a, **kw): pass
    def on_chain_start(self, *a, **kw): pass
    def on_chain_end(self, *a, **kw): pass
    def on_chain_error(self, *a, **kw): pass
    def on_tool_error(self, *a, **kw): pass
