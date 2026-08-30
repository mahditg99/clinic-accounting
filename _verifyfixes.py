# -*- coding: utf-8 -*-
"""Verify the four user-reported fixes:
1. font family actually Vazirmatn
2. patient add (and doctor add) no longer crash
3. checkbox indicator visible (unchecked + checked)
4. products table action buttons not clipped
"""
import os
import sys
import tempfile

os.environ["QT_QPA_PLATFORM"] = "windows"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# throwaway DB
_tmpdb = os.path.join(tempfile.mkdtemp(), "verify_fixes.db")
from app import database
database._db_path = lambda: _tmpdb
database.init_db()

from app.utils import Qt, load_app_fonts, apply_app_font, setup_scaling
from app import auth_core
_W = Qt.QtWidgets
_Core = Qt.QtCore
_Gui = Qt.QtGui

setup_scaling()
app = _W.QApplication(sys.argv)
app.setLayoutDirection(_Core.Qt.RightToLeft)
ok_font = load_app_fonts()
apply_app_font(size=10)
from app.theme import apply_theme
apply_theme(app)

results = []
def check(name, cond, extra=""):
    results.append((name, bool(cond), extra))
    print(("PASS" if cond else "FAIL"), name, extra)

check("load_app_fonts returns True", ok_font)
fam = app.font().family()
check("app font is Vazirmatn", fam.lower() == "vazirmatn", "fam=%s" % fam)

# --- checkbox visibility probe ---
cb = _W.QCheckBox("تست")
cb.show()
pm = cb.grab()
img = pm.toImage()
# count pixels close to border color #c6d3dc or teal in the indicator zone
def count_px(image, pred):
    n = 0
    for y in range(image.height()):
        for x in range(image.width()):
            c = image.pixelColor(x, y)
            if pred(c):
                n += 1
    return n
border = count_px(img, lambda c: abs(c.red()-198)<40 and abs(c.green()-211)<40 and abs(c.blue()-220)<40)
check("checkbox indicator visible (unchecked)", border > 20, "border px=%d" % border)
cb.setChecked(True)
pm2 = cb.grab()
img2 = pm2.toImage()
teal = count_px(img2, lambda c: abs(c.red()-13)<50 and abs(c.green()-110)<50 and abs(c.blue()-140)<50)
white = count_px(img2, lambda c: c.red()>235 and c.green()>235 and c.blue()>235 and c.alpha()>200)
check("checkbox checked shows teal+check", teal > 60, "teal px=%d" % teal)

# --- patient add crash ---
from app.ui.shell import AppWindow
auth_core.ensure_admin()
win = AppWindow(username="admin")
win.show()
app.processEvents()
win.goto("patients")
app.processEvents()
# find the patients page via the stack
from app.ui.patients_page import PatientsPage
ppage = win.findChild(PatientsPage)
check("patients page found", ppage is not None)
ppage.file_no.setText("۰۰۱۲۳")
ppage.first.setText("مریم")
ppage.last.setText("حسینی")
ppage.phone.setText("09123456789")
ppage._save()
app.processEvents()
from app import models
ps = models.list_patients()
check("patient created (no crash)", len(ps) == 1 and ps[0]["file_no"] == "00123",
      "file_no=%s" % (ps[0]["file_no"] if ps else "-"))
check("phone keeps leading zero", ps and ps[0]["phone"] == "09123456789",
      "phone=%s" % (ps[0]["phone"] if ps else "-"))

# --- doctor add ---
from app.ui.doctors_page import DoctorsPage
win.goto("doctors")
app.processEvents()
dpage = win.findChild(DoctorsPage)
dpage.first.setText("رضا")
dpage.last.setText("کریمی")
dpage.specialty.setText("چشم‌پزشکی")
dpage.phone.setText("02112345678")
dpage._save()
app.processEvents()
ds = models.list_doctors_with_id()
new_doc = [d for d in ds if "کریمی" in (d.get("name") or "")]
check("doctor created (no crash)", len(new_doc) == 1, "total=%d" % len(ds))

# --- products add + table buttons clip probe ---
from app.ui.products_page import ProductsPage
win.goto("products")
app.processEvents()
prod = win.findChild(ProductsPage)
prod.title.setText("شارژر موبایل")
prod.purchase.set_value(150000)
prod.sale.set_value(250000)
prod.stock.set_value(5)
prod.low.set_value(2)
prod._save()
for _ in range(8):
    app.processEvents()
prod.table.viewport().update()
for _ in range(4):
    app.processEvents()
pr = models.list_products()
check("product created", len(pr) == 1)
# probe: the action column widget should show full "شارژ مجدد" text
from PyQt5.QtWidgets import QPushButton
batch_btn = None
for b in prod.table.findChildren(QPushButton):
    if b.text() == "شارژ مجدد":
        batch_btn = b
        break
check("batch button exists", batch_btn is not None)
if batch_btn is not None:
    # the style's own sizeHint already accounts for the QSS 12px font +
    # xs padding; the widget must get at least that width from the layout
    have = batch_btn.width()
    need = batch_btn.sizeHint().width()
    check("batch button not clipped", have >= need,
          "have=%d need=%d" % (have, need))

# --- scaling bootstrap ---
check("font DPI pinned to 96", os.environ.get("QT_FONT_DPI") == "96",
      "QT_FONT_DPI=%s" % os.environ.get("QT_FONT_DPI"))
from app.utils import system_scale_factor
check("system scale factor sane", system_scale_factor() >= 1.0,
      "factor=%s" % system_scale_factor())

# --- search boxes: placeholder must NOT be real text ---
check("patients filter starts empty", ppage.filter_edit.text() == ""
      and ppage.filter_edit.placeholderText() != "")
check("doctors filter starts empty", dpage.filter_edit.text() == ""
      and dpage.filter_edit.placeholderText() != "")
from app.ui.archive_page import ArchivePage
apage = win.findChild(ArchivePage)
check("archive search starts empty", apage.search.text() == ""
      and apage.search.placeholderText() != "")

# --- invoice patient picker ---
from app.ui.invoice_page import InvoicePage
import app.ui.invoice_page as IP
_dialogs = []
IP.warning_msg = lambda parent, text, *a, **k: _dialogs.append(("warn", text))
IP.info_msg = lambda parent, text, *a, **k: _dialogs.append(("info", text))
IP.error_msg = lambda parent, text, *a, **k: _dialogs.append(("err", text))
win.goto("invoice")
app.processEvents()
ipage = win.findChild(InvoicePage)
ipage.picker.setText("مریم")  # programmatic -> _refill queries the DB
for _ in range(3):
    app.processEvents()
check("picker shows suggestions", ipage.picker._model.rowCount() >= 1,
      "rows=%d" % ipage.picker._model.rowCount())
pop = ipage.picker._comp.popup()
pop.ensurePolished()
row_h = pop.sizeHintForRow(0)
check("picker rows roomy (not cramped)", row_h >= 28, "row h=%d" % row_h)
disp = ipage.picker._model.item(0).text()
check("picker rows show name not raw id",
      "مریم" in disp and not disp.strip().isdigit(), "disp=%s" % disp)
ipage.picker._on_pick(disp)
check("picker keeps selection", ipage.picker.patient is not None)
check("picker popup dismissed after pick",
      not ipage.picker._comp.popup().isVisible())
# build a valid invoice and save — must NOT warn about the patient
row = ipage._add_item_row(None)
p0 = pr[0]
row.set_product({"id": p0["id"], "title": p0["title"],
                 "sale_price": p0["sale_price"], "stock": p0["stock"]})
row.qty.set_value(2)
ipage._save()
app.processEvents()
inv_rows = models.list_archive_invoices()
check("invoice saved after picker pick", len(inv_rows) == 1,
      "invoices=%d dialogs=%s" % (len(inv_rows), _dialogs))
check("no 'patient required' warning",
      not any("الزامی" in t for kind, t in _dialogs if kind == "warn"))

# --- picker: typed-but-never-clicked name still resolvable ---
ipage._reset_state()
app.processEvents()
ipage.picker.setText("مریم")
for _ in range(3):
    app.processEvents()
resolved = ipage.picker.resolve_patient()
check("resolve_patient recovers unique match",
      resolved is not None and resolved["first_name"] == "مریم")

# --- picker: status line + completer-insertion guard ("patient required") ---
ipage._reset_state()
app.processEvents()
check("status line shows hint when empty",
      "تایپ کنید" in ipage.patient_status.text())
ipage.picker.setText("مریم")
for _ in range(3):
    app.processEvents()
disp3 = ipage.picker._model.item(0).text()
# Worst-case ordering: the completer inserts the full display string into
# the field *before* activated() reaches _on_pick; the old code wiped the
# model on that textChanged and the pick silently vanished.
ipage.picker.setText(disp3)
for _ in range(3):
    app.processEvents()
check("completer-inserted text auto-selects the patient",
      ipage.picker.patient is not None)
check("status line confirms selection",
      "✓" in ipage.patient_status.text())
ipage._reset_state()
app.processEvents()
ipage.picker.setText("ناشناس کامل")
for _ in range(3):
    app.processEvents()
check("status line warns on no match",
      "یافت نشد" in ipage.patient_status.text())
del _dialogs[:]
row = ipage._add_item_row(None)
row.qty.set_value(1)
row.unit.set_value(1000)
ipage._save()
check("no-match save says یافت نشد, not الزامی",
      any("یافت نشد" in t for kind, t in _dialogs)
      and not any("الزامی" in t for kind, t in _dialogs))

# --- archive: action column sized + buttons compact ---
# seed a 2nd invoice so sorting is observable across rows
from app import date_utils
pid2 = models.create_patient("00124", "زهرا", "محمدی", "", "09120000000", "")
models.save_invoice(pid2, None, date_utils.today_iso(),
                    [{"product_id": None, "title": "مشاوره",
                      "unit_price": 700000, "quantity": 1,
                      "row_total": 700000}], [], "")
aw = apage.table.columnWidth(8)
check("archive action column wide", aw >= 200, "w=%d" % aw)
apage.refresh()
for _ in range(6):
    app.processEvents()
apage.table.viewport().update()
for _ in range(4):
    app.processEvents()
am = apage.table.model()
check("archive shows both invoices", am.rowCount() == 2,
      "rows=%d" % am.rowCount())
from PyQt5.QtWidgets import QPushButton
void_btn = None
for b in apage.table.findChildren(QPushButton):
    if b.text() == "ابطال":
        void_btn = b
        break
check("archive void button exists", void_btn is not None)
if void_btn is not None:
    check("archive void button not clipped",
          void_btn.width() >= void_btn.sizeHint().width(),
          "have=%d need=%d" % (void_btn.width(),
                               void_btn.sizeHint().width()))

# --- click-to-sort on every table ---
hdr = apage.table.horizontalHeader()
hdr.setSortIndicator(0, _Core.Qt.AscendingOrder)  # simulate header click
app.processEvents()
am = apage.table.model()
col0 = [am.item(r, 0).data(_Core.Qt.UserRole) for r in range(am.rowCount())]
check("archive sorts asc by شماره", col0 == sorted(col0), "col0=%s" % col0)
col0t = [am.item(r, 0).text() for r in range(am.rowCount())]
check("شماره cells stay Persian after sort",
      not any(any(ch in "0123456789" for ch in t) for t in col0t),
      str(col0t))
hdr.setSortIndicator(0, _Core.Qt.DescendingOrder)
app.processEvents()
col0d = [am.item(r, 0).data(_Core.Qt.UserRole) for r in range(am.rowCount())]
check("archive sorts desc by شماره", col0d == sorted(col0d, reverse=True))
# index widgets must follow their rows after sorting
follow = all(apage.table.indexWidget(am.index(r, 8)) is not None
             for r in range(am.rowCount()))
check("action widgets follow sorted rows", follow)
# numeric-aware sort: money column 4 must sort by value not string
hdr.setSortIndicator(4, _Core.Qt.AscendingOrder)
app.processEvents()
col4 = [am.item(r, 4).data(_Core.Qt.UserRole) for r in range(am.rowCount())]
check("money column sorts numerically", col4 == sorted(col4), "col4=%s" % col4)
col4t = [am.item(r, 4).text() for r in range(am.rowCount())]
check("money cells stay Persian after sort",
      not any(any(ch in "0123456789" for ch in t) for t in col4t),
      str(col4t))
# sort survives a data reload (refill re-applies the active sort)
apage._reload()
app.processEvents()
col4b = [am.item(r, 4).data(_Core.Qt.UserRole) for r in range(am.rowCount())]
check("sort preserved after reload", col4b == sorted(col4b))
hdr.setSortIndicator(-1, _Core.Qt.AscendingOrder)  # reset for later probes

# --- compact action buttons: QSS applies AND painted height fits the row ---
probe_btn = _W.QPushButton("ویرایش")
probe_btn.setProperty("variant", "link")
probe_btn.setProperty("btnsize", "xs")
probe_btn.ensurePolished()
plain_link = _W.QPushButton("ویرایش")
plain_link.setProperty("variant", "link")
plain_link.ensurePolished()
check("btnsize=xs QSS actually applies",
      probe_btn.sizeHint().height() < plain_link.sizeHint().height(),
      "xs=%d link=%d" % (probe_btn.sizeHint().height(),
                         plain_link.sizeHint().height()))
btn0 = None
for r in range(am.rowCount()):
    w0 = apage.table.indexWidget(am.index(r, 8))
    if w0 is not None:
        bs = w0.findChildren(_W.QPushButton)
        if bs:
            btn0 = bs[0]
            break
check("archive action button widget found", btn0 is not None)
if btn0 is not None:
    rowh = apage.table.verticalHeader().sectionSize(0)
    # must be its full compact size (not squeezed by a stale cell geometry)
    # AND strictly smaller than the row (vertically centered, not touching)
    check("action button fits inside row (centered, not clipped)",
          btn0.sizeHint().height() <= btn0.height() < rowh,
          "btn h=%d hint=%d row h=%d" % (btn0.height(),
                                         btn0.sizeHint().height(), rowh))

# --- SVG icons must be complete (not 2x-clipped) at every size ---
from app.ui.shell import _svg_icon, _IC_SET, _IC_DOCS

def _quadrants(pm):
    img = pm.toImage()
    w, h = img.width(), img.height()
    q = {"TL": 0, "TR": 0, "BL": 0, "BR": 0}
    for y in range(h):
        for x in range(w):
            if img.pixelColor(x, y).alpha() > 40:
                q[("T" if y < h / 2 else "B") +
                  ("L" if x < w / 2 else "R")] += 1
    return q

q_set = _quadrants(_svg_icon(_IC_SET, "#0d6e8c", px=19))
check("settings gear icon complete (4 quadrants)", min(q_set.values()) >= 10,
      str(q_set))
q_doc = _quadrants(_svg_icon(_IC_DOCS, "#0d6e8c", px=19))
check("doctors icon complete (4 quadrants)", min(q_doc.values()) >= 10,
      str(q_doc))
br = _quadrants(_svg_icon('<rect x="14" y="14" width="8" height="8"/>',
                          "#000000", px=40))
check("bottom-right-only SVG paints", br["BR"] >= 50, str(br))

# --- every table cell shows Persian digits (no ASCII 0-9) ---
def _ascii_digits(view):
    m = view.model()
    bad = []
    for r in range(m.rowCount()):
        for c in range(m.columnCount()):
            it = m.item(r, c)
            if it and any(ch in "0123456789" for ch in it.text()):
                bad.append((r, c, it.text()))
    return bad

bad_arch = _ascii_digits(apage.table)
check("archive table all-Persian digits", not bad_arch, str(bad_arch[:3]))
ppage = win.pages["patients"]
ppage.refresh()
app.processEvents()
bad_pat = _ascii_digits(ppage.table)
check("patients table all-Persian digits", not bad_pat, str(bad_pat[:3]))
dpage = win.pages["dashboard"]
dpage.refresh()
app.processEvents()
bad_dash = _ascii_digits(dpage.low_table) + _ascii_digits(dpage.method_table)
check("dashboard tables all-Persian digits", not bad_dash, str(bad_dash[:3]))

# --- proportional columns: report tables must not stretch a money column ---
win.goto("product_sales")
app.processEvents()
ps = win.pages["product_sales"]
ps.refresh()
app.processEvents()
w_prod = ps.table.columnWidth(0)
w_profit = ps.table.columnWidth(4)
check("product_sales: محصول column wider than سود",
      w_prod > w_profit and w_prod >= 140,
      "prod=%d profit=%d" % (w_prod, w_profit))
check("product_sales: last column not stretched",
      not ps.table.horizontalHeader().stretchLastSection())
for key, attr, sidx in (("daily", "detail_table", 2),
                        ("financial", "receipts_detail_table", 0),
                        ("doctor_report", "invoices_table", 1)):
    win.goto(key)
    app.processEvents()
    t = getattr(win.pages[key], attr)
    hdr = t.horizontalHeader()
    check("%s stretch column set" % attr,
          hdr.sectionResizeMode(sidx) == _W.QHeaderView.Stretch
          and not hdr.stretchLastSection())

# --- settings: list rows visually separated + add-box uses placeholder ---
win.goto("settings")
app.processEvents()
sp = win.pages["settings"]
check("methods add-box: placeholder not pre-filled text",
      sp.methods_editor.input.text() == ""
      and sp.methods_editor.input.placeholderText() != "",
      "text=%r ph=%r" % (sp.methods_editor.input.text(),
                         sp.methods_editor.input.placeholderText()))
check("cats add-box: placeholder not pre-filled text",
      sp.cats_editor.input.text() == ""
      and sp.cats_editor.input.placeholderText() != "")
rows = sp.methods_editor.rows_lay.parent().findChildren(_W.QFrame)
rows = [r for r in rows if r.objectName() == "listRow"]
check("settings list rows exist", len(rows) >= 2, "n=%d" % len(rows))
if rows:
    r0 = rows[0]
    pm = r0.grab()
    img = pm.toImage()
    mid = img.height() // 2
    edge = img.pixelColor(0, mid)          # left border line (straight at mid)
    inner = img.pixelColor(img.width() // 2, img.height() - 4)  # below text
    # web .list-row parity: 1px #dbe4ea border around a light fill
    border_ok = (abs(edge.red() - 219) < 40 and abs(edge.green() - 228) < 40
                 and abs(edge.blue() - 234) < 40)
    fill_ok = abs(inner.red() - 247) < 25 and abs(inner.blue() - 252) < 25
    check("listRow border painted", border_ok,
          "edge=%s,%s,%s" % (edge.red(), edge.green(), edge.blue()))
    check("listRow fill distinct from border", fill_ok,
          "inner=%s,%s,%s" % (inner.red(), inner.green(), inner.blue()))

# --- RTL: header + cell text must hug the RIGHT edge (Persian tables) ---
def _text_side(view, logical, header=True):
    """Grab one section/cell and report which edge the dark text sits near."""
    hdr = view.horizontalHeader()
    if header:
        pm = hdr.grab()
        x = hdr.sectionViewportPosition(logical)
        w = hdr.sectionSize(logical)
        # header text #5d7385
        pred = lambda r, g, b: (60 < r < 160 and 90 < g < 165
                                and 105 < b < 185)
    else:
        pm = view.viewport().grab()
        x = view.columnViewportPosition(logical)
        w = view.columnWidth(logical)
        # cell text #0f2433 (very dark)
        pred = lambda r, g, b: (r < 90 and g < 110 and b < 130)
    img = pm.toImage()
    d = pm.devicePixelRatio() or 1.0
    x0, x1 = int(x * d), int((x + w) * d)
    minx, maxx = None, None
    for yy in range(0, img.height(), 2):
        for xx in range(max(0, x0), min(img.width(), x1)):
            c = img.pixel(xx, yy)
            r, g, b = (c >> 16) & 255, (c >> 8) & 255, c & 255
            if pred(r, g, b):
                if minx is None or xx < minx:
                    minx = xx
                if maxx is None or xx > maxx:
                    maxx = xx
    if minx is None:
        return None
    return "RIGHT" if (x1 - maxx) <= (minx - x0) else "LEFT"


win.goto("product_sales")
app.processEvents()
ps = win.pages["product_sales"]
ps.refresh()
app.processEvents()
sides = [_text_side(ps.table, c) for c in range(5)]
check("product_sales headers right-aligned (RTL)",
      all(s == "RIGHT" for s in sides), str(sides))
cell_sides = [_text_side(ps.table, c, header=False) for c in range(5)]
check("product_sales cells right-aligned (RTL)",
      all(s == "RIGHT" for s in cell_sides), str(cell_sides))

# --- lazy action widgets: archive must not build one widget per row ---
win.goto("archive")
app.processEvents()
ap = win.pages["archive"]
ap.refresh()
app.processEvents()
for _ in range(6):
    app.processEvents()
m = ap.table.model()
live = sum(1 for r in range(m.rowCount())
           if ap.table.indexWidget(m.index(r, 8)) is not None)
check("archive lazy buttons bounded (not one per row)",
      0 < live < 150, "live=%d rows=%d" % (live, m.rowCount()))

# --- hardware license subsystem (integration) ---
import json
from app import license as lic
from app import rsa_lite as _R

hw = lic.hardware_code()
check("license: hardware code format",
      len(hw.replace("-", "")) == 20 and hw.count("-") == 3, hw)
check("license: code is stable", hw == lic.hardware_code())
check("license: public key fingerprint matches",
      lic.public_fingerprint() == lic.KEY_FINGERPRINT)
check("license: source run is not gated", lic.enforcement_required() is False)
os.environ["AZARAN_LICENSE_ENFORCE"] = "1"
check("license: env var forces the gate", lic.enforcement_required() is True)
os.environ.pop("AZARAN_LICENSE_ENFORCE", None)

# Issue a real license with the vendor key, into a throwaway license dir.
_licdir = tempfile.mkdtemp()
_orig_base = database._base_dir
database._base_dir = lambda: _licdir
try:
    _priv = _R.key_from_json(open(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "keys",
        "issuer_private.json"), encoding="utf-8").read())
    check("license: vendor key matches the shipped public key",
          _R.fingerprint(_priv["n"]) == lic.public_fingerprint())
    _tok = lic.build_token(lic.make_payload(hw, "کلینیک تست",
                                            date_utils.today_iso(), None), _priv)
    with open(os.path.join(_licdir, "candidate.key"), "w", encoding="utf-8") as fh:
        fh.write(_tok + "\n")
    check("license: install writes license.key beside the exe dir",
          lic.install_license(os.path.join(_licdir, "candidate.key")).ok
          and os.path.exists(lic.license_path()))
    st = lic.verify()
    check("license: valid license verifies", st.ok and st.customer == "کلینیک تست",
          st.code)
    check("license: perpetual has no expiry", st.days_left is None)
    _other = lic.build_token(lic.make_payload("ABCDE-FGHIJ-KLMNP-QRSTU", "x",
                                              date_utils.today_iso(), None), _priv)
    check("license: foreign machine refused",
          lic.verify_token(_other).ok
          and lic._check_payload(json.loads(lic.canonical_payload(
              lic.make_payload("ABCDE-FGHIJ-KLMNP-QRSTU", "x",
                               date_utils.today_iso(), None)))).code == lic.HW_MISMATCH)
    check("license: tampered signature refused",
          lic.verify_token(_tok[:-5] + "AAABB").code == lic.BAD_SIGN)
    check("license: garbage file refused",
          lic.verify_token("not-a-license").code == lic.BAD_FORMAT)
    os.remove(lic.license_path())
    check("license: missing file reported", lic.verify().code == lic.MISSING)
finally:
    database._base_dir = _orig_base

# Activation dialog + sidebar entry point
from app.ui import license_dialog as LD
_dlg = LD.ActivationDialog(lic.Status(lic.MISSING, hw=hw))
check("license: activation dialog is RTL",
      _dlg.layoutDirection() == _Core.Qt.RightToLeft)
check("license: activation dialog shows the hardware code",
      any(w.text() == hw for w in _dlg.findChildren(_W.QLineEdit)))
_bt = set(b.text() for b in _dlg.findChildren(_W.QPushButton))
check("activation dialog offers file pick + exit",
      {"انتخاب فایل لایسنس…", "خروج", "کپی"} <= _bt, str(sorted(_bt)))
_btns = [b.text() for b in win.findChildren(_W.QPushButton)]
check("shell: sidebar exposes مجوز نرم‌افزار", "مجوز نرم‌افزار" in _btns)
check("shell: AppWindow.show_license exists",
      callable(getattr(win, "show_license", None)))

fails = [r for r in results if not r[1]]
print("=" * 40)
print("TOTAL %d  FAIL %d" % (len(results), len(fails)))
sys.exit(1 if fails else 0)
