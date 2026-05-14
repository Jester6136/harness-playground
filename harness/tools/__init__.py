"""Custom tools that complement the deepagents built-ins.

We only add tools deepagents doesn't already provide:

  - analyze_image        (vision model handoff for images / PDFs)
  - extract_ttcp         (structured-JSON extraction for Vietnamese kết luận thanh tra)
  - save_ttcp / find_ttcp / search_ttcp / list_ttcp / count_ttcp /
    aggregate_ttcp / update_ttcp / delete_ttcp
                         (Mongo CRUD + full-text + group-by aggregation for TTCP;
                          writes are HITL-gated)
  - search_internal_docs (DataLens ReAct retriever over internal KB)
"""
from harness.tools.search_docs import search_internal_docs
from harness.tools.ttcp_db import (
    aggregate_ttcp,
    count_ttcp,
    delete_ttcp,
    find_ttcp,
    list_ttcp,
    save_ttcp,
    search_ttcp,
    update_ttcp,
)
from harness.tools.vision import analyze_image, extract_ttcp

ALL_TOOLS = [
    analyze_image,
    extract_ttcp,
    save_ttcp,
    find_ttcp,
    search_ttcp,
    list_ttcp,
    count_ttcp,
    aggregate_ttcp,
    update_ttcp,
    delete_ttcp,
    search_internal_docs,
]

__all__ = [
    "ALL_TOOLS",
    "analyze_image",
    "extract_ttcp",
    "save_ttcp",
    "find_ttcp",
    "search_ttcp",
    "list_ttcp",
    "count_ttcp",
    "aggregate_ttcp",
    "update_ttcp",
    "delete_ttcp",
    "search_internal_docs",
]
