# -*- coding: utf-8 -*-
"""Diagnose font loading + text rendering offscreen."""
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding="utf-8")

from app.utils import Qt, load_app_fonts, best_persian_font, resource_path
app = Qt.QtWidgets.QApplication.instance() or Qt.QtWidgets.QApplication(sys.argv)
fdb = Qt.QtGui.QFontDatabase()
print("Vazirmatn before:", "Vazirmatn" in set(fdb.families()))
ok = load_app_fonts()
print("load_app_fonts ->", ok)
print("Vazirmatn after:", "Vazirmatn" in set(fdb.families()))
print("best font:", best_persian_font())
path = resource_path("webapp/static/fonts/Vazirmatn-var.woff2")
print("file exists:", os.path.exists(path), os.path.getsize(path) if os.path.exists(path) else 0)
ident = Qt.QtGui.QFontDatabase.addApplicationFont(path)
print("addApplicationFont ident:", ident)
if ident >= 0:
    print("families:", Qt.QtGui.QFontDatabase.applicationFontFamilies(ident))

# render test: does text produce dark pixels with the chosen font?
lbl = Qt.QtWidgets.QLabel("۱۲۳۴۵ آذران طب")
f = Qt.QtGui.QFont(best_persian_font())
f.setPixelSize(14)
lbl.setFont(f)
lbl.adjustSize()
pm = lbl.grab()
img = pm.toImage()
dark = sum(1 for y in range(img.height()) for x in range(img.width())
           if ((img.pixel(x, y) >> 16) & 255) < 90 and ((img.pixel(x, y) >> 8) & 255) < 90
           and (img.pixel(x, y) & 255) < 90)
print("label %dx%d dark px: %d" % (pm.width(), pm.height(), dark))
