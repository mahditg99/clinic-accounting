# -*- coding: utf-8 -*-
"""Audit every table column: needed width (real data + QSS fonts/padding)
vs actual. Flags clipped or grossly over-wide columns."""
import os
import sys

os.environ["QT_QPA_PLATFORM"] = "windows"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.utils import Qt, load_app_fonts, apply_app_font, setup_scaling
from app import auth_core
_W = Qt.QtWidgets
_Core = Qt.QtCore
_Gui = Qt.QtGui

setup_scaling()
app = _W.QApplication(sys.argv)
app.setLayoutDirection(_Core.Qt.RightToLeft)
load_app_fonts()
apply_app_font(size=10)
from app.theme import apply_theme
apply_theme(app)

from app.ui.shell import AppWindow
auth_core.ensure_admin()
win = AppWindow(username="admin")
win.resize(1400, 900)
win.show()
app.processEvents()

fm_cell = _Gui.QFontMetrics(_Gui.QFont("Vazirmatn", 14))   # QSS 13.5px
fm_hdr = _Gui.QFontMetrics(_Gui.QFont("Vazirmatn", 12, _Gui.QFont.Bold))

problems = 0
for key in ("dashboard", "invoice", "archive", "patients", "doctors",
            "products", "expenses", "daily", "income_expense", "financial",
            "doctor_report", "product_sales", "settings"):
    win.goto(key)
    for _ in range(4):
        app.processEvents()
    page = win.pages[key]
    for t in page.findChildren(_W.QTableView):
        model = t.model()
        if model is None:
            continue
        hdr = t.horizontalHeader()
        name = "%s.%s" % (key, t.objectName() or t.parent().objectName()
                          or "table")
        total = 0
        print("== %s rows=%d ==" % (name, model.rowCount()))
        for c in range(model.columnCount()):
            htxt = model.headerData(c, _Core.Qt.Horizontal) or ""
            need_h = fm_hdr.horizontalAdvance(htxt) + 24 + 18
            need_c = 0
            for r in range(min(model.rowCount(), 200)):
                it = model.item(r, c)
                if it is not None and it.text():
                    need_c = max(need_c,
                                 fm_cell.horizontalAdvance(it.text()) + 26)
            need = max(need_h, need_c, 40)
            actual = t.columnWidth(c)
            mode = hdr.sectionResizeMode(c)
            stretch = (mode == _W.QHeaderView.Stretch or
                       (hdr.stretchLastSection() and
                        c == model.columnCount() - 1))
            total += actual
            flag = ""
            if actual < need - 2 and not stretch:
                flag = "  << CLIPPED need=%d" % need
                problems += 1
            elif not stretch and actual > need * 1.9 and actual > 120:
                flag = "  << WASTEFUL need=%d" % need
                problems += 1
            print("   c%d %-14s actual=%-4d need=%-4d%s%s" % (
                c, htxt[:14], actual, need,
                " [stretch]" if stretch else "", flag))
        print("   viewport=%d sum=%d" % (t.viewport().width(), total))

print("PROBLEMS:", problems)
sys.exit(0)
