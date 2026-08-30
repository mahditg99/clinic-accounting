# -*- coding: utf-8 -*-
"""Convert raw model rows (ints + Gregorian ISO dates) into display-ready
values for the web templates / JSON APIs: Jalali dates and Persian money.

The JSON endpoints return numbers (for client-side computation); the Jinja
templates render the display strings via the same helpers.
"""
from __future__ import annotations

from app import date_utils
from app import money_utils


def fmt_money(amount):
    # type: (int) -> str
    """Persian-formatted, thousand-separated money string (e.g. '۱۲۳٬۴۵۶').

    The separator is the Persian thousands mark '٬' (U+066C); money_utils
    parsers accept it. Negative amounts keep the '-' sign and are wrapped in
    Unicode LTR-isolate controls so RTL pages render them as a real negative
    number (the minus would otherwise be visually detached and read as
    positive).
    """
    try:
        n = int(amount or 0)
    except Exception:
        return str(amount or 0)
    s = money_utils.format_money_persian(abs(n)).replace(",", "\u066c")
    if n < 0:
        return "\u2066-" + s + "\u2069"
    return s


def fmt_date_jalali(iso_date):
    # type: (str) -> str
    """Gregorian ISO 'YYYY-MM-DD...' -> Persian long date string; '' when empty."""
    if not iso_date:
        return ""
    try:
        return date_utils.iso_to_jalali_persian_str(iso_date)
    except Exception:
        return iso_date


def fmt_time(paid_at):
    # type: (str) -> str
    """Extract HH:MM from an ISO datetime as Persian digits, or '' when absent.

    Handles both 'YYYY-MM-DDTHH:MM:SS' and 'YYYY-MM-DD HH:MM:SS' forms.
    """
    if not paid_at:
        return ""
    s = str(paid_at).strip()
    if "T" in s:
        s = s.split("T")[1]
    elif " " in s:
        s = s.split(" ")[1]
    parts = s.split(":")
    if len(parts) >= 2:
        return date_utils.to_persian_digits("%s:%s" % (parts[0], parts[1]))
    return date_utils.to_persian_digits(s[:5])


def to_display(rows, date_fields=(), money_fields=()):
    # type: (list, tuple, tuple) -> list
    """Clone each row dict, applying Jalali + money formatting in place.

    date_fields and money_fields are the row keys to transform. Keys listed in
    money_fields are kept alongside as raw *_num (for client-side arithmetic).
    """
    out = []
    for r in rows:
        d = dict(r)
        for k in date_fields:
            d[k] = fmt_date_jalali(d.get(k))
        for k in money_fields:
            num = int(d.get(k) or 0)
            d[k] = fmt_money(num)
            d[k + "_num"] = num
        out.append(d)
    return out


def patient_row(r):
    # type: (dict) -> dict
    d = dict(r)
    d["gender_persian"] = {"male": "آقا", "female": "خانم"}.get(d.get("gender", ""),
                           "—")
    # Show numbers (file_no, phone, invoice_count) in Persian digits.
    for k in ("file_no", "phone", "invoice_count"):
        if d.get(k):
            d[k] = date_utils.to_persian_digits(d[k])
    d["status_persian"] = "فعال" if d.get("is_active", 1) else "غیرفعال"
    d["full_name"] = "%s %s" % (d.get("first_name", ""), d.get("last_name", ""))
    return d


def product_row(r):
    # type: (dict) -> dict
    d = dict(r)
    for k in ("purchase_price", "sale_price", "price"):
        num = int(d.get(k) or 0)
        d[k + "_num"] = num
        d[k] = fmt_money(num)
    d["stock"] = int(d.get("stock") or 0)
    d["stock_p"] = date_utils.to_persian_digits(d["stock"])
    d["low_stock_warning_p"] = date_utils.to_persian_digits(
        int(d.get("low_stock_warning") or 0))
    d["low_stock"] = (0 < d["stock"] <= int(d.get("low_stock_warning") or 0))
    d["out_of_stock"] = d["stock"] <= 0
    d["status_persian"] = "فعال" if d.get("is_active", 1) else "غیرفعال"
    return d