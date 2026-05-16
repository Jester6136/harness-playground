"""Per-request tenant config.

One harness process serves many accounts. The handful of "customizable"
knobs — which Mongo collection, which MinIO prefix, which DataLens chatbot
code, etc. — used to come from the process-global ``settings`` (env). They
now live in the account record (Mongo) and are bound per request by the
auth layer via :func:`use_tenant`.

Tools/persistence read these through the accessors below. When no tenant is
active (CLI, ``ttcp_batch``, Telegram bot — no login) the accessors fall
back to the global ``settings`` env values, so those entrypoints behave
exactly as before. The backbone (agent graph, LLM, tool logic) is untouched.

Concurrency: a ``ContextVar`` is set in the request coroutine before the
agent runs. asyncio copies the context into the tasks LangGraph spawns, and
langchain-core copies it into the executor threads it runs sync tools in —
so a tool reads the right tenant even though one shared agent serves all
accounts.
"""
from __future__ import annotations

import contextlib
from contextvars import ContextVar
from dataclasses import dataclass

from harness.config import settings


@dataclass(frozen=True)
class Tenant:
    """The per-account overrides. Build with :meth:`from_config`."""

    ttcp_collection: str
    ttcp_prefix: str
    datalens_chatbot_code: str
    ttcp_bucket: str
    ttcp_sync_url: str

    @classmethod
    def from_config(cls, cfg: dict | None) -> "Tenant":
        """Build from an account's ``config`` dict; missing keys fall back to
        the global env defaults (so an account only needs to override what
        differs)."""
        cfg = cfg or {}
        return cls(
            ttcp_collection=cfg.get("ttcp_collection") or settings.ttcp_collection,
            ttcp_prefix=cfg.get("ttcp_prefix") or settings.ttcp_prefix,
            datalens_chatbot_code=cfg.get("datalens_chatbot_code")
            or settings.datalens_chatbot_code,
            ttcp_bucket=cfg.get("ttcp_bucket") or settings.ttcp_bucket,
            # sync url: explicit "" in the account disables the webhook for
            # that tenant; absent key → global default.
            ttcp_sync_url=cfg["ttcp_sync_url"]
            if "ttcp_sync_url" in cfg
            else settings.ttcp_sync_url,
        )


def _env_tenant() -> Tenant:
    """The implicit tenant from process env — used when nobody set one."""
    return Tenant.from_config(None)


_active: ContextVar[Tenant | None] = ContextVar("hp_tenant", default=None)


def current() -> Tenant:
    """Active tenant for this request, or the env-derived default."""
    return _active.get() or _env_tenant()


def set_tenant(t: Tenant):
    """Bind a tenant to the current context. Returns the ContextVar token
    (pass to ``reset_tenant`` to restore)."""
    return _active.set(t)


def reset_tenant(token) -> None:
    with contextlib.suppress(ValueError):
        _active.reset(token)


@contextlib.contextmanager
def use_tenant(t: Tenant):
    """Scope a tenant to a block (used by the request middleware)."""
    token = _active.set(t)
    try:
        yield
    finally:
        reset_tenant(token)


# ── accessors (call these instead of settings.<x> at tenant-sensitive sites) ──

def ttcp_collection() -> str:
    return current().ttcp_collection


def ttcp_prefix() -> str:
    return current().ttcp_prefix


def ttcp_bucket() -> str:
    return current().ttcp_bucket


def datalens_chatbot_code() -> str:
    return current().datalens_chatbot_code


def ttcp_sync_url() -> str:
    return current().ttcp_sync_url
