"""FastAPI app exposing the agent as a REST + SSE API.

Endpoints (see docs/API.md for full contract):
  POST /chat/stream                              — SSE chat stream
  POST /threads/{thread_id}/runs/resume          — resume after HITL interrupt
  GET  /threads/{user_id}                        — list sessions
  GET  /threads/{user_id}/{session_id}/messages  — message history
  DELETE /threads/{user_id}/{session_id}         — delete a session
  GET  /health                                   — readiness probe
  GET  /commands                                 — slash command metadata
  GET  /pipelines                                — pipeline list
  POST /api/{pipeline_name}                      — run a registered pipeline
  POST /upload                                   — upload an image / PDF
  GET  /ui                                       — single-page demo UI

Auth: pass X-User-Id header (verified upstream by reverse-proxy/gateway).
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from harness.agent import make_agent
from harness.api.chat import router as chat_router
from harness.api.misc import router as misc_router
from harness.api.pipelines import register_pipeline_routes, router as pipelines_router
from harness.api.threads import router as threads_router
from harness.logging_config import setup_logging
from harness.persistence.checkpoints import make_async_checkpointer
from harness.persistence.store import close_store, get_store

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.checkpointer = await make_async_checkpointer()
    app.state.store = await get_store()
    app.state.agent = make_agent(
        checkpointer=app.state.checkpointer,
        store=app.state.store,
    )
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

app.include_router(chat_router)
app.include_router(threads_router)
app.include_router(pipelines_router)
app.include_router(misc_router)

# Pipelines are registered at import time (see harness/extensions/pipelines.py),
# so we can mount their dynamic /api/{name} endpoints right after app creation.
register_pipeline_routes(app)
