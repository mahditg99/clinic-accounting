# -*- coding: utf-8 -*-
"""Machine-bound license for the packaged (exe) build.

Flow
----
* ``hardware_code()`` derives a stable, human-transferable code from the
  Windows ``MachineGuid`` (falls back to MAC + computer name).
* The vendor signs a small JSON payload for that code with the *private* RSA
  key held in ``keys/issuer_private.json`` and sends back ``license.key``.
* ``verify()`` checks the signature against the public key embedded below,
  then that the payload names *this* machine and has not expired.

Deliberately dependency-free (stdlib only) and Qt-free at import time, so the
issuer tool can import this module without a database or a QApplication.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import sys
import tempfile
from datetime import date, datetime
from typing import Dict, Optional

from . import rsa_lite

# --------------------------------------------------------------------------- #
# Vendor public key.  Replace both values (and KEY_FINGERPRINT) whenever a new
# key pair is generated with tools/license_issuer.py, then rebuild the exe.
# --------------------------------------------------------------------------- #

PUB_N_HEX = (
    "aeb014b99eaab08dc5de9baab5712e39f08d60cae3c1294bfb2003223ad7dfbc"
    "17785df93ce8671af7f05062023c6a82d04f1c73a9c4046fe54038113ae60ff6"
    "28ef407c4d40fd6d04d18759abfa3d203c22bf299147397b49a03ad33b4f858d"
    "a61c6a6e0d59cb10c8fc7e8d78d88a6a294965cffea8dd5605aafe8968cb9477"
    "32d010b07e0af08fa6853dcf9229819cdca7f97ecd23c8482d6039f6d6e64e20"
    "d9001e83e1bf3017da6acaba71fbf3f1aea8c1bdd422eb5e6e1147b7c20cf9e8"
    "1da152c74fee9f009e864bfcf7e3305aacf7a08f55cf7e1d311e98f1c56e252b"
    "8f0ff5edd155ab7eab1c03473aee3fe7cc6562cc828465ed2ac9e4c900b1a74b"
)
PUB_E = 65537
KEY_FINGERPRINT = "6D869E66"

PRODUCT = "AZARAN1"
FORMAT_VERSION = 1
LICENSE_FILE = "license.key"
EXPIRY_WARN_DAYS = 15
CLOCK_SLACK_DAYS = 2
_SEEN_KEY = "license.last_seen"

# Status codes
OK = "OK"
MISSING = "MISSING"
BAD_FORMAT = "BAD_FORMAT"
BAD_SIGN = "BAD_SIGN"
HW_MISMATCH = "HW_MISMATCH"
EXPIRED = "EXPIRED"
CLOCK_TAMPER = "CLOCK_TAMPER"

REASONS = {
    MISSING: "برای این دستگاه لایسنسی یافت نشد.",
    BAD_FORMAT: "فایل لایسنس خوانا نیست؛ لطفاً فایل اصلی را دوباره بفرستید.",
    BAD_SIGN: "امضای فایل لایسنس معتبر نیست. این فایل برای این نسخهٔ برنامه صادر نشده یا دستکاری شده است.",
    HW_MISMATCH: "این لایسنس برای دستگاه دیگری صادر شده و روی این رایانه کار نمی‌کند.",
    EXPIRED: "مدت اعتبار لایسنس این نرم‌افزار به پایان رسیده است.",
    CLOCK_TAMPER: "ساعت ویندوز از آخرین اجرای برنامه عقب‌تر است. لطفاً ساعت و تاریخ سیستم را اصلاح کنید.",
}


class Status(object):
    """Outcome of a license check — also what the UI dialogs render."""

    def __init__(self, code, payload=None, days_left=None, hw=""):
        # type: (str, Optional[dict], Optional[int], str) -> None
        self.code = code
        self.payload = payload or {}
        self.days_left = days_left
        self.hw = hw
        self.ok = code == OK

    @property
    def message(self):
        # type: () -> str
        if self.code == OK:
            return "لایسنس معتبر است."
        msg = REASONS.get(self.code, "لایسنس معتبر نیست.")
        if self.code == EXPIRED:
            exp = self.payload.get("expires")
            if exp:
                msg = "لایسنس این نرم‌افزار در تاریخ %s منقضی شده است." % _fa_date(exp)
        return msg

    @property
    def customer(self):
        # type: () -> str
        return (self.payload.get("name") or "").strip()

    def __repr__(self):
        # type: () -> str
        return "<Status %s days_left=%r>" % (self.code, self.days_left)


# --------------------------------------------------------------------------- #
# Hardware identity
# --------------------------------------------------------------------------- #

_HW_CACHE = {}  # type: Dict[str, str]


def _machine_guid():
    # type: () -> Optional[str]
    """Windows' own unique install id — survives hardware changes, is absent
    from any user-editable file, and needs no extra privileges to read."""
    if os.name != "nt":
        return None
    try:
        import winreg
    except Exception:
        return None
    accesses = []
    try:
        accesses.append(winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
    except Exception:
        pass
    accesses.append(winreg.KEY_READ)
    for access in accesses:
        key = None
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                 r"SOFTWARE\Microsoft\Cryptography", 0, access)
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
            if value:
                return str(value).strip().lower()
        except Exception:
            pass
        finally:
            if key is not None:
                try:
                    winreg.CloseKey(key)
                except Exception:
                    pass
    return None


def machine_source():
    # type: () -> str
    """The raw string the hardware code is hashed from (also handy in support)."""
    guid = _machine_guid()
    if guid:
        return "MG:" + guid
    import socket
    try:
        import uuid as _uuid
        mac = _uuid.getnode()
    except Exception:
        mac = 0
    name = os.environ.get("COMPUTERNAME") or socket.gethostname() or "unknown"
    return "FB:%x:%s" % (int(mac), name)


def _grouped(raw20):
    # type: (str) -> str
    return "-".join(raw20[i:i + 5] for i in range(0, len(raw20), 5))


def hardware_code(source=None):
    # type: (Optional[str]) -> str
    """``ABCDE-FGHIJ-KLMNP-QRSTU`` — 20 base32 chars (no 0/1) of SHA-256."""
    src = source if source is not None else machine_source()
    cached = _HW_CACHE.get(src)
    if cached:
        return cached
    digest = hashlib.sha256((PRODUCT + "|" + src).encode("utf-8")).digest()
    # 13 bytes -> 21 base32 chars; keep the first 20 so the groups are even.
    code = _grouped(base64.b32encode(digest[:13]).decode("ascii").rstrip("=")[:20])
    _HW_CACHE[src] = code
    return code


def normalize_code(text):
    # type: (Optional[str]) -> str
    """Accept whatever the customer pasted (spaces, dashes, lowercase, Persian
    digits) and return the canonical grouped form, or ``''`` if unusable."""
    if not text:
        return ""
    raw = str(text)
    try:  # tolerate Persian/Arabic digits typed by hand
        raw = raw.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
                                          "01234567890123456789"))
    except Exception:
        pass
    allowed = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
    chars = [c for c in raw.upper() if c in allowed]
    if len(chars) != 20:
        return ""
    return _grouped("".join(chars))


def code_is_valid(text):
    # type: (Optional[str]) -> bool
    return bool(normalize_code(text))


# --------------------------------------------------------------------------- #
# Token format:  AZARAN1.<b64url(payload)>.<b64url(signature)>
# --------------------------------------------------------------------------- #

def canonical_payload(payload):
    # type: (dict) -> bytes
    """The exact bytes that get signed.  The verifier signs nothing — it
    decodes these same bytes out of the token — so the two sides can never
    disagree about JSON formatting."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def _b64e(data):
    # type: (bytes) -> str
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64d(text):
    # type: (str) -> bytes
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def build_token(payload, private_keys):
    # type: (dict, dict) -> str
    """Issuer side: sign a payload with the vendor private key."""
    data = canonical_payload(payload)
    sig = rsa_lite.sign(data, int(private_keys["d"]), int(private_keys["n"]))
    return "%s.%s.%s" % (PRODUCT, _b64e(data), _b64e(sig))


def parse_token(token):
    # type: (str) -> tuple
    """Return ``(payload_bytes, signature_bytes)`` or raise ValueError.

    All whitespace is removed (not collapsed to spaces): a token pasted out of
    an email or SMS can arrive hard-wrapped, and base64url never contains a
    space of its own.
    """
    body = "".join((token or "").split())
    parts = body.split(".")
    if len(parts) != 3:
        raise ValueError("not a license token")
    if parts[0] != PRODUCT:
        raise ValueError("unknown license product")
    return _b64d(parts[1]), _b64d(parts[2])


def verify_token(token):
    # type: (str) -> Status
    """Signature + version check only (no hardware/expiry logic)."""
    try:
        data, sig = parse_token(token)
    except Exception:
        return Status(BAD_FORMAT)
    try:
        good = rsa_lite.verify(data, sig, PUB_E, int(PUB_N_HEX, 16))
    except Exception:
        return Status(BAD_SIGN)
    if not good:
        return Status(BAD_SIGN)
    try:
        payload = json.loads(data.decode("utf-8"))
    except Exception:
        return Status(BAD_FORMAT)
    if not isinstance(payload, dict) or int(payload.get("v") or 0) != FORMAT_VERSION:
        return Status(BAD_FORMAT)
    return Status(OK, payload)


# --------------------------------------------------------------------------- #
# License file location
# --------------------------------------------------------------------------- #

def license_dir():
    # type: () -> str
    """Folder that holds ``license.key`` — the same portable directory the
    SQLite database lives in (next to the exe when frozen)."""
    try:
        from .database import _base_dir
        return _base_dir()
    except Exception:
        if getattr(sys, "frozen", False):
            return os.path.dirname(os.path.abspath(sys.executable))
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def license_path():
    # type: () -> str
    return os.path.join(license_dir(), LICENSE_FILE)


def read_token():
    # type: () -> Optional[str]
    path = license_path()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read().strip()
        return text or None
    except Exception:
        return None


def install_license(src_path):
    # type: (str) -> Status
    """Copy a chosen file into place (temp + replace) and re-verify it.

    Returns the status of the *installed* license; on failure the previous
    file is left untouched so a bad pick can never brick a working install.
    """
    try:
        with open(src_path, "r", encoding="utf-8") as fh:
            text = fh.read().strip()
    except Exception:
        return Status(BAD_FORMAT)
    st = verify_token(text)
    if not st.ok:
        return st
    st = _check_payload(st.payload)
    if not st.ok:
        return st
    dst = license_path()
    folder = os.path.dirname(dst)
    try:
        if not os.path.isdir(folder):
            os.makedirs(folder)
        fd, tmp = tempfile.mkstemp(dir=folder, prefix=".license-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(text + "\n")
            if os.path.exists(dst):
                shutil.copystat(dst, tmp)
            os.replace(tmp, dst)
        except Exception:
            try:
                os.remove(tmp)
            except Exception:
                pass
            raise
    except Exception:
        return Status(BAD_FORMAT)
    return st


# --------------------------------------------------------------------------- #
# Full check: signature + machine + expiry + clock
# --------------------------------------------------------------------------- #

def _today():
    # type: () -> date
    return date.today()


def _iso(d):
    # type: (str) -> Optional[date]
    try:
        return datetime.strptime(str(d)[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def _fa_date(iso):
    # type: (str) -> str
    try:
        from . import date_utils
        return date_utils.iso_to_jalali_persian_str(str(iso)[:10])
    except Exception:
        return str(iso)


def _days_left(payload):
    # type: (dict) -> Optional[int]
    exp = _iso(payload.get("expires") or "")
    if not exp:
        return None
    return (exp - _today()).days


def _last_seen():
    # type: () -> Optional[date]
    try:
        from . import settings as _settings
        raw = _settings.get_setting(_SEEN_KEY)
    except Exception:
        return None
    return _iso(raw) if raw else None


def _remember_seen(today):
    # type: (date) -> None
    try:
        from . import settings as _settings
        _settings.set_setting(_SEEN_KEY, today.isoformat())
    except Exception:
        pass  # no DB (issuer tool) — the clock guard simply stays off


def _check_payload(payload):
    # type: (dict) -> Status
    want = normalize_code(payload.get("hw") or "")
    have = hardware_code()
    if want != have:
        return Status(HW_MISMATCH, payload, hw=have)
    days = _days_left(payload)
    if days is not None and days < 0:
        return Status(EXPIRED, payload, days, hw=have)
    today = _today()
    seen = _last_seen()
    if seen is not None and (today - seen).days < -CLOCK_SLACK_DAYS:
        return Status(CLOCK_TAMPER, payload, days, hw=have)
    if seen is None or today > seen:
        _remember_seen(today)
    return Status(OK, payload, days, hw=have)


def verify():
    # type: () -> Status
    """The one call the app makes at startup."""
    token = read_token()
    if not token:
        return Status(MISSING, hw=hardware_code())
    st = verify_token(token)
    if not st.ok:
        st.hw = hardware_code()
        return st
    return _check_payload(st.payload)


def warns_of_expiry(status):
    # type: (Status) -> bool
    return bool(status and status.ok and status.days_left is not None
                and 0 <= status.days_left <= EXPIRY_WARN_DAYS)


def enforcement_required():
    # type: () -> bool
    """Licenses gate the shipped exe only; running from source stays open so
    the dev/test scripts keep working. ``AZARAN_LICENSE_ENFORCE=1`` forces it."""
    if getattr(sys, "frozen", False):
        return True
    return (os.environ.get("AZARAN_LICENSE_ENFORCE") or "").strip() == "1"


_LAST = None  # type: Optional[Status]


def last_status():
    # type: () -> Optional[Status]
    return _LAST


def enforce_startup():
    # type: () -> bool
    """Gate used by ``main.py``.  Returns True when the app may continue."""
    global _LAST
    if not enforcement_required():
        return True
    from app.utils import Qt
    _LAST = verify()
    if _LAST.ok:
        return True
    from .ui.license_dialog import ActivationDialog
    while True:
        dlg = ActivationDialog(_LAST)
        if dlg.exec_() != Qt.QtWidgets.QDialog.Accepted:
            return False
        _LAST = verify()
        if _LAST.ok:
            return True


# --------------------------------------------------------------------------- #
# Issuer-side helpers (used by tools/license_issuer.py, harmless in the exe)
# --------------------------------------------------------------------------- #

def make_payload(hw_code, customer, issued_iso, expires_iso):
    # type: (str, str, str, Optional[str]) -> dict
    return {
        "v": FORMAT_VERSION,
        "hw": normalize_code(hw_code) or (hw_code or "").strip().upper(),
        "name": (customer or "").strip(),
        "issued": (issued_iso or "")[:10],
        "expires": (expires_iso or "")[:10] if expires_iso else None,
    }


def public_fingerprint():
    # type: () -> str
    return rsa_lite.fingerprint(int(PUB_N_HEX, 16), PUB_E)
