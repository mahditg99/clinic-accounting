# -*- coding: utf-8 -*-
"""Geometry + pixel audit of the license dialogs (RTL correctness, clipping).

For every dialog state we render, check:
  * no widget is clipped (height >= its own minimumSizeHint)
  * every widget sits inside the dialog
  * single-line labels hug the RIGHT edge (RTL) — measured from pixels
  * the hardware-code field is centred and shows all 20 chars
"""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta

os.environ.pop("QT_QPA_PLATFORM", None)
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from app.utils import Qt, apply_app_font, load_app_fonts, setup_scaling  # noqa: E402
from app import rsa_lite as R  # noqa: E402
from app import license as lic  # noqa: E402

setup_scaling()
app = Qt.QtWidgets.QApplication.instance() or Qt.QtWidgets.QApplication(sys.argv)
app.setLayoutDirection(Qt.QtCore.Qt.RightToLeft)
load_app_fonts()
apply_app_font(size=10)
try:
    app.setStyle("Fusion")
except Exception:
    pass
from app.theme import apply_theme  # noqa: E402
apply_theme(app)
from app.ui import license_dialog as LD  # noqa: E402

W, C = Qt.QtWidgets, Qt.QtCore
PRIV = R.key_from_json(open(os.path.join(HERE, "keys", "issuer_private.json"),
                            encoding="utf-8").read())
HW = lic.hardware_code()
PROBLEMS = []


def is_text(r, g, b):
    return r < 175 and g < 175 and b < 200


def text_bbox(pm, rect):
    """Device-pixel bbox of text inside a logical rect, or None."""
    d = pm.devicePixelRatio() or 1.0
    img = pm.toImage()
    x0, y0 = int(rect[0] * d), int(rect[1] * d)
    x1, y1 = int((rect[0] + rect[2]) * d), int((rect[1] + rect[3]) * d)
    minx = maxx = miny = maxy = None
    for yy in range(max(0, y0), min(img.height(), y1)):
        for xx in range(max(0, x0), min(img.width(), x1)):
            c = img.pixel(xx, yy)
            if is_text((c >> 16) & 255, (c >> 8) & 255, c & 255):
                if minx is None or xx < minx:
                    minx = xx
                if maxx is None or xx > maxx:
                    maxx = xx
                if miny is None or yy < miny:
                    miny = yy
                if maxy is None or yy > maxy:
                    maxy = yy
    if minx is None:
        return None
    return minx, miny, maxx, maxy


def side_of(pm, rect):
    bb = text_bbox(pm, rect)
    if bb is None:
        return "EMPTY", None
    x, y, w, h = rect
    d = pm.devicePixelRatio() or 1.0
    minx, miny, maxx, maxy = bb
    gap_l = (minx - x * d) / d
    gap_r = ((x + w) * d - maxx) / d
    if gap_l < 6 and gap_r < 6:
        return "FILL", (round(gap_l, 1), round(gap_r, 1))
    if abs(gap_l - gap_r) < 8:
        return "CENTER", (round(gap_l, 1), round(gap_r, 1))
    return ("RIGHT" if gap_r < gap_l else "LEFT"), (round(gap_l, 1), round(gap_r, 1))


def audit(name, dlg):
    print("\n== %s ==" % name)
    dlg.show()
    for _ in range(5):
        app.processEvents()
    pm = dlg.grab()
    dpr = pm.devicePixelRatio() or 1.0
    print("size %dx%d (logical %dx%d)" % (
        pm.width(), pm.height(), pm.width() / dpr, pm.height() / dpr))

    # clipping / containment
    for wgt in dlg.findChildren(W.QWidget):
        if not wgt.isVisible():
            continue
        getter = getattr(wgt, "text", None)
        if getter is None or not callable(getter) or not (getter() or "").strip():
            continue
        hint = wgt.minimumSizeHint()
        if wgt.height() < hint.height() - 1:
            PROBLEMS.append("%s: %s clipped h=%d hint=%d" % (
                name, wgt.metaObject().className(), wgt.height(), hint.height()))
            print("  CLIP %s h=%d<%d" % (wgt.objectName() or getter()[:18],
                                          wgt.height(), hint.height()))
        top = wgt.mapTo(dlg, C.QPoint(0, 0))
        if top.x() < -1 or top.y() < -1 or (top.x() + wgt.width()) > dlg.width() + 1 \
                or (top.y() + wgt.height()) > dlg.height() + 1:
            PROBLEMS.append("%s: %s outside dialog at %d,%d %dx%d" % (
                name, getter()[:18], top.x(), top.y(), wgt.width(), wgt.height()))
            print("  OUTSIDE %s at %d,%d" % (wgt.objectName() or getter()[:18],
                                             top.x(), top.y()))

    # alignment of single-line labels
    for lab in dlg.findChildren(W.QLabel):
        txt = lab.text().strip()
        if not txt or not lab.isVisible():
            continue
        p = lab.mapTo(dlg, C.QPoint(0, 0))
        rect = (p.x(), p.y(), lab.width(), lab.height())
        side, gaps = side_of(pm, rect)
        wrapped = lab.wordWrap() and lab.height() > lab.fontMetrics().height() + 6
        tag = "WRAP" if wrapped else side
        print("  %-6s %-46s %s" % (tag, txt[:44].replace("\n", " "), gaps))
        if not wrapped and side == "LEFT":
            PROBLEMS.append("%s: label hugs LEFT: %r" % (name, txt[:30]))

    # hardware code field
    edits = [e for e in dlg.findChildren(W.QLineEdit) if e.objectName() == "hwCode"]
    if not edits:
        PROBLEMS.append("%s: no hardware code field" % name)
    else:
        e = edits[0]
        if e.text() != HW:
            PROBLEMS.append("%s: code field shows %r" % (name, e.text()))
        p = e.mapTo(dlg, C.QPoint(0, 0))
        bb = text_bbox(pm, (p.x(), p.y(), e.width(), e.height()))
        if bb is None:
            PROBLEMS.append("%s: hardware code renders blank" % name)
            print("  CODE   blank!")
        else:
            gap_l = bb[0] - p.x() * dpr
            gap_r = (p.x() + e.width()) * dpr - bb[2]
            centred = abs(gap_l - gap_r) < 12 * dpr
            print("  CODE   gaps L=%.0f R=%.0f %s" % (gap_l / dpr, gap_r / dpr,
                                                      "CENTRED" if centred else "OFF"))
            if not centred:
                PROBLEMS.append("%s: code not centred" % name)
    dlg.hide()
    return pm


def pay(expires, name="کلینیک دندان‌پزشکی آذر", hw=HW):
    return lic.make_payload(hw, name, (date.today() - timedelta(days=400)).isoformat(),
                            expires)


audit("activation/missing", LD.ActivationDialog(lic.Status(lic.MISSING, hw=HW)))
audit("activation/wrong-machine",
      LD.ActivationDialog(lic.Status(lic.HW_MISMATCH, pay(None), hw=HW)))
audit("activation/bad-sign",
      LD.ActivationDialog(lic.Status(lic.BAD_SIGN, hw=HW)))
audit("activation/expired",
      LD.ActivationDialog(lic.Status(lic.EXPIRED, pay((date.today() - timedelta(days=3))
                                                      .isoformat()), -3, HW)))
audit("details/dated",
      LD.LicenseDetailsDialog(status=lic.Status(
          lic.OK, pay((date.today() + timedelta(days=7)).isoformat()), 7, HW)))
audit("details/perpetual",
      LD.LicenseDetailsDialog(status=lic.Status(lic.OK, pay(None, "مرکز پزشکی نور"),
                                                None, HW)))

print("\nPROBLEMS: %d" % len(PROBLEMS))
for p in PROBLEMS:
    print("  -", p)
sys.stdout.flush()
sys.exit(1 if PROBLEMS else 0)
