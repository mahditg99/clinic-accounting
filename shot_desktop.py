# -*- coding: utf-8 -*-
"""Offscreen->windows screenshots of the desktop UI (real dev DB).

Uses the native 'windows' platform because the offscreen plugin on this box
has no font database (renders no glyphs). Windows renders correctly; we grab
each page and probe pixels to verify the Clinic-Pulse redesign.
"""
from __future__ import annotations

import os
import sys

os.environ.pop("QT_QPA_PLATFORM", None)
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "shots", "desktop")
os.makedirs(OUT, exist_ok=True)

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

win = AppWindow(username="admin")
win.resize(1366, 850)
win.show()
app.processEvents()

W = Qt.QtWidgets


def grab(widget, name):
    app.processEvents()
    pm = widget.grab()
    path = os.path.join(OUT, name + ".png")
    pm.save(path, "PNG")
    print("saved", name, pm.width(), "x", pm.height())
    return pm


def _dev(pm, x0, y0, x1, y1):
    """Probe rects are given in LOGICAL px; grab() returns a DPR-scaled
    device image — scale the rect by the pixmap's devicePixelRatio."""
    d = pm.devicePixelRatio() or 1.0
    return int(x0 * d), int(y0 * d), int(x1 * d), int(y1 * d)


def dark_in(pm, x0, y0, x1, y1, thr=120):
    x0, y0, x1, y1 = _dev(pm, x0, y0, x1, y1)
    img = pm.toImage()
    n = 0
    for y in range(max(0, y0), min(img.height(), y1)):
        for x in range(max(0, x0), min(img.width(), x1)):
            c = img.pixel(x, y)
            r, g, b = (c >> 16) & 255, (c >> 8) & 255, c & 255
            if r < thr and g < thr and b < thr:
                n += 1
    return n


def colored_in(pm, x0, y0, x1, y1, pred):
    x0, y0, x1, y1 = _dev(pm, x0, y0, x1, y1)
    img = pm.toImage()
    n = 0
    for y in range(max(0, y0), min(img.height(), y1)):
        for x in range(max(0, x0), min(img.width(), x1)):
            c = img.pixel(x, y)
            if pred((c >> 16) & 255, (c >> 8) & 255, c & 255):
                n += 1
    return n


def probe(pm, x, y):
    x, y = _dev(pm, x, y, x + 1, y + 1)[:2]
    img = pm.toImage()
    c = img.pixel(x, y)
    return "#%02x%02x%02x" % ((c >> 16) & 255, (c >> 8) & 255, c & 255)


for key in list(win._keys):
    win.goto(key)
    app.processEvents()
    app.processEvents()
    pm = grab(win, key)
    if key == "dashboard":
        print("  sidebar:", probe(pm, 1250, 500), "topbar:", probe(pm, 600, 40),
              "canvas:", probe(pm, 600, 830))
        print("  ribbon red px:",
              colored_in(pm, 300, 0, 1000, 12,
                         lambda r, g, b: r > 180 and g < 120 and b < 130))
        # RTL layout: sidebar right (x>1130), top-bar title at the right of
        # the main column, hero spans the column below it.
        print("  topbar text px:", dark_in(pm, 900, 15, 1100, 55))
        print("  sidebar nav text px:", dark_in(pm, 1150, 120, 1360, 700, 150))
        print("  hero text px:", dark_in(pm, 40, 110, 1100, 210))
        # quick-access tile icons: grab each QLabel#qIco directly. The old
        # DPR bug painted the icon at 2x, so its teal bbox sat off-centre
        # (shifted) and clipped; a correct icon is centred in the 38px box.
        for lab in win.findChildren(W.QLabel):
            if lab.objectName() != "qIco":
                continue
            ipm = lab.grab()
            iimg = ipm.toImage()
            w0, h0 = iimg.width(), iimg.height()
            xs, ys = [], []
            for yy in range(h0):
                for xx in range(w0):
                    c = iimg.pixel(xx, yy)
                    r, g, b = (c >> 16) & 255, (c >> 8) & 255, c & 255
                    if r < 120 and 80 < g < 170 and 110 < b < 190:  # teal
                        xs.append(xx); ys.append(yy)
            if not xs:
                print("  qIco %dx%d: NO TEAL!" % (w0, h0))
                continue
            cx, cy = (min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0
            span = max(max(xs) - min(xs), max(ys) - min(ys))
            ok = abs(cx - w0 / 2) <= 6 and abs(cy - h0 / 2) <= 6 and span > 20
            print("  qIco %dx%d teal=%d bbox=%d..%d x %d..%d" %
                  (w0, h0, len(xs), min(xs), max(xs), min(ys), max(ys)),
                  "OK" if ok else "OFF-CENTRE/CLIPPED!")

# Calendar popup
win.goto("daily")
app.processEvents()
from app.ui import fields as F  # noqa: E402
from datetime import date  # noqa: E402
pop = F._JalaliCalendarPopup(None, date.today())
pop.adjustSize()
pop.show()
app.processEvents()
cpm = grab(pop, "calendar")
# day grid region: below weekday row (~y=60) to above today button
print("calendar size:", cpm.width(), "x", cpm.height())
print("  day-number dark px:", dark_in(cpm, 8, 60, cpm.width() - 8, cpm.height() - 40))
pop.close()

print("DONE")
