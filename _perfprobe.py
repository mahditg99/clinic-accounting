# -*- coding: utf-8 -*-
"""Timing probe: page switch / resize / scroll with the seeded demo data."""
import os
import sys
import time

os.environ.pop("QT_QPA_PLATFORM", None)
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from app.utils import Qt, apply_app_font, load_app_fonts, setup_scaling  # noqa: E402
from app.database import init_db  # noqa: E402

init_db()
setup_scaling()
app = Qt.QtWidgets.QApplication.instance() or Qt.QtWidgets.QApplication(sys.argv)
app.setLayoutDirection(Qt.QtCore.Qt.RightToLeft)
try:
    app.setStyle("Fusion")
except Exception:
    pass
load_app_fonts()
apply_app_font()
from app.theme import apply_theme  # noqa: E402
apply_theme(app)
from app.ui.shell import AppWindow  # noqa: E402

W = Qt.QtWidgets

win = AppWindow(username="admin")
win.resize(1366, 850)
win.show()
app.processEvents()


def timed(label, fn):
    t0 = time.perf_counter()
    fn()
    app.processEvents()
    app.processEvents()
    print("%s: %.0f ms" % (label, (time.perf_counter() - t0) * 1000))


for key in ["archive", "patients", "products", "expenses", "dashboard",
            "daily", "financial", "income_expense", "product_sales",
            "doctor_report", "doctors", "settings"]:
    timed("switch->%s" % key, lambda k=key: win.goto(k))

arch = win.pages["archive"]
tbl = arch.findChildren(W.QTableView)[0]
print("archive rows:", tbl.model().rowCount())

timed("resize 1200x700", lambda: win.resize(1200, 700))
timed("resize 1366x850", lambda: win.resize(1366, 850))

sb = tbl.verticalScrollBar()


def scroll():
    for v in (100, 300, 599, 0):
        sb.setValue(v)
        app.processEvents()


timed("scroll x4", scroll)

timed("re-render archive", lambda: arch.refresh())
print("DONE")
