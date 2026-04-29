"""Pipeline mode — single-shot LLM calls with structured output.

A pipeline is a named LLM chain that takes a prompt/file and returns a
Pydantic model (JSON). Unlike the full agent, pipelines:
  - Have no tools (no tool calls).
  - Return structured JSON, not free-form text.
  - Are exposed as POST /api/{name} by harness/api.py automatically.

Usage:
    @register_pipeline(
        name="summarize_text",
        description="Return a JSON summary of the provided text.",
        input_model=SummarizeInput,
        output_model=SummarizeOutput,
    )
    async def pipeline_summarize(data: SummarizeInput) -> SummarizeOutput:
        ...  # implemented via make_pipeline() below

Registration:
    Pipelines are auto-discovered from harness/pipelines.py and skills/*/pipelines.py
    (not yet implemented — T2.2 scope is harness-level only).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Type

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel

from harness.llm import make_llm


@dataclass
class Pipeline:
    name: str
    description: str
    system_prompt: str
    input_model: Type[BaseModel]
    output_model: Type[BaseModel]


PIPELINES: dict[str, Pipeline] = {}


def register_pipeline(
    name: str,
    description: str,
    system_prompt: str,
    input_model: Type[BaseModel],
    output_model: Type[BaseModel],
) -> Pipeline:
    """Register a pipeline and return the Pipeline object."""
    p = Pipeline(
        name=name,
        description=description,
        system_prompt=system_prompt,
        input_model=input_model,
        output_model=output_model,
    )
    PIPELINES[name] = p
    return p


def make_pipeline(pipeline: Pipeline):
    """Build a LangChain chain for the pipeline using structured output.

    Pipelines force `enable_thinking=False` regardless of global setting:
    structured output already constrains the model and reasoning tokens
    would just inflate latency without helping.
    """
    llm = make_llm(enable_thinking=False)
    prompt = ChatPromptTemplate.from_messages([
        ("system", pipeline.system_prompt),
        ("human", "{input}"),
    ])
    return prompt | llm.with_structured_output(pipeline.output_model)


async def run_pipeline(name: str, data: dict[str, Any]) -> dict[str, Any]:
    """Run a registered pipeline with raw dict input. Returns dict output."""
    pipeline = PIPELINES.get(name)
    if pipeline is None:
        raise KeyError(f"Pipeline {name!r} not found")

    input_obj = pipeline.input_model(**data)
    chain = make_pipeline(pipeline)
    result = await chain.ainvoke({"input": input_obj.model_dump_json()})
    if isinstance(result, BaseModel):
        return result.model_dump()
    return result


# ---------------------------------------------------------------------------
# Built-in example pipeline: text summarization
# ---------------------------------------------------------------------------

class SummarizeInput(BaseModel):
    text: str
    language: str = "Vietnamese"


class SummarizeOutput(BaseModel):
    title: str
    summary: str
    key_points: list[str]
    word_count: int


register_pipeline(
    name="summarize_text",
    description="Summarize text into a structured JSON report.",
    system_prompt=(
        "You are a summarization assistant. Given a text, return a structured "
        "summary with a title, a 2-3 sentence summary, key points, and word count. "
        "Respond in {language} unless instructed otherwise."
    ),
    input_model=SummarizeInput,
    output_model=SummarizeOutput,
)
