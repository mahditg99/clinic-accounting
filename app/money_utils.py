# -*- coding: utf-8 -*-
"""Integer-only money helpers (Iranian Toman). No floats for money."""
from __future__ import annotations

from typing import Optional


_PERSIAN_DIGITS = {
    "0": "۰", "1": "۱", "2": "۲", "3": "۳", "4": "۴",
    "5": "۵", "6": "۶", "7": "۷", "8": "۸", "9": "۹",
}

# Arabic-Indic digits (٠-٩) fold to the same Latin digits as Persian ones,
# so pasted/typed Arabic numerals still parse and search correctly.
_ARABIC_DIGITS = {
    "0": "٠", "1": "١", "2": "٢", "3": "٣", "4": "٤",
    "5": "٥", "6": "٦", "7": "٧", "8": "٨", "9": "٩",
}


def _to_english_digits(text):
    # type: (str) -> str
    fa_to_en = {fa: en for en, fa in _PERSIAN_DIGITS.items()}
    ar_to_en = {ar: en for en, ar in _ARABIC_DIGITS.items()}
    fa_to_en.update(ar_to_en)
    out = []
    for ch in str(text):
        out.append(fa_to_en.get(ch, ch))
    return "".join(out)


def format_money(amount):
    # type: (Optional[int]) -> str
    """Thousand-separated money string, e.g. 12345 -> '12,345'."""
    if amount is None:
        return ""
    n = int(amount)
    sign = "-" if n < 0 else ""
    n = abs(n)
    s = "{:,}".format(n)
    return sign + s


def format_money_persian(amount):
    # type: (Optional[int]) -> str
    """Persian-display money: ۱۲٬۳۴۵ (Persian digits + Persian thousands mark)."""
    s = format_money(amount)
    out = []
    for ch in s:
        if ch == ",":
            out.append("\u066c")  # Persian thousands separator ٬
        else:
            out.append(_PERSIAN_DIGITS.get(ch, ch))
    return "".join(out)


def parse_money(text):
    # type: (str) -> Optional[int]
    """Parse a user-entered money string. Returns None if blank/invalid.

    Accepts Persian/Arabic digits and any of the thousands separators
    ',' (ASCII), '،' (Arabic comma) and '٬' (Persian thousands mark).
    """
    if text is None:
        return None
    s = _to_english_digits(str(text)).strip()
    for sep in (",", "\u060c", "\u066c"):
        s = s.replace(sep, "")
    if s == "":
        return None
    sign = 1
    if s.startswith("-"):
        sign = -1
        s = s[1:]
    elif s.startswith("+"):
        s = s[1:]
    if not s.isdigit():
        return None
    try:
        return sign * int(s)
    except ValueError:
        return None


def parse_int(text, default=0):
    # type: (str, int) -> int
    if text is None:
        return default
    s = _to_english_digits(str(text)).strip()
    for sep in (",", "\u060c", "\u066c"):
        s = s.replace(sep, "")
    if s == "" or not s.lstrip("-+").isdigit():
        return default
    try:
        return int(s)
    except ValueError:
        return default
