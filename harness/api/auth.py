"""Login / logout routes + session helpers (in-process auth).

The session cookie is the sole credential carrier. Per-account config lives
in the Mongo account doc (NOT in the cookie) so changing an account's
profile takes effect immediately without revoking sessions.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from harness.auth import (
    COOKIE_NAME,
    COOKIE_SECURE,
    SESSION_TTL,
    authenticate,
    get_account,
    make_session,
    read_session,
    tenant_for_account,
)
from harness.tenant import set_tenant

log = logging.getLogger(__name__)
router = APIRouter()


# ── login page ──────────────────────────────────────────────────────────────

_LOGIN_HTML = """<!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Đăng nhập</title><style>
body{{font-family:'Times New Roman',Times,serif;background:#f1f5f9;display:flex;
min-height:100vh;align-items:center;justify-content:center;margin:0}}
.card{{background:#fff;padding:2.2rem 2.4rem;border-radius:10px;
box-shadow:0 10px 30px rgba(0,0,0,.12);width:340px;border-top:5px solid #a3171e}}
h1{{margin:0 0 1.3rem;font-size:1.25rem;color:#8a1319;text-align:center}}
label{{display:block;font-size:.8rem;font-weight:700;color:#374151;margin:.6rem 0 .25rem}}
input{{width:100%;box-sizing:border-box;padding:.6rem .7rem;border:1px solid #cbd5e1;
border-radius:6px;font-size:.95rem}}
button{{width:100%;margin-top:1.3rem;padding:.65rem;background:#a3171e;color:#fff;
border:0;border-radius:6px;font-weight:700;font-size:.95rem;cursor:pointer}}
button:hover{{background:#8a1319}}.err{{color:#b91c1c;font-size:.82rem;
margin-top:.8rem;text-align:center}}</style></head>
<body><form class="card" method="post" action="/login">
<h1>Hệ thống Tra cứu Thanh tra</h1>
<label>Tài khoản</label>
<input name="username" autocomplete="username" autofocus required>
<label>Mật khẩu</label>
<input name="password" type="password" autocomplete="current-password" required>
<input type="hidden" name="next" value="{next}">
<button type="submit">Đăng nhập</button>{err}</form></body></html>"""


def _login_page(error: str = "", next_url: str = "/ui") -> HTMLResponse:
    err = f'<div class="err">{error}</div>' if error else ""
    return HTMLResponse(_LOGIN_HTML.format(err=err, next=next_url))


def _safe_next(value: str | None) -> str:
    """Open-redirect guard: only allow same-site absolute paths."""
    if not value or not value.startswith("/") or value.startswith("//"):
        return "/ui"
    return value


# ── routes ──────────────────────────────────────────────────────────────────

@router.get("/login", include_in_schema=False)
async def login_form(request: Request):
    if read_session(request.cookies.get(COOKIE_NAME)):
        return RedirectResponse("/ui", status_code=303)
    return _login_page(next_url=_safe_next(request.query_params.get("next")))


@router.post("/login", include_in_schema=False)
async def login_submit(
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form("/ui"),
):
    if not authenticate(username, password):
        return _login_page("Sai tài khoản hoặc mật khẩu.", _safe_next(next))
    resp = RedirectResponse(_safe_next(next), status_code=303)
    resp.set_cookie(
        COOKIE_NAME, make_session(username),
        max_age=SESSION_TTL, httponly=True, samesite="lax",
        secure=COOKIE_SECURE, path="/",
    )
    return resp


@router.post("/logout", include_in_schema=False)
async def logout():
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie(COOKIE_NAME, path="/")
    return resp


@router.get("/me", include_in_schema=False)
async def me(request: Request):
    """Tiny helper for the UI: which account am I, what's my profile?"""
    sess = read_session(request.cookies.get(COOKIE_NAME))
    if not sess:
        return {"authenticated": False}
    acct = get_account(sess.username) or {}
    return {
        "authenticated": True,
        "username": sess.username,
        "label": acct.get("label", ""),
        "config": acct.get("config") or {},
    }


# ── helper for deps.get_user / middleware ───────────────────────────────────

def resolve_session_and_bind_tenant(request: Request) -> str | None:
    """If the request carries a valid session cookie, load the account, bind
    the tenant ContextVar for this request, and return the username. Else
    None (caller decides whether to fall back to header auth or 401).
    """
    sess = read_session(request.cookies.get(COOKIE_NAME))
    if not sess:
        return None
    acct = get_account(sess.username)
    if not acct or acct.get("disabled"):
        return None
    set_tenant(tenant_for_account(acct))
    return sess.username


__all__ = ["router", "resolve_session_and_bind_tenant"]
