"""CLI entry point. Run:  python main.py "your task here" """
import sys

from harness import observability as obs
from harness.client import make_client
from harness.loop import run


def main() -> None:
    prompt = " ".join(sys.argv[1:]).strip() or (
        "List the files in the current directory and summarize what this project does."
    )
    obs.banner("user prompt")
    print(prompt)

    client = make_client()
    run(client, prompt)


if __name__ == "__main__":
    main()
