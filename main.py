"""CLI: per-user, per-session conversational agent.

Examples:
    python main.py "summarize this codebase"                          # default user, default session
    python main.py --user alice --session research "scan for secrets"
    python main.py --user alice --session research "summarize findings"   # remembers prior turn
    python main.py --list-users
    python main.py --list-sessions --user alice
    python main.py --delete-session --user alice --session research
"""
import argparse
import sys

from harness.agent import make_agent
from harness.sessions import (
    delete_session,
    list_sessions,
    list_users,
    make_checkpointer,
    thread_id,
)


def _display(msg) -> None:
    """Pretty-print one LangChain message as it streams in."""
    t = getattr(msg, "type", "")
    content = getattr(msg, "content", "") or ""

    if t == "human":
        return  # we already echoed the user prompt

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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt", nargs="*", help="Message to send")
    parser.add_argument("--user", default="default", help="User id (default: 'default')")
    parser.add_argument("--session", default="main", help="Session id (default: 'main')")
    parser.add_argument("--list-users", action="store_true", help="List all users with stored sessions")
    parser.add_argument("--list-sessions", action="store_true", help="List sessions for --user")
    parser.add_argument("--delete-session", action="store_true", help="Delete --user/--session")
    args = parser.parse_args()

    # Admin paths first — these don't need to spin up the agent.
    if args.list_users:
        users = list_users()
        for u in users:
            print(u)
        if not users:
            print("(no users yet)")
        return

    if args.list_sessions:
        sessions = list_sessions(args.user)
        for s in sessions:
            print(s)
        if not sessions:
            print(f"(no sessions for user {args.user!r})")
        return

    if args.delete_session:
        delete_session(args.user, args.session)
        print(f"deleted {args.user}:{args.session}")
        return

    prompt = " ".join(args.prompt).strip()
    if not prompt:
        parser.print_help()
        sys.exit(1)

    checkpointer = make_checkpointer()
    agent = make_agent(checkpointer=checkpointer)

    config = {"configurable": {"thread_id": thread_id(args.user, args.session)}}

    # Count prior messages so we don't re-display them on resume.
    prior = agent.get_state(config)
    prior_count = len(prior.values.get("messages", [])) if prior.values else 0

    print(
        f"\n────── [{args.user}:{args.session}]"
        f" ({prior_count} prior msgs) ──────"
    )
    print(f"user: {prompt}\n")

    inputs = {"messages": [{"role": "user", "content": prompt}]}
    seen = prior_count

    for chunk in agent.stream(inputs, config=config, stream_mode="values"):
        msgs = chunk.get("messages", [])
        for msg in msgs[seen:]:
            _display(msg)
        seen = len(msgs)


if __name__ == "__main__":
    main()
