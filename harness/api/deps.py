"""Shared FastAPI dependencies."""
from __future__ import annotations

from fastapi import Header, HTTPException, Request


def get_user(x_user_id: str | None = Header(default=None)) -> str:
    """Extract the user id from the X-User-Id header.

    Auth/JWT verification is assumed to happen upstream (gateway/proxy);
    we trust the header value and only require it to be present.
    """
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-Id header required")
    return x_user_id


def get_agent(request: Request):
    """Pull the shared agent from app.state (initialized by lifespan)."""
    return request.app.state.agent
