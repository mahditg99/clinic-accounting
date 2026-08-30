# -*- coding: utf-8 -*-
"""SQLite database connection, schema creation and first-run seeding."""
from __future__ import annotations

import datetime as _dt
import os
import shutil
import sqlite3
import sys
from typing import List, Optional

from . import date_utils

DB_NAME = "azaran_teb.db"
BACKUP_DIR = "backups"
BACKUP_PREFIX = "clinic_backup_"
MAX_BACKUPS = 5


def _base_dir():
    # type: () -> str
    """Directory that holds azaran_teb.db and backups/.

    * Source run: the project folder (parent of the ``app`` package).
    * Frozen exe (PyInstaller): the folder containing the exe, so the app is
      portable and data survives restarts (``__file__`` would point into a
      temporary extraction dir that is wiped on exit).
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Invoice numbering starts at 1000 (clinic convention); existing lower numbers
# are renumbered once at startup by _ensure_invoice_no_floor().
INVOICE_NO_FLOOR = 1000

# The default "no referrer" doctor name. It is created at seed time and
# must never be deleted (only deactivated via is_active flag).
NO_DOCTOR_NAME = "بدون معرف"  # بدون معرف

_DEFAULT_PAYMENT_METHODS = ["پوز", "نقد",
                            "انتقال", "چک"]  # پوز، نقد، انتقال، چک

_DEFAULT_EXPENSE_CATEGORIES = [
    "حقوق", "اجاره", "خرید تجهیزات", "قبوض", "متفرقه",
]  # حقوق، اجاره، خرید تجهیزات، قبوض، متفرقه

_SCHEMA = """
CREATE TABLE IF NOT EXISTS patients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_no TEXT UNIQUE NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    gender TEXT CHECK(gender IN ('male','female','')) DEFAULT '',
    is_active INTEGER DEFAULT 1,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS doctors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    is_active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    price INTEGER DEFAULT 0,
    purchase_price INTEGER DEFAULT 0,
    sale_price INTEGER DEFAULT 0,
    stock INTEGER DEFAULT 0,
    low_stock_warning INTEGER DEFAULT 0,
    description TEXT DEFAULT '',
    sort_order INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_no INTEGER UNIQUE NOT NULL,
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    doctor_id INTEGER REFERENCES doctors(id),
    issued_at TEXT NOT NULL,
    total_amount INTEGER DEFAULT 0,
    total_cost INTEGER DEFAULT 0,
    total_profit INTEGER DEFAULT 0,
    notes TEXT DEFAULT '',
    is_deleted INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS invoice_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id),
    product_id INTEGER REFERENCES products(id),
    title TEXT NOT NULL,
    unit_price INTEGER DEFAULT 0,
    cost_price INTEGER DEFAULT 0,
    quantity INTEGER DEFAULT 1,
    row_total INTEGER DEFAULT 0,
    row_cost INTEGER DEFAULT 0,
    row_profit INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id),
    method TEXT NOT NULL,
    amount INTEGER DEFAULT 0,
    paid_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    amount INTEGER DEFAULT 0,
    description TEXT DEFAULT '',
    category TEXT DEFAULT 'متفرقه',
    expense_date TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE INDEX IF NOT EXISTS idx_invoice_items_invoice ON invoice_items(invoice_id);
CREATE INDEX IF NOT EXISTS idx_payments_invoice ON payments(invoice_id);
CREATE INDEX IF NOT EXISTS idx_invoices_patient ON invoices(patient_id);
CREATE INDEX IF NOT EXISTS idx_invoices_doctor ON invoices(doctor_id);
"""


def _db_path():
    # type: () -> str
    return os.path.join(_base_dir(), DB_NAME)


def get_connection():
    # type: () -> sqlite3.Connection
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    # type: () -> None
    # Back up the existing DB before any migration touches it.
    backup_path = _backup_db()

    conn = get_connection()
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
        migrated = _migrate(conn)
        if _ensure_invoice_no_floor(conn):
            migrated = True
        if backup_path is not None:
            if migrated:
                # Keep the backup (something changed this run).
                _prune_backups()
            else:
                # Nothing migrated; the snapshot was identical to live DB.
                _remove_file(backup_path)
        if _is_empty(conn):
            pass
            # _seed(conn)
        _ensure_required_settings(conn)
        conn.commit()
    finally:
        conn.close()


def _is_empty(conn):
    # type: (sqlite3.Connection) -> bool
    cur = conn.execute("SELECT COUNT(*) FROM doctors")
    count = cur.fetchone()[0]
    return count == 0


def _ensure_invoice_no_floor(conn):
    # type: (sqlite3.Connection) -> bool
    """One-time renumbering so invoice numbers start at INVOICE_NO_FLOOR (1000).

    If any invoice_no is below the floor, all invoices are renumbered in
    issue-date order (oldest = 1000). A two-pass update (temporary high
    range first) avoids UNIQUE collisions mid-way. Returns True if changed.
    """
    cur = conn.execute("SELECT MIN(invoice_no), COUNT(*) FROM invoices")
    mn, cnt = cur.fetchone()
    if not cnt or mn is None or int(mn) >= INVOICE_NO_FLOOR:
        return False
    rows = conn.execute(
        "SELECT id FROM invoices ORDER BY issued_at, id").fetchall()
    temp_base = 1000000
    for k, r in enumerate(rows):
        conn.execute("UPDATE invoices SET invoice_no = ? WHERE id = ?",
                     (temp_base + k, r["id"]))
    for k, r in enumerate(rows):
        conn.execute("UPDATE invoices SET invoice_no = ? WHERE id = ?",
                     (INVOICE_NO_FLOOR + k, r["id"]))
    return True


# --------------------------------------------------------------------------- #
# Backup (pre-migration snapshot)
# --------------------------------------------------------------------------- #

def _backup_dir():
    # type: () -> str
    return os.path.join(_base_dir(), BACKUP_DIR)


def _backup_db():
    # type: () -> Optional[str]
    """Copy azaran_teb.db to backups/clinic_backup_YYYYMMDD_HHMMSS.db.

    Returns the backup path, or None if there is no DB to back up. Safe to
    call before the DB exists (fresh install). Never raises — logs to
    migrate.log on failure.
    """
    src = _db_path()
    if not os.path.exists(src) or os.path.getsize(src) == 0:
        return None
    bdir = _backup_dir()
    try:
        if not os.path.isdir(bdir):
            os.makedirs(bdir)
    except OSError:
        return None
    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")  # local time
    dest = os.path.join(bdir, BACKUP_PREFIX + stamp + ".db")
    try:
        shutil.copy2(src, dest)
    except OSError as exc:
        _log("backup failed: %s" % str(exc))
        return None
    return dest


def _prune_backups():
    # type: () -> None
    bdir = _backup_dir()
    if not os.path.isdir(bdir):
        return
    try:
        files = [f for f in os.listdir(bdir)
                 if f.startswith(BACKUP_PREFIX) and f.endswith(".db")]
    except OSError:
        return
    if len(files) <= MAX_BACKUPS:
        return
    # Oldest first by mtime.
    files.sort(key=lambda f: os.path.getmtime(os.path.join(bdir, f)))
    for f in files[:-MAX_BACKUPS]:
        try:
            os.remove(os.path.join(bdir, f))
        except OSError:
            pass


def _remove_file(path):
    # type: (str) -> None
    try:
        os.remove(path)
    except OSError:
        pass


def _log(message):
    # type: (str) -> None
    try:
        bdir = _backup_dir()
        if not os.path.isdir(bdir):
            os.makedirs(bdir)
        with open(os.path.join(bdir, "migrate.log"), "a", encoding="utf-8") as fh:
            stamp = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            fh.write("[%s] %s\n" % (stamp, message))
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# Migration (additive, idempotent, never drops tables or data)
# --------------------------------------------------------------------------- #

def _has_column(conn, table, column):
    # type: (sqlite3.Connection, str, str) -> bool
    cur = conn.execute("PRAGMA table_info(%s)" % table)
    for row in cur.fetchall():
        if row[1] == column:  # PRAGMA column index 1 is the name
            return True
    return False


def _add_column_if_missing(conn, table, column, definition):
    # type: (sqlite3.Connection, str, str, str) -> bool
    """Add `column` to `table` if absent. Returns True if it was added.

    `definition` is the full column-spec after the name, e.g. 'INTEGER DEFAULT 0'.
    Uses parameter-safe identifier quoting (table/column names are internal
    constants, not user input).
    """
    if _has_column(conn, table, column):
        return False
    q = 'ALTER TABLE "%s" ADD COLUMN "%s" %s' % (table, column, definition)
    try:
        conn.execute(q)
    except sqlite3.OperationalError as exc:
        # Column may have been added by a concurrent process; treat as no-op.
        _log("add column failed (%s.%s): %s" % (table, column, str(exc)))
        return False
    return True


def _migrate(conn):
    # type: (sqlite3.Connection) -> bool
    """Apply additive schema migration. Returns True if any column was added."""
    added = []  # list of (table, column)

    # products: purchase_price, sale_price, is_active (older builds may
    # have products without is_active; CREATE TABLE IF NOT EXISTS does NOT
    # add columns to an existing table, so migrate them explicitly).
    if _add_column_if_missing(conn, "products", "purchase_price", "INTEGER DEFAULT 0"):
        added.append(("products", "purchase_price"))
    if _add_column_if_missing(conn, "products", "sale_price", "INTEGER DEFAULT 0"):
        added.append(("products", "sale_price"))
    if _add_column_if_missing(conn, "products", "is_active", "INTEGER DEFAULT 1"):
        added.append(("products", "is_active"))

    # invoice_items: cost_price, row_cost, row_profit
    if _add_column_if_missing(conn, "invoice_items", "cost_price", "INTEGER DEFAULT 0"):
        added.append(("invoice_items", "cost_price"))
    if _add_column_if_missing(conn, "invoice_items", "row_cost", "INTEGER DEFAULT 0"):
        added.append(("invoice_items", "row_cost"))
    if _add_column_if_missing(conn, "invoice_items", "row_profit", "INTEGER DEFAULT 0"):
        added.append(("invoice_items", "row_profit"))

    # invoices: total_cost, total_profit
    if _add_column_if_missing(conn, "invoices", "total_cost", "INTEGER DEFAULT 0"):
        added.append(("invoices", "total_cost"))
    if _add_column_if_missing(conn, "invoices", "total_profit", "INTEGER DEFAULT 0"):
        added.append(("invoices", "total_profit"))

    # expenses: category
    if _add_column_if_missing(conn, "expenses", "category", "TEXT DEFAULT 'متفرقه'"):
        added.append(("expenses", "category"))

    # doctors: structured contact/identity columns (item 15)
    for col in ("first_name", "last_name", "specialty", "address", "phone"):
        if _add_column_if_missing(conn, "doctors", col, "TEXT DEFAULT ''"):
            added.append(("doctors", col))
    # patients: contact columns (item 15)
    if _add_column_if_missing(conn, "patients", "phone", "TEXT DEFAULT ''"):
        added.append(("patients", "phone"))
    if _add_column_if_missing(conn, "patients", "address", "TEXT DEFAULT ''"):
        added.append(("patients", "address"))

    # Backfill doctors first/last name from the legacy single `name` column
    # (only for rows created before the structured fields existed).
    added_cols = [c for _, c in added]
    if "first_name" in added_cols and _has_column(conn, "doctors", "name"):
        rows = conn.execute(
            "SELECT id, name FROM doctors "
            "WHERE name IS NOT NULL AND trim(name) <> ''").fetchall()
        for rid, nm in rows:
            parts = str(nm).split(None, 1)
            fn = parts[0] if parts else ""
            ln = parts[1] if len(parts) > 1 else ""
            if fn or ln:
                conn.execute(
                    "UPDATE doctors SET first_name = ?, last_name = ? "
                    "WHERE id = ? AND (first_name IS NULL OR first_name = '')",
                    (fn, ln, rid))

    # Backfill data (guarded by column existence so it is safe to repeat on
    # any legacy schema). If sale_price just added, copy old price into it.
    # NOTE: 'price' is kept as a legacy mirror column (never dropped).
    if ("products", "sale_price") in added:
        conn.execute("UPDATE products SET sale_price = price "
                     "WHERE sale_price = 0 AND price > 0")
    # Deactivate zero/empty-stock products per the new stock-batch rule.
    # Guarded: only run if is_active exists (older schemas that lacked it
    # just had it added above).
    if _has_column(conn, "products", "is_active"):
        conn.execute("UPDATE products SET is_active = 0 WHERE stock <= 0")

    # Old invoice_items: cost unknown -> treat profit as full row_total
    # (overstates profit for old data; documented). Safe and idempotent.
    if ("invoice_items", "row_profit") in added:
        conn.execute("UPDATE invoice_items SET row_cost = 0, "
                     "row_profit = row_total WHERE row_profit = 0")
    if ("invoice_items", "cost_price") in added:
        conn.execute("UPDATE invoice_items SET cost_price = 0 "
                     "WHERE cost_price IS NULL")

    # Old invoices: no item cost recorded -> assume total_profit = total_amount
    # (approximate; documented in report note). Safe and idempotent.
    if ("invoices", "total_profit") in added:
        conn.execute("UPDATE invoices SET total_cost = 0, "
                     "total_profit = total_amount WHERE total_profit = 0")
    if ("invoices", "total_cost") in added:
        conn.execute("UPDATE invoices SET total_cost = 0 "
                     "WHERE total_cost IS NULL")

    # Normalize any NULL category on existing expenses.
    if ("expenses", "category") in added:
        conn.execute("UPDATE expenses SET category = 'متفرقه' "
                     "WHERE category IS NULL OR category = ''")

    if added:
        conn.commit()
        _log("migration added columns: %s" %
             ", ".join("%s.%s" % t for t in added))
    return len(added) > 0


def _ensure_required_settings(conn):
    # type: (sqlite3.Connection) -> None
    defaults = {
        "app_title": "آذران طب",  # آذران طب
        "version": "1.0.0",
        "update_invoice_date_on_edit": "0",
        "show_doctor_in_print": "0",
        "print_size": "A4",
        "expense_categories": "\n".join(_DEFAULT_EXPENSE_CATEGORIES),
        # Note: payment_methods is also seeded on first run via _seed(); listing
        # it here makes the app self-heal if a deployed DB loses the key (the
        # getter has a fallback, but persisting the default keeps it consistent).
        "payment_methods": "\n".join(_DEFAULT_PAYMENT_METHODS),
    }
    for key, value in defaults.items():
        cur = conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cur.fetchone()
        if row is None:
            conn.execute("INSERT INTO settings(key, value) VALUES (?, ?)",
                         (key, value))


def _seed(conn):
    # type: (sqlite3.Connection) -> None
    now_iso = date_utils.now_iso()
    today_iso = date_utils.today_iso()

    # Default doctor "بدون معرف".
    conn.execute("INSERT INTO doctors(name, is_active) VALUES (?, 1)",
                 (NO_DOCTOR_NAME,))
    cur = conn.execute("SELECT id FROM doctors WHERE name = ?", (NO_DOCTOR_NAME,))
    no_doctor_id = cur.fetchone()[0]

    # Sample products. Each tuple: title, purchase_price, sale_price, stock,
    # low_stock_warning, description, sort_order. `price` mirrors sale_price.
    products = [
        ("AFO بزرگسالان", 600000, 850000, 5, 2, "AFO بزرگسالان", 1),  # noqa
        ("ابداکشن بریس بزرگسال", 500000, 720000, 3, 2,  # noqa
         "ابداکشن بریس بزرگسال", 2),
        ("صندل ارتوپدیک", 280000, 380000, 8, 3, "صندل ارتوپدیک", 3),  # noqa
    ]
    for title, purchase_price, sale_price, stock, low, desc, sort_order in products:
        conn.execute(
            "INSERT INTO products(title, price, purchase_price, sale_price, "
            "stock, low_stock_warning, description, sort_order, is_active) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)",
            (title, sale_price, purchase_price, sale_price, stock, low, desc,
             sort_order))

    # One sample patient.
    # conn.execute(
    #     "INSERT INTO patients(file_no, first_name, last_name, gender, "
    #     "is_active, created_at) VALUES (?, ?, ?, ?, 1, ?)",
    #     ("1001", "علی", "رضایی", "male", now_iso))  # علی رضایی
    cur = conn.execute("SELECT id FROM patients WHERE file_no = ?", ("1001",))
    patient_id = cur.fetchone()[0]

    # Insert payment methods into settings.
    methods = "\n".join(_DEFAULT_PAYMENT_METHODS)
    conn.execute("INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)",
                 ("payment_methods", methods))
    # Insert default expense categories into settings.
    cats = "\n".join(_DEFAULT_EXPENSE_CATEGORIES)
    conn.execute("INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)",
                 ("expense_categories", cats))

    # One sample invoice with one item and one payment.
    cur = conn.execute("SELECT MAX(invoice_no) FROM invoices")
    row = cur.fetchone()
    invoice_no = (row[0] or 0) + 1

    cur = conn.execute("SELECT id FROM products WHERE title LIKE ?", ("AFO%",))
    prow = cur.fetchone()
    product_id = prow[0] if prow else None

    unit_price = 850000          # sale_price at time of sale
    cost_price = 600000         # purchase_price at time of sale
    qty = 1
    row_total = unit_price * qty
    row_cost = cost_price * qty
    row_profit = row_total - row_cost
    total = row_total
    total_cost = row_cost
    total_profit = row_profit
    conn.execute(
        "INSERT INTO invoices(invoice_no, patient_id, doctor_id, issued_at, "
        "total_amount, total_cost, total_profit, notes, is_deleted) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, '', 0)",
        (invoice_no, patient_id, no_doctor_id, today_iso, total, total_cost,
         total_profit))
    cur = conn.execute("SELECT id FROM invoices WHERE invoice_no = ?", (invoice_no,))
    invoice_id = cur.fetchone()[0]

    conn.execute(
        "INSERT INTO invoice_items(invoice_id, product_id, title, unit_price, "
        "cost_price, quantity, row_total, row_cost, row_profit) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (invoice_id, product_id, "AFO بزرگسالان",
         unit_price, cost_price, qty, row_total, row_cost, row_profit))
    # Decrease stock for the seeded product (stock stays > 0 here).
    if product_id is not None:
        conn.execute("UPDATE products SET stock = stock - ? WHERE id = ?",
                     (qty, product_id))

    conn.execute(
        "INSERT INTO payments(invoice_id, method, amount, paid_at) VALUES (?, ?, ?, ?)",
        (invoice_id, "نقد", 500000, now_iso))  # نقد


def next_invoice_no(conn=None):
    # type: (Optional[sqlite3.Connection]) -> int
    own = conn is None
    if own:
        conn = get_connection()
    try:
        cur = conn.execute("SELECT MAX(invoice_no) FROM invoices")
        row = cur.fetchone()
        if row is None or row[0] is None:
            return INVOICE_NO_FLOOR
        return max(INVOICE_NO_FLOOR, int(row[0]) + 1)
    finally:
        if own:
            conn.close()
