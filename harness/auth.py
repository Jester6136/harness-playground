"""Login + accounts (in-process; no separate gateway).

One harness process serves many accounts. Each account record carries its
own per-tenant config (collection / prefix / DataLens chatbot code, …) so
the active :mod:`harness.tenant` resolves to the logged-in account's values.

Account doc (Mongo, ``AUTH_USERS_COLLECTION``)::

    { _id: <username>,
      password: "scrypt$N$r$p$salt$hash",
      config:   {ttcp_collection, ttcp_prefix, datalens_chatbot_code, ...},
      label:    <free-form display name, optional>,
      disabled: <bool, optional> }

Stdlib only — ``hashlib.scrypt`` + ``hmac``; no extra dependency.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
import time
from dataclasses import dataclass

from pymongo import MongoClient

from harness.config import settings
from harness.tenant import Tenant

log = logging.getLogger(__name__)

# ── config (env-driven; AUTH_* preferred, GATEWAY_* kept as back-compat) ────

def _env(name: str, *fallbacks: str, default: str = "") -> str:
    for n in (name, *fallbacks):
        v = os.getenv(n)
        if v is not None and v != "":
            return v
    return default


AUTH_MONGO_URI = _env(
    "AUTH_MONGO_URI", "GATEWAY_MONGO_URI",
    default=settings.mongo_uri,
)
AUTH_MONGO_DB = _env(
    "AUTH_MONGO_DB", "GATEWAY_MONGO_DB",
    default=settings.mongo_db_name,
)
AUTH_USERS_COLLECTION = _env(
    "AUTH_USERS_COLLECTION", "GATEWAY_USERS_COLLECTION",
    default="accounts",
)

AUTH_SECRET = _env("AUTH_SECRET", "GATEWAY_SECRET")
if not AUTH_SECRET:
    AUTH_SECRET = secrets.token_hex(32)
    _SECRET_EPHEMERAL = True
else:
    _SECRET_EPHEMERAL = False

SESSION_TTL = int(_env("AUTH_SESSION_TTL", "GATEWAY_SESSION_TTL", default=str(12 * 3600)))
COOKIE_NAME = _env("AUTH_COOKIE_NAME", "GATEWAY_COOKIE_NAME", default="hp_session")
COOKIE_SECURE = _env(
    "AUTH_COOKIE_SECURE", "GATEWAY_COOKIE_SECURE", default="false",
).strip().lower() == "true"

# Bootstrap account — created on first startup if the accounts collection is
# empty. With empty `config`, it inherits the process env (so a fresh install
# works out of the box; the operator can change password + add real accounts
# later via `python -m harness.useradd`).
BOOTSTRAP_USER = _env("AUTH_BOOTSTRAP_USER", default="bags")
BOOTSTRAP_PASSWORD = _env("AUTH_BOOTSTRAP_PASSWORD", default="bags111")

# scrypt parameters (OWASP-ish; tunable for slow boxes).
_SCRYPT_N = int(_env("AUTH_SCRYPT_N", default=str(2**14)))
_SCRYPT_R = int(_env("AUTH_SCRYPT_R", default="8"))
_SCRYPT_P = int(_env("AUTH_SCRYPT_P", default="1"))


# ── password hashing ────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Return ``scrypt$N$r$p$salt_hex$hash_hex`` (self-describing)."""
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(
        password.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P,
        dklen=32, maxmem=0,
    )
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Constant-time verify against a ``hash_password`` string."""
    try:
        algo, n, r, p, salt_hex, hash_hex = stored.split("$")
        if algo != "scrypt":
            return False
        dk = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt_hex),
            n=int(n), r=int(r), p=int(p),
            dklen=len(bytes.fromhex(hash_hex)),
            maxmem=0,
        )
        return hmac.compare_digest(dk, bytes.fromhex(hash_hex))
    except (ValueError, TypeError):
        return False


# ── signed session token ────────────────────────────────────────────────────
# Payload: "username|exp_ts" (config travels with the account doc, NOT the
# cookie — operators can change an account's profile without revoking the
# cookie). HMAC-SHA256 sig appended after a '.'.

def _sign(payload: str) -> str:
    return hmac.new(
        AUTH_SECRET.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()


def make_session(username: str, ttl: int = SESSION_TTL) -> str:
    exp = int(time.time()) + ttl
    payload = f"{username}|{exp}"
    return f"{payload}.{_sign(payload)}"


@dataclass
class Session:
    username: str
    exp: int


def read_session(token: str | None) -> Session | None:
    """Verify signature + expiry. Returns None if missing/invalid/expired."""
    if not token or "." not in token:
        return None
    payload, _, sig = token.rpartition(".")
    if not hmac.compare_digest(sig, _sign(payload)):
        return None
    parts = payload.split("|")
    if len(parts) != 2:
        return None
    username, exp_s = parts
    try:
        exp = int(exp_s)
    except ValueError:
        return None
    if exp < int(time.time()):
        return None
    return Session(username=username, exp=exp)


# ── Mongo account store ─────────────────────────────────────────────────────

_client: MongoClient | None = None


def _users():
    global _client
    if _client is None:
        _client = MongoClient(AUTH_MONGO_URI, serverSelectionTimeoutMS=5000)
    return _client[AUTH_MONGO_DB][AUTH_USERS_COLLECTION]


def get_account(username: str) -> dict | None:
    """Return the raw account doc, or None."""
    return _users().find_one({"_id": username})


def authenticate(username: str, password: str) -> dict | None:
    """Return the account doc on success (caller resolves the tenant), or None."""
    doc = get_account(username)
    if not doc or doc.get("disabled"):
        return None
    if not verify_password(password, doc.get("password", "")):
        return None
    return doc


def upsert_user(
    username: str, password: str, config: dict | None = None,
    label: str = "",
) -> None:
    """Create/replace an account (used by the useradd CLI)."""
    if "|" in username:
        raise ValueError("username must not contain '|'")
    _users().update_one(
        {"_id": username},
        {"$set": {
            "password": hash_password(password),
            "config": config or {},
            "label": label,
            "disabled": False,
        }},
        upsert=True,
    )


def tenant_for_account(account: dict) -> Tenant:
    """Build the active :class:`Tenant` from an account doc."""
    return Tenant.from_config(account.get("config") or {})


# ── default account bootstrap ───────────────────────────────────────────────

def bootstrap_default_account() -> None:
    """Create the default account on first startup so a fresh install is
    usable immediately. No-op once at least one account exists."""
    coll = _users()
    if coll.count_documents({}, limit=1) > 0:
        return
    upsert_user(
        BOOTSTRAP_USER, BOOTSTRAP_PASSWORD,
        config={},  # empty → falls back to env defaults
        label="default (bootstrap)",
    )
    log.warning(
        "auth: bootstrapped default account '%s' — CHANGE THE PASSWORD "
        "in production (`python -m harness.useradd %s <newprofile> "
        "--password ...`).",
        BOOTSTRAP_USER, BOOTSTRAP_USER,
    )
