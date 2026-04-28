"""CLI entry point — streams the agent and prints a structured trace."""
import sys

from harness.agent import make_agent


def _display(msg) -> None:
    """Pretty-print one LangChain message as it streams in."""
    t = getattr(msg, "type", "")
    content = getattr(msg, "content", "") or ""

    if t == "human":
        return  # user prompt was already echoed at the top

    if t == "ai":
        for tc in getattr(msg, "tool_calls", []) or []:
            print(f"  [tool→]    {tc['name']}({tc['args']})")
        if content.strip():
            print(f"  [assistant] {content}")
        return

    if t == "tool":
        snippet = (
            content if len(content) <= 240
            else content[:240] + f"... [{len(content)} chars total]"
        )
        indented = snippet.replace("\n", "\n              ")
        name = getattr(msg, "name", "?")
        print(f"  [←result]  {name}: {indented}")


def main() -> None:
    prompt = " ".join(sys.argv[1:]).strip() or (
        "List the files here and summarize what this project does."
    )
    print(f"\n────── user prompt ──────\n{prompt}\n")

    agent = make_agent()
    inputs = {"messages": [{"role": "user", "content": prompt}]}

    # stream_mode="values" yields the FULL state after each node executes.
    # We track how many messages we've already printed so we only show deltas.
    seen = 0
    for chunk in agent.stream(inputs, stream_mode="values"):
        msgs = chunk.get("messages", [])
        for msg in msgs[seen:]:
            _display(msg)
        seen = len(msgs)


if __name__ == "__main__":
    main()
