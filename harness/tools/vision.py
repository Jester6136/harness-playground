"""Vision tool: hand off images / PDFs to the VLM."""
from __future__ import annotations

from langchain_core.messages import HumanMessage
from langchain_core.tools import tool

from harness.llm import make_llm
from harness.logging_config import log_tool_call
from harness.multimodal import file_to_contents


@tool
@log_tool_call
def analyze_image(path: str, question: str = "Describe this image in detail.") -> str:
    """Analyze an image or PDF using the vision model.

    Supports JPEG, PNG, GIF, WebP, and PDF (converted to images automatically).
    Returns the model's answer to the question about the file contents.
    """
    contents = file_to_contents(path)
    if not contents:
        return f"ERROR: unsupported or unreadable file: {path}"

    vlm = make_llm()
    msg = HumanMessage(content=[{"type": "text", "text": question}] + contents)
    # Pass callbacks=[] to prevent LangGraph's streaming callbacks from propagating
    # into this inner VLM call — otherwise its tokens bleed into the outer SSE stream.
    response = vlm.invoke([msg], config={"callbacks": []})
    return response.content
