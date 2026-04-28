"""Eval framework — run YAML test cases against the agent and report results.

Usage:
    python -m harness.eval                 # run all cases in evals/
    python -m harness.eval --filter smoke  # filter by name substring
    python -m harness.eval --json          # output JSON report

Each YAML file in evals/ defines one or more cases:

    - name: basic_hello
      input: "say hello"
      expected:
        contains: "hello"          # case-insensitive substring match
        # OR:
        # regex: "hel+o"           # regex search
        # tool_called: read_file   # assert a specific tool was called

    - name: list_dir_works
      input: "list files in current directory"
      expected:
        tool_called: list_dir

Cases run against a stateless agent (no checkpointer) to avoid state bleed.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import time
from pathlib import Path
from typing import Any

import yaml

from harness.agent import make_agent

EVALS_DIR = Path(__file__).resolve().parent.parent / "evals"


def _load_cases() -> list[dict]:
    cases = []
    if not EVALS_DIR.exists():
        return cases
    for path in sorted(EVALS_DIR.glob("*.yaml")):
        docs = yaml.safe_load_all(path.read_text())
        for doc in docs:
            if isinstance(doc, list):
                cases.extend(doc)
            elif isinstance(doc, dict):
                cases.append(doc)
    return cases


async def _run_case(agent, case: dict) -> dict:
    """Run one test case. Returns result dict with pass/fail + details."""
    name = case.get("name", "unnamed")
    prompt = case.get("input", "")
    expected = case.get("expected", {})

    start = time.monotonic()
    messages = []
    tool_calls_seen = []

    try:
        async for chunk in agent.astream(
            {"messages": [{"role": "user", "content": prompt}]},
            stream_mode="values",
        ):
            if "__interrupt__" in chunk:
                break
            msgs = chunk.get("messages", [])
            messages = msgs

        elapsed_ms = int((time.monotonic() - start) * 1000)

        # Collect AI content and tool calls from messages.
        ai_content = ""
        for msg in messages:
            t = getattr(msg, "type", "")
            if t == "ai":
                ai_content += getattr(msg, "content", "") or ""
                for tc in getattr(msg, "tool_calls", []) or []:
                    tool_calls_seen.append(tc["name"])

        # Evaluate expectations.
        passed = True
        failures = []

        if "contains" in expected:
            needle = expected["contains"].lower()
            if needle not in ai_content.lower():
                passed = False
                failures.append(f"expected content to contain {needle!r}")

        if "regex" in expected:
            if not re.search(expected["regex"], ai_content, re.IGNORECASE):
                passed = False
                failures.append(f"expected content to match regex {expected['regex']!r}")

        if "tool_called" in expected:
            tool = expected["tool_called"]
            if tool not in tool_calls_seen:
                passed = False
                failures.append(f"expected tool {tool!r} to be called (got {tool_calls_seen})")

        return {
            "name": name,
            "passed": passed,
            "elapsed_ms": elapsed_ms,
            "failures": failures,
            "ai_content_snippet": ai_content[:200],
            "tools_called": tool_calls_seen,
        }

    except Exception as exc:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return {
            "name": name,
            "passed": False,
            "elapsed_ms": elapsed_ms,
            "failures": [f"exception: {exc}"],
            "ai_content_snippet": "",
            "tools_called": [],
        }


async def run_evals(filter_str: str | None = None) -> list[dict]:
    cases = _load_cases()
    if filter_str:
        cases = [c for c in cases if filter_str.lower() in c.get("name", "").lower()]

    agent = make_agent()  # stateless — no checkpointer

    results = []
    for case in cases:
        result = await _run_case(agent, case)
        results.append(result)
        status = "PASS" if result["passed"] else "FAIL"
        print(f"  [{status}] {result['name']} ({result['elapsed_ms']}ms)")
        for f in result["failures"]:
            print(f"         → {f}")

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Run harness evals")
    parser.add_argument("--filter", help="Filter cases by name substring")
    parser.add_argument("--json", action="store_true", help="Output JSON report")
    args = parser.parse_args()

    results = asyncio.run(run_evals(args.filter))

    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    print(f"\n{passed}/{total} passed")

    if args.json:
        print(json.dumps(results, indent=2))

    if passed < total:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
