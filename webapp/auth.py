# -*- coding: utf-8 -*-
"""Login, session and change-password handling for the FastAPI web app.

Credentials live in the shared ``settings`` table (keys ``admin_user`` and
``admin_pass_hash``) so the same store backs the desktop app's preferences and
password changes survive a process restart. Password hashing and cookie signing
use only the Python standard library (no passlib / itsdangerous).

Session format: an HMAC-SHA256-signed cookie whose payload is
``base64(username:exp_epoch)``. The signature is recomputed on each request to
verify integrity; an expired or tampered cookie is treated as logged out.
"""
from __future__ import annotations

import base64
import hmac
import hashlib
import os
import secrets
import time
from typing import Optional

from fastapi import Depends, Request
from fastapi.responses import RedirectResponse

from app import auth_core
from app.auth_core import (  # noqa: F401  (re-exported for existing callers)
    ensure_admin, verify_user, change_password,
    hash_password as _hash_password, verify_password as _verify_password,
)

SESSION_COOKIE = "azaran_session"
SESSION_TTL_SECONDS = 8 * 60 * 60  # 8 hours

# Server secret for cookie signing. Derived per-install and persisted so tokens
# survive restarts. Override with env var AZARAN_SECRET in production.
_SECRET_FILE = None
_SECRET = None


def _server_secret():
    # type: () -> bytes
    global _SECRET_FILE, _SECRET
    if _SECRET is not None:
        return _SECRET
    env = os.environ.get("AZARAN_SECRET")
    if env:
        _SECRET = env.encode("utf-8")
        return _SECRET
    if _SECRET_FILE is None:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        _SECRET_FILE = os.path.join(base, "webapp", ".session_secret")
    try:
        with open(_SECRET_FILE, "rb") as fh:
            _SECRET = fh.read().strip()
    except OSError:
        _SECRET = secrets.token_bytes(32)
        try:
            with open(_SECRET_FILE, "wb") as fh:
                fh.write(_SECRET)
        except OSError:
            pass  # non-persistent (in-memory only) is acceptable fallback
    return _SECRET


# --------------------------------------------------------------------------- #
# Session cookie (signed via stdlib HMAC)
# --------------------------------------------------------------------------- #

def _sign(payload):
    # type: (bytes) -> str
    return hmac.new(_server_secret(), payload, hashlib.sha256).hexdigest()


def _b64encode(data):
    # type: (bytes) -> str
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64decode(data):
    # type: (str) -> bytes
    pad = "=" * (-len(data) % 4)
    try:
        return base64.urlsafe_b64decode(data + pad)
    except Exception:
        return b""


def make_session_cookie(username):
    # type: (str) -> str
    exp = int(time.time()) + SESSION_TTL_SECONDS
    payload = _b64encode(("%s:%d" % (username, exp)).encode("utf-8"))
    sig = _sign((payload + ".").encode("utf-8"))
    return payload + "." + sig


def read_session_cookie(cookie_value):
    # type: (Optional[str]) -> Optional[str]
    """Return the username if the cookie is valid/unsigned/not-expired, else None."""
    if not cookie_value:
        return None
    if "." not in cookie_value:
        return None
    payload, sig = cookie_value.rsplit(".", 1)
    expected = _sign((payload + ".").encode("utf-8"))
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        raw = _b64decode(payload).decode("utf-8")
        username, exp_str = raw.rsplit(":", 1)
    except Exception:
        return None
    try:
        if int(exp_str) < int(time.time()):
            return None
    except ValueError:
        return None
    return username


def logged_in_username(request):
    # type: (Request) -> Optional[str]
    return read_session_cookie(request.cookies.get(SESSION_COOKIE))


def require_login(request):
    # type: (Request) -> str
    """FastAPI dependency. Redirects to /login when not authenticated."""
    username = logged_in_username(request)
    if not username:
        raise _LoginRequired()
    return username


class _LoginRequired(Exception):
    pass


def logout_redirect():
    # type: () -> RedirectResponse
    resp = RedirectResponse(url="/login", status_code=303)
    resp.delete_cookie(SESSION_COOKIE)
    return resp