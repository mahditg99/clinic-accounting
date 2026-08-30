# -*- coding: utf-8 -*-
"""Why does offscreen grab show no text?"""
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

from app.utils import Qt
app = Qt.QtWidgets.QApplication.instance() or Qt.QtWidgets.QApplication(sys.argv)
_Gui = Qt.QtGui
_W = Qt.QtWidgets
_Core = Qt.QtCore

def dark_count(img):
    n = 0
    for y in range(img.height()):
        for x in range(img.width()):
            c = img.pixel(x, y)
            r, g, b = (c >> 16) & 255, (c >> 8) & 255, c & 255
            if r < 120 and g < 120 and b < 120:
                n += 1
    return n

# 1) QFontMetrics sanity
for fam in ("Tahoma", "Arial"):
    f = _Gui.QFont(fam)
    f.setPixelSize(14)
    fm = _Gui.QFontMetrics(f)
    print(fam, "height:", fm.height(), "ascent:", fm.ascent(),
          "width('1234'):", fm.width("1234"),
          "glyphCount 1:", f.glyphCount("1") if hasattr(f, "glyphCount") else "?")

# 2) QPainter drawText on QImage (no widget)
img = _Gui.QImage(200, 40, _Gui.QImage.Format_RGB32)
img.fill(_Gui.QColor("#ffffff"))
p = _Gui.QPainter(img)
f = _Gui.QFont("Tahoma"); f.setPixelSize(14)
p.setFont(f)
p.setPen(_Gui.QColor("#0f2433"))
p.drawText(10, 25, "1234 آذران")
p.end()
print("drawText dark px:", dark_count(img))

# 3) QLabel grab, default app font
lbl = _W.QLabel("1234 آذران")
lbl.show()
app.processEvents()
pm = lbl.grab()
print("label grab:", pm.width(), "x", pm.height(),
      "dark px:", dark_count(pm.toImage()))

# 4) QLabel with explicit stylesheet color
lbl2 = _W.QLabel("1234 آذران")
lbl2.setStyleSheet("color:#0f2433; background:#ffffff;")
lbl2.show()
app.processEvents()
pm2 = lbl2.grab()
print("label2 dark px:", dark_count(pm2.toImage()))

# 5) app font info
af = app.font()
print("app font:", af.family(), af.pixelSize(), af.pointSize())
