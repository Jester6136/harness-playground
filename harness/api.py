"""FastAPI app exposing the agent as a REST + SSE API.

Endpoints:
  POST /chat/stream              — send a message, receive SSE stream
  GET  /threads/{user_id}        — list sessions for a user
  GET  /threads/{user_id}/{session_id}/messages — message history
  DELETE /threads/{user_id}/{session_id}        — delete a session
  POST /threads/{thread_id}/runs/resume         — resume after HITL interrupt
  GET  /health                   — readiness probe
  GET  /commands                 — slash command metadata (T2.1)

SSE event format:
  event: message       data: {"type": "ai", "content": "..."}
  event: tool_call     data: {"tool": "...", "args": {...}}
  event: tool_result   data: {"tool": "...", "content": "..."}
  event: interrupt     data: {"type": "approval", "tool": "...", "args": {...}}
  event: done          data: {}
  event: error         data: {"message": "..."}

Auth: pass X-User-Id header (verified upstream by reverse-proxy/gateway).
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from pathlib import Path

from fastapi import FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from langgraph.types import Command
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from harness.agent import make_agent
from harness.sessions import delete_session, list_sessions, make_async_checkpointer, thread_id

from harness.logging_config import setup_logging
setup_logging()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App lifecycle — one shared async checkpointer for all requests.
# ---------------------------------------------------------------------------

_checkpointer = None
_store = None
_agent = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _checkpointer, _store, _agent
    _checkpointer = await make_async_checkpointer()
    from harness.store import close_store, get_store
    _store = await get_store()
    _agent = make_agent(checkpointer=_checkpointer, store=_store)
    logger.info("Agent ready")
    yield
    await close_store()
    logger.info("Shutting down")


app = FastAPI(title="harness-playground API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _get_user(x_user_id: str | None) -> str:
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-Id header required")
    return x_user_id


# ---------------------------------------------------------------------------
# SSE streaming helper
# ---------------------------------------------------------------------------

async def _event_stream(
    agent,
    inputs: dict | Command,
    config: dict,
    seen: int,
) -> AsyncGenerator[dict, None]:
    """Yield SSE dicts using dual stream_mode=['messages','values'].

    'messages' mode gives AIMessageChunks for token-by-token streaming.
    'values' mode gives full state snapshots for tool_call/tool_result/interrupt detection.
    """
    current_input = inputs
    while True:
        interrupt_payloads: list[Any] = []
        async for mode, data in agent.astream(
            current_input, config=config, stream_mode=["messages", "values"]
        ):
            if mode == "messages":
                msg, _meta = data
                if getattr(msg, "type", "") == "AIMessageChunk":
                    content = getattr(msg, "content", "") or ""
                    if content:
                        yield {"event": "token", "data": json.dumps({"content": content})}

            elif mode == "values":
                if "__interrupt__" in data:
                    interrupt_payloads = data["__interrupt__"]
                    break
                msgs = data.get("messages", [])
                for msg in msgs[seen:]:
                    t = getattr(msg, "type", "")
                    if t == "ai":
                        for tc in (getattr(msg, "tool_calls", []) or []):
                            yield {"event": "tool_call", "data": json.dumps({"tool": tc["name"], "args": tc["args"]})}
                    elif t == "tool":
                        yield {
                            "event": "tool_result",
                            "data": json.dumps({
                                "tool": getattr(msg, "name", "?"),
                                "content": getattr(msg, "content", "") or "",
                            }),
                        }
                seen = len(msgs)

        if not interrupt_payloads:
            break

        for intr in interrupt_payloads:
            val = intr.value if hasattr(intr, "value") else intr
            yield {"event": "interrupt", "data": json.dumps(val)}

        return

    yield {"event": "done", "data": "{}"}


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    session_id: str = "main"
    message: str


class ResumeRequest(BaseModel):
    resume: str  # "approve" or "deny"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    from harness.db import healthcheck
    checks: dict[str, Any] = {"status": "ok"}
    checks["postgres"] = "ok" if await healthcheck() else "error"
    return checks


@app.post("/chat/stream")
async def chat_stream(
    body: ChatRequest,
    x_user_id: str | None = Header(default=None),
):
    user = _get_user(x_user_id)
    tid = thread_id(user, body.session_id)
    config = {"configurable": {"thread_id": tid}}

    # Slash command dispatch.
    from harness.commands import dispatch, parse_command
    parsed = parse_command(body.message)
    if parsed:
        cmd, args = parsed
        handler_type, result = await dispatch(cmd, args)

        async def generate_cmd():
            if handler_type == "direct":
                yield {"event": "message", "data": json.dumps({"type": "ai", "content": result})}
                yield {"event": "done", "data": "{}"}
            else:
                # "agent" — treat result as the prompt; fall through to agent stream.
                prior = await _agent.aget_state(config)
                seen = len(prior.values.get("messages", [])) if prior.values else 0
                inputs = {"messages": [{"role": "user", "content": result}]}
                async for event in _event_stream(_agent, inputs, config, seen):
                    yield event

        return EventSourceResponse(generate_cmd())

    prior = await _agent.aget_state(config)
    seen = len(prior.values.get("messages", [])) if prior.values else 0

    inputs = {"messages": [{"role": "user", "content": body.message}]}

    async def generate():
        async for event in _event_stream(_agent, inputs, config, seen):
            yield event

    return EventSourceResponse(generate())


@app.post("/threads/{raw_thread_id:path}/runs/resume")
async def resume(raw_thread_id: str, body: ResumeRequest):
    """Resume an interrupted run. raw_thread_id = '{user}:{session}'."""
    config = {"configurable": {"thread_id": raw_thread_id}}

    async def generate():
        prior = await _agent.aget_state(config)
        seen = len(prior.values.get("messages", [])) if prior.values else 0
        async for event in _event_stream(_agent, Command(resume=body.resume), config, seen):
            yield event

    return EventSourceResponse(generate())


@app.get("/threads/{user_id}")
async def get_sessions(user_id: str, x_user_id: str | None = Header(default=None)):
    _get_user(x_user_id)
    return {"sessions": list_sessions(user_id)}


@app.get("/threads/{user_id}/{session_id}/messages")
async def get_messages(
    user_id: str,
    session_id: str,
    x_user_id: str | None = Header(default=None),
):
    _get_user(x_user_id)
    tid = thread_id(user_id, session_id)
    config = {"configurable": {"thread_id": tid}}
    state = await _agent.aget_state(config)
    msgs = []
    for msg in (state.values.get("messages", []) if state.values else []):
        msgs.append({
            "type": getattr(msg, "type", "unknown"),
            "content": getattr(msg, "content", ""),
            "name": getattr(msg, "name", None),
        })
    return {"messages": msgs}


@app.delete("/threads/{user_id}/{session_id}")
async def delete_session_endpoint(
    user_id: str,
    session_id: str,
    x_user_id: str | None = Header(default=None),
):
    _get_user(x_user_id)
    delete_session(user_id, session_id)
    return {"deleted": True}


@app.get("/commands")
async def get_commands():
    """Slash command metadata for frontend autocomplete."""
    from harness.commands import COMMANDS
    return {
        "commands": [
            {"name": c.name, "description": c.description, "args": c.args_schema}
            for c in COMMANDS.values()
        ]
    }


@app.get("/pipelines")
async def get_pipelines():
    """List registered pipelines and their input/output schemas."""
    from harness.pipelines import PIPELINES
    result = []
    for p in PIPELINES.values():
        result.append({
            "name": p.name,
            "description": p.description,
            "input_schema": p.input_model.model_json_schema(),
            "output_schema": p.output_model.model_json_schema(),
        })
    return {"pipelines": result}


# Auto-register pipeline endpoints at startup.
# Each pipeline gets POST /api/{name} that accepts its input_model as JSON body.
def _register_pipeline_endpoints() -> None:
    from harness.pipelines import PIPELINES, run_pipeline

    for pipeline_name in list(PIPELINES.keys()):
        # Capture by value in closure.
        name = pipeline_name

        async def pipeline_endpoint(request: Request, _name: str = name):
            body = await request.json()
            try:
                result = await run_pipeline(_name, body)
                return JSONResponse(content=result)
            except KeyError as exc:
                raise HTTPException(status_code=404, detail=str(exc))
            except Exception as exc:
                raise HTTPException(status_code=500, detail=str(exc))

        app.add_api_route(
            f"/api/{name}",
            pipeline_endpoint,
            methods=["POST"],
            name=f"pipeline_{name}",
            summary=PIPELINES[name].description,
        )


_register_pipeline_endpoints()


@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    x_user_id: str | None = Header(default=None),
):
    """Accept a file upload, persist it under ./uploads/, return its path."""
    _get_user(x_user_id)
    uploads_dir = Path(__file__).parent.parent / "uploads"
    uploads_dir.mkdir(exist_ok=True)
    ext = Path(file.filename or "upload").suffix or ".bin"
    fname = f"{uuid.uuid4().hex}{ext}"
    dest = uploads_dir / fname
    dest.write_bytes(await file.read())
    return {"path": str(dest.resolve()), "name": file.filename}


@app.get("/ui", response_class=HTMLResponse, include_in_schema=False)
async def ui():
    p = Path(__file__).parent.parent / "static" / "index.html"
    return HTMLResponse(p.read_text())
