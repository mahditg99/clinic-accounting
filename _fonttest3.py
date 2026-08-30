# -*- coding: utf-8 -*-
"""Test whether the real 'windows' platform renders text in grab()."""
import os, sys
os.environ.pop("QT_QPA_PLATFORM", None)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

from app.utils import Qt
app = Qt.QtWidgets.QApplication.instance() or Qt.QtWidgets.QApplication(sys.argv)
_Gui = Qt.QtGui
_W = Qt.QtWidgets

def dark_count(img):
    n = 0
    for y in range(img.height()):
        for x in range(img.width()):
            c = img.pixel(x, y)
            r, g, b = (c >> 16) & 255, (c >> 8) & 255, c & 255
            if r < 120 and g < 120 and b < 120:
                n += 1
    return n

print("style:", app.style().objectName())
lbl = _W.QLabel("1234 آذران طب")
lbl.setStyleSheet("color:#0f2433; background:#ffffff; font-size:14px;")
lbl.show()
app.processEvents()
pm = lbl.grab()
print("label grab:", pm.width(), "x", pm.height(), "dark px:", dark_count(pm.toImage()))
lbl.hide()
