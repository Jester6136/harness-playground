"""Thread (session) admin endpoints — list, fetch messages, delete."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from harness.api.deps import get_user
from harness.persistence.checkpoints import delete_session, list_sessions, thread_id

router = APIRouter()


@router.get("/threads/{user_id}")
async def get_sessions(user_id: str, _user: str = Depends(get_user)):
    return {"sessions": list_sessions(user_id)}


@router.get("/threads/{user_id}/{session_id}/messages")
async def get_messages(
    user_id: str,
    session_id: str,
    request: Request,
    _user: str = Depends(get_user),
):
    agent = request.app.state.agent
    tid = thread_id(user_id, session_id)
    config = {"configurable": {"thread_id": tid}}
    state = await agent.aget_state(config)
    msgs = []
    for msg in (state.values.get("messages", []) if state.values else []):
        msgs.append({
            "type": getattr(msg, "type", "unknown"),
            "content": getattr(msg, "content", ""),
            "name": getattr(msg, "name", None),
        })
    return {"messages": msgs}


@router.delete("/threads/{user_id}/{session_id}")
async def delete_session_endpoint(
    user_id: str,
    session_id: str,
    _user: str = Depends(get_user),
):
    delete_session(user_id, session_id)
    return {"deleted": True}
