# -*- coding: utf-8 -*-
"""Measure every table action-column: do the buttons FIT the row?

For each page with index-widget action columns:
  needed_w = sum(button widths) + spacing + margins
  vs column width; and max button height vs row height.
"""
import os
import sys

os.environ["QT_QPA_PLATFORM"] = "windows"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import database
database.init_db()

from app.utils import Qt, load_app_fonts, apply_app_font, setup_scaling
_W = Qt.QtWidgets
_Core = Qt.QtCore

setup_scaling()
app = _W.QApplication(sys.argv)
app.setLayoutDirection(_Core.Qt.RightToLeft)
load_app_fonts()
apply_app_font(size=10)
from app.theme import apply_theme
apply_theme(app)
from app.ui.shell import AppWindow

win = AppWindow(username="admin")
win.show()
app.processEvents()

fails = 0


def audit(page_key, table, action_col):
    global fails
    view = table
    model = view.model()
    hdr = view.horizontalHeader()
    row_h = view.verticalHeader().sectionSize(0) if model.rowCount() else 34
    col_w = hdr.sectionSize(action_col)
    worst_w = 0
    worst_h = 0
    detail = ""
    for r in range(min(model.rowCount(), 6)):
        w = view.indexWidget(model.index(r, action_col))
        if w is None:
            continue
        lay = w.layout()
        btns = [c for c in w.findChildren(_W.QPushButton)]
        if not btns:
            continue
        need = sum(b.sizeHint().width() for b in btns) \
            + lay.spacing() * (len(btns) - 1) \
            + lay.contentsMargins().left() + lay.contentsMargins().right()
        # ACTUAL painted height (what the user sees), not sizeHint
        bh = max(b.height() for b in btns)
        if need > worst_w:
            worst_w, worst_h, detail = need, bh, "%d btns" % len(btns)
    ok_w = worst_w <= col_w
    ok_h = worst_h <= row_h
    status = "OK" if (ok_w and ok_h) else "OVERFLOW"
    if not (ok_w and ok_h):
        fails += 1
    print("%-14s col=%3d need=%3d h=%3d row=%3d  %s (%s)" %
          (page_key, col_w, worst_w, worst_h, row_h, status, detail))


for key, col in [("archive", 8), ("patients", 7), ("doctors", 6),
                 ("products", 6), ("expenses", 4), ("settings", 4)]:
    win.goto(key)
    for _ in range(4):
        app.processEvents()
    page = win.pages[key]
    table = page.backup_table if key == "settings" else page.table
    audit(key, table, col)

print("RESULT:", "ALL FIT" if fails == 0 else "%d OVERFLOW" % fails)
sys.exit(1 if fails else 0)
