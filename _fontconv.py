# -*- coding: utf-8 -*-
"""One-shot: Vazirmatn-var.woff2 -> plain TTF (Qt 5.15-compatible).

NOTE: fontTools' varLib.instancer output is REJECTED by Qt 5.15's FreeType
(ident=-1), but a plain flavor-strip keeps the variable tables and loads
fine (exposes Regular+Bold; heavier weights render via Qt's bold).
"""
import os
from fontTools.ttLib import TTFont

SRC = os.path.join("webapp", "static", "fonts", "Vazirmatn-var.woff2")
DST = os.path.join("app", "resources", "fonts")
os.makedirs(DST, exist_ok=True)

# remove the broken instanced files
for name in os.listdir(DST):
    os.remove(os.path.join(DST, name))

f = TTFont(SRC)
f.flavor = None
out = os.path.join(DST, "Vazirmatn.ttf")
f.save(out)
print("wrote", out, os.path.getsize(out), "bytes")
