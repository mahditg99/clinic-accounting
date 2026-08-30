# -*- coding: utf-8 -*-
"""Pixel probe: where does each column-header's TEXT sit inside its section?

Grabs every table header in the app (real dev DB, read-only) and, per
section, finds the dark-text bbox and reports the gap to the right vs left
edge. In an RTL app the header text must hug the RIGHT edge (like the web).
Also reports which visual side logical column 0 lands on (RTL => right).
"""
import os
import sys

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
C = Qt.QtCore

win = AppWindow(username="admin")
win.resize(1366, 850)
win.show()
app.processEvents()


def is_text(r, g, b):
    # header text #5d7385 (93,115,133); exclude bg #f4f8fa, border #b3c4cf,
    # and the teal sort arrow (13,110,140)
    return 60 < r < 160 and 90 < g < 165 and 105 < b < 185


def probe_header(view, name):
    hdr = view.horizontalHeader()
    pm = hdr.grab()
    img = pm.toImage()
    d = pm.devicePixelRatio() or 1.0
    n = hdr.count()
    print("== %s (%d cols, dir=%s)" % (
        name, n, "RTL" if hdr.layoutDirection() == C.Qt.RightToLeft else "LTR"))
    for logical in range(n):
        x = hdr.sectionViewportPosition(logical)  # visual x from LEFT
        w = hdr.sectionSize(logical)
        if w <= 0:
            continue
        x0, x1 = int(x * d), int((x + w) * d)
        y1 = img.height()
        minx, maxx = None, None
        for yy in range(0, y1, 2):
            for xx in range(max(0, x0), min(img.width(), x1)):
                c = img.pixel(xx, yy)
                r, g, b = (c >> 16) & 255, (c >> 8) & 255, c & 255
                if is_text(r, g, b):
                    if minx is None or xx < minx:
                        minx = xx
                    if maxx is None or xx > maxx:
                        maxx = xx
        label = str(view.model().headerData(logical, C.Qt.Horizontal))
        if minx is None:
            print("   col%d '%s': NO TEXT PIXELS" % (logical, label))
            continue
        gap_right = x1 - maxx
        gap_left = minx - x0
        side = "RIGHT" if gap_right <= gap_left else "LEFT "
        print("   col%d '%s': w=%d text=%d..%d gapL=%d gapR=%d -> %s" % (
            logical, label, w, int(minx / d), int(maxx / d),
            int(gap_left / d), int(gap_right / d), side))


def is_cell_text(r, g, b):
    # cell text #0f2433 (15,36,51) — very dark; exclude bg/alt-bg/borders
    return r < 90 and g < 110 and b < 130


def probe_cells(view, name):
    """Measure row-0 cell text position (visual) for each column."""
    model = view.model()
    if model.rowCount() == 0:
        return
    vp = view.viewport()
    pm = vp.grab()
    img = pm.toImage()
    d = pm.devicePixelRatio() or 1.0
    print("-- cells %s" % name)
    for logical in range(model.columnCount()):
        x = view.columnViewportPosition(logical)
        w = view.columnWidth(logical)
        if w <= 0:
            continue
        x0, x1 = int(x * d), int((x + w) * d)
        y0, y1 = 0, min(img.height(), int(34 * d))
        minx, maxx = None, None
        for yy in range(y0, y1):
            for xx in range(max(0, x0), min(img.width(), x1)):
                c = img.pixel(xx, yy)
                r, g, b = (c >> 16) & 255, (c >> 8) & 255, c & 255
                if is_cell_text(r, g, b):
                    if minx is None or xx < minx:
                        minx = xx
                    if maxx is None or xx > maxx:
                        maxx = xx
        it = model.item(0, logical)
        label = it.text() if it else ""
        if minx is None:
            print("   col%d '%s': no dark px" % (logical, label))
            continue
        gap_right = x1 - maxx
        gap_left = minx - x0
        side = "RIGHT" if gap_right <= gap_left else "LEFT "
        print("   col%d '%s': w=%d gapL=%d gapR=%d -> %s" % (
            logical, label, w, int(gap_left / d), int(gap_right / d), side))


for key in list(win._keys):
    win.goto(key)
    app.processEvents()
    app.processEvents()
    page = win.pages.get(key) if hasattr(win, "pages") else None
    if page is None:
        continue
    tables = page.findChildren(W.QTableView)
    for t in tables:
        probe_header(t, key + "/" + (t.objectName() or "table"))
        probe_cells(t, key + "/" + (t.objectName() or "table"))

# MoneyEdit: does AlignRight mirror to visual left in a QLineEdit too?
from app.ui import fields as F  # noqa: E402
me = F.MoneyEdit()
me.resize(220, 34)
me.setText("۱٬۲۰۰٬۰۰۰")
me.show()
app.processEvents()
pm = me.grab()
img = pm.toImage()
d = pm.devicePixelRatio() or 1.0
minx, maxx = None, None
for yy in range(img.height()):
    for xx in range(img.width()):
        c = img.pixel(xx, yy)
        r, g, b = (c >> 16) & 255, (c >> 8) & 255, c & 255
        if r < 90 and g < 110 and b < 130:
            if minx is None or xx < minx:
                minx = xx
            if maxx is None or xx > maxx:
                maxx = xx
if minx is None:
    print("MoneyEdit: NO TEXT PIXELS")
else:
    gapR = img.width() - maxx
    gapL = minx
    print("MoneyEdit: gapL=%d gapR=%d -> %s" % (
        int(gapL / d), int(gapR / d),
        "RIGHT" if gapR <= gapL else "LEFT"))
me.close()

print("DONE")
