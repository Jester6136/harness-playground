"""Shared FastAPI dependencies."""
from __future__ import annotations

from fastapi import Header, HTTPException, Request

from harness.api.auth import resolve_session_and_bind_tenant


def get_user(
    request: Request,
    x_user_id: str | None = Header(default=None),
) -> str:
    """Authenticate the request and bind the per-account tenant.

    Two paths are accepted (in order of preference):
      1. Browser session cookie — set by ``POST /login``. On success we load
         the account, bind :mod:`harness.tenant` for the request (so tools
         use that account's collection / prefix / DataLens code), and return
         the username as the user id.
      2. ``X-User-Id`` header — kept as a back-compat path for the Telegram
         channel and CLI tools that pre-date the login system. NO tenant is
         bound on this path (tools fall back to env defaults).

    Either is required; otherwise 401.
    """
    user = resolve_session_and_bind_tenant(request)
    if user:
        return user
    if x_user_id:
        return x_user_id
    raise HTTPException(status_code=401, detail="Authentication required")


def get_agent(request: Request):
    """Pull the shared agent from app.state (initialized by lifespan)."""
    return request.app.state.agent
