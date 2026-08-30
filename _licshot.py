# -*- coding: utf-8 -*-
"""Render the license dialogs to PNG so their RTL layout can be inspected."""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta

os.environ.pop("QT_QPA_PLATFORM", None)
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "shots", "license")
os.makedirs(OUT, exist_ok=True)

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

PRIV = R.key_from_json(open(os.path.join(HERE, "keys", "issuer_private.json"),
                            encoding="utf-8").read())
HW = lic.hardware_code()


def payload(expires, name="کلینیک دندان‌پزشکی آذر", hw=HW):
    return lic.make_payload(hw, name, (date.today() - timedelta(days=400)).isoformat(),
                            expires)


def grab(widget, name):
    widget.show()
    for _ in range(4):
        app.processEvents()
    pm = widget.grab()
    path = os.path.join(OUT, name + ".png")
    pm.save(path, "PNG")
    print("saved", name, pm.width(), "x", pm.height())
    widget.hide()
    return pm


# 1. no license at all (what the customer sees on a fresh machine)
grab(LD.ActivationDialog(lic.Status(lic.MISSING, hw=HW)), "01_missing")

# 2. license issued for another machine
grab(LD.ActivationDialog(lic.Status(lic.HW_MISMATCH,
                                    payload(None), hw=HW)), "02_wrong_machine")

# 3. expired
grab(LD.ActivationDialog(lic.Status(lic.EXPIRED,
                                    payload((date.today() - timedelta(days=3))
                                          .isoformat()), -3, HW)), "03_expired")

# 4. details of a valid dated license
st = lic.Status(lic.OK, payload((date.today() + timedelta(days=7)).isoformat(),
                                "کلینیک دندان‌پزشکی آذر"), 7, HW)
grab(LD.LicenseDetailsDialog(status=st), "04_details_dated")

# 5. details of a perpetual license
grab(LD.LicenseDetailsDialog(status=lic.Status(lic.OK, payload(None, "مرکز پزشکی نور"),
                                               None, HW)), "05_details_perpetual")

print("DONE  hw=" + HW)
