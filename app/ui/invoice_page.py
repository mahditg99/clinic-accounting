# -*- coding: utf-8 -*-
"""Invoice page — mirrors webapp/templates/invoice_new.html (new + edit)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..utils import Qt, warning_msg, error_msg, confirm_msg, info_msg
from .. import models, settings as settings_mod, date_utils, money_utils
from . import fields as F
from . import printing
from ..theme import card, primary, success, danger, sum_card

_Core = Qt.QtCore
_Gui = Qt.QtGui
_W = Qt.QtWidgets


# --------------------------------------------------------------------------- #
class PatientPicker(F.FaLineEdit):
    """Patient search box with autocomplete (web's #patientSearch)."""

    patientChanged = _Core.Signal(object)  # dict | None

    def __init__(self, parent=None):
        super().__init__(parent, "جستجوی نام یا شماره پرونده...")
        self.setCompleter(None)
        self._comp = _W.QCompleter(self)
        self._comp.setCaseSensitivity(_Core.Qt.CaseInsensitive)
        self._comp.setFilterMode(_Core.Qt.MatchContains)
        self._comp.setMaxVisibleItems(8)
        try:
            self._comp.setCompletionMode(_W.QCompleter.PopupCompletion)
        except Exception:
            pass
        self.setCompleter(self._comp)
        self._model = _Gui.QStandardItemModel(self)
        self._comp.setModel(self._model)
        self._comp.activated.connect(self._on_pick)
        # Roomy, readable suggestion rows (web .suggestion-list parity).
        pop = self._comp.popup()
        pop.setObjectName("pickerPopup")
        pop.setLayoutDirection(_Core.Qt.RightToLeft)
        pop.setUniformItemSizes(True)
        self.patient = None  # type: Optional[Dict[str, Any]]
        # Last suggestion list [(id, display)] — kept even after the model is
        # rebuilt, so a click/typed-exact-match always resolves to a patient.
        self._rows = []  # type: List[Any]
        self.textEdited.connect(self._on_typing)
        self.textChanged.connect(self._refill)
        # Leaving the field with a typed (but unclicked) name: accept it when
        # it identifies exactly one patient, so saving never "loses" it.
        self.editingFinished.connect(self._resolve_quiet)

    def _on_typing(self, _text):
        self.patient = None
        self.patientChanged.emit(None)

    def _refill(self, text):
        if self.patient is not None:
            return  # selection made; don't re-query the display string
        text = text.strip()
        if len(text) < 1:
            self._model.removeRows(0, self._model.rowCount())
            self._rows = []
            return
        # The completer inserts the clicked/accepted suggestion into the
        # field around the time it emits activated(); that insertion lands
        # here as a "search" for the full display string — which matches no
        # name and would wipe the suggestions before _on_pick can read them
        # (the pick silently vanishes -> "patient required" on save). If the
        # text is exactly one of the suggestions just shown, treat it as
        # that selection instead of re-searching.
        for pid, disp in self._rows:
            if disp == text:
                p = models.get_patient(pid)
                if p is not None:
                    self.patient = p
                    self._dismiss_popup()
                    self.patientChanged.emit(p)
                    return
        self._model.removeRows(0, self._model.rowCount())
        rows = self._search(text)
        self._rows = [(p["id"], disp) for p, disp in rows[:30]]
        for p, disp in rows[:30]:
            it = _Gui.QStandardItem(disp)
            it.setEditable(False)
            # Explicit roomy row: stylesheet item padding does not feed
            # QListView::sizeHintForRow, so set the height on the item.
            it.setSizeHint(_Core.QSize(0, 34))
            # UserRole, NOT the default role: setData without a role writes
            # DisplayRole and the popup would show the raw id instead of the
            # patient's name.
            it.setData(_Core.QVariant(p["id"]), _Core.Qt.UserRole)
            self._model.appendRow(it)
        pop = self._comp.popup()
        if pop is not None:
            pop.setMinimumWidth(max(280, self.width()))

    @staticmethod
    def _search(text):
        """[(patient, display-string)] — file-number and name queries."""
        seen = set()
        rows = []
        folded = F.en(text)
        queries = []
        if folded.isdigit():
            queries.append((folded, True))
        queries.append((text, False))
        for q, by_file in queries:
            for p in models.search_active_patients(q, by_file=by_file):
                if p["id"] in seen:
                    continue
                seen.add(p["id"])
                rows.append((p, "%s %s — پرونده %s" % (
                    p["first_name"], p["last_name"], F.fa(p["file_no"]))))
        return rows

    def _dismiss_popup(self):
        pop = self._comp.popup()
        if pop is not None:
            pop.hide()
        self._comp.setCompletionPrefix("")

    def close_popup(self):
        # Public hook for the page: after a reset the (now empty) popup must
        # not stay floating under the field.
        self._dismiss_popup()

    def _find_id(self, text):
        # type: (str) -> Optional[int]
        """Map a suggestion display-string to its patient id — model first,
        then the cached last-suggestion list (the model can be rebuilt by a
        textChanged that lands between the click and this lookup)."""
        for r in range(self._model.rowCount()):
            it = self._model.item(r)
            if it and it.text() == text:
                return int(it.data(_Core.Qt.UserRole))
        t = text.strip()
        for pid, disp in self._rows:
            if disp == t:
                return int(pid)
        return None

    def _on_pick(self, text):
        pid = self._find_id(text)
        if pid is None:
            return
        p = models.get_patient(pid)
        if p is None:
            return
        self.patient = p
        # Close the popup *before* setText, otherwise the completer
        # re-completes the full display string and leaves a stray
        # empty box floating under the field.
        self._dismiss_popup()
        if self.text() != text:
            self.setText(text)
        self.patientChanged.emit(p)

    def resolve_patient(self):
        # type: () -> Optional[Dict[str, Any]]
        """Current selection, or recover one from the typed text: exact
        popup-row match first, then a fresh search when it is unique."""
        if self.patient is not None:
            return self.patient
        text = self.text().strip()
        if not text:
            return None
        pid = self._find_id(self.text())
        if pid is not None:
            p = models.get_patient(pid)
            if p is not None:
                self.patient = p
                self.patientChanged.emit(p)
                return p
        rows = [p for p, _ in self._search(text)]
        if len(rows) == 1:
            self.patient = rows[0]
            self.patientChanged.emit(self.patient)
            return self.patient
        return None

    def ambiguous(self):
        # type: () -> bool
        """True when the typed text matches several patients (the user must
        pick one from the suggestion list)."""
        text = self.text().strip()
        if not text or self.patient is not None:
            return False
        return len(self._search(text)) > 1

    def _resolve_quiet(self):
        self._dismiss_popup()
        self.resolve_patient()

    def set_patient(self, p):
        # type: (Optional[Dict[str, Any]]) -> None
        self.patient = p
        if p:
            self.setText("%s %s — پرونده %s" % (
                p["first_name"], p["last_name"], F.fa(p["file_no"])))
        else:
            self.clear()
        self.patientChanged.emit(p)


# --------------------------------------------------------------------------- #
class ItemRow(_W.QWidget):
    changed = _Core.Signal()
    removed = _Core.Signal()

    def __init__(self, products, parent=None):
        super().__init__(parent)
        self.products = products
        self.product = None  # type: Optional[Dict[str, Any]]
        self.custom_title = ""
        outer = _W.QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 2)
        outer.setSpacing(2)
        h = _W.QHBoxLayout()
        h.setSpacing(6)
        self.prod_btn = _W.QPushButton("انتخاب کالا …")
        self.prod_btn.setMinimumWidth(190)
        self.menu = _W.QMenu(self.prod_btn)
        for p in self.products:
            label = "%s  |  قیمت %s  |  موجودی %s" % (
                p["title"], money_utils.format_money_persian(p["sale_price"]),
                F.fa(p["stock"]))
            act = self.menu.addAction(label)
            act.setData(_Core.QVariant(p["id"]))
            act.triggered.connect(lambda _=False, pp=p: self.set_product(pp))
        self.prod_btn.setMenu(self.menu)  # click opens the product menu
        self.qty = F.QtyEdit()
        self.qty.setPlaceholderText("تعداد")
        self.qty.setFixedWidth(80)
        # Default تعداد = ۱ for new rows (web parity): picking a product
        # immediately shows the row total without typing a quantity.
        # (Edit mode overwrites this with the stored quantity.)
        self.qty.set_value(1)
        self.unit = F.MoneyEdit()
        self.unit.setPlaceholderText("فی (تومان)")
        self.unit.setMinimumWidth(120)
        self.total = _W.QLabel("")
        self.total.setMinimumWidth(110)
        self.total.setAlignment(_Core.Qt.AlignRight | _Core.Qt.AlignVCenter)
        self.total.setStyleSheet(
            "background:#f4f8fa; border:1px solid #dbe4ea; border-radius:9px;"
            "padding:6px 8px; font-weight:700;")
        self.del_btn = _W.QPushButton("حذف")
        self.del_btn.setProperty("variant", "link")
        self.del_btn.setProperty("tone", "danger")
        self.del_btn.clicked.connect(self.removed.emit)
        h.addWidget(self.prod_btn)
        h.addWidget(self.qty)
        h.addWidget(self.unit)
        h.addWidget(self.total)
        h.addWidget(self.del_btn)
        outer.addLayout(h)
        self.stock_lbl = _W.QLabel("")
        self.stock_lbl.setStyleSheet("color:#5d7385; font-size:11px;")
        outer.addWidget(self.stock_lbl)
        self.qty.textChanged.connect(self._recompute)
        self.unit.textChanged.connect(self._recompute)

    def set_product(self, p):
        self.product = p
        self.prod_btn.setText(p["title"] or "کالای بدون نام")
        self.unit.set_value(int(p["sale_price"] or 0))
        self.stock_lbl.setText("موجودی: %s" % F.fa(p["stock"]))
        self._recompute()

    def _recompute(self):
        q, u = self.qty.value(), self.unit.value()
        self.total.setText(money_utils.format_money_persian(q * u)
                           if q and u else "")
        self.changed.emit()

    def is_valid(self):
        return self.qty.value() > 0 and self.unit.value() > 0

    def data(self):
        # type: () -> Optional[Dict[str, Any]]
        if not self.is_valid():
            return None
        title = ""
        pid = None
        if self.product is not None:
            pid = self.product["id"]
            title = self.product["title"]
        else:
            title = self.custom_title or "بدون عنوان"
        return {"product_id": pid, "title": title,
                "unit_price": self.unit.value(), "quantity": self.qty.value(),
                "row_total": self.unit.value() * self.qty.value()}


class PaymentRow(_W.QWidget):
    changed = _Core.Signal()
    removed = _Core.Signal()

    def __init__(self, methods, parent=None):
        super().__init__(parent)
        h = _W.QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)
        self.method = _W.QComboBox()
        self.method.addItems(list(methods))
        self.method.setMinimumWidth(130)
        self.amount = F.MoneyEdit()
        self.amount.setPlaceholderText("مبلغ")
        self.del_btn = _W.QPushButton("حذف")
        self.del_btn.setProperty("variant", "link")
        self.del_btn.setProperty("tone", "danger")
        self.del_btn.clicked.connect(self.removed.emit)
        h.addWidget(self.method)
        h.addWidget(self.amount, 1)
        h.addWidget(self.del_btn)
        self.amount.textChanged.connect(lambda _: self.changed.emit())

    def value(self):
        return self.amount.value()


# --------------------------------------------------------------------------- #
class InvoicePage(_W.QWidget):
    def __init__(self, window):
        super().__init__(window)
        self.window_ = window
        self.setLayoutDirection(_Core.Qt.RightToLeft)
        self._invoice_id = None  # type: Optional[int]
        self._invoice_no = ""
        self._item_rows = []  # type: List[ItemRow]
        self._pay_rows = []  # type: List[PaymentRow]

        outer = _W.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        area, v = F.page_shell()
        outer.addWidget(area)

        head = F.page_header("فاکتور جدید")
        v.addWidget(head)
        self.sub_lbl = _W.QLabel("")
        self.sub_lbl.setObjectName("sectionSub")

        cols = _W.QHBoxLayout()
        cols.setSpacing(14)
        cols.addWidget(self._build_info_card(), 2)
        cols.addWidget(self._build_items_card(), 3)
        v.addLayout(cols)
        v.addStretch(1)
        self._reset_state()

    # ------------------------------------------------------------------ #
    def _build_info_card(self):
        box = _W.QWidget()
        v = _W.QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)
        v.addWidget(F.card_title("مشخصات فاکتور"))

        v.addWidget(_W.QLabel("بیمار"))
        self.picker = PatientPicker()
        v.addWidget(self.picker)
        # Live, unambiguous feedback about the patient selection state —
        # the old single "الزامی است" message hid three different causes.
        self.patient_status = _W.QLabel("")
        self.patient_status.setObjectName("patientStatus")
        self.patient_status.setWordWrap(True)
        v.addWidget(self.patient_status)
        self.picker.patientChanged.connect(
            lambda _p: self._update_patient_status())
        self.picker.textChanged.connect(
            lambda _t: self._update_patient_status())

        v.addWidget(_W.QLabel("پزشک معالج"))
        self.doctor = _W.QComboBox()
        v.addWidget(self.doctor)

        v.addWidget(_W.QLabel("تاریخ صدور (شمسی)"))
        self.date = F.JalaliDateEdit(iso=date_utils.today_iso())
        v.addWidget(self.date)
        self.update_issued = _W.QCheckBox("به‌روزرسانی تاریخ صدور")
        self.update_issued.hide()
        v.addWidget(self.update_issued)

        v.addWidget(_W.QLabel("یادداشت"))
        self.notes = _W.QPlainTextEdit()
        self.notes.setMaximumHeight(70)
        v.addWidget(self.notes)

        self.print_btn = primary(_W.QPushButton("پیش‌نمایش چاپ"), 0)
        self.print_btn.clicked.connect(self._print_preview)
        v.addWidget(self.print_btn)
        v.addStretch(1)
        return card(box)

    def _build_items_card(self):
        box = _W.QWidget()
        v = _W.QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)
        v.addWidget(F.card_title("اقلام فاکتور"))
        self.items_host = _W.QWidget()
        self.items_lay = _W.QVBoxLayout(self.items_host)
        self.items_lay.setContentsMargins(0, 0, 0, 0)
        self.items_lay.setSpacing(6)
        v.addWidget(self.items_host)
        self.add_item_btn = _W.QPushButton("＋ افزودن کالا")
        self.add_item_btn.clicked.connect(lambda: self._add_item_row(None))
        v.addWidget(self.add_item_btn)

        v.addSpacing(10)
        v.addWidget(F.card_title("پرداخت‌ها"))
        self.pay_host = _W.QWidget()
        self.pay_lay = _W.QVBoxLayout(self.pay_host)
        self.pay_lay.setContentsMargins(0, 0, 0, 0)
        self.pay_lay.setSpacing(6)
        v.addWidget(self.pay_host)
        self.add_pay_btn = _W.QPushButton("＋ افزودن پرداخت")
        self.add_pay_btn.clicked.connect(lambda: self._add_pay_row(None))
        v.addWidget(self.add_pay_btn)

        tiles = _W.QHBoxLayout()
        tiles.setSpacing(10)
        self.tile_total = sum_card("جمع کل: ۰", "info")
        self.tile_paid = sum_card("پرداخت‌شده: ۰", "success")
        self.tile_rem = sum_card("باقی مانده: ۰", "warn")
        for t in (self.tile_total, self.tile_paid, self.tile_rem):
            t.setMinimumHeight(54)
            tiles.addWidget(t, 1)
        v.addLayout(tiles)

        self.save_btn = success(_W.QPushButton("ذخیره فاکتور"), 0)
        self.save_btn.setMinimumHeight(40)
        self.save_btn.clicked.connect(self._save)
        v.addWidget(self.save_btn)
        self.cancel_edit_btn = _W.QPushButton("انصراف از ویرایش")
        self.cancel_edit_btn.clicked.connect(self._reset_state)
        self.cancel_edit_btn.hide()
        v.addWidget(self.cancel_edit_btn)
        return card(box)

    # ------------------------------------------------------------------ #
    # Lists / state
    # ------------------------------------------------------------------ #
    def refresh(self):
        """Reload pickers; never clobber an in-progress form."""
        self._reload_doctors()

    def _reload_doctors(self):
        cur = self.doctor.currentData()
        self.doctor.clear()
        self.doctor.addItem("بدون معرف", _Core.QVariant(None))
        for d in models.list_doctors_with_id():
            if d["name"] == "بدون معرف":
                continue
            self.doctor.addItem(F.fa(d["name"]), _Core.QVariant(d["id"]))
        if cur is not None:
            idx = self.doctor.findData(_Core.QVariant(cur))
            if idx >= 0:
                self.doctor.setCurrentIndex(idx)

    def _reset_state(self, keep_doctor=False):
        self._invoice_id = None
        self._invoice_no = str(models.next_invoice_no_stub())
        self.sub_lbl.setText("شماره فاکتور: " + F.fa(self._invoice_no))
        self.window_.set_page_title("فاکتور جدید",
                                    "شماره فاکتور: " + F.fa(self._invoice_no))
        self.picker.set_patient(None)
        self.picker.close_popup()
        if not keep_doctor:
            self.doctor.setCurrentIndex(0)
        self.date.set_iso(date_utils.today_iso())
        self.update_issued.hide()
        self.update_issued.setChecked(False)
        self.notes.setPlainText("")
        for r in list(self._item_rows):
            r.deleteLater()
        self._item_rows = []
        for r in list(self._pay_rows):
            r.deleteLater()
        self._pay_rows = []
        self._recalc()

    def load_invoice_for_edit(self, invoice_id):
        inv = models.get_invoice(invoice_id)
        if inv is None or inv["is_deleted"]:
            warning_msg(self, "فاکتور یافت نشد.")
            return
        self._invoice_id = invoice_id
        self._invoice_no = str(inv["invoice_no"])
        self.sub_lbl.setText("شماره فاکتور: " + F.fa(self._invoice_no))
        self.window_.set_page_title("ویرایش فاکتور",
                                    "شماره فاکتور: " + F.fa(self._invoice_no))
        self.picker.set_patient(models.get_patient(inv["patient_id"]))
        self._reload_doctors()
        idx = self.doctor.findData(_Core.QVariant(inv["doctor_id"]))
        self.doctor.setCurrentIndex(max(idx, 0))
        self.date.set_iso((inv["issued_at"] or "")[:10])
        self.update_issued.show()
        self.notes.setPlainText(inv["notes"] or "")
        for r in list(self._item_rows):
            r.deleteLater()
        self._item_rows = []
        for it in models.list_invoice_items(invoice_id):
            self._add_item_row(it)
        for r in list(self._pay_rows):
            r.deleteLater()
        self._pay_rows = []
        for pm in models.list_payments(invoice_id):
            self._add_pay_row(pm)
        self.cancel_edit_btn.show()
        self._recalc()

    # ------------------------------------------------------------------ #
    # Rows
    # ------------------------------------------------------------------ #
    def _products(self):
        return models.list_products(active_only=True)

    def _add_item_row(self, preset):
        row = ItemRow(self._products())
        if preset:
            prod = None
            if preset.get("product_id"):
                for p in row.products:
                    if p["id"] == preset["product_id"]:
                        prod = p
                        break
            if prod is not None:
                row.product = prod
                row.prod_btn.setText(prod["title"] or "کالای بدون نام")
                row.stock_lbl.setText("موجودی: %s" % F.fa(prod["stock"]))
            row.custom_title = preset.get("title") or ""
            row.qty.setText(F.fa(preset["quantity"]))
            row.unit.set_value(int(preset["unit_price"] or 0))
        row.changed.connect(self._recalc)
        row.removed.connect(lambda r=row: self._drop_row(self._item_rows,
                                                         self.items_lay, r))
        self._item_rows.append(row)
        self.items_lay.addWidget(row)
        self._recalc()
        return row

    def _add_pay_row(self, preset):
        row = PaymentRow(settings_mod.get_payment_methods())
        if preset:
            idx = row.method.findText(preset["method"])
            if idx >= 0:
                row.method.setCurrentIndex(idx)
            row.amount.set_value(int(preset["amount"]))
        row.changed.connect(self._recalc)
        row.removed.connect(lambda r=row: self._drop_row(self._pay_rows,
                                                         self.pay_lay, r))
        self._pay_rows.append(row)
        self.pay_lay.addWidget(row)
        self._recalc()
        return row

    @staticmethod
    def _drop_row(rows, layout, row):
        if row in rows:
            rows.remove(row)
        layout.removeWidget(row)
        row.deleteLater()
        # schedule recalc on the owning page
        w = row.parent()
        while w is not None and not isinstance(w, InvoicePage):
            w = w.parent()
        if w is not None:
            w._recalc()

    # ------------------------------------------------------------------ #
    def _update_patient_status(self):
        p = self.picker.patient
        if p is not None:
            self.patient_status.setText(
                "✓ بیمار انتخاب شد: %s %s — پرونده %s" % (
                    p["first_name"], p["last_name"], F.fa(p["file_no"])))
            self.patient_status.setStyleSheet(
                "color:#0a7a5c; font-size:12px; font-weight:600;")
            return
        text = self.picker.text().strip()
        if not text:
            self.patient_status.setText(
                "نام یا شماره پرونده را تایپ کنید و یکی را از فهرست انتخاب کنید.")
            self.patient_status.setStyleSheet(
                "color:#5d7385; font-size:11px;")
            return
        n = len(self.picker._rows)
        if n == 0:
            self.patient_status.setText(
                "⚠ بیماری با این نام یا شماره پرونده یافت نشد.")
            self.patient_status.setStyleSheet(
                "color:#c0392b; font-size:12px; font-weight:600;")
        elif n > 1:
            self.patient_status.setText(
                "⚠ %s بیمار یافت شد — برای ثبت فاکتور یکی را از فهرست "
                "پیشنهادی انتخاب کنید." % F.fa(n))
            self.patient_status.setStyleSheet(
                "color:#b06a00; font-size:12px; font-weight:600;")
        else:
            self.patient_status.setText(
                "۱ بیمار یافت شد — با کلیک روی پیشنهاد فهرست، انتخاب قطعی "
                "می‌شود.")
            self.patient_status.setStyleSheet(
                "color:#5d7385; font-size:11px;")

    # ------------------------------------------------------------------ #
    def _recalc(self):
        total = sum((r.data() or {}).get("row_total", 0) for r in self._item_rows)
        paid = sum(r.value() for r in self._pay_rows)
        self.tile_total.setText("جمع کل: %s" % money_utils.format_money_persian(total))
        self.tile_paid.setText("پرداخت‌شده: %s" % money_utils.format_money_persian(paid))
        self.tile_rem.setText("باقی مانده: %s" %
                              money_utils.format_money_persian(total - paid))
        # Web rule: add-item disabled until last item row is valid;
        # add-payment disabled until last payment has an amount.
        self.add_item_btn.setEnabled(
            not self._item_rows or self._item_rows[-1].is_valid())
        self.add_pay_btn.setEnabled(
            not self._pay_rows or self._pay_rows[-1].value() > 0)

    # ------------------------------------------------------------------ #
    def _collect(self):
        items = []
        for r in self._item_rows:
            d = r.data()
            if d:
                items.append(d)
        payments = []
        for r in self._pay_rows:
            if r.value() > 0:
                payments.append({"method": r.method.currentText(),
                                 "amount": r.value(),
                                 "paid_at": date_utils.now_iso()})
        return items, payments

    def _save(self):
        patient = self.picker.resolve_patient()
        if patient is None:
            text = self.picker.text().strip()
            if not text:
                warning_msg(self, "انتخاب بیمار الزامی است: نام یا شماره "
                                  "پرونده را تایپ کرده و یکی را از فهرست "
                                  "پیشنهادی انتخاب کنید.")
            elif self.picker.ambiguous():
                warning_msg(self, "چند بیمار با این عبارت یافت شد؛ لطفاً "
                                  "یکی را از فهرست پیشنهادی انتخاب کنید.")
            else:
                warning_msg(self, "بیماری با این نام یا شماره پرونده یافت "
                                  "نشد. اگر بیمار جدید است، ابتدا از صفحهٔ "
                                  "«پرونده‌ها» ثبتش کنید.")
            self._update_patient_status()
            return
        items, payments = self._collect()
        if not items:
            warning_msg(self, "حداقل یک ردیف کالا با تعداد و مبلغ معتبر "
                              "اضافه کنید.")
            return
        total = sum(i["row_total"] for i in items)
        paid = sum(p["amount"] for p in payments)
        if paid > total:
            over = paid - total
            msg = ("پرداخت بیش از مبلغ فاکتور است (مبلغ اضافه: %s تومان). "
                   "آیا ادامه می‌دهید؟" % money_utils.format_money_persian(over))
            if not confirm_msg(self, msg):
                return
        doctor_id = self.doctor.currentData()
        doctor_id = int(doctor_id) if doctor_id is not None else None
        try:
            inv_id = models.save_invoice(
                self.picker.patient["id"], doctor_id,
                self.date.iso() or date_utils.today_iso(),
                items, payments, self.notes.toPlainText().strip(),
                invoice_id=self._invoice_id,
                update_issued=self.update_issued.isChecked())
        except ValueError as exc:
            error_msg(self, str(exc))
            return
        except Exception as exc:
            error_msg(self, "خطا در ذخیره فاکتور: %s" % exc)
            return
        self._reset_state()
        # After a successful save jump straight to the A4 print preview —
        # the dialog has its own print button, so printing stays optional.
        try:
            printing.show_invoice_preview(self, inv_id)
        except Exception as exc:  # never lose the "saved" confirmation
            error_msg(self, "فاکتور ذخیره شد اما پیش‌نمایش چاپ باز نشد: %s" % exc)
        else:
            info_msg(self, "فاکتور با موفقیت ذخیره شد.")
        self.window_.goto("archive")
        return inv_id

    # ------------------------------------------------------------------ #
    def _print_preview(self):
        if self.picker.resolve_patient() is None:
            warning_msg(self, "ابتدا بیمار را از فهرست پیشنهادی انتخاب کنید.")
            self._update_patient_status()
            return
        items, payments = self._collect()
        if not items:
            warning_msg(self, "ابتدا حداقل یک کالا اضافه کنید.")
            return
        dlg = _W.QDialog(self)
        dlg.setWindowTitle("پیش‌نمایش چاپ")
        dlg.resize(760, 620)
        dlg.setLayoutDirection(_Core.Qt.RightToLeft)
        v = _W.QVBoxLayout(dlg)
        chk = _W.QCheckBox("درج نام پزشک معالج در فاکتور")
        chk.setChecked(settings_mod.get_setting("show_doctor_in_print",
                                                "0") == "1")
        v.addWidget(chk)
        view = _W.QTextEdit()
        view.setReadOnly(True)
        v.addWidget(view, 1)

        def html():
            total = sum(i["row_total"] for i in items)
            paid = sum(p["amount"] for p in payments)
            p = self.picker.patient
            return printing.build_proforma_html({
                "app_title": settings_mod.get_setting("app_title", "آذران طب"),
                "invoice_no": self._invoice_no,
                "issued_jalali": date_utils.iso_to_jalali_persian_str(
                    self.date.iso() or date_utils.today_iso()),
                "patient_name": "%s %s" % (p["first_name"], p["last_name"]),
                "file_no": p["file_no"],
                "doctor_name": self.doctor.currentText()
                if self.doctor.currentData() is not None else "",
                "show_doctor": chk.isChecked(),
                "notes": self.notes.toPlainText().strip(),
                "rows": items, "total": total, "paid": paid})

        def render():
            view.setHtml(html())

        chk.toggled.connect(lambda _: render())
        render()
        row = _W.QHBoxLayout()
        b_print = primary(_W.QPushButton("چاپ"), 110)
        b_close = _W.QPushButton("بستن")
        b_print.clicked.connect(
            lambda: printing.show_print_preview(dlg, html()))
        b_close.clicked.connect(dlg.accept)
        row.addWidget(b_print)
        row.addWidget(b_close)
        v.addLayout(row)
        dlg.exec_()
