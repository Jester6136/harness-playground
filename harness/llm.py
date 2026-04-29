"""LLM client factory — single place that knows how to talk to vLLM.

Centralises the `extra_body` plumbing for reasoning ("thinking") so every
callsite (agent, pipelines, vision tool) gets the same behavior.
"""
from __future__ import annotations

from langchain_openai import ChatOpenAI

from harness.config import (
    TEMPERATURE,
    VLLM_API_KEY,
    VLLM_BASE_URL,
    VLLM_MODEL_NAME,
    settings,
)


def make_llm(
    enable_thinking: bool | None = None,
    temperature: float | None = None,
) -> ChatOpenAI:
    """Build a ChatOpenAI client pointed at vLLM.

    If `enable_thinking` is None, the value of `settings.enable_thinking`
    is used. When True, the request includes `chat_template_kwargs.enable_thinking`
    via OpenAI extra_body — the served model exposes reasoning tokens that
    LangChain surfaces in `AIMessageChunk.additional_kwargs.reasoning_content`.
    """
    thinking = settings.enable_thinking if enable_thinking is None else enable_thinking
    kwargs: dict = {}
    if thinking:
        kwargs["extra_body"] = {"chat_template_kwargs": {"enable_thinking": True}}
    return ChatOpenAI(
        base_url=VLLM_BASE_URL,
        api_key=VLLM_API_KEY,
        model=VLLM_MODEL_NAME,
        temperature=TEMPERATURE if temperature is None else temperature,
        **kwargs,
    )
