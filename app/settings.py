# -*- coding: utf-8 -*-
"""Settings + reference-data (doctors, payment methods) helpers."""
from __future__ import annotations

import sqlite3
from typing import List, Optional

from .database import NO_DOCTOR_NAME, get_connection


def get_setting(key, default=None):
    # type: (str, Optional[str]) -> Optional[str]
    conn = get_connection()
    try:
        cur = conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cur.fetchone()
        if row is None:
            return default
        return row[0]
    finally:
        conn.close()


def set_setting(key, value):
    # type: (str, str) -> None
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO settings(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value))
        conn.commit()
    finally:
        conn.close()


def get_payment_methods():
    # type: () -> List[str]
    raw = get_setting("payment_methods", "پوز\nنقد\nانتقال\nچک")
    return [m.strip() for m in raw.split("\n") if m.strip()]


def set_payment_methods(methods):
    # type: (List[str]) -> None
    set_setting("payment_methods", "\n".join(methods))


def get_expense_categories():
    # type: () -> List[str]
    raw = get_setting("expense_categories",
                      "\n".join(["حقوق", "اجاره", "خرید تجهیزات", "قبوض",
                                "متفرقه"]))
    return [c.strip() for c in raw.split("\n") if c.strip()]


def set_expense_categories(categories):
    # type: (List[str]) -> None
    set_setting("expense_categories", "\n".join(categories))


def add_expense_category(name):
    # type: (str) -> None
    name = (name or "").strip()
    if name == "":
        return
    cats = get_expense_categories()
    if name in cats:
        return
    cats.append(name)
    set_expense_categories(cats)


def is_expense_category_used(category):
    # type: (str) -> bool
    conn = get_connection()
    try:
        cur = conn.execute("SELECT COUNT(*) FROM expenses WHERE category = ?",
                           (category,))
        return cur.fetchone()[0] > 0
    finally:
        conn.close()


def is_payment_method_used(method):
    # type: (str) -> bool
    conn = get_connection()
    try:
        cur = conn.execute("SELECT COUNT(*) FROM payments WHERE method = ?", (method,))
        return cur.fetchone()[0] > 0
    finally:
        conn.close()


def list_doctors(active_only=False):
    # type: (bool) -> List[dict]
    conn = get_connection()
    try:
        if active_only:
            cur = conn.execute("SELECT id, name, first_name, last_name, "
                               "specialty, address, phone, is_active "
                               "FROM doctors WHERE is_active = 1 ORDER BY id")
        else:
            cur = conn.execute("SELECT id, name, first_name, last_name, "
                               "specialty, address, phone, is_active "
                               "FROM doctors ORDER BY id")
        rows = cur.fetchall()
        out = []
        for r in rows:
            out.append({"id": r["id"], "name": r[1], "first_name": r[2],
                        "last_name": r[3], "specialty": r[4], "address": r[5],
                        "phone": r[6], "is_active": r[7]})
        return out
    finally:
        conn.close()


def find_doctor_id_by_name(name):
    # type: (str) -> Optional[int]
    conn = get_connection()
    try:
        cur = conn.execute("SELECT id FROM doctors WHERE name = ?", (name,))
        row = cur.fetchone()
        return int(row[0]) if row else None
    finally:
        conn.close()


_DUP_DOCTOR = "پزشکی با این نام قبلاً ثبت شده است."


def add_doctor(name, specialty="", address="", phone="", first_name="", last_name=""):
    # type: (str, str, str, str, str, str) -> int
    name = name.strip()
    if not name:
        name = ("%s %s" % (first_name, last_name)).strip()
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO doctors(name, first_name, last_name, specialty, "
            "address, phone, is_active) VALUES (?, ?, ?, ?, ?, ?, 1)",
            (name, first_name, last_name, specialty, address, phone))
        conn.commit()
        return int(cur.lastrowid)
    except sqlite3.IntegrityError as exc:
        raise ValueError(_DUP_DOCTOR) from exc
    finally:
        conn.close()


def is_doctor_used(doctor_id):
    # type: (int) -> bool
    conn = get_connection()
    try:
        cur = conn.execute("SELECT COUNT(*) FROM invoices WHERE doctor_id = ?",
                           (doctor_id,))
        return cur.fetchone()[0] > 0
    finally:
        conn.close()


def update_doctor(doctor_id, name, specialty="", address="", phone="",
                  first_name="", last_name=""):
    # type: (int, str, str, str, str, str, str) -> None
    name = name.strip()
    if not name:
        name = ("%s %s" % (first_name, last_name)).strip()
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE doctors SET name = ?, first_name = ?, last_name = ?, "
            "specialty = ?, address = ?, phone = ? WHERE id = ?",
            (name, first_name, last_name, specialty, address, phone, doctor_id))
        conn.commit()
    except sqlite3.IntegrityError as exc:
        raise ValueError(_DUP_DOCTOR) from exc
    finally:
        conn.close()


def deactivate_doctor(doctor_id):
    # type: (int) -> None
    conn = get_connection()
    try:
        conn.execute("UPDATE doctors SET is_active = 0 WHERE id = ?", (doctor_id,))
        conn.commit()
    finally:
        conn.close()


def activate_doctor(doctor_id):
    # type: (int) -> None
    conn = get_connection()
    try:
        conn.execute("UPDATE doctors SET is_active = 1 WHERE id = ?", (doctor_id,))
        conn.commit()
    finally:
        conn.close()


def hard_delete_doctor(doctor_id):
    # type: (int) -> None
    conn = get_connection()
    try:
        conn.execute("DELETE FROM doctors WHERE id = ?", (doctor_id,))
        conn.commit()
    finally:
        conn.close()


def get_no_doctor_id():
    # type: () -> int
    conn = get_connection()
    try:
        cur = conn.execute("SELECT id FROM doctors WHERE name = ?", (NO_DOCTOR_NAME,))
        row = cur.fetchone()
        if row is None:
            cur2 = conn.execute(
                "INSERT INTO doctors(name, is_active) VALUES (?, 1)",
                (NO_DOCTOR_NAME,))
            conn.commit()
            return int(cur2.lastrowid)
        return int(row[0])
    finally:
        conn.close()


def is_no_doctor(name):
    # type: (str) -> bool
    return name.strip() == NO_DOCTOR_NAME
