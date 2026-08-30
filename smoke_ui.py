# -*- coding: utf-8 -*-
"""Offscreen smoke test for the v2 desktop UI (QT_QPA_PLATFORM=offscreen)."""
from __future__ import annotations

import os
import sys
import traceback

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

fail = 0


def step(name, fn):
    global fail
    try:
        fn()
        print("OK   %s" % name)
    except Exception:
        fail += 1
        print("FAIL %s" % name)
        traceback.print_exc()


# 1. compile all modules
import py_compile
for root, dirs, files in os.walk("app"):
    dirs[:] = [d for d in dirs if d != "__pycache__"]
    for f in sorted(files):
        if f.endswith(".py"):
            p = os.path.join(root, f)
            step("compile %s" % p, lambda p=p: py_compile.compile(p, doraise=True))
for f in ("main.py",):
    step("compile %s" % f, lambda f=f: py_compile.compile(f, doraise=True))

# Use a throwaway DB so the real azaran_teb.db is never touched.
import tempfile
import app.database as dbmod
_tmpdir = tempfile.mkdtemp(prefix="azaran_smoke_")
dbmod._db_path = lambda: os.path.join(_tmpdir, "smoke.db")

from app.database import init_db
init_db()

from app.utils import Qt, setup_scaling
setup_scaling()
app = Qt.QtWidgets.QApplication.instance() or Qt.QtWidgets.QApplication(sys.argv)
app.setLayoutDirection(Qt.QtCore.Qt.RightToLeft)
from app.theme import apply_theme
apply_theme(app)

from app.ui.shell import AppWindow
win = None


def make():
    global win
    win = AppWindow(username="admin")
    win.show()


step("instantiate AppWindow", make)

if win is not None:
    for key in list(win._keys):
        def go(k=key):
            win.goto(k)
            app.processEvents()
        step("goto %s" % key, go)

    # exercise a few interactions
    def inv_add_row():
        p = win.pages["invoice"]
        p.add_item_btn.click()
        app.processEvents()
    step("invoice: add item row", inv_add_row)

    def daily_print_html():
        from app.ui import printing
        p = win.pages["daily"]
        html = printing.build_report_html("t", [
            {"kind": "text", "text": "x"},
            {"kind": "cards", "cards": [{"label": "a", "value": "1",
                                         "color": "#333"}]},
            {"kind": "table", "title": "tt", "columns": ["a", "b"],
             "rows": [["1", "2"]]}])
        assert "<table" in html and "tt" in html
    step("printing: report html", daily_print_html)

    def settings_reload():
        sp = win.pages["settings"]
        sp._reload_backups()
        sp.methods_editor._add()  # empty -> error dialog would block; call render
    step("settings: reload backups", lambda: win.pages["settings"]._reload_backups())

    def patients_filter():
        pp = win.pages["patients"]
        pp.filter_edit.setText("۱۲۳")
        app.processEvents()
    step("patients: live search w/ Persian digits", patients_filter)

    def doctors_filter():
        dp = win.pages["doctors"]
        attr = "filter_edit" if hasattr(dp, "filter_edit") else "search"
        getattr(dp, attr).setText("دکتر")
        app.processEvents()
    step("doctors: live search", doctors_filter)

    def financial_year():
        fp = win.pages["financial"]
        fp.period_combo.setCurrentIndex(1)  # yearly
        app.processEvents()
        fp._show_report()
    step("financial: yearly period reload", financial_year)

    def archive_search():
        ap = win.pages["archive"]
        ap.search.setText("احمد")
        app.processEvents()
    step("archive: live search", archive_search)

    def invoice_roundtrip():
        from app import models
        from app import date_utils
        pid = models.create_patient("90001", "مریم", "آزمون", "female",
                                    "09120000000")
        prod = models.add_product("کالای آزمایشی", 1000, 2500, 10, 2, "")
        now = date_utils.now_iso()
        inv_id = models.save_invoice(
            pid, None, now,
            [{"product_id": prod, "title": "کالای آزمایشی",
              "unit_price": 2500, "quantity": 2, "row_total": 5000}],
            [{"method": "نقدی", "amount": 3000, "paid_at": now}],
            "یادداشت تست")
        inv = models.get_invoice(inv_id)
        assert inv and int(inv["total_amount"]) == 5000, inv
        p = win.pages["invoice"]
        p.load_invoice_for_edit(inv_id)
        app.processEvents()
        win.goto("archive")
        app.processEvents()
        win.goto("invoice")
        app.processEvents()
    step("invoice: model round-trip + edit load", invoice_roundtrip)

print("=" * 50)
print("FAILURES: %d" % fail)
sys.exit(1 if fail else 0)
