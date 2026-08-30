# -*- coding: utf-8 -*-
"""Layout + behaviour audit of the vendor issuer GUI (no mouse interaction)."""
from __future__ import annotations

import os
import sys

os.environ.pop("QT_QPA_PLATFORM", None)
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))

from app import license as lic                                    # noqa: E402
from app.utils import Qt                                          # noqa: E402
import license_issuer as LI                                       # noqa: E402

W, C = Qt.QtWidgets, Qt.QtCore
app = LI.bootstrap_app()
PROBLEMS = []


def check(name, cond, extra=""):
    if cond:
        return
    PROBLEMS.append("%s %s" % (name, extra))
    print("FAIL  %s %s" % (name, extra))


win = LI.IssuerWindow()
win.show()
for _ in range(6):
    app.processEvents()

tabs = win.findChild(W.QTabWidget)
check("three tabs", tabs is not None and tabs.count() == 3)
check("tab names", [tabs.tabText(i) for i in range(3)] ==
      ["صدور لایسنس", "کلیدها", "راهنما"],
      str([tabs.tabText(i) for i in range(3)]))
check("window RTL", win.layoutDirection() == C.Qt.RightToLeft)
check("hw field is LTR (Latin code)", win.hw.layoutDirection() == C.Qt.LeftToRight)

# clipping
pm = win.grab()
d = pm.devicePixelRatio() or 1.0
for wgt in win.findChildren(W.QWidget):
    if not wgt.isVisible():
        continue
    getter = getattr(wgt, "text", None)
    if getter is None or not callable(getter) or not (getter() or "").strip():
        continue
    hint = wgt.minimumSizeHint()
    check("no clip: %s" % getter()[:22], wgt.height() >= hint.height() - 1,
          "h=%d hint=%d" % (wgt.height(), hint.height()))

# hardware-code button + live validation
win.b_mine.click()
check("mine button fills code", win.hw.text() == lic.hardware_code(), win.hw.text())
check("hint says valid", "معتبر" in win.hw_hint.text(), win.hw_hint.text())
win.hw.setText("ABCDE")
check("short code flagged", "۲۰ نویسه" in win.hw_hint.text(), win.hw_hint.text())
win.hw.setText(lic.hardware_code().lower().replace("-", " "))
check("messy paste normalises", "معتبر" in win.hw_hint.text(), win.hw_hint.text())

# expiry controls
win._quick(730)
from datetime import date, timedelta
check("quick 2 years", win.exp.iso() == (date.today() + timedelta(days=730)).isoformat(),
      win.exp.iso())
check("expiry label shows days", "روز اعتبار" in win.exp_lbl.text(), win.exp_lbl.text())
win.perp.setChecked(True)
check("perpetual disables date", win.exp.btn.isEnabled() is False)
check("perpetual label", "هیچ‌وقت" in win.exp_lbl.text(), win.exp_lbl.text())
win.perp.setChecked(False)

# issuing through the GUI path
win.name.setText("کلینیک گرافیکی تست")
win._quick(365)
tok = win._make_token()
st = lic.verify_token(tok)
check("GUI token verifies", st.ok, st.code)
check("GUI token carries name", st.payload.get("name") == "کلینیک گرافیکی تست")
check("GUI token hw", st.payload.get("hw") == lic.hardware_code())
check("status says built", "ساخته شد" in win.status.text(), win.status.text())
check("preview shows token", win.out.toPlainText().strip() == tok)
win.perp.setChecked(True)
st2 = lic.verify_token(win._make_token())
check("GUI perpetual ok", st2.ok and st2.payload["expires"] is None, st2.code)

# error path: bad code
win.perp.setChecked(False)
win.hw.setText("nope")
try:
    win._make_token()
    check("bad code raises", False)
except ValueError:
    check("bad code raises", True)
check("error surfaced in status", "کد سخت‌افزاری" in win.status.text(), win.status.text())

# keys tab reflects the real key
labels = " | ".join(l.text() for l in win.findChildren(W.QLabel))
check("keys tab shows fingerprint", LI.rsa_lite.fingerprint(
    LI.load_private()["n"]) in labels, labels[:120])
check("keys tab says matching", "هم‌خوان با برنامه" in labels)
check("private key warning present", "issuer_private.json" in labels)
check("regen button exists", any(b.text() == "ساخت جفت‌کلید جدید"
                                 for b in win.findChildren(W.QPushButton)))

# help tab content
check("help has steps", "کد سخت‌افزاری را بگیرید" in labels and "تمدید" in labels)

print("\nissuer layout: %d problems" % len(PROBLEMS))
for p in PROBLEMS:
    print("  -", p)
sys.stdout.flush()
sys.exit(1 if PROBLEMS else 0)
