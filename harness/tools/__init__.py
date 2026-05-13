"""Custom tools that complement the deepagents built-ins.

We only add tools deepagents doesn't already provide:

  - analyze_image        (vision model handoff for images / PDFs)
  - extract_gcn          (structured-JSON extraction for Vietnamese GCN docs)
  - save_gcn / find_gcn / search_gcn / update_gcn / delete_gcn
                         (MongoDB CRUD + full-text search for GCN; writes are HITL-gated)
  - search_internal_docs (DataLens ReAct retriever over internal KB)
  - remember_about_user  (persist a fact in long-term Postgres store)
  - recall_user_context  (read all remembered facts)
"""
from harness.tools.gcn_db import (
    delete_gcn,
    find_gcn,
    save_gcn,
    search_gcn,
    update_gcn,
)
from harness.tools.memory import recall_user_context, remember_about_user
from harness.tools.search_docs import search_internal_docs
from harness.tools.vision import analyze_image, extract_gcn

ALL_TOOLS = [
    analyze_image,
    extract_gcn,
    save_gcn,
    find_gcn,
    search_gcn,
    update_gcn,
    delete_gcn,
    search_internal_docs,
    remember_about_user,
    recall_user_context,
]

__all__ = [
    "ALL_TOOLS",
    "analyze_image",
    "extract_gcn",
    "save_gcn",
    "find_gcn",
    "search_gcn",
    "update_gcn",
    "delete_gcn",
    "search_internal_docs",
    "remember_about_user",
    "recall_user_context",
]
