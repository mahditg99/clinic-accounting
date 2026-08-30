# -*- coding: utf-8 -*-
"""Data-access layer: thin functions over sqlite3 (no ORM).

All monetary values are integers (Toman). Dates stored as Gregorian ISO.
"""
from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional, Tuple

from .database import next_invoice_no
from . import date_utils


def _search_word(word):
    # type: (str) -> str
    """Normalize one search word for LIKE matching.

    Folds Persian/Arabic-Indic digits to Latin (DB stores Latin) and turns
    ZWNJ (نیم‌فاصله) into a SQL wildcard so "حساب‌داری" matches both spellings.
    Idempotent — safe to call on already-normalized text.
    """
    folded = date_utils.to_english_digits(word)
    return folded.replace("\u200c", "%")


# --------------------------------------------------------------------------- #
# Patients
# --------------------------------------------------------------------------- #

def create_patient(file_no, first_name, last_name, gender, phone="", address=""):
    # type: (str, str, str, str, str, str) -> int
    conn = _conn()
    try:
        cur = conn.execute(
            "INSERT INTO patients(file_no, first_name, last_name, gender, "
            "phone, address, is_active, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, 1, ?)",
            (file_no, first_name, last_name, gender, phone, address,
             date_utils.now_iso()))
        conn.commit()
        return int(cur.lastrowid)
    except sqlite3.IntegrityError as exc:
        raise ValueError("شماره پرونده تکراری است.") from exc
    finally:
        conn.close()


def get_patient(patient_id):
    # type: (int) -> Optional[Dict[str, Any]]
    conn = _conn()
    try:
        cur = conn.execute("SELECT * FROM patients WHERE id = ?", (patient_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def search_active_patients(query_text, by_file):
    # type: (str, bool) -> List[Dict[str, Any]]
    conn = _conn()
    try:
        if by_file:
            sql = ("SELECT id, file_no, first_name, last_name, gender, "
                   "is_active FROM patients WHERE is_active = 1 AND "
                   "file_no LIKE ? ORDER BY file_no")
        else:
            # Word-wise match: "مریم حسابداری" finds first+last in any order.
            words = [w for w in query_text.strip().split() if w]
            conds, params = [], []
            for w in words:
                like = "%" + _search_word(w) + "%"
                conds.append("(first_name LIKE ? OR last_name LIKE ?)")
                params.extend([like, like])
            where = " AND ".join(conds) if conds else "1=1"
            sql = ("SELECT id, file_no, first_name, last_name, gender, "
                   "is_active FROM patients WHERE is_active = 1 AND "
                   + where + " ORDER BY file_no")
        if by_file:
            rows = conn.execute(
                sql, ("%" + _search_word(query_text.strip()) + "%",)).fetchall()
        else:
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def list_patients(active_only=False):
    # type: (bool) -> List[Dict[str, Any]]
    conn = _conn()
    try:
        if active_only:
            sql = ("SELECT p.id, p.file_no, p.first_name, p.last_name, "
                   "p.gender, p.phone, p.address, p.is_active, "
                   "(SELECT COUNT(*) FROM invoices i "
                   " WHERE i.patient_id = p.id AND i.is_deleted = 0) AS invoice_count "
                   "FROM patients p WHERE p.is_active = 1 "
                   "ORDER BY p.file_no")
        else:
            sql = ("SELECT p.id, p.file_no, p.first_name, p.last_name, "
                   "p.gender, p.phone, p.address, p.is_active, "
                   "(SELECT COUNT(*) FROM invoices i "
                   " WHERE i.patient_id = p.id AND i.is_deleted = 0) AS invoice_count "
                   "FROM patients p ORDER BY p.file_no")
        rows = conn.execute(sql).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def update_patient(patient_id, first_name, last_name, gender, phone="", address=""):
    # type: (int, str, str, str, str, str) -> None
    conn = _conn()
    try:
        conn.execute(
            "UPDATE patients SET first_name = ?, last_name = ?, gender = ?, "
            "phone = ?, address = ? WHERE id = ?",
            (first_name, last_name, gender, phone, address, patient_id))
        conn.commit()
    finally:
        conn.close()


def deactivate_patient(patient_id):
    # type: (int) -> None
    conn = _conn()
    try:
        conn.execute("UPDATE patients SET is_active = 0 WHERE id = ?", (patient_id,))
        conn.commit()
    finally:
        conn.close()


def delete_patient(patient_id):
    # type: (int) -> None
    conn = _conn()
    try:
        conn.execute("DELETE FROM patients WHERE id = ?", (patient_id,))
        conn.commit()
    finally:
        conn.close()


def patient_has_invoices(patient_id):
    # type: (int) -> bool
    conn = _conn()
    try:
        cur = conn.execute(
            "SELECT COUNT(*) FROM invoices WHERE patient_id = ? AND is_deleted = 0",
            (patient_id,))
        return cur.fetchone()[0] > 0
    finally:
        conn.close()


def file_no_exists(file_no, exclude_id=None):
    # type: (str, Optional[int]) -> bool
    conn = _conn()
    try:
        if exclude_id is None:
            cur = conn.execute("SELECT id FROM patients WHERE file_no = ?", (file_no,))
        else:
            cur = conn.execute(
                "SELECT id FROM patients WHERE file_no = ? AND id != ?",
                (file_no, exclude_id))
        return cur.fetchone() is not None
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Products
# --------------------------------------------------------------------------- #

def list_products(active_only=False):
    # type: (bool) -> List[Dict[str, Any]]
    conn = _conn()
    try:
        sql = ("SELECT id, title, price, purchase_price, sale_price, stock, "
               "low_stock_warning, description, sort_order, is_active "
               "FROM products ")
        if active_only:
            sql += "WHERE is_active = 1 "
        sql += "ORDER BY sort_order, title"
        rows = conn.execute(sql).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _validate_money(value, field_name):
    # type: (Any, str) -> int
    """Coerce to int, reject negatives. Raises Persian ValueError on bad input."""
    try:
        n = int(value) if value is not None else 0
    except (TypeError, ValueError):
        raise ValueError("مقدار «%s» باید عدد صحیح باشد." % field_name)
    if n < 0:
        raise ValueError("مقدار «%s» نمی‌تواند منفی باشد." % field_name)
    return n


def add_product(title, purchase_price, sale_price, stock, low_stock_warning,
                description):
    # type: (str, int, int, int, int, str) -> int
    title = (title or "").strip()
    if title == "":
        raise ValueError("نام محصول الزامی است.")
    purchase_price = _validate_money(purchase_price, "قیمت خرید")
    sale_price = _validate_money(sale_price, "قیمت فروش")
    stock = _validate_money(stock, "موجودی")
    low_stock_warning = _validate_money(low_stock_warning, "حداکم موجودی")
    is_active = 1 if stock > 0 else 0
    conn = _conn()
    try:
        cur = conn.execute(
            "INSERT INTO products(title, price, purchase_price, sale_price, "
            "stock, low_stock_warning, description, sort_order, is_active) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, COALESCE((SELECT MAX(sort_order) "
            "FROM products),0)+1, ?)",
            (title, sale_price, purchase_price, sale_price, stock,
             low_stock_warning, description, is_active))
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def update_product(product_id, title, purchase_price, sale_price, stock,
                   low_stock_warning, description):
    # type: (int, str, int, int, int, int, str) -> None
    title = (title or "").strip()
    if title == "":
        raise ValueError("نام محصول الزامی است.")
    purchase_price = _validate_money(purchase_price, "قیمت خرید")
    sale_price = _validate_money(sale_price, "قیمت فروش")
    stock = _validate_money(stock, "موجودی")
    low_stock_warning = _validate_money(low_stock_warning, "حداکم موجودی")
    is_active = 1 if stock > 0 else 0
    conn = _conn()
    try:
        conn.execute(
            "UPDATE products SET title = ?, price = ?, purchase_price = ?, "
            "sale_price = ?, stock = ?, low_stock_warning = ?, description = ?, "
            "is_active = ? WHERE id = ?",
            (title, sale_price, purchase_price, sale_price, stock,
             low_stock_warning, description, is_active, product_id))
        conn.commit()
    finally:
        conn.close()


def deactivate_product(product_id):
    # type: (int) -> None
    conn = _conn()
    try:
        conn.execute("UPDATE products SET is_active = 0 WHERE id = ?",
                     (product_id,))
        conn.commit()
    finally:
        conn.close()


def hard_delete_product(product_id):
    # type: (int) -> None
    conn = _conn()
    try:
        conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
        conn.commit()
    finally:
        conn.close()


def product_used_in_invoices(product_id):
    # type: (int) -> bool
    conn = _conn()
    try:
        cur = conn.execute(
            "SELECT COUNT(*) FROM invoice_items WHERE product_id = ?",
            (product_id,))
        return cur.fetchone()[0] > 0
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Invoices
# --------------------------------------------------------------------------- #

def list_invoice_items(invoice_id):
    # type: (int) -> List[Dict[str, Any]]
    conn = _conn()
    try:
        cur = conn.execute(
            "SELECT id, invoice_id, product_id, title, unit_price, cost_price, "
            "quantity, row_total, row_cost, row_profit "
            "FROM invoice_items WHERE invoice_id = ? ORDER BY id",
            (invoice_id,))
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def list_payments(invoice_id):
    # type: (int) -> List[Dict[str, Any]]
    conn = _conn()
    try:
        cur = conn.execute(
            "SELECT id, invoice_id, method, amount, paid_at "
            "FROM payments WHERE invoice_id = ? ORDER BY id",
            (invoice_id,))
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_invoice(invoice_id):
    # type: (int) -> Optional[Dict[str, Any]]
    conn = _conn()
    try:
        cur = conn.execute(
            "SELECT i.id, i.invoice_no, i.patient_id, i.doctor_id, "
            "i.issued_at, i.total_amount, i.notes, i.is_deleted, "
            "p.file_no, p.first_name, p.last_name, p.gender, "
            "d.name AS doctor_name "
            "FROM invoices i "
            "JOIN patients p ON p.id = i.patient_id "
            "LEFT JOIN doctors d ON d.id = i.doctor_id "
            "WHERE i.id = ?",
            (invoice_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def invoice_paid_sum(invoice_id):
    # type: (int) -> int
    conn = _conn()
    try:
        cur = conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM payments "
            "WHERE invoice_id = ?", (invoice_id,))
        return int(cur.fetchone()[0])
    finally:
        conn.close()


def save_invoice(patient_id, doctor_id, issued_at_iso, items, payments,
                 notes, invoice_id=None, update_issued=False):
    # type: (int, Optional[int], str, List[Dict[str,Any]], List[Dict[str,Any]], str, Optional[int], bool) -> int
    """Create or update an invoice, adjusting product stock correctly.

    items  : list of dicts with keys product_id (or None), title, unit_price,
             quantity, row_total. cost_price is read from the product's
             purchase_price at sale time if not supplied by the caller.
    payments: list of dicts with keys method, amount, paid_at (ISO).
    """
    conn = _conn()
    try:
        conn.execute("BEGIN")

        # When editing, restore old stock first so the new quantities are
        # validated against the *effective* available stock.
        existing_items = []  # type: List[Dict[str, Any]]
        if invoice_id is not None:
            existing_items = list_invoice_items(invoice_id)
            for it in existing_items:
                if it.get("product_id") is not None:
                    _apply_stock_delta(conn, it["product_id"],
                                      +int(it["quantity"]))

        # ---- Stock validation: block the whole transaction if any product
        # would go negative. We aggregate demand per product and compare to the
        # live stock (which already reflects restored old items when editing).
        short_msg = _check_stock_availability_tx(conn, items)
        if short_msg is not None:
            raise ValueError(short_msg)  # rolls back via the except block

        # ---- Insert/replace invoice header.
        if invoice_id is None:
            invoice_no = next_invoice_no(conn)
            cur = conn.execute(
                "INSERT INTO invoices(invoice_no, patient_id, doctor_id, "
                "issued_at, total_amount, total_cost, total_profit, notes, "
                "is_deleted) VALUES (?, ?, ?, ?, ?, 0, 0, ?, 0)",
                (invoice_no, patient_id, doctor_id, issued_at_iso, 0, notes))
            invoice_id = int(cur.lastrowid)
        else:
            # Delete old items + payments (stock already restored above).
            conn.execute("DELETE FROM invoice_items WHERE invoice_id = ?",
                         (invoice_id,))
            conn.execute("DELETE FROM payments WHERE invoice_id = ?",
                         (invoice_id,))

        # ---- Insert items, copying cost_price from the product at sale time.
        total_amount = 0
        total_cost = 0
        total_profit = 0
        for it in items:
            pid = it.get("product_id")
            qty = int(it.get("quantity", 1) or 1)
            unit_price = int(it.get("unit_price", 0) or 0)
            row_total = int(it.get("row_total", unit_price * qty) or 0)
            cost_price = _resolve_cost_price(conn, pid, it.get("cost_price"))
            row_cost = cost_price * qty
            row_profit = row_total - row_cost
            conn.execute(
                "INSERT INTO invoice_items(invoice_id, product_id, title, "
                "unit_price, cost_price, quantity, row_total, row_cost, "
                "row_profit) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (invoice_id, pid, it["title"], unit_price, cost_price, qty,
                 row_total, row_cost, row_profit))
            # Decrease stock (and auto-deactivate at zero) after validation.
            if pid is not None:
                _apply_stock_delta(conn, pid, -qty)
            total_amount += row_total
            total_cost += row_cost
            total_profit += row_profit

        # ---- Insert payments.
        for pm in payments:
            conn.execute(
                "INSERT INTO payments(invoice_id, method, amount, paid_at) "
                "VALUES (?, ?, ?, ?)",
                (invoice_id, pm["method"], int(pm["amount"]),
                 pm.get("paid_at", date_utils.now_iso())))

        # ---- Update invoice totals (incl. cost/profit).
        if update_issued:
            conn.execute(
                "UPDATE invoices SET patient_id = ?, doctor_id = ?, "
                "total_amount = ?, total_cost = ?, total_profit = ?, notes = ?, "
                "issued_at = ? WHERE id = ?",
                (patient_id, doctor_id, total_amount, total_cost, total_profit,
                 notes, issued_at_iso, invoice_id))
        else:
            conn.execute(
                "UPDATE invoices SET patient_id = ?, doctor_id = ?, "
                "total_amount = ?, total_cost = ?, total_profit = ?, notes = ? "
                "WHERE id = ?",
                (patient_id, doctor_id, total_amount, total_cost, total_profit,
                 notes, invoice_id))
        conn.commit()
        return int(invoice_id)
    except Exception as exc:
        conn.rollback()
        raise exc
    finally:
        conn.close()


def _resolve_cost_price(conn, product_id, explicit):
    # type: (sqlite3.Connection, Optional[int], Any) -> int
    """Return the per-item cost price (purchase_price) for billing.

    If the caller supplied an explicit cost_price (e.g. on edit of an old
    invoice), use it. Otherwise read purchase_price from the product. If the
    product is gone or has no purchase price, returns 0 (unknown historical
    cost -> profit treated as full row_total, documented as approximate).
    """
    if explicit is not None:
        try:
            n = int(explicit)
            return n if n >= 0 else 0
        except (TypeError, ValueError):
            return 0
    if product_id is None:
        return 0
    cur = conn.execute("SELECT purchase_price FROM products WHERE id = ?",
                       (product_id,))
    row = cur.fetchone()
    if row is None:
        return 0
    try:
        n = int(row[0])
        return n if n >= 0 else 0
    except (TypeError, ValueError):
        return 0


def _check_stock_availability_tx(conn, items):
    # type: (sqlite3.Connection, List[Dict[str,Any]]) -> Optional[str]
    """Within a transaction, return a Persian error message if any product
    would go negative, else None.

    Aggregates demand per product_id and compares to live stock (which, on
    edit, already reflects restored old items). Returns the FIRST shortfall so
    the caller can abort with a clear message.
    """
    needed = {}  # pid -> total demand
    first_pid = None
    for it in items:
        pid = it.get("product_id")
        if pid is None:
            continue
        qty = int(it.get("quantity", 1) or 1)
        needed[pid] = needed.get(pid, 0) + qty
        if first_pid is None:
            first_pid = pid
    if not needed:
        return None
    for pid, demand in needed.items():
        cur = conn.execute("SELECT title, stock FROM products WHERE id = ?",
                           (pid,))
        row = cur.fetchone()
        if row is None:
            continue
        title = row[0]
        stock = int(row[1])
        if stock - demand < 0:
            return ("موجودی کافی نیست. محصول: %s. موجودی فعلی: %d. "
                    "تعداد درخواستی: %d" % (title, stock, demand))
    return None


def _apply_stock_delta(conn, product_id, delta):
    # type: (sqlite3.Connection, Optional[int], int) -> None
    """Adjust stock by `delta` (signed). When stock hits 0 the product is
    auto-deactivated; when it rises above 0 it is reactivated (e.g. after a
    soft-delete or edit-stock-restore). Never clamps: stock is only changed
    within a validated transaction, so it never goes negative here.
    """
    if product_id is None:
        return
    delta = int(delta)
    conn.execute(
        "UPDATE products SET stock = stock + ? WHERE id = ?",
        (delta, int(product_id)))
    conn.execute(
        "UPDATE products SET is_active = CASE WHEN stock > 0 THEN 1 ELSE 0 END "
        "WHERE id = ?",
        (int(product_id),))


def check_stock_availability(items):
    # type: (List[Dict[str,Any]]) -> List[Dict[str,Any]]
    """Return list of items that would drop stock below zero.
    Each returned dict has keys: title, requested, available (current stock).
    Only items with a product_id and product_id is not None are checked.
    """
    needed = {}  # product_id -> total demand
    titles = {}
    for it in items:
        pid = it.get("product_id")
        if pid is None:
            continue
        needed[pid] = needed.get(pid, 0) + int(it.get("quantity", 1) or 1)
        titles.setdefault(pid, it.get("title", ""))
    if not needed:
        return []
    conn = _conn()
    shortfalls = []
    try:
        for pid, demand in needed.items():
            cur = conn.execute("SELECT stock, title FROM products WHERE id = ?", (pid,))
            row = cur.fetchone()
            if row is None:
                continue
            stock = int(row[0])
            if stock - demand < 0:
                shortfalls.append({
                    "title": titles.get(pid, row[1]),
                    "requested": demand,
                    "available": stock,
                })
        return shortfalls
    finally:
        conn.close()


def soft_delete_invoice(invoice_id):
    # type: (int) -> None
    conn = _conn()
    try:
        # Restore stock for all items before soft-deleting.
        items = list_invoice_items(invoice_id)
        for it in items:
            if it.get("product_id") is not None:
                _apply_stock_delta(conn, it["product_id"], +int(it["quantity"]))
        conn.execute("UPDATE invoices SET is_deleted = 1 WHERE id = ?", (invoice_id,))
        conn.commit()
    finally:
        conn.close()


def restore_stock_for_invoice(invoice_id, conn=None):
    # type: (int, Optional[sqlite3.Connection]) -> None
    own = conn is None
    if own:
        conn = _conn()
    try:
        items = list_invoice_items(invoice_id)
        for it in items:
            if it.get("product_id") is not None:
                _apply_stock_delta(conn, it["product_id"], +int(it["quantity"]))
    finally:
        if own:
            conn.close()


# --------------------------------------------------------------------------- #
# Invoice archive queries
# --------------------------------------------------------------------------- #

def list_archive_invoices(doctor_filter=None, date_from=None, date_to=None,
                          search_text=""):
    # type: (Optional[int], Optional[str], Optional[str], str) -> List[Dict[str, Any]]
    """doctor_filter=None -> all; 'none' -> بدون معرف; int id -> that doctor.

    date_from/date_to are Gregorian ISO 'YYYY-MM-DD' (inclusive).
    """
    sql = (
        "SELECT i.id, i.invoice_no, i.issued_at, i.total_amount, "
        "p.file_no, p.first_name, p.last_name, "
        "d.id AS doctor_id, d.name AS doctor_name, "
        "(SELECT COALESCE(SUM(pm.amount),0) FROM payments pm "
        " WHERE pm.invoice_id = i.id) AS paid_sum "
        "FROM invoices i "
        "JOIN patients p ON p.id = i.patient_id "
        "LEFT JOIN doctors d ON d.id = i.doctor_id "
        "WHERE i.is_deleted = 0 ")
    params = []
    if doctor_filter == "none":
        sql += "AND i.doctor_id IS NULL "
    elif isinstance(doctor_filter, int):
        sql += "AND i.doctor_id = ? "
        params.append(doctor_filter)
    if date_from:
        sql += "AND i.issued_at >= ? "
        params.append(date_from)
    if date_to:
        sql += "AND i.issued_at <= ? "
        params.append(date_to + " 23:59:59")
    if search_text:
        # Every typed word must match somewhere (name + surname together, or
        # surname first — order of words is free, they just all have to hit).
        # Digits are folded to Latin so Persian-typed queries still match.
        for w in search_text.strip().split():
            like = "%" + _search_word(w) + "%"
            sql += ("AND (p.first_name LIKE ? OR p.last_name LIKE ? "
                    "OR p.file_no LIKE ? OR CAST(i.invoice_no AS TEXT) LIKE ?) ")
            params.extend([like, like, like, like])
    sql += "ORDER BY i.invoice_no DESC"
    conn = _conn()
    try:
        rows = conn.execute(sql, params).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["remaining"] = int(d["total_amount"]) - int(d["paid_sum"])
            d["patient_name"] = ("%s %s" % (d["first_name"], d["last_name"]))
            out.append(d)
        return out
    finally:
        conn.close()


def list_doctors_with_id():
    # type: () -> List[Dict[str, Any]]
    from .database import NO_DOCTOR_NAME
    conn = _conn()
    try:
        cur = conn.execute("SELECT id, name FROM doctors WHERE is_active = 1 "
                           "ORDER BY id")
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Daily report
# --------------------------------------------------------------------------- #

def daily_report(date_iso):
    # type: (str) -> Dict[str, Any]
    """Returns {'payments': [...], 'by_method': [...], 'total': int}.

    summary (by_method): list of {'method','count','total'}.
    detail: list of {'method','paid_at','amount','invoice_no','file_no','patient_name'}.
    Only payments of non-deleted invoices on the given Gregorian date.
    """
    sql = (
        "SELECT pm.method, pm.paid_at, pm.amount, i.id AS invoice_id, "
        "i.invoice_no, p.file_no, p.first_name, p.last_name "
        "FROM payments pm "
        "JOIN invoices i ON i.id = pm.invoice_id "
        "JOIN patients p ON p.id = i.patient_id "
        "WHERE i.is_deleted = 0 AND substr(pm.paid_at,1,10) = ? "
        "ORDER BY pm.paid_at DESC")
    conn = _conn()
    try:
        rows = conn.execute(sql, (date_iso,)).fetchall()
        payments = []
        total = 0
        method_totals = {}  # method -> [count, sum]
        for r in rows:
            d = dict(r)
            d["patient_name"] = "%s %s" % (d["first_name"], d["last_name"])
            payments.append(d)
            total += int(d["amount"])
            key = d["method"]
            if key not in method_totals:
                method_totals[key] = [0, 0]
            method_totals[key][0] += 1
            method_totals[key][1] += int(d["amount"])
        by_method = [{"method": m, "count": method_totals[m][0],
                      "total": method_totals[m][1]}
                     for m in method_totals]
        # فروش (sales): total invoiced amount of invoices issued that day.
        sales = int(conn.execute(
            "SELECT COALESCE(SUM(total_amount),0) FROM invoices "
            "WHERE is_deleted = 0 AND issued_at LIKE ?",
            (date_iso + "%",)).fetchone()[0])
        return {"payments": payments, "by_method": by_method,
                "total": total, "sales": sales,
                "remaining": sales - total}
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Income / expense report
# --------------------------------------------------------------------------- #

def income_expense_report(date_from=None, date_to=None):
    # type: (Optional[str], Optional[str]) -> Dict[str, Any]
    """All amounts integer Toman.

    دریافتی = sum of payments in range.
    هزینه = sum of expenses in range.
    بستانکار = total remaining (total_amount - paid) of non-deleted invoices
             whose issued_at <= date_to (or all if no date_to).
    """
    conn = _conn()
    try:
        income = 0
        expense = 0
        # Income (payments).
        psql = ("SELECT COALESCE(SUM(pm.amount),0) FROM payments pm "
                "JOIN invoices i ON i.id = pm.invoice_id "
                "WHERE i.is_deleted = 0 ")
        pparams = []
        if date_from:
            psql += "AND substr(pm.paid_at,1,10) >= ? "
            pparams.append(date_from)
        if date_to:
            psql += "AND substr(pm.paid_at,1,10) <= ? "
            pparams.append(date_to)
        income = int(conn.execute(psql, pparams).fetchone()[0])

        # Expenses.
        esql = "SELECT COALESCE(SUM(amount),0) FROM expenses WHERE 1=1 "
        eparams = []
        if date_from:
            esql += "AND expense_date >= ? "
            eparams.append(date_from)
        if date_to:
            esql += "AND expense_date <= ? "
            eparams.append(date_to + " 23:59:59")
        expense = int(conn.execute(esql, eparams).fetchone()[0])

        # بستانکار: remaining of non-deleted invoices up to date_to.
        rsql = ("SELECT COALESCE(SUM(i.total_amount),0) - "
                "(SELECT COALESCE(SUM(pm.amount),0) FROM payments pm "
                " JOIN invoices i2 ON i2.id = pm.invoice_id "
                " WHERE i2.is_deleted = 0 "
                " AND (? IS NULL OR i2.issued_at <= ?)) "
                "FROM invoices i WHERE i.is_deleted = 0 ")
        rparams = [date_to + " 23:59:59" if date_to else None,
                   date_to + " 23:59:59" if date_to else None]
        if date_to:
            rsql += "AND i.issued_at <= ? "
            rparams.append(date_to + " 23:59:59")
        receivable = int(conn.execute(rsql, rparams).fetchone()[0])

        # Expenses list.
        esql2 = ("SELECT id, expense_date, amount, description, category FROM expenses "
                 "WHERE 1=1 ")
        eparams2 = []
        if date_from:
            esql2 += "AND expense_date >= ? "
            eparams2.append(date_from)
        if date_to:
            esql2 += "AND expense_date <= ? "
            eparams2.append(date_to + " 23:59:59")
        esql2 += "ORDER BY expense_date DESC, id DESC"
        expenses = [dict(r) for r in conn.execute(esql2, eparams2).fetchall()]

        # Doctor summary: group non-deleted invoices in range by doctor.
        dsql = ("SELECT COALESCE(d.name, 'بدون معرف') AS doctor, "
               "COALESCE(SUM(i.total_amount),0) AS total "
               "FROM invoices i LEFT JOIN doctors d ON d.id = i.doctor_id "
               "WHERE i.is_deleted = 0 ")
        dparams = []
        if date_from:
            dsql += "AND i.issued_at >= ? "
            dparams.append(date_from)
        if date_to:
            dsql += "AND i.issued_at <= ? "
            dparams.append(date_to + " 23:59:59")
        dsql += "GROUP BY doctor ORDER BY total DESC"
        doctor_summary = [dict(r) for r in conn.execute(dsql, dparams).fetchall()]

        # فروش (sales): total invoiced value of non-deleted invoices in range.
        salsql = "SELECT COALESCE(SUM(total_amount),0) FROM invoices WHERE is_deleted = 0 "
        salparams = []
        if date_from:
            salsql += "AND issued_at >= ? "
            salparams.append(date_from)
        if date_to:
            salsql += "AND issued_at <= ? "
            salparams.append(date_to + " 23:59:59")
        sales = int(conn.execute(salsql, salparams).fetchone()[0])

        return {
            "income": income,
            "expense": expense,
            "profit": income - expense,
            "sales": sales,
            "receivable": receivable,
            "expenses": expenses,
            "doctor_summary": doctor_summary,
        }
    finally:
        conn.close()


def add_expense(amount, description, expense_date_iso, category="متفرقه"):
    # type: (int, str, str, str) -> int
    if category is None or category == "":
        category = "متفرقه"
    conn = _conn()
    try:
        cur = conn.execute(
            "INSERT INTO expenses(amount, description, category, expense_date) "
            "VALUES (?, ?, ?, ?)",
            (int(amount), description, category, expense_date_iso))
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def delete_expense(expense_id):
    # type: (int) -> None
    conn = _conn()
    try:
        conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
        conn.commit()
    finally:
        conn.close()


def list_expenses(date_from=None, date_to=None, category=None):
    # type: (Optional[str], Optional[str], Optional[str]) -> List[Dict[str, Any]]
    conn = _conn()
    try:
        sql = ("SELECT id, expense_date, amount, description, category "
               "FROM expenses WHERE 1=1 ")
        params = []
        if date_from:
            sql += "AND expense_date >= ? "
            params.append(date_from)
        if date_to:
            sql += "AND expense_date <= ? "
            params.append(date_to + " 23:59:59")
        if category and category != "all":
            sql += "AND category = ? "
            params.append(category)
        sql += "ORDER BY expense_date DESC, id DESC"
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Doctor referral report
# --------------------------------------------------------------------------- #

def doctor_referral_report(doctor_id_or_none, date_from=None, date_to=None):
    # type: (Optional[int], Optional[str], Optional[str]) -> Dict[str, Any]
    """Get unique patients of the doctor in the invoice date range.

    doctor_id_or_none: int id, "none" string for بدون معرف, or None for all.
    Returns {'rows': [...], 'count': int}.
    Columns: file_no, patient_name, invoice_count, total_sum, paid_sum,
             remaining, last_invoice_date (ISO).
    """
    conn = _conn()
    try:
        # Shared WHERE clause builder (text order = params order).
        def _clauses():
            clauses = []
            params = []
            if doctor_id_or_none == "none":
                clauses.append("i.doctor_id IS NULL")
            elif isinstance(doctor_id_or_none, int):
                clauses.append("i.doctor_id = ?")
                params.append(doctor_id_or_none)
            if date_from:
                clauses.append("i.issued_at >= ?")
                params.append(date_from)
            if date_to:
                clauses.append("i.issued_at <= ?")
                params.append(date_to + " 23:59:59")
            return clauses, params

        clauses, prm = _clauses()
        where = (" AND " + " AND ".join(clauses)) if clauses else ""

        # Per-doctor invoice totals (a doctor = one stock batch of referrals).
        inv_sql = (
            "SELECT COALESCE(d.id,0) AS doctor_id, "
            "COALESCE(d.name,'بدون معرف') AS doctor_name, "
            "COUNT(i.id) AS invoice_count, "
            "COALESCE(SUM(i.total_amount),0) AS total_sum, "
            "MAX(i.issued_at) AS last_invoice_date "
            "FROM invoices i LEFT JOIN doctors d ON d.id = i.doctor_id "
            "WHERE i.is_deleted = 0" + where + " "
            "GROUP BY COALESCE(d.id,0), COALESCE(d.name,'بدون معرف') "
            "ORDER BY doctor_name"
        )
        inv_rows = conn.execute(inv_sql, prm).fetchall()

        # Per-doctor payments (separate so SUM isn't inflated by row joins).
        pay_sql = (
            "SELECT COALESCE(d.id,0) AS doctor_id, "
            "COALESCE(SUM(pm.amount),0) AS paid_sum "
            "FROM payments pm JOIN invoices i ON i.id = pm.invoice_id "
            "LEFT JOIN doctors d ON d.id = i.doctor_id "
            "WHERE i.is_deleted = 0" + where + " "
            "GROUP BY COALESCE(d.id,0)"
        )
        pay_rows = conn.execute(pay_sql, prm).fetchall()
        pay_map = {r["doctor_id"]: int(r["paid_sum"]) for r in pay_rows}

        out = []
        for r in inv_rows:
            d = dict(r)
            d["paid_sum"] = pay_map.get(d["doctor_id"], 0)
            d["remaining"] = int(d["total_sum"]) - d["paid_sum"]
            out.append(d)
        return {"rows": out, "count": len(out)}
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# New financial / referral reports (business requirements 8A-8D)
# --------------------------------------------------------------------------- #

def receipts_report(start_date, end_date):
    # type: (Optional[str], Optional[str]) -> Dict[str, Any]
    """8A. Receipts (cash in) based on payments.paid_at.

    Returns:
        total_received: int
        summary_by_method: list of {'method','count','amount'}
        payment_details: list of {'payment_id','paid_at','method','amount',
                                  'invoice_no','patient_name','patient_file_no'}
    Only payments of non-deleted invoices in the Gregorian-ISO date range.
    """
    conn = _conn()
    try:
        sql = (
            "SELECT pm.id AS payment_id, pm.paid_at, pm.method, pm.amount, "
            "i.invoice_no, p.file_no AS patient_file_no, "
            "p.first_name, p.last_name "
            "FROM payments pm "
            "JOIN invoices i ON i.id = pm.invoice_id "
            "JOIN patients p ON p.id = i.patient_id "
            "WHERE i.is_deleted = 0 ")
        params = []
        if start_date:
            sql += "AND substr(pm.paid_at,1,10) >= ? "
            params.append(start_date)
        if end_date:
            sql += "AND substr(pm.paid_at,1,10) <= ? "
            params.append(end_date)
        sql += "ORDER BY pm.paid_at DESC, pm.id DESC"
        rows = conn.execute(sql, params).fetchall()
        total_received = 0
        method_totals = {}  # method -> [count, sum]
        payment_details = []
        for r in rows:
            d = dict(r)
            d["patient_name"] = "%s %s" % (d["first_name"], d["last_name"])
            amount = int(d["amount"])
            total_received += amount
            method = d["method"]
            if method not in method_totals:
                method_totals[method] = [0, 0]
            method_totals[method][0] += 1
            method_totals[method][1] += amount
            d["amount"] = amount
            payment_details.append(d)
        summary_by_method = [
            {"method": m, "count": method_totals[m][0],
             "amount": method_totals[m][1]}
            for m in method_totals]
        return {
            "total_received": total_received,
            "summary_by_method": summary_by_method,
            "payment_details": payment_details,
        }
    finally:
        conn.close()


def expenses_report(start_date, end_date):
    # type: (Optional[str], Optional[str]) -> Dict[str, Any]
    """8B. Expenses based on expenses.expense_date.

    Returns:
        total_expense: int
        summary_by_category: list of {'category','count','amount'}
        expense_details: list of {'id','expense_date','amount','description',
                                  'category'}
    """
    conn = _conn()
    try:
        sql = ("SELECT id, expense_date, amount, description, category "
               "FROM expenses WHERE 1=1 ")
        params = []
        if start_date:
            sql += "AND expense_date >= ? "
            params.append(start_date)
        if end_date:
            sql += "AND expense_date <= ? "
            params.append(end_date + " 23:59:59")
        sql += "ORDER BY expense_date DESC, id DESC"
        rows = conn.execute(sql, params).fetchall()
        total_expense = 0
        cat_totals = {}  # category -> [count, sum]
        expense_details = []
        for r in rows:
            d = dict(r)
            amount = int(d["amount"])
            total_expense += amount
            cat = d.get("category") or "متفرقه"
            if cat not in cat_totals:
                cat_totals[cat] = [0, 0]
            cat_totals[cat][0] += 1
            cat_totals[cat][1] += amount
            expense_details.append(d)
        summary_by_category = [
            {"category": c, "count": cat_totals[c][0],
             "amount": cat_totals[c][1]}
            for c in cat_totals]
        return {
            "total_expense": total_expense,
            "summary_by_category": summary_by_category,
            "expense_details": expense_details,
        }
    finally:
        conn.close()


def sales_profit_report(start_date, end_date):
    # type: (Optional[str], Optional[str]) -> Dict[str, Any]
    """8C. Sales & profit report based on non-deleted invoices.issued_at.

    receipts (payments) != sales (invoices): here we report SALES/PROFIT only.
    Returns:
        invoice_count: int
        gross_sales: int        = SUM(total_amount)
        cost_of_goods_sold: int = SUM(total_cost)
        gross_profit: int       = gross_sales - cogs
        total_expenses: int     = SUM(expenses) in range
        net_profit: int         = gross_profit - total_expenses
        summary_by_doctor: list of {'doctor','invoice_count','gross_sales',
                                    'total_cost','profit'}
        summary_by_product: list of {'product','quantity','row_total',
                                     'row_cost','profit'}
    """
    conn = _conn()
    try:
        # ---- Invoices / sales in range (non-deleted).
        isql = (
            "SELECT i.id, i.invoice_no, i.total_amount, i.total_cost, "
            "i.total_profit, i.doctor_id "
            "FROM invoices i WHERE i.is_deleted = 0 ")
        iparams = []
        if start_date:
            isql += "AND i.issued_at >= ? "
            iparams.append(start_date)
        if end_date:
            isql += "AND i.issued_at <= ? "
            iparams.append(end_date + " 23:59:59")
        inv_rows = conn.execute(isql, iparams).fetchall()
        invoice_count = len(inv_rows)
        gross_sales = sum(int(r["total_amount"]) for r in inv_rows)
        cost_of_goods_sold = sum(int(r["total_cost"]) for r in inv_rows)
        gross_profit = gross_sales - cost_of_goods_sold

        # ---- Expenses in range.
        esql = "SELECT COALESCE(SUM(amount),0) FROM expenses WHERE 1=1 "
        eparams = []
        if start_date:
            esql += "AND expense_date >= ? "
            eparams.append(start_date)
        if end_date:
            esql += "AND expense_date <= ? "
            eparams.append(end_date + " 23:59:59")
        total_expenses = int(conn.execute(esql, eparams).fetchone()[0])
        net_profit = gross_profit - total_expenses

        # ---- Summary by doctor (join on the same filtered set).
        dsql = (
            "SELECT COALESCE(d.name, 'بدون معرف') AS doctor, "
            "COUNT(i.id) AS invoice_count, "
            "COALESCE(SUM(i.total_amount),0) AS gross_sales, "
            "COALESCE(SUM(i.total_cost),0) AS total_cost "
            "FROM invoices i LEFT JOIN doctors d ON d.id = i.doctor_id "
            "WHERE i.is_deleted = 0 ")
        dparams = []
        if start_date:
            dsql += "AND i.issued_at >= ? "
            dparams.append(start_date)
        if end_date:
            dsql += "AND i.issued_at <= ? "
            dparams.append(end_date + " 23:59:59")
        dsql += ("GROUP BY doctor "
                 "ORDER BY gross_sales DESC")
        summary_by_doctor = []
        for r in conn.execute(dsql, dparams).fetchall():
            sales = int(r["gross_sales"])
            cost = int(r["total_cost"])
            summary_by_doctor.append({
                "doctor": r["doctor"],
                "invoice_count": int(r["invoice_count"]),
                "gross_sales": sales,
                "total_cost": cost,
                "profit": sales - cost,
            })

        # ---- Summary by product (items of non-deleted invoices in range).
        # Group by product_id (the stock "batch"), NOT title: per the stock-batch
        # model each batch is its own products row, even when several batches
        # share the same title. Grouping by title would merge different cost
        # bases and misstate profit. Items without a product fall back to their
        # free-text title so product-less rows aren't all lumped together.
        psql = (
            "SELECT CASE WHEN ii.product_id IS NULL THEN ii.title "
            "            ELSE CAST(ii.product_id AS TEXT) END AS grp, "
            "COALESCE(NULLIF(ii.title,''),'بدون عنوان') AS product, "
            "SUM(ii.quantity) AS quantity, "
            "SUM(ii.row_total) AS row_total, "
            "SUM(ii.row_cost) AS row_cost "
            "FROM invoice_items ii "
            "JOIN invoices i ON i.id = ii.invoice_id "
            "WHERE i.is_deleted = 0 ")
        pparams = []
        if start_date:
            psql += "AND i.issued_at >= ? "
            pparams.append(start_date)
        if end_date:
            psql += "AND i.issued_at <= ? "
            pparams.append(end_date + " 23:59:59")
        psql += ("GROUP BY grp "
                 "ORDER BY row_total DESC")
        summary_by_product = []
        for r in conn.execute(psql, pparams).fetchall():
            row_total = int(r["row_total"])
            row_cost = int(r["row_cost"])
            summary_by_product.append({
                "product": r["product"],
                "quantity": int(r["quantity"]),
                "row_total": row_total,
                "row_cost": row_cost,
                "profit": row_total - row_cost,
            })

        return {
            "invoice_count": invoice_count,
            "gross_sales": gross_sales,
            "cost_of_goods_sold": cost_of_goods_sold,
            "gross_profit": gross_profit,
            "total_expenses": total_expenses,
            "net_profit": net_profit,
            "summary_by_doctor": summary_by_doctor,
            "summary_by_product": summary_by_product,
        }
    finally:
        conn.close()


def product_sales_report(start_date=None, end_date=None):
    # type: (Optional[str], Optional[str]) -> Dict[str, Any]
    """Product sales report: per product/batch sales in a Gregorian-ISO range.

    Grouped by product_id (the stock "batch"), so two batches with the same
    title but different cost bases are kept separate. Product-less items fall
    back to their free-text title.

    Returns:
        rows: list of {'product_id','title','quantity','units_sold_f',
                       'row_total','row_cost','profit','row_total_f',
                       'row_cost_f','profit_f'}
        total_quantity: int
        total_revenue: int
        total_cost: int
        total_profit: int
        invoice_count: int
    """
    conn = _conn()
    try:
        sql = (
            "SELECT ii.product_id, "
            "CASE WHEN ii.product_id IS NULL THEN ii.title "
            "     ELSE COALESCE(NULLIF(ii.title,''),'بدون عنوان') END AS title, "
            "SUM(ii.quantity) AS quantity, "
            "SUM(ii.row_total) AS row_total, "
            "SUM(ii.row_cost) AS row_cost "
            "FROM invoice_items ii "
            "JOIN invoices i ON i.id = ii.invoice_id "
            "WHERE i.is_deleted = 0 ")
        params = []
        if start_date:
            sql += "AND i.issued_at >= ? "
            params.append(start_date)
        if end_date:
            sql += "AND i.issued_at <= ? "
            params.append(end_date + " 23:59:59")
        sql += ("GROUP BY ii.product_id, title "
                "ORDER BY row_total DESC")
        rows = []
        total_qty = total_rev = total_cost = 0
        for r in conn.execute(sql, params).fetchall():
            qty = int(r["quantity"])
            rev = int(r["row_total"])
            cost = int(r["row_cost"])
            total_qty += qty
            total_rev += rev
            total_cost += cost
            rows.append({
                "product_id": r["product_id"],
                "title": r["title"],
                "quantity": qty,
                "row_total": rev,
                "row_cost": cost,
                "profit": rev - cost,
            })
        icount = int(conn.execute(
            "SELECT COUNT(*) FROM invoices i WHERE i.is_deleted = 0 "
            + ("AND i.issued_at >= ? " if start_date else "")
            + ("AND i.issued_at <= ? " if end_date else ""),
            tuple([x for x in (start_date, end_date + " 23:59:59" if end_date else None) if x is not None])).fetchone()[0])
        return {
            "rows": rows,
            "total_quantity": total_qty,
            "total_revenue": total_rev,
            "total_cost": total_cost,
            "total_profit": total_rev - total_cost,
            "invoice_count": icount,
        }
    finally:
        conn.close()


def doctor_report(doctor_id, start_date, end_date):
    # type: (int, Optional[str], Optional[str]) -> Dict[str, Any]
    """8D. Detailed doctor report for one doctor in a Gregorian-ISO range.

    doctor_id is an int (the همان doctor). Use 'withoutreferrer' semantics at
    the caller level; this function expects a real doctor id.

    Returns:
        unique_patient_count: int
        invoice_count: int
        total_sales: int
        total_cost: int
        total_profit: int
        total_received: int     (payments for this doctor's invoices)
        total_remaining: int    (total_sales - total_received)
        patients_summary: list of {'file_no','patient_name','invoice_count',
                                    'total_sales','total_received','remaining'}
        invoices_summary: list of {'invoice_no','issued_at','patient_name',
                                    'total_amount','total_cost','total_profit',
                                    'total_received','remaining'}
        invoice_items_detail: list with ONE ROW PER INVOICE ITEM:
            {'invoice_id','invoice_no','issued_at','patient_name',
             'patient_file_no','doctor_name','product_title','quantity',
             'unit_price','cost_price','row_total','row_cost','row_profit'}
    """
    conn = _conn()
    try:
        doctor_name = doctor_name_for(doctor_id)

        # ---- Invoices for this doctor in range.
        isql = (
            "SELECT i.id, i.invoice_no, i.issued_at, i.total_amount, "
            "i.total_cost, i.total_profit, p.id AS patient_id, "
            "p.file_no AS patient_file_no, p.first_name, p.last_name "
            "FROM invoices i "
            "JOIN patients p ON p.id = i.patient_id "
            "WHERE i.is_deleted = 0 AND i.doctor_id = ? ")
        iparams = [doctor_id]
        if start_date:
            isql += "AND i.issued_at >= ? "
            iparams.append(start_date)
        if end_date:
            isql += "AND i.issued_at <= ? "
            iparams.append(end_date + " 23:59:59")
        isql += "ORDER BY i.invoice_no"
        inv_rows = conn.execute(isql, iparams).fetchall()

        invoice_count = len(inv_rows)
        total_sales = sum(int(r["total_amount"]) for r in inv_rows)
        total_cost = sum(int(r["total_cost"]) for r in inv_rows)
        total_profit = sum(int(r["total_profit"]) for r in inv_rows)

        # ---- Payments per invoice.
        invoice_ids = [int(r["id"]) for r in inv_rows]
        received_by_invoice = {}  # invoice_id -> received
        if invoice_ids:
            placeholders = ",".join("?" * len(invoice_ids))
            psql = ("SELECT invoice_id, COALESCE(SUM(amount),0) AS received "
                    "FROM payments WHERE invoice_id IN (%s) "
                    "GROUP BY invoice_id" % placeholders)
            for r in conn.execute(psql, invoice_ids).fetchall():
                received_by_invoice[int(r["invoice_id"])] = int(r["received"])
        total_received = sum(received_by_invoice.values())
        total_remaining = total_sales - total_received

        # ---- Patients summary & invoices summary.
        patients_agg = {}  # patient_id -> {counts/totals}
        invoices_summary = []
        for r in inv_rows:
            inv_id = int(r["id"])
            received = received_by_invoice.get(inv_id, 0)
            patient_name = "%s %s" % (r["first_name"], r["last_name"])
            invoices_summary.append({
                "invoice_no": int(r["invoice_no"]),
                "issued_at": r["issued_at"],
                "patient_name": patient_name,
                "total_amount": int(r["total_amount"]),
                "total_cost": int(r["total_cost"]),
                "total_profit": int(r["total_profit"]),
                "total_received": received,
                "remaining": int(r["total_amount"]) - received,
            })
            pid = int(r["patient_id"])
            if pid not in patients_agg:
                patients_agg[pid] = {
                    "file_no": r["patient_file_no"],
                    "patient_name": patient_name,
                    "invoice_count": 0,
                    "total_sales": 0,
                    "total_received": 0,
                }
            pa = patients_agg[pid]
            pa["invoice_count"] += 1
            pa["total_sales"] += int(r["total_amount"])
            pa["total_received"] += received
        patients_summary = []
        for pa in patients_agg.values():
            pa["remaining"] = pa["total_sales"] - pa["total_received"]
            patients_summary.append(pa)
        patients_summary.sort(key=lambda x: x["file_no"])
        unique_patient_count = len(patients_summary)

        # ---- Invoice items detail: one row per item, enriched with
        # invoice/patient/doctor data.
        detail = []
        if invoice_ids:
            placeholders = ",".join("?" * len(invoice_ids))
            dsql = (
                "SELECT ii.invoice_id, ii.product_id, ii.title AS product_title, "
                "ii.quantity, ii.unit_price, ii.cost_price, ii.row_total, "
                "ii.row_cost, ii.row_profit, "
                "i.invoice_no, i.issued_at, "
                "p.file_no AS patient_file_no, p.first_name, p.last_name "
                "FROM invoice_items ii "
                "JOIN invoices i ON i.id = ii.invoice_id "
                "JOIN patients p ON p.id = i.patient_id "
                "WHERE ii.invoice_id IN (%s) "
                "ORDER BY i.invoice_no, ii.id" % placeholders)
            for r in conn.execute(dsql, invoice_ids).fetchall():
                detail.append({
                    "invoice_id": int(r["invoice_id"]),
                    "invoice_no": int(r["invoice_no"]),
                    "issued_at": r["issued_at"],
                    "patient_name": "%s %s" % (r["first_name"], r["last_name"]),
                    "patient_file_no": r["patient_file_no"],
                    "doctor_name": doctor_name,
                    "product_title": r["product_title"],
                    "quantity": int(r["quantity"]),
                    "unit_price": int(r["unit_price"]),
                    "cost_price": int(r["cost_price"]),
                    "row_total": int(r["row_total"]),
                    "row_cost": int(r["row_cost"]),
                    "row_profit": int(r["row_profit"]),
                })

        return {
            "doctor_name": doctor_name,
            "unique_patient_count": unique_patient_count,
            "invoice_count": invoice_count,
            "total_sales": total_sales,
            "total_cost": total_cost,
            "total_profit": total_profit,
            "total_received": total_received,
            "total_remaining": total_remaining,
            "patients_summary": patients_summary,
            "invoices_summary": invoices_summary,
            "invoice_items_detail": detail,
        }
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _conn():
    # type: () -> sqlite3.Connection
    from .database import get_connection
    return get_connection()


def doctor_name_for(doctor_id):
    # type: (Optional[int]) -> str
    if doctor_id is None:
        return "بدون معرف"
    conn = _conn()
    try:
        cur = conn.execute("SELECT name FROM doctors WHERE id = ?", (doctor_id,))
        row = cur.fetchone()
        return row[0] if row else "بدون معرف"
    finally:
        conn.close()


def next_invoice_no_stub():
    # type: () -> int
    """UI-only convenience wrapper around database.next_invoice_no()."""
    from .database import next_invoice_no
    return next_invoice_no()
