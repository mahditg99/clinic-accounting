# -*- coding: utf-8 -*-
"""Functional probe for LAZY row-action widgets.

Verifies on the real dev DB (read-only except stubbed dialogs):
  A. archive builds buttons only for visible rows (bounded count)
  B. "مشاهده" on row 0 opens THAT invoice (print html matches row 0)
  C. after sorting by جمع کل desc, row 0's button still matches row 0
  D. after scrolling to the bottom, buttons still match their rows
  E. patients "ویرایش" loads the right patient id (before + after sort)
  F. expenses "حذف" targets the right expense id
  G. widget count stays bounded after scrolling the whole table
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
from app.ui import fields as F  # noqa: E402
from app.ui import printing  # noqa: E402

W = Qt.QtWidgets
C = Qt.QtCore

FAILS = []


def check(name, ok, detail=""):
    print(("  OK  " if ok else " FAIL ") + name + ("  " + detail if detail else ""))
    if not ok:
        FAILS.append(name)


def spin(n=6):
    for _ in range(n):
        app.processEvents()


win = AppWindow(username="admin")
win.resize(1366, 850)
win.show()

# capture print previews instead of opening them
captured = []
printing.show_print_preview = lambda parent, html: captured.append(html)

win.goto("archive")
spin()
arch = win.pages["archive"]
tbl = arch.table
model = tbl.model()
n = model.rowCount()
print("archive rows:", n)


def live_widgets(view, col):
    m = view.model()
    return sum(1 for r in range(m.rowCount())
               if view.indexWidget(m.index(r, col)) is not None)


cnt = live_widgets(tbl, 8)
check("A: buttons bounded (not one per row)", 0 < cnt < 150,
      "live=%d of %d" % (cnt, n))


def click_view(row):
    captured.clear()
    w = tbl.indexWidget(model.index(row, 8))
    if w is None:
        return None
    btn = w.findChildren(W.QPushButton)[0]
    btn.click()
    spin(2)
    return captured[0] if captured else None


def row_no(row):
    return F.en(model.item(row, 0).text())


html = click_view(0)
check("B: row0 view opens row0 invoice",
      html is not None and ("فاکتور شماره %s" % row_no(0) in html
                            or "شماره %s" % row_no(0) in html
                            or row_no(0) in html),
      "row0=%s" % row_no(0))

# C: sort by جمع کل (col 4) descending, then verify row 0 again
hdr = tbl.horizontalHeader()
hdr.setSortIndicator(4, C.Qt.DescendingOrder)
spin()
html = click_view(0)
check("C: after sort, row0 button matches row0",
      html is not None and row_no(0) in html, "row0=%s" % row_no(0))
# and the totals really are sorted desc
t0 = F.en(model.item(0, 4).text()).replace(",", "").replace("\u066c", "")
t1 = F.en(model.item(1, 4).text()).replace(",", "").replace("\u066c", "")
check("C2: sort applied (col4 desc)", int(t0) >= int(t1), "%s >= %s" % (t0, t1))

# D: scroll to the bottom and verify the last visible row
sb = tbl.verticalScrollBar()
sb.setValue(sb.maximum())
spin()
last_vis = tbl.rowAt(tbl.viewport().height() - 5)
if last_vis < 0:
    last_vis = n - 1
html = click_view(last_vis)
check("D: after scroll, button matches row",
      html is not None and row_no(last_vis) in html, "row=%d" % last_vis)

# G: still bounded after jumping around
sb.setValue(0)
spin()
sb.setValue(sb.maximum() // 2)
spin()
sb.setValue(sb.maximum())
spin()
cnt2 = live_widgets(tbl, 8)
check("G: widgets stay bounded after scroll", cnt2 < 150, "live=%d" % cnt2)

# ---- patients ---- #
win.goto("patients")
spin()
pat = win.pages["patients"]
ptbl = pat.table
pmodel = ptbl.model()
pn = pmodel.rowCount()
print("patients rows:", pn)
cntp = live_widgets(ptbl, 7)
check("A2: patient buttons bounded", 0 < cntp < 150, "live=%d" % cntp)

b_edit = ptbl.indexWidget(pmodel.index(0, 7)).findChildren(W.QPushButton)[0]
b_edit.click()
spin()
want_id = int(pmodel.item(0, 0).data(F.ROW_ID)["id"])
check("E: ویرایش loads row0 patient", pat._editing_id == want_id,
      "editing=%s want=%s" % (pat._editing_id, want_id))
ptbl.horizontalHeader().setSortIndicator(2, C.Qt.AscendingOrder)
spin()
b_edit = ptbl.indexWidget(pmodel.index(0, 7)).findChildren(W.QPushButton)[0]
b_edit.click()
spin()
want_id = int(pmodel.item(0, 0).data(F.ROW_ID)["id"])
check("E2: after sort, ویرایش loads row0 patient",
      pat._editing_id == want_id, "editing=%s want=%s" % (pat._editing_id, want_id))

# ---- expenses ---- #
win.goto("expenses")
spin()
exp = win.pages["expenses"]
etbl = exp.table
emodel = etbl.model()
en = emodel.rowCount()
print("expenses rows:", en)
recorded = []
exp._delete = lambda i: recorded.append(i)
w = etbl.indexWidget(emodel.index(0, 4))
btn = w.findChildren(W.QPushButton)[0]
btn.click()
spin()
want = int(emodel.item(0, 0).data(F.ROW_ID))
check("F: حذف targets row0 expense", recorded and recorded[0] == want,
      "got=%s want=%s" % (recorded[:1], want))

print("PROBLEMS:", len(FAILS), FAILS)
print("DONE")
sys.exit(1 if FAILS else 0)
