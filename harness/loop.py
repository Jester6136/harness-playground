"""The agentic loop — the heart of the harness.

Pattern (this is "ReAct" implemented over native tool-calling):

    loop until done or max_iterations:
        response = LLM(messages, tools=schemas)
        record assistant message in history
        if model didn't call tools: return final text
        for each tool call:
            check permission
            execute tool
            record result in history (paired with tool_call_id)
"""
import json

from openai import OpenAI

from . import observability as obs
from .config import MAX_ITERATIONS, SYSTEM_PROMPT, TEMPERATURE, VLLM_MODEL_NAME
from .permissions import check as check_permission
from .tools import REGISTRY, schemas


def run(client: OpenAI, user_prompt: str) -> str:
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    tool_schemas = schemas()

    for iteration in range(1, MAX_ITERATIONS + 1):
        obs.turn(iteration)

        response = client.chat.completions.create(
            model=VLLM_MODEL_NAME,
            messages=messages,
            tools=tool_schemas,
            temperature=TEMPERATURE,
        )
        choice = response.choices[0]
        msg = choice.message

        if response.usage:
            obs.usage(response.usage.prompt_tokens, response.usage.completion_tokens)

        # Persist the assistant turn. The tool_calls field MUST be carried over
        # verbatim — the API requires every tool_call to be paired with a tool
        # result in the next user turn, matched by id.
        assistant_entry: dict = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            assistant_entry["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in msg.tool_calls
            ]
        messages.append(assistant_entry)
        obs.assistant_text(msg.content or "")

        # Stop condition: model emitted text but no tool calls → it's done.
        if not msg.tool_calls:
            obs.final(msg.content or "")
            return msg.content or ""

        # Execute each tool call and append a paired tool message.
        for tc in msg.tool_calls:
            result = _execute_one(tc.function.name, tc.function.arguments)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })

    obs.banner("max iterations reached")
    return "ERROR: hit max iterations without finishing"


def _execute_one(name: str, raw_arguments: str) -> str:
    """Run a single tool call. All errors are converted to strings so the
    loop can keep going and the model can recover."""
    try:
        args = json.loads(raw_arguments or "{}")
    except json.JSONDecodeError as e:
        result = f"ERROR: invalid JSON arguments from model: {e}"
        obs.tool_result(name, result)
        return result

    obs.tool_call(name, args)

    tool = REGISTRY.get(name)
    if tool is None:
        result = f"ERROR: unknown tool {name!r}"
        obs.tool_result(name, result)
        return result

    allowed, reason = check_permission(tool, args)
    if not allowed:
        result = f"ERROR: {reason}"
        obs.tool_result(name, result)
        return result

    try:
        result = tool.execute(args)
    except Exception as e:
        result = f"ERROR: {type(e).__name__}: {e}"

    obs.tool_result(name, result)
    return result
