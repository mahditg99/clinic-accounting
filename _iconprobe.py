# -*- coding: utf-8 -*-
"""Verify the FIXED _svg_icon: full icon visible, correct DPR, no clipping.

Tests with the real production function on:
  1) a bottom-right-only rect  -> must paint bottom-right (was invisible before)
  2) the real settings gear    -> painted bbox must cover ~the whole canvas
     (a 2x-clipped render leaves the bottom-right quarter empty)
"""
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "windows")
from app.utils import Qt, setup_scaling
setup_scaling()
from PyQt5 import QtGui, QtCore

_W = Qt.QtWidgets
_app = _W.QApplication(sys.argv)

from app.ui.shell import _svg_icon, _IC_SET


def bbox(im):
    xs, ys = [], []
    for y in range(im.height()):
        for x in range(im.width()):
            if im.pixelColor(x, y).alpha() > 40:
                xs.append(x); ys.append(y)
    return (min(xs), max(xs), min(ys), max(ys)) if xs else None


fails = 0

# 1) bottom-right-only content
pm = _svg_icon('<rect x="14" y="14" width="8" height="8"/>', "#000000", px=40)
b = bbox(pm.toImage())
print("bottom-right rect bbox:", b, "(device 80)")
if b is None or b[0] < 30 or b[1] < 60 or b[2] < 30 or b[3] < 60:
    print("  FAIL: bottom-right content missing/clipped"); fails += 1
else:
    print("  PASS")

# 2) real gear icon: content must reach all four quadrants
pm = _svg_icon(_IC_SET, "#0d6e8c", px=19)
img = pm.toImage()
w, h = img.width(), img.height()
q = {"TL": 0, "TR": 0, "BL": 0, "BR": 0}
for y in range(h):
    for x in range(w):
        if img.pixelColor(x, y).alpha() > 40:
            q[("T" if y < h / 2 else "B") + ("L" if x < w / 2 else "R")] += 1
print("gear dpr:", pm.devicePixelRatio(), "device:", w, "x", h, "quadrants:", q)
if min(q.values()) < 10:
    print("  FAIL: a quadrant is empty (clipped)"); fails += 1
else:
    print("  PASS")

# 3) same at a small size (16px) — must still be complete
pm = _svg_icon(_IC_SET, "#0d6e8c", px=16)
img = pm.toImage()
w, h = img.width(), img.height()
q = {"TL": 0, "TR": 0, "BL": 0, "BR": 0}
for y in range(h):
    for x in range(w):
        if img.pixelColor(x, y).alpha() > 40:
            q[("T" if y < h / 2 else "B") + ("L" if x < w / 2 else "R")] += 1
print("gear@16 quadrants:", q)
if min(q.values()) < 8:
    print("  FAIL"); fails += 1
else:
    print("  PASS")

print("RESULT:", "ALL PASS" if fails == 0 else "%d FAIL" % fails)
sys.exit(1 if fails else 0)
