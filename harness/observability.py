"""Lightweight tracing — prints a structured view of what the loop is doing.

Real harnesses log to JSON files or send to a tracing backend (OpenTelemetry,
Langfuse, Helicone). This is the educational version: stdout, color-free,
human-readable.
"""
import json


def banner(title: str) -> None:
    line = "─" * 6
    print(f"\n{line} {title} {'─' * max(2, 60 - len(title))}")


def turn(iteration: int) -> None:
    print(f"\n╭── iteration {iteration} ──")


def assistant_text(text: str) -> None:
    if text and text.strip():
        print(f"│ [assistant] {text}")


def tool_call(name: str, args: dict) -> None:
    print(f"│ [tool→]    {name}({json.dumps(args)})")


def tool_result(name: str, result: str, max_len: int = 240) -> None:
    snippet = result if len(result) <= max_len else result[:max_len] + f"... [{len(result)} chars total]"
    indented = snippet.replace("\n", "\n│             ")
    print(f"│ [←result]  {name}: {indented}")


def usage(prompt_tokens: int, completion_tokens: int) -> None:
    print(f"│ [usage]    prompt={prompt_tokens} completion={completion_tokens}")


def final(text: str) -> None:
    banner("final answer")
    print(text or "(empty)")
