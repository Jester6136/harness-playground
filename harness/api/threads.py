"""Thread (session) admin endpoints — list, fetch messages, rename, delete."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from harness.api.deps import get_user
from harness.persistence.checkpoints import delete_session, list_sessions, thread_id
from harness.persistence.session_titles import (
    delete_title,
    get_titles_for_user,
    set_title,
)

router = APIRouter()


@router.get("/threads/{user_id}")
async def get_sessions(user_id: str, _user: str = Depends(get_user)):
    """Return the user's sessions, **most-recently-active first**.

    Each entry: ``{id, title, updated_at}``. Sessions that have a title doc
    (touched after this feature shipped) sort first by ``updated_at`` desc;
    legacy sessions without one fall to the bottom, sorted by id (which is
    a base36 timestamp ⇒ rough chronological order anyway).
    """
    ids = list_sessions(user_id)
    titles = get_titles_for_user(user_id)
    rows = []
    for sid in ids:
        meta = titles.get(sid, {})
        rows.append({
            "id": sid,
            "title": meta.get("title") or "",
            "updated_at": meta.get("updated_at"),
        })
    rows.sort(
        key=lambda r: (r["updated_at"] is None, -(r["updated_at"].timestamp() if r["updated_at"] else 0), r["id"]),
    )
    # Keep old field for back-compat with any unseen client.
    return {"sessions": [r["id"] for r in rows], "items": rows}


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
    final_msgs = state.values.get("messages", []) if state.values else []

    # LangChain messages carry no timestamp, but the checkpointer stamps each
    # superstep. Reconstruct per-message time ≈ the checkpoint a message first
    # appeared in (walk history oldest→newest). Failure here just drops times
    # — the UI degrades to no clock rather than erroring.
    first_seen: dict[str, str] = {}
    try:
        snaps = [s async for s in agent.aget_state_history(config)]
        for snap in reversed(snaps):  # oldest first
            ts = getattr(snap, "created_at", None)
            if not ts:
                continue
            for m in (snap.values.get("messages", []) if snap.values else []):
                mid = getattr(m, "id", None)
                if mid and mid not in first_seen:
                    first_seen[mid] = ts
    except Exception:
        first_seen = {}

    msgs = []
    for msg in final_msgs:
        msgs.append({
            "type": getattr(msg, "type", "unknown"),
            "content": getattr(msg, "content", ""),
            "name": getattr(msg, "name", None),
            "ts": first_seen.get(getattr(msg, "id", None)),
        })
    return {"messages": msgs}


class RenameBody(BaseModel):
    title: str


@router.patch("/threads/{user_id}/{session_id}")
async def rename_session(
    user_id: str,
    session_id: str,
    body: RenameBody,
    _user: str = Depends(get_user),
):
    """Rename a session's display title. Does NOT touch the LangGraph thread —
    the session_id stays the same (so message history stays intact)."""
    set_title(thread_id(user_id, session_id), body.title)
    return {"ok": True, "title": body.title.strip()[:120]}


@router.delete("/threads/{user_id}/{session_id}")
async def delete_session_endpoint(
    user_id: str,
    session_id: str,
    _user: str = Depends(get_user),
):
    tid = thread_id(user_id, session_id)
    delete_session(user_id, session_id)
    delete_title(tid)
    return {"deleted": True}
