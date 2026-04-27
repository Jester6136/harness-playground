"""Thin wrapper around the OpenAI SDK pointed at our vLLM server.

We isolate this so the rest of the code never imports `openai` directly —
swap providers (Anthropic, Ollama, llama.cpp) by changing this one file.
"""
from openai import OpenAI

from .config import VLLM_API_KEY, VLLM_BASE_URL


def make_client() -> OpenAI:
    return OpenAI(base_url=VLLM_BASE_URL, api_key=VLLM_API_KEY)
