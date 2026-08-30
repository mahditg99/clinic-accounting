# -*- coding: utf-8 -*-
"""Repro: new invoice -> pick patient from suggestion popup -> save
says 'patient selection required'. Simulates REAL mouse click + Enter."""
import os
import sys
import tempfile

os.environ["QT_QPA_PLATFORM"] = "windows"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

_tmpdb = os.path.join(tempfile.mkdtemp(), "pick.db")
from app import database
database._db_path = lambda: _tmpdb
database.init_db()

from app.utils import Qt, load_app_fonts, apply_app_font, setup_scaling
from app import models
from PyQt5 import QtTest

_W = Qt.QtWidgets
_Core = Qt.QtCore
_Gui = Qt.QtGui

setup_scaling()
app = _W.QApplication(sys.argv)
app.setLayoutDirection(_Core.Qt.RightToLeft)
load_app_fonts()
apply_app_font(size=10)
from app.theme import apply_theme
apply_theme(app)

from app.ui import invoice_page
from app.ui.invoice_page import InvoicePage

warnings = []
invoice_page.warning_msg = lambda _p, m, **k: warnings.append(m)
invoice_page.info_msg = lambda _p, m, **k: warnings.append("INFO:" + m)
invoice_page.error_msg = lambda _p, m, **k: warnings.append("ERR:" + m)

pid1 = models.create_patient("70001", "مریم", "رضایی", "female", "", "")
pid2 = models.create_patient("70002", "مریم", "حسابداری", "female", "", "")
pid3 = models.create_patient("70003", "زهرا", "محمدی", "female", "", "")


class StubWin(_W.QWidget):
    def set_page_title(self, *a):
        pass

    def goto(self, name):
        pass


def pump(n=6):
    for _ in range(n):
        app.processEvents()
        QtTest.QTest.qWait(20)


def fresh_page():
    page = InvoicePage(StubWin())
    page.resize(1100, 700)
    page.show()
    pump()
    return page


def fill_items(page):
    row = page._add_item_row(None)
    row.qty.setText("2")
    row.unit.set_value(5000)
    pump(2)


def popup_view(picker):
    # QCompleter::popup() *is* the QListView in Qt5.
    return picker._comp.popup()


def type_text(picker, s):
    """QLineEdit.insert emits textEdited+textChanged exactly like typing;
    then drive the completer the way a key-press would (keyClicks cannot
    inject non-ASCII: qasciikey ASSERT)."""
    picker.insert(s)
    picker._comp.setCompletionPrefix(picker.text())
    picker._comp.complete()
    pump(8)


def click_suggestion(page, which=0):
    picker = page.picker
    picker.setFocus()
    pump(2)
    type_text(picker, "مریم")
    pop = picker._comp.popup()
    view = popup_view(picker)
    print("  popup visible:", pop.isVisible(),
          "rows:", picker._model.rowCount())
    idx = view.model().index(which, 0)
    rect = view.visualRect(idx)
    QtTest.QTest.mouseClick(view.viewport(), _Core.Qt.LeftButton,
                            _Core.Qt.NoModifier, rect.center())
    pump(8)
    print("  after click: text=%r patient=%r" % (
        picker.text(), picker.patient["id"] if picker.patient else None))


def try_save(page, label):
    del warnings[:]
    fill_items(page)
    QtTest.QTest.mouseClick(page.save_btn, _Core.Qt.LeftButton,
                            _Core.Qt.NoModifier,
                            page.save_btn.rect().center())
    pump(4)
    pop_open = page.picker._comp.popup().isVisible()
    print("  %s -> warnings=%r invoices_in_db=%d popup_open=%s" % (
        label, warnings, len(models.list_archive_invoices()), pop_open))
    return warnings, pop_open


print("== Flow A: mouse-click a suggestion, then save ==")
page = fresh_page()
click_suggestion(page, 0)
w, pop_open = try_save(page, "save after click")
a_ok = not any("الزامی" in m for m in w) and not pop_open
print("  FLOW A OK" if a_ok else "  FLOW A REPRODUCED BUG")

print("== Flow B: type full unique name, Tab out, save ==")
page = fresh_page()
page.picker.setFocus()
pump(2)
type_text(page.picker, "زهرا محمدی")
QtTest.QTest.keyClick(page.picker, _Core.Qt.Key_Tab)
pump(4)
print("  patient=%r" % (page.picker.patient["id"]
                        if page.picker.patient else None))
w, pop_open = try_save(page, "save after tab")
b_ok = not any("الزامی" in m for m in w) and not pop_open
print("  FLOW B OK" if b_ok else "  FLOW B BUG")

print("== Flow C: type 'مریم' (ambiguous), save -> expect چند بیمار msg ==")
page = fresh_page()
page.picker.setFocus()
pump(2)
type_text(page.picker, "مریم")
w, pop_open = try_save(page, "save ambiguous")
c_ok = any("چند بیمار" in m for m in w)
print("  FLOW C OK" if c_ok else "  FLOW C BUG: %r" % w)

print("== Flow D: Enter-select from popup, save ==")
page = fresh_page()
picker = page.picker
picker.setFocus()
pump(2)
type_text(picker, "زهرا")
pop = picker._comp.popup()
print("  popup rows:", picker._model.rowCount(), "visible:", pop.isVisible())
QtTest.QTest.keyClick(picker, _Core.Qt.Key_Down)
pump(3)
QtTest.QTest.keyClick(picker, _Core.Qt.Key_Return)
pump(8)
print("  after enter: text=%r patient=%r" % (
    picker.text(), picker.patient["id"] if picker.patient else None))
w, pop_open = try_save(page, "save after enter-pick")
d_ok = not any("الزامی" in m for m in w) and not pop_open
print("  FLOW D OK" if d_ok else "  FLOW D BUG")

print("== Flow E: edit existing invoice (set_patient), save ==")
inv_id = models.list_archive_invoices()[0]["id"]
page = fresh_page()
page.load_invoice_for_edit(inv_id)
pump(4)
print("  patient=%r text=%r" % (
    page.picker.patient["id"] if page.picker.patient else None,
    page.picker.text()))
w, pop_open = try_save(page, "save edit")
e_ok = not any("الزامی" in m for m in w) and not pop_open
print("  FLOW E OK" if e_ok else "  FLOW E BUG")

print("== Flow F: type file number ۷۰۰۰۱, click suggestion, save ==")
page = fresh_page()
page.picker.setFocus()
pump(2)
type_text(page.picker, "۷۰۰۰۱")
view = popup_view(page.picker)
pop = page.picker._comp.popup()
print("  popup rows:", page.picker._model.rowCount())
if page.picker._model.rowCount():
    idx = view.model().index(0, 0)
    QtTest.QTest.mouseClick(view.viewport(), _Core.Qt.LeftButton,
                            _Core.Qt.NoModifier,
                            view.visualRect(idx).center())
    pump(6)
print("  patient=%r" % (page.picker.patient["id"]
                        if page.picker.patient else None))
w, pop_open = try_save(page, "save file-no")
f_ok = not any("الزامی" in m for m in w) and not pop_open
print("  FLOW F OK" if f_ok else "  FLOW F BUG")

print("== Flow G: type unique full name, click save directly (no Tab) ==")
page = fresh_page()
page.picker.setFocus()
pump(2)
type_text(page.picker, "زهرا محمدی")
w, pop_open = try_save(page, "save typed")
g_ok = not any("الزامی" in m for m in w) and not pop_open
print("  FLOW G OK" if g_ok else "  FLOW G BUG")

print("== Flow H: click suggestion, then click another field, save ==")
page = fresh_page()
click_suggestion(page, 1)
page.doctor.setFocus()
pump(3)
page.notes.setFocus()
pump(3)
w, pop_open = try_save(page, "save after refocus")
h_ok = not any("الزامی" in m for m in w) and not pop_open
print("  FLOW H OK" if h_ok else "  FLOW H BUG")

allok = a_ok and b_ok and c_ok and d_ok and e_ok and f_ok and g_ok and h_ok

print("== Flow I: type non-existent name, save -> expect یافت نشد ==")
page = fresh_page()
page.picker.setFocus()
pump(2)
type_text(page.picker, "ناموجود کاملن")
w, pop_open = try_save(page, "save no-match")
i_ok = any("یافت نشد" in m for m in w)
print("  FLOW I OK" if i_ok else "  FLOW I BUG: %r" % w)

print("== Flow J: empty picker, save -> expect الزامی ==")
page = fresh_page()
w, pop_open = try_save(page, "save empty")
j_ok = any("الزامی" in m for m in w)
print("  FLOW J OK" if j_ok else "  FLOW J BUG: %r" % w)

print("== Status line states ==")
page = fresh_page()
st0 = page.patient_status.text()
click_suggestion(page, 0)
st1 = page.patient_status.text()
page.picker.set_patient(None)
page.picker.insert("ناموجود")
pump(4)
st2 = page.patient_status.text()
page.picker.set_patient(None)
page.picker.insert("مریم")
pump(4)
st3 = page.patient_status.text()
print("  empty-hint:", repr(st0[:40]))
print("  selected  :", repr(st1[:40]))
print("  no-match  :", repr(st2[:40]))
print("  ambiguous :", repr(st3[:40]))
s_ok = ("تایپ کنید" in st0 and "✓" in st1 and "یافت نشد" in st2
        and "بیمار یافت شد" in st3)
print("  STATUS OK" if s_ok else "  STATUS BUG")

print("== Fallback: model wiped before activated (defensive _rows path) ==")
page = fresh_page()
picker = page.picker
picker.setFocus()
pump(2)
type_text(picker, "مریم")
disp = picker._model.item(0).text()
# simulate worst-case ordering: textChanged re-search wipes the model
picker.setText(disp)          # -> _refill(disp) -> 0 rows -> model empty
print("  model rows after wipe:", picker._model.rowCount())
picker._on_pick(disp)         # activated arrives late
fb_ok = picker.patient is not None and picker.patient["id"] == pid1
print("  patient=%s" % (picker.patient["id"] if picker.patient else None))
print("  FALLBACK OK" if fb_ok else "  FALLBACK BUG")

allok = allok and i_ok and j_ok and s_ok and fb_ok
print("RESULT:", "ALL FLOWS OK" if allok else "BUG REPRODUCED")
sys.exit(0 if allok else 1)
