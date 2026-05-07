"""Custom tools that complement the deepagents built-ins.

We only add tools deepagents doesn't already provide:

  - analyze_image        (vision model handoff for images / PDFs)
  - extract_gcn          (structured-JSON extraction for Vietnamese GCN docs)
  - search_internal_docs (DataLens ReAct retriever over internal KB)
  - remember_about_user  (persist a fact in long-term Postgres store)
  - recall_user_context  (read all remembered facts)
"""
from harness.tools.memory import recall_user_context, remember_about_user
from harness.tools.search_docs import search_internal_docs
from harness.tools.vision import analyze_image, extract_gcn

ALL_TOOLS = [
    analyze_image,
    extract_gcn,
    search_internal_docs,
    remember_about_user,
    recall_user_context,
]

__all__ = [
    "ALL_TOOLS",
    "analyze_image",
    "extract_gcn",
    "search_internal_docs",
    "remember_about_user",
    "recall_user_context",
]
