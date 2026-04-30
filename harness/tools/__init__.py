"""Custom tools that complement the deepagents built-ins.

deepagents already provides: write_todos, ls, read_file, write_file,
edit_file, glob, grep, execute, task. We only add tools it doesn't have:

  - analyze_image       (vision model handoff for images / PDFs)
  - remember_about_user (persist a fact in long-term Postgres store)
  - recall_user_context (read all remembered facts)
"""
from harness.tools.memory import recall_user_context, remember_about_user
from harness.tools.vision import analyze_image

ALL_TOOLS = [analyze_image, remember_about_user, recall_user_context]

__all__ = [
    "ALL_TOOLS",
    "analyze_image",
    "remember_about_user",
    "recall_user_context",
]
