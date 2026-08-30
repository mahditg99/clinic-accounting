# -*- coding: utf-8 -*-
"""فاکتور جدید - New invoice page."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..utils import Qt
from .. import models, settings, date_utils, money_utils
from ..dialogs.patient_search_dialog import PatientSearchDialog
from . import print_utils

_Widgets = Qt.QtWidgets
_Core = Qt.QtCore
_Gui = Qt.QtGui


class _ItemsModel(_Core.QAbstractTableModel):
    HEADERS = ["ردیف", "عنوان محصول", "قیمت فروش", "تعداد", "جمع ردیف"]

    def __init__(self):
        # type: () -> None
        super(_ItemsModel, self).__init__()
        self._rows = []  # type: List[Dict[str, Any]]

    def set_rows(self, rows):
        # type: (List[Dict[str, Any]]) -> None
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def rows(self):
        # type: () -> List[Dict[str, Any]]
        return self._rows

    def rowCount(self, parent=None):  # noqa
        return len(self._rows)

    def columnCount(self, parent=None):  # noqa
        return len(self.HEADERS)

    def headerData(self, section, orientation, role=None):  # noqa
        if role != _Core.Qt.DisplayRole:
            return None
        if orientation == _Core.Qt.Horizontal:
            return self.HEADERS[section]
        return section + 1

    def data(self, index, role=None):  # noqa
        if not index.isValid():
            return None
        r = self._rows[index.row()]
        if role == _Core.Qt.DisplayRole:
            if index.column() == 0:
                return date_utils.to_persian_digits(str(index.row() + 1))
            if index.column() == 1:
                return r["title"]
            if index.column() == 2:
                return money_utils.format_money_persian(r["unit_price"])
            if index.column() == 3:
                return date_utils.to_persian_digits(str(r["quantity"]))
            if index.column() == 4:
                return money_utils.format_money_persian(r["row_total"])
        if role == _Core.Qt.TextAlignmentRole:
            if index.column() in (2, 3, 4):
                return _Core.Qt.AlignCenter
            return _Core.Qt.AlignRight | _Core.Qt.AlignVCenter
        return None


class _PaymentsModel(_Core.QAbstractTableModel):
    HEADERS = ["ردیف", "نوع پرداخت", "مبلغ"]

    def __init__(self):
        # type: () -> None
        super(_PaymentsModel, self).__init__()
        self._rows = []  # type: List[Dict[str, Any]]

    def set_rows(self, rows):
        # type: (List[Dict[str, Any]]) -> None
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def rows(self):
        # type: () -> List[Dict[str, Any]]
        return self._rows

    def rowCount(self, parent=None):  # noqa
        return len(self._rows)

    def columnCount(self, parent=None):  # noqa
        return len(self.HEADERS)

    def headerData(self, section, orientation, role=None):  # noqa
        if role != _Core.Qt.DisplayRole:
            return None
        if orientation == _Core.Qt.Horizontal:
            return self.HEADERS[section]
        return section + 1

    def data(self, index, role=None):  # noqa
        if not index.isValid():
            return None
        r = self._rows[index.row()]
        if role == _Core.Qt.DisplayRole:
            if index.column() == 0:
                return date_utils.to_persian_digits(str(index.row() + 1))
            if index.column() == 1:
                return r["method"]
            if index.column() == 2:
                return money_utils.format_money_persian(r["amount"])
        if role == _Core.Qt.TextAlignmentRole:
            if index.column() == 2:
                return _Core.Qt.AlignCenter
            return _Core.Qt.AlignRight | _Core.Qt.AlignVCenter
        return None


class InvoicePage(_Widgets.QWidget):
    def __init__(self, main_window=None):
        # type: (Optional[Any]) -> None
        super(InvoicePage, self).__init__()
        self._main = main_window
        from ..utils import make_rtl, best_persian_font
        make_rtl(self)
        self.setFont(_Gui.QFont(best_persian_font(), 10))
        self._patient = None  # type: Optional[Dict[str, Any]]
        self._editing_invoice_id = None  # type: Optional[int]
        # product_id -> original quantity loaded from the invoice under edit.
        # The backend restores these to stock before validating a re-save; the
        # client stock guard must mirror that, or it blocks legitimate edits.
        self._original_item_qty = {}  # type: Dict[int, int]
        self._items_model = _ItemsModel()
        self._payments_model = _PaymentsModel()
        self._build_ui()
        self._refresh_combos()
        self._reset_form()

    # ------------------------------------------------------------------ #
    # UI construction
    # ------------------------------------------------------------------ #
    def _build_ui(self):
        layout = _Widgets.QVBoxLayout(self)

        title = _Widgets.QLabel("فاکتور جدید")
        title.setProperty("role", "page-title")
        title.setStyleSheet("")
        title.setAlignment(_Core.Qt.AlignCenter)
        layout.addWidget(title)

        # Top invoice meta row.
        meta_row = _Widgets.QHBoxLayout()
        self.pick_patient_btn = _Widgets.QPushButton("انتخاب بیمار")
        self.pick_patient_btn.clicked.connect(self._pick_patient)
        self.patient_label = _Widgets.QLabel("بیماری انتخاب نشده است")
        self.patient_label.setStyleSheet(
            "QLabel{border:1px solid #bbb; padding:6px; border-radius:4px;}")
        meta_row.addWidget(self.pick_patient_btn)
        meta_row.addWidget(self.patient_label, 1)
        layout.addLayout(meta_row)

        # Doctor + invoice number.
        info_row = _Widgets.QHBoxLayout()
        info_row.addWidget(_Widgets.QLabel("پزشک معالج:"))
        self.doctor_combo = _Widgets.QComboBox()
        info_row.addWidget(self.doctor_combo, 1)
        self.invoice_no_lbl = _Widgets.QLabel("شماره فاکتور: —")
        info_row.addWidget(self.invoice_no_lbl)
        layout.addLayout(info_row)

        # Items section.
        items_group = _Widgets.QGroupBox("اقلام فاکتور")
        items_layout = _Widgets.QVBoxLayout(items_group)
        # Add row.
        add_row = _Widgets.QHBoxLayout()
        add_row.addWidget(_Widgets.QLabel("وسیله طبی:"))
        self.product_combo = _Widgets.QComboBox()
        add_row.addWidget(self.product_combo, 2)
        add_row.addWidget(_Widgets.QLabel("فی:"))
        self.price_edit = _Widgets.QLineEdit()
        self.price_edit.setAlignment(_Core.Qt.AlignRight)
        self.price_edit.setValidator(_Gui.QRegExpValidator(_Core.QRegExp("^[0-9۰-۹,،]*$")))
        add_row.addWidget(self.price_edit)
        add_row.addWidget(_Widgets.QLabel("تعداد:"))
        self.qty_edit = _Widgets.QLineEdit("1")
        self.qty_edit.setAlignment(_Core.Qt.AlignRight)
        self.qty_edit.setValidator(_Gui.QIntValidator(1, 999999999))
        add_row.addWidget(self.qty_edit)
        self.stock_hint = _Widgets.QLabel("موجودی: —")
        self.stock_hint.setStyleSheet("QLabel{color:#1565c0; font-weight:bold;}")
        add_row.addWidget(self.stock_hint)
        self.add_item_btn = _Widgets.QPushButton("اضافه کن")
        self.add_item_btn.clicked.connect(self._add_item)
        self.remove_item_btn = _Widgets.QPushButton("حذف ردیف")
        self.remove_item_btn.clicked.connect(self._remove_item)
        add_row.addWidget(self.add_item_btn)
        add_row.addWidget(self.remove_item_btn)
        items_layout.addLayout(add_row)

        self.items_table = _Widgets.QTableView()
        self.items_table.setModel(self._items_model)
        self.items_table.setSelectionBehavior(_Widgets.QTableView.SelectRows)
        self.items_table.setSelectionMode(_Widgets.QTableView.SingleSelection)
        self.items_table.setEditTriggers(_Widgets.QTableView.NoEditTriggers)
        self.items_table.horizontalHeader().setStretchLastSection(True)
        self.items_table.verticalHeader().setVisible(False)
        self.items_table.verticalHeader().setDefaultSectionSize(26)
        items_layout.addWidget(self.items_table)
        layout.addWidget(items_group)

        # Payments section.
        pay_group = _Widgets.QGroupBox("پیش‌پرداخت / پرداخت‌ها")
        pay_layout = _Widgets.QVBoxLayout(pay_group)
        pay_row = _Widgets.QHBoxLayout()
        pay_row.addWidget(_Widgets.QLabel("نوع پرداخت:"))
        self.method_combo = _Widgets.QComboBox()
        pay_row.addWidget(self.method_combo, 1)
        pay_row.addWidget(_Widgets.QLabel("مبلغ:"))
        self.pay_amount_edit = _Widgets.QLineEdit()
        self.pay_amount_edit.setAlignment(_Core.Qt.AlignRight)
        self.pay_amount_edit.setValidator(_Gui.QRegExpValidator(_Core.QRegExp("^[0-9۰-۹,،]*$")))
        pay_row.addWidget(self.pay_amount_edit)
        self.add_pay_btn = _Widgets.QPushButton("اضافه ردیف پرداخت")
        self.add_pay_btn.clicked.connect(self._add_payment)
        self.remove_pay_btn = _Widgets.QPushButton("حذف ردیف پرداخت")
        self.remove_pay_btn.clicked.connect(self._remove_payment)
        pay_row.addWidget(self.add_pay_btn)
        pay_row.addWidget(self.remove_pay_btn)
        pay_layout.addLayout(pay_row)

        self.payments_table = _Widgets.QTableView()
        self.payments_table.setModel(self._payments_model)
        self.payments_table.setSelectionBehavior(_Widgets.QTableView.SelectRows)
        self.payments_table.setSelectionMode(_Widgets.QTableView.SingleSelection)
        self.payments_table.setEditTriggers(_Widgets.QTableView.NoEditTriggers)
        self.payments_table.horizontalHeader().setStretchLastSection(True)
        self.payments_table.verticalHeader().setVisible(False)
        self.payments_table.verticalHeader().setDefaultSectionSize(26)
        pay_layout.addWidget(self.payments_table)
        layout.addWidget(pay_group)

        # Totals + notes.
        totals_row = _Widgets.QHBoxLayout()
        from ..theme import make_totals_label
        self.total_lbl = make_totals_label("total")
        self.paid_lbl = make_totals_label("paid")
        self.remaining_lbl = make_totals_label("remaining")
        totals_row.addWidget(self.total_lbl, 1)
        totals_row.addWidget(self.paid_lbl, 1)
        totals_row.addWidget(self.remaining_lbl, 1)
        layout.addLayout(totals_row)

        notes_row = _Widgets.QHBoxLayout()
        notes_row.addWidget(_Widgets.QLabel("توضیحات:"))
        self.notes_edit = _Widgets.QLineEdit()
        self.notes_edit.setAlignment(_Core.Qt.AlignRight)
        notes_row.addWidget(self.notes_edit, 1)
        layout.addLayout(notes_row)

        # Bottom action buttons.
        actions_row = _Widgets.QHBoxLayout()
        from ..theme import primary
        self.save_btn = primary(_Widgets.QPushButton("ذخیره فاکتور"))
        self.save_btn.clicked.connect(self._save_invoice)
        self.print_btn = _Widgets.QPushButton("چاپ پیش‌نمایش فاکتور")
        self.print_btn.clicked.connect(self._print_preview)
        self.new_btn = _Widgets.QPushButton("پاک کردن فرم / جدید")
        self.new_btn.clicked.connect(self._reset_form)
        actions_row.addWidget(self.save_btn)
        actions_row.addWidget(self.print_btn)
        actions_row.addStretch(1)
        actions_row.addWidget(self.new_btn)
        layout.addLayout(actions_row)

        layout.addStretch(1)

    # ------------------------------------------------------------------ #
    # Combos / refresh
    # ------------------------------------------------------------------ #
    def refresh(self):
        # type: () -> None
        self._refresh_combos()
        self._reset_form()

    def _refresh_combos(self):
        # Doctors.
        self.doctor_combo.clear()
        for d in models.list_doctors_with_id():
            self.doctor_combo.addItem(d["name"], d["id"])
        # Products: only active AND stock > 0 are saleable.
        self._active_products = [p for p in models.list_products(active_only=True)
                                 if int(p.get("stock", 0)) > 0]
        self.product_combo.clear()
        self.product_combo.addItem("— بدون محصول —", None)
        for p in self._active_products:
            label = "%s - فروش: %s - موجودی: %s" % (
                p["title"],
                money_utils.format_money_persian(p["sale_price"]),
                date_utils.to_persian_digits(str(p["stock"])))
            self.product_combo.addItem(label, p["id"])
        # Payment methods.
        self.method_combo.clear()
        for m in settings.get_payment_methods():
            self.method_combo.addItem(m)
        # Selecting a product fills the price + stock hint.
        try:
            self.product_combo.currentIndexChanged.disconnect()
        except Exception:
            pass
        self.product_combo.currentIndexChanged.connect(self._on_product_changed)

    def _current_product(self):
        # type: () -> Optional[Dict[str, Any]]
        pid = self.product_combo.currentData()
        if pid is None:
            return None
        for p in getattr(self, "_active_products", []):
            if p["id"] == pid:
                return p
        return None

    def _on_product_changed(self, _index):
        p = self._current_product()
        if p is None:
            self.stock_hint.setText("موجودی: —")
            return
        self.price_edit.setText(
            date_utils.to_persian_digits(str(p["sale_price"])))
        self.stock_hint.setText(
            "موجودی: %s" % date_utils.to_persian_digits(str(p["stock"])))

    # ------------------------------------------------------------------ #
    # Patient
    # ------------------------------------------------------------------ #
    def _pick_patient(self):
        dlg = PatientSearchDialog(self)
        if dlg.exec_() == _Widgets.QDialog.Accepted:
            self._patient = dlg.selected_patient()
            self._update_patient_label()

    def _update_patient_label(self):
        if self._patient is None:
            self.patient_label.setText("بیماری انتخاب نشده است")
            return
        name = "%s %s" % (self._patient["first_name"], self._patient["last_name"])
        file_no = self._patient["file_no"]
        self.patient_label.setText("%s - شماره پرونده: %s" % (
            name, date_utils.to_persian_digits(file_no)))

    # ------------------------------------------------------------------ #
    # Items
    # ------------------------------------------------------------------ #
    def _add_item(self):
        from ..utils import error_msg, warning_msg
        p = self._current_product()
        if p is None:
            error_msg(self, "یک وسیله طبی انتخاب کنید.")
            return
        price = money_utils.parse_money(self.price_edit.text())
        if price is None or price < 0:
            error_msg(self, "قیمت فروش نامعتبر است.")
            return
        qty = money_utils.parse_int(self.qty_edit.text(), 0)
        if qty <= 0:
            error_msg(self, "تعداد باید بزرگ‌تر از صفر باشد.")
            return
        # Client-side stock guard: also aggregate demand from items already
        # in the list (the backend will re-validate authoritatively too).
        already = sum(int(r["quantity"]) for r in self._items_model.rows()
                      if r.get("product_id") == p["id"])
        # On edit, the invoice's original quantities for this product will be
        # returned to stock when the edit saves (models.save_invoice restores
        # old items before validating). Add that back here so the client guard
        # agrees with the backend instead of blocking a legitimate edit.
        restore = int(self._original_item_qty.get(p["id"], 0))
        avail = int(p["stock"]) + restore - already
        if qty > avail:
            error_msg(self,
                      "موجودی کافی نیست. محصول: %s. موجودی فعلی: %s. "
                      "تعداد درخواستی: %s" %
                      (p["title"], date_utils.to_persian_digits(str(int(p["stock"]))),
                       date_utils.to_persian_digits(str(qty))))
            return
        row = {
            "product_id": p["id"],
            "title": p["title"],
            "unit_price": price,
            "quantity": qty,
            "row_total": price * qty,
        }
        rows = self._items_model.rows()
        rows.append(row)
        self._items_model.set_rows(rows)
        self._update_totals()
        # Reset qty but keep product selected.
        self.qty_edit.setText("1")

    def _remove_item(self):
        idx = self.items_table.currentIndex()
        if not idx.isValid():
            return
        rows = self._items_model.rows()
        if 0 <= idx.row() < len(rows):
            del rows[idx.row()]
            self._items_model.set_rows(rows)
            self._update_totals()

    # ------------------------------------------------------------------ #
    # Payments
    # ------------------------------------------------------------------ #
    def _add_payment(self):
        from ..utils import error_msg
        method = self.method_combo.currentText()
        if method.strip() == "":
            error_msg(self, "روش پرداختی وجود ندارد. در تنظیمات اضافه کنید.")
            return
        amount = money_utils.parse_money(self.pay_amount_edit.text())
        if amount is None or amount <= 0:
            error_msg(self, "مبلغ پرداخت نامعتبر است.")
            return
        rows = self._payments_model.rows()
        rows.append({"method": method, "amount": amount,
                     "paid_at": date_utils.now_iso()})
        self._payments_model.set_rows(rows)
        self.pay_amount_edit.setText("")
        self._update_totals()

    def _remove_payment(self):
        idx = self.payments_table.currentIndex()
        if not idx.isValid():
            return
        rows = self._payments_model.rows()
        if 0 <= idx.row() < len(rows):
            del rows[idx.row()]
            self._payments_model.set_rows(rows)
            self._update_totals()

    # ------------------------------------------------------------------ #
    # Totals
    # ------------------------------------------------------------------ #
    def _update_totals(self):
        from ..money_utils import format_money_persian
        total = sum(int(r["row_total"]) for r in self._items_model.rows())
        paid = sum(int(r["amount"]) for r in self._payments_model.rows())
        remaining = total - paid
        self.total_lbl.setText("جمع کل: %s" % format_money_persian(total))
        self.paid_lbl.setText("پرداخت‌شده / پیش‌پرداخت: %s" %
                              format_money_persian(paid))
        self.remaining_lbl.setText("باقی مانده: %s" % format_money_persian(remaining))

    # ------------------------------------------------------------------ #
    # Save
    # ------------------------------------------------------------------ #
    def _save_invoice(self):
        from ..utils import error_msg, warning_msg, confirm_msg, info_msg
        if self._patient is None:
            error_msg(self, "ابتدا بیمار را انتخاب کنید.")
            return
        rows = self._items_model.rows()
        if len(rows) == 0:
            error_msg(self, "فاکتور باید حداقل یک ردیف داشته باشد.")
            return
        total = sum(int(r["row_total"]) for r in rows)
        paid = sum(int(r["amount"]) for r in self._payments_model.rows())
        if paid > total and not confirm_msg(
                self,
                "مجموع پرداخت‌ها از جمع کل فاکتور بیشتر است. آیا مایل به ادامه هستید؟"):
            return
        doctor_id = self.doctor_combo.currentData()
        notes = self.notes_edit.text().strip()
        # Determine issued_at.
        update_date = False
        if self._editing_invoice_id is not None:
            update_date = settings.get_setting(
                "update_invoice_date_on_edit", "0") == "1"
        if self._editing_invoice_id is not None and not update_date:
            inv = models.get_invoice(self._editing_invoice_id)
            issued_at = inv["issued_at"] if inv else date_utils.today_iso()
        else:
            issued_at = date_utils.today_iso()
        try:
            inv_id = models.save_invoice(
                self._patient["id"], doctor_id, issued_at, rows,
                self._payments_model.rows(), notes,
                invoice_id=self._editing_invoice_id,
                update_issued=update_date)
        except Exception as exc:
            error_msg(self, "خطا در ذخیره فاکتور: %s" % str(exc))
            return
        info_msg(self, "فاکتور با موفقیت ذخیره شد." if not update_date
                 else "فاکتور با موفقیت ویرایش شد.")
        if self._main is not None:
            try:
                self._main.refresh_other_pages()
            except Exception:
                pass
        self._reset_form()

    # ------------------------------------------------------------------ #
    # Print preview
    # ------------------------------------------------------------------ #
    def _print_preview(self):
        from ..utils import error_msg
        if self._patient is None and self._editing_invoice_id is None:
            error_msg(self, "ابتدا بیمار را انتخاب کنید یا فاکتور را ذخیره کنید.")
            return
        rows = self._items_model.rows()
        if len(rows) == 0:
            error_msg(self, "فاکتور خالی است.")
            return
        total = sum(int(r["row_total"]) for r in rows)
        paid = sum(int(r["amount"]) for r in self._payments_model.rows())
        remaining = total - paid
        app_title = settings.get_setting("app_title", "آذران طب")
        show_doctor = settings.get_setting("show_doctor_in_print", "0") == "1"
        doctor_name = ""
        if show_doctor:
            doctor_name = self.doctor_combo.currentText()
        invoice_no = ""
        if self._editing_invoice_id is not None:
            inv = models.get_invoice(self._editing_invoice_id)
            invoice_no = inv["invoice_no"] if inv else ""
        else:
            invoice_no = "— پیش‌نمایش —"
        invoice = {
            "app_title": app_title,
            "invoice_no": str(invoice_no),
            "issued_at": date_utils.today_iso(),
            "patient_name": "%s %s" % (self._patient["first_name"],
                                       self._patient["last_name"])
                            if self._patient else "",
            "file_no": self._patient["file_no"] if self._patient else "",
            "doctor_name": doctor_name,
            "rows": [dict(r, index=i + 1) for i, r in enumerate(rows)],
            "total": total,
            "paid": paid,
            "remaining": remaining,
            "show_doctor": show_doctor,
        }
        html = print_utils.build_invoice_html(invoice)
        print_utils.show_print_preview(self, html)

    # ------------------------------------------------------------------ #
    # Reset / load for edit
    # ------------------------------------------------------------------ #
    def _reset_form(self):
        self._patient = None
        self._editing_invoice_id = None
        self._original_item_qty = {}
        self._items_model.set_rows([])
        self._payments_model.set_rows([])
        self.notes_edit.setText("")
        self.price_edit.setText("")
        self.qty_edit.setText("1")
        self.pay_amount_edit.setText("")
        self.invoice_no_lbl.setText("شماره فاکتور: %s" %
                                    date_utils.to_persian_digits(
                                        str(models.next_invoice_no_stub())))
        self._update_patient_label()
        self._update_totals()

    def load_invoice_for_edit(self, invoice_id):
        # type: (int) -> None
        from ..utils import error_msg
        inv = models.get_invoice(invoice_id)
        if inv is None:
            error_msg(self, "فاکتور یافت نشد.")
            return
        if inv["is_deleted"]:
            error_msg(self, "این فاکتور باطل شده است.")
            return
        self._reset_form()
        self._editing_invoice_id = invoice_id
        # Patient.
        self._patient = {
            "id": inv["patient_id"],
            "file_no": inv["file_no"],
            "first_name": inv["first_name"],
            "last_name": inv["last_name"],
            "gender": inv["gender"],
        }
        self._update_patient_label()
        # Doctor.
        for i in range(self.doctor_combo.count()):
            if self.doctor_combo.itemData(i) == inv["doctor_id"]:
                self.doctor_combo.setCurrentIndex(i)
                break
        # Items.
        items = models.list_invoice_items(invoice_id)
        item_rows = []
        # Capture the invoice's original quantities per product so the client
        # stock guard can account for stock that will be restored on save
        # (mirrors models.save_invoice's restore-then-validate on edit).
        self._original_item_qty = {}  # type: Dict[int, int]
        for it in items:
            if it.get("product_id") is not None:
                pid = int(it["product_id"])
                self._original_item_qty[pid] = \
                    self._original_item_qty.get(pid, 0) + int(it["quantity"])
            item_rows.append({
                "product_id": it["product_id"],
                "title": it["title"],
                "unit_price": it["unit_price"],
                "cost_price": it.get("cost_price", 0),
                "quantity": it["quantity"],
                "row_total": it["row_total"],
            })
        self._items_model.set_rows(item_rows)
        # Payments.
        pays = models.list_payments(invoice_id)
        pay_rows = [{"method": p["method"],
                     "amount": p["amount"],
                     "paid_at": p["paid_at"]} for p in pays]
        self._payments_model.set_rows(pay_rows)
        # Notes + invoice no.
        self.notes_edit.setText(inv["notes"] or "")
        self.invoice_no_lbl.setText("شماره فاکتور: %s" %
                                    date_utils.to_persian_digits(str(inv["invoice_no"])))
        self._update_totals()
