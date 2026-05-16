"""Chat streaming + interrupt resume endpoints."""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Request
from langgraph.types import Command
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from harness.api.deps import get_user
from harness.api.streaming import event_stream
from harness.extensions.commands import dispatch, parse_command
from harness.persistence.checkpoints import delete_session, thread_id
from harness.persistence.session_titles import (
    delete_title,
    set_title_if_missing,
    touch,
)


def _derive_title(msg: str) -> str:
    """Một-dòng, ≤60 ký tự, bỏ tiền tố ``[Attached file at: ...]`` UI nhét vào."""
    if not msg:
        return ""
    if msg.startswith("[Attached file at:") and "]" in msg:
        msg = msg.split("]", 1)[1]
    msg = msg.strip()
    if not msg:
        return ""
    first_line = msg.splitlines()[0].strip()
    return first_line if len(first_line) <= 60 else first_line[:57].rstrip() + "…"

router = APIRouter()


class ChatRequest(BaseModel):
    session_id: str = "main"
    message: str


class ResumeRequest(BaseModel):
    resume: str  # "approve" or "deny"


@router.post("/chat/stream")
async def chat_stream(
    body: ChatRequest,
    request: Request,
    user: str = Depends(get_user),
):
    agent = request.app.state.agent
    tid = thread_id(user, body.session_id)
    config = {"configurable": {"thread_id": tid}}

    parsed = parse_command(body.message)
    if parsed:
        cmd, args = parsed
        handler_type, result = await dispatch(cmd, args)

        async def generate_cmd():
            if handler_type == "clear":
                delete_session(user, body.session_id)
                delete_title(tid)
                yield {"event": "message", "data": json.dumps({"type": "ai", "content": result})}
                yield {"event": "session_cleared", "data": json.dumps({"session_id": body.session_id})}
                yield {"event": "done", "data": "{}"}
            elif handler_type == "direct":
                yield {"event": "message", "data": json.dumps({"type": "ai", "content": result})}
                yield {"event": "done", "data": "{}"}
            else:
                # "agent" — treat result as the prompt; fall through to agent stream.
                prior = await agent.aget_state(config)
                seen = len(prior.values.get("messages", [])) if prior.values else 0
                inputs = {"messages": [{"role": "user", "content": result}]}
                is_new = seen == 0
                touch(tid)
                async for event in event_stream(agent, inputs, config, seen):
                    yield event
                if is_new:
                    set_title_if_missing(tid, _derive_title(result))

        return EventSourceResponse(generate_cmd())

    prior = await agent.aget_state(config)
    seen = len(prior.values.get("messages", [])) if prior.values else 0
    inputs = {"messages": [{"role": "user", "content": body.message}]}
    is_new = seen == 0
    touch(tid)  # bump "last active" → sidebar đẩy phiên này lên đầu

    async def generate():
        async for event in event_stream(agent, inputs, config, seen):
            yield event
        if is_new:
            # Tin nhắn đầu của phiên này → tự sinh title (nếu chưa có).
            set_title_if_missing(tid, _derive_title(body.message))

    return EventSourceResponse(generate())


async def _build_resume_command(agent, config: dict, decision: str) -> Command:
    """Convert 'approve'/'deny' to deepagents decisions dict when needed.

    deepagents' HumanInTheLoopMiddleware expects:
        {"decisions": [{"type": "approve"}, ...]}   (one entry per action_request)
    Plain string resume is used as fallback for non-deepagents interrupts.
    """
    state = await agent.aget_state(config)
    for task in getattr(state, "tasks", []) or []:
        for intr in getattr(task, "interrupts", []) or []:
            val: Any = getattr(intr, "value", None)
            if isinstance(val, dict) and "action_requests" in val:
                dtype = "approve" if decision == "approve" else "reject"
                decisions = [
                    {"type": "approve"} if dtype == "approve"
                    else {"type": "reject", "message": "Denied by user"}
                    for _ in val["action_requests"]
                ]
                return Command(resume={"decisions": decisions})
    return Command(resume=decision)


@router.post("/threads/{raw_thread_id:path}/runs/resume")
async def resume(
    raw_thread_id: str,
    body: ResumeRequest,
    request: Request,
    _user: str = Depends(get_user),  # auth + bind tenant for resumed tool runs
):
    """Resume an interrupted run. raw_thread_id = '{user}:{session}'."""
    agent = request.app.state.agent
    config = {"configurable": {"thread_id": raw_thread_id}}

    async def generate():
        prior = await agent.aget_state(config)
        seen = len(prior.values.get("messages", [])) if prior.values else 0
        cmd = await _build_resume_command(agent, config, body.resume)
        async for event in event_stream(agent, cmd, config, seen):
            yield event

    return EventSourceResponse(generate())
