# -*- coding: utf-8 -*-
"""Credential storage + PBKDF2 hashing shared by the web app and desktop app.

Stdlib only (no FastAPI import) so the packaged desktop exe can verify the
same ``admin_user`` / ``admin_pass_hash`` settings rows the web UI uses.
``webapp/auth.py`` re-exports these functions to keep one source of truth.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Optional

_HASH_ALGO = "pbkdf2_sha256"
_ITERATIONS = 200_000


def _new_salt():
    # type: () -> bytes
    return secrets.token_bytes(16)


def hash_password(password, salt=None):
    # type: (str, Optional[bytes]) -> str
    """PBKDF2-HMAC-SHA256 -> 'algo$iters$salt$hash'."""
    from . import settings as settings_mod  # local import: avoid cycles
    salt = salt or _new_salt()
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return "%s$%d$%s$%s" % (_HASH_ALGO, _ITERATIONS, salt.hex(), dk.hex())


def verify_password(password, stored):
    # type: (str, str) -> bool
    try:
        algo, iters_str, salt_hex, hash_hex = stored.split("$")
        if algo != _HASH_ALGO:
            return False
        salt = bytes.fromhex(salt_hex)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt,
                                 int(iters_str))
        return hmac.compare_digest(dk.hex(), hash_hex)
    except (ValueError, AttributeError, TypeError):
        return False


def ensure_admin(default_user="admin", default_password="admin"):
    # type: (str, str) -> None
    """Create admin_user / admin_pass_hash (default admin@admin) if absent."""
    from . import settings as settings_mod
    user = settings_mod.get_setting("admin_user")
    if not user:
        settings_mod.set_setting("admin_user", default_user)
    if not settings_mod.get_setting("admin_pass_hash"):
        settings_mod.set_setting("admin_pass_hash", hash_password(default_password))


def verify_user(username, password):
    # type: (str, str) -> bool
    from . import settings as settings_mod
    admin_user = settings_mod.get_setting("admin_user", "admin")
    if not admin_user or username != admin_user:
        return False
    stored = settings_mod.get_setting("admin_pass_hash")
    if not stored:
        return False
    return verify_password(password, stored)


def change_password(current, new_password):
    # type: (str, str) -> None
    """Verify the current password and store a new hash. Raises ValueError."""
    from . import settings as settings_mod
    if not verify_user(settings_mod.get_setting("admin_user", "admin"), current):
        raise ValueError("رمز عبور فعلی اشتباه است.")
    if len(new_password) < 4:
        raise ValueError("رمز جدید باید حداقل ۴ کاراکتر باشد.")
    settings_mod.set_setting("admin_pass_hash", hash_password(new_password))
