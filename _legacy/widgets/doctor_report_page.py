# -*- coding: utf-8 -*-
"""گزارش پزشکان - Doctor report with patients/invoices/item-level details."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..utils import Qt
from .. import models, date_utils, money_utils
from ..dialogs.jalali_date_dialog import JalaliDateEdit
from . import print_utils

_Widgets = Qt.QtWidgets
_Core = Qt.QtCore
_Gui = Qt.QtGui


def _money(value):
    # type: (int) -> str
    return money_utils.format_money_persian(value)


class _StringTable(_Core.QAbstractTableModel):
    def __init__(self, headers):
        # type: (List[str]) -> None
        super(_StringTable, self).__init__()
        self.HEADERS = headers
        self._rows = []  # type: List[List[Any]]

    def set_rows(self, rows):
        # type: (List[List[Any]]) -> None
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def rows(self):
        # type: () -> List[List[Any]]
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
        return date_utils.to_persian_digits(str(section + 1))

    def data(self, index, role=None):  # noqa
        if not index.isValid():
            return None
        if role != _Core.Qt.DisplayRole:
            return None
        r = self._rows[index.row()]
        v = r[index.column()] if index.column() < len(r) else ""
        return str(v)


def _card(text, color):
    # type: (str, str) -> _Widgets.QLabel
    # Map legacy hex accent colors onto the design-system tones.
    tone = {"#1565c0": "info", "#00838f": "info", "#2e7d32": "success",
            "#6a1b9a": "accent", "#ef6c00": "warn",
            "#c62828": "danger"}.get(color, "info")
    from ..theme import sum_card
    return sum_card(text, tone)


def _make_table(model):
    # type: (_StringTable) -> _Widgets.QTableView
    t = _Widgets.QTableView()
    t.setModel(model)
    t.setEditTriggers(_Widgets.QTableView.NoEditTriggers)
    t.horizontalHeader().setStretchLastSection(True)
    t.verticalHeader().setVisible(False)
    t.verticalHeader().setDefaultSectionSize(26)
    return t


class DoctorReportPage(_Widgets.QWidget):
    def __init__(self, main_window=None):
        # type: (Optional[Any]) -> None
        super(DoctorReportPage, self).__init__()
        self._main = main_window
        from ..utils import make_rtl, best_persian_font
        make_rtl(self)
        self.setFont(_Gui.QFont(best_persian_font(), 10))
        self._patients_model = _StringTable(
            ["ردیف", "شماره پرونده", "نام بیمار", "تعداد فاکتور",
             "جمع فروش", "جمع دریافتی", "باقی مانده"])
        self._invoices_model = _StringTable(
            ["ردیف", "شماره فاکتور", "تاریخ", "بیمار", "جمع کل",
             "هزینه خرید", "سود", "دریافتی", "باقی مانده"])
        self._items_model = _StringTable(
            ["ردیف", "شماره فاکتور", "تاریخ", "بیمار", "شماره پرونده",
             "محصول", "تعداد", "قیمت فروش", "قیمت خرید", "جمع ردیف", "سود ردیف"])
        self._last_report = None  # type: Optional[Dict[str, Any]]
        self._build_ui()
        self.refresh_doctors()

    def refresh_doctors(self):
        # type: () -> None
        self.doctor_combo.clear()
        self.doctor_combo.addItem("همه پزشکان", None)
        for d in models.list_doctors_with_id():
            self.doctor_combo.addItem(d["name"], d["id"])

    def _build_ui(self):
        from ..theme import card, section_title, primary
        layout = _Widgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(12)

        title = _Widgets.QLabel("گزارش پزشکان")
        title.setProperty("role", "page-title")
        title.setStyleSheet("")
        title.setAlignment(_Core.Qt.AlignCenter)
        layout.addWidget(title)

        # ---------------- Controls + summary card ----------------
        ctrl_holder = _Widgets.QWidget()
        cl = _Widgets.QVBoxLayout(ctrl_holder)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(10)
        cl.addWidget(section_title("عملکرد پزشک", "بیماران، فاکتورها و سود در محدوده تاریخ"))

        ctrl = _Widgets.QHBoxLayout()
        ctrl.setSpacing(6)
        ctrl.addWidget(_Widgets.QLabel("پزشک:"))
        self.doctor_combo = _Widgets.QComboBox()
        ctrl.addWidget(self.doctor_combo)
        ctrl.addWidget(_Widgets.QLabel("از تاریخ:"))
        self.date_from = JalaliDateEdit(self, initial="")
        ctrl.addWidget(self.date_from)
        ctrl.addWidget(_Widgets.QLabel("تا تاریخ:"))
        self.date_to = JalaliDateEdit(self, initial=date_utils.today_jalali_str())
        ctrl.addWidget(self.date_to)
        self.show_btn = primary(_Widgets.QPushButton("نمایش گزارش"), 130)
        self.show_btn.clicked.connect(self._show_report)
        self.print_btn = _Widgets.QPushButton("چاپ گزارش")
        self.print_btn.clicked.connect(self._print_report)
        ctrl.addWidget(self.show_btn)
        ctrl.addWidget(self.print_btn)
        ctrl.addStretch(1)
        cl.addLayout(ctrl)

        # Top summary cards.
        cards = _Widgets.QHBoxLayout()
        cards.setSpacing(10)
        self.card_patients = _card("تعداد بیماران معرفی‌شده: ۰", "#1565c0")
        self.card_invoices = _card("تعداد فاکتورها: ۰", "#00838f")
        self.card_sales = _card("جمع فروش: ۰", "#2e7d32")
        self.card_profit = _card("جمع سود: ۰", "#6a1b9a")
        self.card_received = _card("جمع دریافتی: ۰", "#ef6c00")
        self.card_remaining = _card("جمع باقی مانده: ۰", "#c62828")
        for c in (self.card_patients, self.card_invoices, self.card_sales,
                  self.card_profit, self.card_received, self.card_remaining):
            cards.addWidget(c, 1)
        cl.addLayout(cards)
        layout.addWidget(card(ctrl_holder))

        # ---------------- Sub-tabs card ----------------
        tabs_holder = _Widgets.QWidget()
        tl = _Widgets.QVBoxLayout(tabs_holder)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(8)
        tl.addWidget(section_title("جزئیات گزارش"))
        self.tabs = _Widgets.QTabWidget()
        self.tabs.setLayoutDirection(_Core.Qt.RightToLeft)
        self.patients_table = _make_table(self._patients_model)
        self.invoices_table = _make_table(self._invoices_model)
        self.items_table = _make_table(self._items_model)
        self.tabs.addTab(self.patients_table, "خلاصه بیماران")
        self.tabs.addTab(self.invoices_table, "خلاصه فاکتورها")
        self.tabs.addTab(self.items_table, "ریز اقلام فاکتورها")
        tl.addWidget(self.tabs, 1)
        layout.addWidget(card(tabs_holder), 1)

    def _show_report(self):
        from ..utils import error_msg
        doctor_id = self.doctor_combo.currentData()
        date_from_iso = self.date_from.iso_value()
        date_to_iso = self.date_to.iso_value()
        if doctor_id is None:
            error_msg(self, "لطفاً یک پزشک را انتخاب کنید (گزارش همه پزشکان در "
                            "صفحه فروش و سود در دسترس است).")
            return
        try:
            rep = models.doctor_report(doctor_id, date_from_iso, date_to_iso)
        except Exception as exc:
            error_msg(self, "خطا در اجرای گزارش: %s" % str(exc))
            return
        self._last_report = rep
        self.card_patients.setText(
            "تعداد بیماران معرفی‌شده: %s" %
            date_utils.to_persian_digits(str(rep["unique_patient_count"])))
        self.card_invoices.setText(
            "تعداد فاکتورها: %s" %
            date_utils.to_persian_digits(str(rep["invoice_count"])))
        self.card_sales.setText("جمع فروش: %s" % _money(rep["total_sales"]))
        self.card_profit.setText("جمع سود: %s" % _money(rep["total_profit"]))
        self.card_received.setText("جمع دریافتی: %s" % _money(rep["total_received"]))
        self.card_remaining.setText("جمع باقی مانده: %s" % _money(rep["total_remaining"]))

        self._patients_model.set_rows([
            [date_utils.to_persian_digits(str(i + 1)),
             date_utils.to_persian_digits(p["file_no"]),
             p["patient_name"],
             date_utils.to_persian_digits(str(p["invoice_count"])),
             _money(p["total_sales"]), _money(p["total_received"]),
             _money(p["remaining"])]
            for i, p in enumerate(rep["patients_summary"])])
        self._invoices_model.set_rows([
            [date_utils.to_persian_digits(str(i + 1)),
             date_utils.to_persian_digits(str(inv["invoice_no"])),
             date_utils.iso_to_jalali_persian_str(inv["issued_at"]),
             inv["patient_name"], _money(inv["total_amount"]),
             _money(inv["total_cost"]), _money(inv["total_profit"]),
             _money(inv["total_received"]), _money(inv["remaining"])]
            for i, inv in enumerate(rep["invoices_summary"])])
        self._items_model.set_rows([
            [date_utils.to_persian_digits(str(i + 1)),
             date_utils.to_persian_digits(str(it["invoice_no"])),
             date_utils.iso_to_jalali_persian_str(it["issued_at"]),
             it["patient_name"],
             date_utils.to_persian_digits(it["patient_file_no"]),
             it["product_title"],
             date_utils.to_persian_digits(str(it["quantity"])),
             _money(it["unit_price"]), _money(it["cost_price"]),
             _money(it["row_total"]), _money(it["row_profit"])]
            for i, it in enumerate(rep["invoice_items_detail"])])

    def _print_report(self):
        from ..utils import error_msg
        doctor_id = self.doctor_combo.currentData()
        if doctor_id is None:
            error_msg(self, "ابتدا یک پزشک را انتخاب کنید.")
            return
        rep = self._last_report
        if rep is None:
            rep = models.doctor_report(doctor_id, self.date_from.iso_value(),
                                       self.date_to.iso_value())
        doctor_name = self.doctor_combo.currentText()
        d_from = (date_utils.iso_to_jalali_persian_str(self.date_from.iso_value())
                  if self.date_from.iso_value() else "")
        d_to = (date_utils.iso_to_jalali_persian_str(self.date_to.iso_value())
                if self.date_to.iso_value() else "")
        title = "گزارش پزشک - %s (%s تا %s)" % (doctor_name, d_from or "—",
                                            d_to or "—")
        sections = [
            {"kind": "cards", "cards": [
                {"label": "تعداد بیماران",
                 "value": date_utils.to_persian_digits(str(rep["unique_patient_count"])),
                 "color": "#1565c0"},
                {"label": "تعداد فاکتورها",
                 "value": date_utils.to_persian_digits(str(rep["invoice_count"])),
                 "color": "#00838f"},
                {"label": "جمع فروش", "value": _money(rep["total_sales"]),
                 "color": "#2e7d32"},
                {"label": "جمع سود", "value": _money(rep["total_profit"]),
                 "color": "#6a1b9a"},
                {"label": "جمع دریافتی", "value": _money(rep["total_received"]),
                 "color": "#ef6c00"},
                {"label": "جمع باقی مانده",
                 "value": _money(rep["total_remaining"]), "color": "#c62828"},
            ]},
            {"kind": "text", "text": "خلاصه بیماران"},
            {"kind": "table",
             "columns": ["ردیف", "شماره پرونده", "نام بیمار", "تعداد فاکتور",
                         "جمع فروش", "جمع دریافتی", "باقی مانده"],
             "rows": [[date_utils.to_persian_digits(str(i + 1)),
                       date_utils.to_persian_digits(p["file_no"]),
                       p["patient_name"],
                       date_utils.to_persian_digits(str(p["invoice_count"])),
                       _money(p["total_sales"]), _money(p["total_received"]),
                       _money(p["remaining"])]
                      for i, p in enumerate(rep["patients_summary"])]},
            {"kind": "text", "text": "خلاصه فاکتورها"},
            {"kind": "table",
             "columns": ["ردیف", "شماره فاکتور", "تاریخ", "بیمار", "جمع کل",
                         "هزینه خرید", "سود", "دریافتی", "باقی مانده"],
             "rows": [[date_utils.to_persian_digits(str(i + 1)),
                       date_utils.to_persian_digits(str(inv["invoice_no"])),
                       date_utils.iso_to_jalali_persian_str(inv["issued_at"]),
                       inv["patient_name"], _money(inv["total_amount"]),
                       _money(inv["total_cost"]), _money(inv["total_profit"]),
                       _money(inv["total_received"]), _money(inv["remaining"])]
                      for i, inv in enumerate(rep["invoices_summary"])]},
            {"kind": "text", "text": "ریز اقلام فاکتورها"},
            {"kind": "table",
             "columns": ["ردیف", "شماره فاکتور", "تاریخ", "بیمار", "شماره پرونده",
                         "محصول", "تعداد", "قیمت فروش", "قیمت خرید",
                         "جمع ردیف", "سود ردیف"],
             "rows": [[date_utils.to_persian_digits(str(i + 1)),
                       date_utils.to_persian_digits(str(it["invoice_no"])),
                       date_utils.iso_to_jalali_persian_str(it["issued_at"]),
                       it["patient_name"],
                       date_utils.to_persian_digits(it["patient_file_no"]),
                       it["product_title"],
                       date_utils.to_persian_digits(str(it["quantity"])),
                       _money(it["unit_price"]), _money(it["cost_price"]),
                       _money(it["row_total"]), _money(it["row_profit"])]
                      for i, it in enumerate(rep["invoice_items_detail"])]},
        ]
        print_utils.show_print_preview(self, print_utils.build_report_html(title, sections))
