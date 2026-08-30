# -*- coding: utf-8 -*-
"""گزارش‌های مالی - Financial reports page with sub-tabs.

Sub-tabs:
  A. دریافتی روزانه   - daily receipts
  B. دریافتی ماهیانه  - monthly receipts
  C. هزینه روزانه     - daily expenses (+ add/delete)
  D. هزینه ماهیانه    - monthly expenses
  E. فروش و سود       - sales & profit
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..utils import Qt
from .. import models, settings, date_utils, money_utils
from ..dialogs.jalali_date_dialog import JalaliDateEdit
from . import print_utils

_Widgets = Qt.QtWidgets
_Core = Qt.QtCore
_Gui = Qt.QtGui


_PERSIAN_MONTHS = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]


def _money(value):
    # type: (int) -> str
    return money_utils.format_money_persian(value)


# --------------------------------------------------------------------------- #
# Shared table models
# --------------------------------------------------------------------------- #

class _StringTable(_Core.QAbstractTableModel):
    """Generic read-only header+rows model backed by a list of lists."""

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

    def row_id(self, row_index):
        # type: (int) -> Optional[Any]
        """Return the UserRole id stored as a third element if present."""
        if 0 <= row_index < len(self._rows):
            r = self._rows[row_index]
            if len(r) > 3 and r[-1] == "__id__":
                return r[-2] if len(r) > 1 else None
        return None


# --------------------------------------------------------------------------- #
# Helper: Jalali month selector (year + month)
# --------------------------------------------------------------------------- #

class _JalaliMonthSelector(_Widgets.QWidget):
    def __init__(self, parent=None):
        # type: (Optional[_Widgets.QWidget]) -> None
        super(_JalaliMonthSelector, self).__init__(parent)
        from ..utils import make_rtl
        make_rtl(self)
        layout = _Widgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(_Widgets.QLabel("سال:"))
        self.year_spin = _Widgets.QSpinBox()
        self.year_spin.setRange(1300, 1500)
        self.year_spin.setValue(date_utils.jalali_year_now())
        layout.addWidget(self.year_spin)
        layout.addWidget(_Widgets.QLabel("ماه:"))
        self.month_spin = _Widgets.QSpinBox()
        self.month_spin.setRange(1, 12)
        self.month_spin.setValue(date_utils.jalali_month_now())
        layout.addWidget(self.month_spin)
        self.month_name = _Widgets.QLabel("—")
        layout.addWidget(self.month_name)
        self._update_name()
        self.month_spin.valueChanged.connect(self._update_name)
        self.year_spin.valueChanged.connect(self._update_name)
        layout.addStretch(1)

    def _update_name(self, _=None):
        m = self.month_spin.value()
        self.month_name.setText(
            _PERSIAN_MONTHS[m - 1] if 1 <= m <= 12 else "—")

    def range_iso(self):
        # type: () -> (str, str)
        return date_utils.jalali_month_range_iso(self.year_spin.value(),
                                                 self.month_spin.value())

    def label(self):
        # type: () -> str
        return "%s %s" % (date_utils.to_persian_digits(str(self.year_spin.value())),
                          _PERSIAN_MONTHS[self.month_spin.value() - 1])


def _make_table(model):
    # type: (_StringTable) -> _Widgets.QTableView
    t = _Widgets.QTableView()
    t.setModel(model)
    t.setEditTriggers(_Widgets.QTableView.NoEditTriggers)
    t.setSelectionBehavior(_Widgets.QTableView.SelectRows)
    t.setSelectionMode(_Widgets.QTableView.SingleSelection)
    t.horizontalHeader().setStretchLastSection(True)
    t.verticalHeader().setVisible(False)
    t.verticalHeader().setDefaultSectionSize(26)
    return t


def _card(text, color):
    # type: (str, str) -> _Widgets.QLabel
    # Map legacy hex accent colors onto the design-system tones.
    tone = {"#1565c0": "info", "#00838f": "info", "#2e7d32": "success",
            "#6a1b9a": "accent", "#ef6c00": "warn",
            "#c62828": "danger"}.get(color, "info")
    from ..theme import sum_card
    return sum_card(text, tone)


# --------------------------------------------------------------------------- #
# A. Daily receipts sub-tab
# --------------------------------------------------------------------------- #

class _DailyReceiptsTab(_Widgets.QWidget):
    def __init__(self, parent=None):
        # type: (Optional[_Widgets.QWidget]) -> None
        super(_DailyReceiptsTab, self).__init__(parent)
        from ..utils import make_rtl, best_persian_font
        make_rtl(self)
        self.setFont(_Gui.QFont(best_persian_font(), 10))
        self._summary = _StringTable(["ردیف", "روش پرداخت", "تعداد", "جمع"])
        self._detail = _StringTable(
            ["ردیف", "روش پرداخت", "زمان", "مبلغ", "شماره فاکتور",
             "شماره پرونده", "نام بیمار"])
        self._build_ui()

    def _build_ui(self):
        from ..theme import card, section_title, primary, success, danger
        layout = _Widgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Controls card.
        ctrl_holder = _Widgets.QWidget()
        cl = _Widgets.QVBoxLayout(ctrl_holder)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(10)
        cl.addWidget(section_title("دریافتی روزانه", "مشاهده دریافتی‌های یک روز خاص"))
        ctrl = _Widgets.QHBoxLayout()
        ctrl.setSpacing(6)
        ctrl.addWidget(_Widgets.QLabel("تاریخ:"))
        self.date_edit = JalaliDateEdit(self, initial=date_utils.today_jalali_str())
        ctrl.addWidget(self.date_edit)
        self.show_btn = primary(_Widgets.QPushButton("نمایش گزارش"), 130)
        self.show_btn.clicked.connect(self._show)
        self.print_btn = _Widgets.QPushButton("چاپ گزارش")
        self.print_btn.clicked.connect(self._print)
        ctrl.addWidget(self.show_btn)
        ctrl.addWidget(self.print_btn)
        ctrl.addStretch(1)
        cl.addLayout(ctrl)
        self.total_label = _card("مجموع دریافتی: ۰", "#2e7d32")
        cl.addWidget(self.total_label)
        layout.addWidget(card(ctrl_holder))

        # Summary card.
        sum_holder = _Widgets.QWidget()
        sl = _Widgets.QVBoxLayout(sum_holder)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(8)
        sl.addWidget(section_title("خلاصه بر اساس روش پرداخت"))
        self.summary_table = _make_table(self._summary)
        sl.addWidget(self.summary_table, 1)
        layout.addWidget(card(sum_holder), 1)

        # Detail card.
        det_holder = _Widgets.QWidget()
        dl = _Widgets.QVBoxLayout(det_holder)
        dl.setContentsMargins(0, 0, 0, 0)
        dl.setSpacing(8)
        dl.addWidget(section_title("مشخصات پرداخت‌ها"))
        self.detail_table = _make_table(self._detail)
        dl.addWidget(self.detail_table, 1)
        layout.addWidget(card(det_holder), 1)

    def _show(self):
        from ..utils import error_msg
        iso = self.date_edit.iso_value()
        if iso is None:
            error_msg(self, "تاریخ معتبر وارد کنید.")
            return
        rep = models.receipts_report(iso, iso)
        self.total_label.setText("مجموع دریافتی: %s" % _money(rep["total_received"]))
        self._summary.set_rows([
            [date_utils.to_persian_digits(str(i + 1)), s["method"],
             date_utils.to_persian_digits(str(s["count"])),
             _money(s["amount"])]
            for i, s in enumerate(rep["summary_by_method"])])
        self._detail.set_rows([
            [date_utils.to_persian_digits(str(i + 1)), p["method"],
             date_utils.to_persian_digits(str(p["paid_at"])[11:16] or ""),
             _money(p["amount"]),
             date_utils.to_persian_digits(str(p["invoice_no"])),
             date_utils.to_persian_digits(p["patient_file_no"]),
             p["patient_name"]]
            for i, p in enumerate(rep["payment_details"])])
        self._rep = rep
        self._iso = iso

    def _print(self):
        iso = self.date_edit.iso_value()
        if iso is None:
            return
        rep = models.receipts_report(iso, iso)
        title = "گزارش دریافتی روزانه - تاریخ %s" % date_utils.iso_to_jalali_persian_str(iso)
        sections = [
            {"kind": "text", "text": "مجموع دریافتی: %s تومان" % _money(rep["total_received"])},
            {"kind": "table", "columns": ["ردیف", "روش پرداخت", "تعداد", "جمع"],
             "rows": [[date_utils.to_persian_digits(str(i + 1)), s["method"],
                       date_utils.to_persian_digits(str(s["count"])),
                       _money(s["amount"])]
                      for i, s in enumerate(rep["summary_by_method"])]},
            {"kind": "table", "columns": ["ردیف", "روش پرداخت", "زمان", "مبلغ",
                                          "شماره فاکتور", "شماره پرونده", "نام بیمار"],
             "rows": [[date_utils.to_persian_digits(str(i + 1)), p["method"],
                       str(p["paid_at"])[11:16], _money(p["amount"]),
                       date_utils.to_persian_digits(str(p["invoice_no"])),
                       date_utils.to_persian_digits(p["patient_file_no"]),
                       p["patient_name"]]
                      for i, p in enumerate(rep["payment_details"])]},
        ]
        print_utils.show_print_preview(self, print_utils.build_report_html(title, sections))


# --------------------------------------------------------------------------- #
# B. Monthly receipts sub-tab
# --------------------------------------------------------------------------- #

class _MonthlyReceiptsTab(_Widgets.QWidget):
    def __init__(self, parent=None):
        # type: (Optional[_Widgets.QWidget]) -> None
        super(_MonthlyReceiptsTab, self).__init__(parent)
        from ..utils import make_rtl, best_persian_font
        make_rtl(self)
        self.setFont(_Gui.QFont(best_persian_font(), 10))
        self._summary = _StringTable(["ردیف", "روش پرداخت", "تعداد", "جمع"])
        self._selector = _JalaliMonthSelector(self)
        self._build_ui()

    def _build_ui(self):
        from ..theme import card, section_title, primary
        layout = _Widgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        ctrl_holder = _Widgets.QWidget()
        cl = _Widgets.QVBoxLayout(ctrl_holder)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(10)
        cl.addWidget(section_title("دریافتی ماهیانه", "خلاصه پرداخت‌ها در یک ماه شمسی"))
        ctrl = _Widgets.QHBoxLayout()
        ctrl.setSpacing(6)
        ctrl.addWidget(self._selector)
        self.show_btn = primary(_Widgets.QPushButton("نمایش گزارش"), 130)
        self.show_btn.clicked.connect(self._show)
        self.print_btn = _Widgets.QPushButton("چاپ گزارش")
        self.print_btn.clicked.connect(self._print)
        ctrl.addWidget(self.show_btn)
        ctrl.addWidget(self.print_btn)
        ctrl.addStretch(1)
        cl.addLayout(ctrl)
        self.total_label = _card("مجموع دریافتی: ۰", "#2e7d32")
        cl.addWidget(self.total_label)
        layout.addWidget(card(ctrl_holder))

        sum_holder = _Widgets.QWidget()
        sl = _Widgets.QVBoxLayout(sum_holder)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(8)
        sl.addWidget(section_title("خلاصه بر اساس روش پرداخت"))
        self.summary_table = _make_table(self._summary)
        sl.addWidget(self.summary_table, 1)
        layout.addWidget(card(sum_holder), 1)

    def _show(self):
        start, end = self._selector.range_iso()
        # receipts_report filters by substr(paid_at,1,10) >= start which
        # contains time; strip time for the date compare to behave correctly.
        start_d = start[:10]
        end_d = end[:10]
        rep = models.receipts_report(start_d, end_d)
        self.total_label.setText("مجموع دریافتی: %s" % _money(rep["total_received"]))
        self._summary.set_rows([
            [date_utils.to_persian_digits(str(i + 1)), s["method"],
             date_utils.to_persian_digits(str(s["count"])),
             _money(s["amount"])]
            for i, s in enumerate(rep["summary_by_method"])])
        self._rep = rep

    def _print(self):
        start, end = self._selector.range_iso()
        rep = models.receipts_report(start[:10], end[:10])
        title = "گزارش دریافتی ماهیانه - %s" % self._selector.label()
        sections = [
            {"kind": "text", "text": "مجموع دریافتی: %s تومان" % _money(rep["total_received"])},
            {"kind": "table", "columns": ["ردیف", "روش پرداخت", "تعداد", "جمع"],
             "rows": [[date_utils.to_persian_digits(str(i + 1)), s["method"],
                       date_utils.to_persian_digits(str(s["count"])),
                       _money(s["amount"])]
                      for i, s in enumerate(rep["summary_by_method"])]},
        ]
        print_utils.show_print_preview(self, print_utils.build_report_html(title, sections))


# --------------------------------------------------------------------------- #
# C. Daily expenses sub-tab (with add/delete form)
# --------------------------------------------------------------------------- #

class _DailyExpensesTab(_Widgets.QWidget):
    def __init__(self, parent=None):
        # type: (Optional[_Widgets.QWidget]) -> None
        super(_DailyExpensesTab, self).__init__(parent)
        from ..utils import make_rtl, best_persian_font
        make_rtl(self)
        self.setFont(_Gui.QFont(best_persian_font(), 10))
        self._model = _StringTable(["ردیف", "تاریخ", "مبلغ", "دسته‌بندی", "توضیحات", "", "__id__"])
        # hide the two trailing helper columns from view
        self._build_ui()

    def _build_ui(self):
        from ..theme import card, section_title, primary, success, danger
        layout = _Widgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Controls card.
        ctrl_holder = _Widgets.QWidget()
        cl = _Widgets.QVBoxLayout(ctrl_holder)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(10)
        cl.addWidget(section_title("هزینه روزانه", "ثبت یا مشاهده هزینه‌های یک روز"))
        ctrl = _Widgets.QHBoxLayout()
        ctrl.setSpacing(6)
        ctrl.addWidget(_Widgets.QLabel("تاریخ:"))
        self.date_edit = JalaliDateEdit(self, initial=date_utils.today_jalali_str())
        ctrl.addWidget(self.date_edit)
        self.show_btn = primary(_Widgets.QPushButton("نمایش گزارش"), 130)
        self.show_btn.clicked.connect(self._show_report)
        self.print_btn = _Widgets.QPushButton("چاپ گزارش")
        self.print_btn.clicked.connect(self._print)
        ctrl.addWidget(self.show_btn)
        ctrl.addWidget(self.print_btn)
        ctrl.addStretch(1)
        cl.addLayout(ctrl)
        self.total_label = _card("مجموع هزینه: ۰", "#c62828")
        cl.addWidget(self.total_label)
        layout.addWidget(card(ctrl_holder))

        # Expense-entry card.
        exp_holder = _Widgets.QWidget()
        ehl = _Widgets.QVBoxLayout(exp_holder)
        ehl.setContentsMargins(0, 0, 0, 0)
        ehl.setSpacing(10)
        ehl.addWidget(section_title("ثبت هزینه", "ثبت هزینه جدید با دسته‌بندی"))
        form = _Widgets.QHBoxLayout()
        form.setSpacing(6)
        form.addWidget(_Widgets.QLabel("مبلغ:"))
        self.amount_edit = _Widgets.QLineEdit()
        self.amount_edit.setAlignment(_Core.Qt.AlignRight)
        self.amount_edit.setValidator(_Gui.QRegExpValidator(_Core.QRegExp("^[0-9۰-۹]*$")))
        form.addWidget(self.amount_edit)
        form.addWidget(_Widgets.QLabel("دسته‌بندی:"))
        self.category_combo = _Widgets.QComboBox()
        for c in settings.get_expense_categories():
            self.category_combo.addItem(c)
        form.addWidget(self.category_combo)
        form.addWidget(_Widgets.QLabel("توضیحات:"))
        self.desc_edit = _Widgets.QLineEdit()
        self.desc_edit.setAlignment(_Core.Qt.AlignRight)
        form.addWidget(self.desc_edit, 1)
        form.addWidget(_Widgets.QLabel("تاریخ:"))
        self.exp_date = JalaliDateEdit(self, initial=date_utils.today_jalali_str())
        form.addWidget(self.exp_date)
        self.add_btn = success(_Widgets.QPushButton("ثبت هزینه"), 120)
        self.add_btn.clicked.connect(self._add_expense)
        self.del_btn = danger(_Widgets.QPushButton("حذف هزینه"), 120)
        self.del_btn.clicked.connect(self._delete_expense)
        form.addWidget(self.add_btn)
        form.addWidget(self.del_btn)
        ehl.addLayout(form)
        layout.addWidget(card(exp_holder))

        # Detail card.
        det_holder = _Widgets.QWidget()
        dl = _Widgets.QVBoxLayout(det_holder)
        dl.setContentsMargins(0, 0, 0, 0)
        dl.setSpacing(8)
        dl.addWidget(section_title("ریز هزینه‌ها"))
        self.table = _make_table(self._model)
        # hide the trailing helper columns (index 5,6).
        self.table.setColumnHidden(5, True)
        self.table.setColumnHidden(6, True)
        dl.addWidget(self.table, 1)
        layout.addWidget(card(det_holder), 1)

    def _refresh_categories(self):
        cur = self.category_combo.currentText()
        self.category_combo.clear()
        for c in settings.get_expense_categories():
            self.category_combo.addItem(c)
        if cur:
            idx = self.category_combo.findText(cur)
            if idx >= 0:
                self.category_combo.setCurrentIndex(idx)

    def _show_report(self):
        iso = self.date_edit.iso_value()
        self._refresh_categories()
        rep = models.expenses_report(iso, iso) if iso else models.expenses_report(None, None)
        self.total_label.setText("مجموع هزینه: %s" % _money(rep["total_expense"]))
        self._model.set_rows([
            [date_utils.to_persian_digits(str(i + 1)),
             date_utils.iso_to_jalali_persian_str(e["expense_date"]),
             _money(e["amount"]), e.get("category") or "متفرقه",
             e["description"] or "", "", e["id"]]
            for i, e in enumerate(rep["expense_details"])])
        self._rep = rep
        self._iso = iso

    def _add_expense(self):
        from ..utils import error_msg, info_msg
        amount = money_utils.parse_money(self.amount_edit.text())
        if amount is None or amount <= 0:
            error_msg(self, "مبلغ هزینه نامعتبر است.")
            return
        desc = self.desc_edit.text().strip()
        cat = self.category_combo.currentText().strip() or "متفرقه"
        date_iso = self.exp_date.iso_value()
        if date_iso is None:
            error_msg(self, "تاریخ هزینه نامعتبر است.")
            return
        try:
            models.add_expense(amount, desc, date_iso, cat)
        except Exception as exc:
            error_msg(self, "خطا در ثبت هزینه: %s" % str(exc))
            return
        info_msg(self, "هزینه ثبت شد.")
        self.amount_edit.setText("")
        self.desc_edit.setText("")
        self._show_report()

    def _delete_expense(self):
        from ..utils import error_msg, confirm_msg, info_msg
        idx = self.table.currentIndex()
        if not idx.isValid():
            error_msg(self, "یک هزینه را انتخاب کنید.")
            return
        eid = self._model.rows()[idx.row()][-1]
        if confirm_msg(self, "این هزینه حذف شود؟"):
            models.delete_expense(eid)
            info_msg(self, "هزینه حذف شد.")
            self._show_report()

    def _print(self):
        iso = self.date_edit.iso_value()
        rep = models.expenses_report(iso, iso) if iso else models.expenses_report(None, None)
        title = "گزارش هزینه روزانه - تاریخ %s" % (
            date_utils.iso_to_jalali_persian_str(iso) if iso else "همه")
        sections = [
            {"kind": "text", "text": "مجموع هزینه: %s تومان" % _money(rep["total_expense"])},
            {"kind": "table", "columns": ["ردیف", "تاریخ", "مبلغ", "دسته‌بندی", "توضیحات"],
             "rows": [[date_utils.to_persian_digits(str(i + 1)),
                       date_utils.iso_to_jalali_persian_str(e["expense_date"]),
                       _money(e["amount"]), e.get("category") or "متفرقه",
                       e["description"] or ""]
                      for i, e in enumerate(rep["expense_details"])]},
        ]
        print_utils.show_print_preview(self, print_utils.build_report_html(title, sections))


# --------------------------------------------------------------------------- #
# D. Monthly expenses sub-tab
# --------------------------------------------------------------------------- #

class _MonthlyExpensesTab(_Widgets.QWidget):
    def __init__(self, parent=None):
        # type: (Optional[_Widgets.QWidget]) -> None
        super(_MonthlyExpensesTab, self).__init__(parent)
        from ..utils import make_rtl, best_persian_font
        make_rtl(self)
        self.setFont(_Gui.QFont(best_persian_font(), 10))
        self._summary = _StringTable(["ردیف", "دسته‌بندی", "تعداد", "جمع"])
        self._detail = _StringTable(["ردیف", "تاریخ", "مبلغ", "دسته‌بندی", "توضیحات"])
        self._selector = _JalaliMonthSelector(self)
        self._build_ui()

    def _build_ui(self):
        from ..theme import card, section_title, primary
        layout = _Widgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        ctrl_holder = _Widgets.QWidget()
        cl = _Widgets.QVBoxLayout(ctrl_holder)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(10)
        cl.addWidget(section_title("هزینه ماهیانه", "خلاصه هزینه‌ها در یک ماه شمسی"))
        ctrl = _Widgets.QHBoxLayout()
        ctrl.setSpacing(6)
        ctrl.addWidget(self._selector)
        self.show_btn = primary(_Widgets.QPushButton("نمایش گزارش"), 130)
        self.show_btn.clicked.connect(self._show)
        self.print_btn = _Widgets.QPushButton("چاپ گزارش")
        self.print_btn.clicked.connect(self._print)
        ctrl.addWidget(self.show_btn)
        ctrl.addWidget(self.print_btn)
        ctrl.addStretch(1)
        cl.addLayout(ctrl)
        self.total_label = _card("مجموع هزینه: ۰", "#c62828")
        cl.addWidget(self.total_label)
        layout.addWidget(card(ctrl_holder))

        sum_holder = _Widgets.QWidget()
        sl = _Widgets.QVBoxLayout(sum_holder)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(8)
        sl.addWidget(section_title("خلاصه بر اساس دسته‌بندی"))
        self.summary_table = _make_table(self._summary)
        sl.addWidget(self.summary_table, 1)
        layout.addWidget(card(sum_holder), 1)

        det_holder = _Widgets.QWidget()
        dl = _Widgets.QVBoxLayout(det_holder)
        dl.setContentsMargins(0, 0, 0, 0)
        dl.setSpacing(8)
        dl.addWidget(section_title("ریز هزینه‌ها"))
        self.detail_table = _make_table(self._detail)
        dl.addWidget(self.detail_table, 1)
        layout.addWidget(card(det_holder), 1)

    def _show(self):
        start, end = self._selector.range_iso()
        rep = models.expenses_report(start[:10], end[:10])
        self.total_label.setText("مجموع هزینه: %s" % _money(rep["total_expense"]))
        self._summary.set_rows([
            [date_utils.to_persian_digits(str(i + 1)), s["category"],
             date_utils.to_persian_digits(str(s["count"])),
             _money(s["amount"])]
            for i, s in enumerate(rep["summary_by_category"])])
        self._detail.set_rows([
            [date_utils.to_persian_digits(str(i + 1)),
             date_utils.iso_to_jalali_persian_str(e["expense_date"]),
             _money(e["amount"]), e.get("category") or "متفرقه",
             e["description"] or ""]
            for i, e in enumerate(rep["expense_details"])])
        self._rep = rep

    def _print(self):
        start, end = self._selector.range_iso()
        rep = models.expenses_report(start[:10], end[:10])
        title = "گزارش هزینه ماهیانه - %s" % self._selector.label()
        sections = [
            {"kind": "text", "text": "مجموع هزینه: %s تومان" % _money(rep["total_expense"])},
            {"kind": "table", "columns": ["ردیف", "دسته‌بندی", "تعداد", "جمع"],
             "rows": [[date_utils.to_persian_digits(str(i + 1)), s["category"],
                       date_utils.to_persian_digits(str(s["count"])),
                       _money(s["amount"])]
                      for i, s in enumerate(rep["summary_by_category"])]},
            {"kind": "table", "columns": ["ردیف", "تاریخ", "مبلغ", "دسته‌بندی", "توضیحات"],
             "rows": [[date_utils.to_persian_digits(str(i + 1)),
                       date_utils.iso_to_jalali_persian_str(e["expense_date"]),
                       _money(e["amount"]), e.get("category") or "متفرقه",
                       e["description"] or ""]
                      for i, e in enumerate(rep["expense_details"])]},
        ]
        print_utils.show_print_preview(self, print_utils.build_report_html(title, sections))


# --------------------------------------------------------------------------- #
# E. Sales & profit sub-tab
# --------------------------------------------------------------------------- #

class _SalesProfitTab(_Widgets.QWidget):
    def __init__(self, parent=None):
        # type: (Optional[_Widgets.QWidget]) -> None
        super(_SalesProfitTab, self).__init__(parent)
        from ..utils import make_rtl, best_persian_font
        make_rtl(self)
        self.setFont(_Gui.QFont(best_persian_font(), 10))
        self._doctor = _StringTable(["ردیف", "پزشک", "تعداد فاکتور",
                                     "فروش ناخالص", "هزینه خرید", "سود"])
        self._product = _StringTable(["ردیف", "محصول", "تعداد", "جمع ردیف",
                                      "هزینه خرید", "سود"])
        self._selector = _JalaliMonthSelector(self)
        self._build_ui()

    def _build_ui(self):
        from ..theme import card, section_title, primary
        layout = _Widgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Controls + summary cards.
        ctrl_holder = _Widgets.QWidget()
        cl = _Widgets.QVBoxLayout(ctrl_holder)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(10)
        cl.addWidget(section_title("فروش و سود", "سود ناخالص و خالص در یک ماه شمسی"))
        ctrl = _Widgets.QHBoxLayout()
        ctrl.setSpacing(6)
        ctrl.addWidget(self._selector)
        self.show_btn = primary(_Widgets.QPushButton("نمایش گزارش"), 130)
        self.show_btn.clicked.connect(self._show)
        self.print_btn = _Widgets.QPushButton("چاپ گزارش")
        self.print_btn.clicked.connect(self._print)
        ctrl.addWidget(self.show_btn)
        ctrl.addWidget(self.print_btn)
        ctrl.addStretch(1)
        cl.addLayout(ctrl)

        cards = _Widgets.QHBoxLayout()
        cards.setSpacing(10)
        self.gross_card = _card("فروش ناخالص: ۰", "#1565c0")
        self.cogs_card = _card("هزینه خرید محصولات: ۰", "#c62828")
        self.profit_card = _card("سود فروش: ۰", "#2e7d32")
        self.exp_card = _card("هزینه‌های دوره: ۰", "#ef6c00")
        self.net_card = _card("خالص دوره: ۰", "#6a1b9a")
        for c in (self.gross_card, self.cogs_card, self.profit_card,
                  self.exp_card, self.net_card):
            cards.addWidget(c, 1)
        cl.addLayout(cards)
        layout.addWidget(card(ctrl_holder))

        doc_holder = _Widgets.QWidget()
        dol = _Widgets.QVBoxLayout(doc_holder)
        dol.setContentsMargins(0, 0, 0, 0)
        dol.setSpacing(8)
        dol.addWidget(section_title("خلاصه بر اساس پزشک"))
        self.doctor_table = _make_table(self._doctor)
        dol.addWidget(self.doctor_table, 1)
        layout.addWidget(card(doc_holder), 1)

        prod_holder = _Widgets.QWidget()
        pl = _Widgets.QVBoxLayout(prod_holder)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(8)
        pl.addWidget(section_title("خلاصه بر اساس محصول"))
        self.product_table = _make_table(self._product)
        pl.addWidget(self.product_table, 1)
        layout.addWidget(card(prod_holder), 1)

    def _show(self):
        start, end = self._selector.range_iso()
        rep = models.sales_profit_report(start[:10], end[:10])
        self.gross_card.setText("فروش ناخالص: %s" % _money(rep["gross_sales"]))
        self.cogs_card.setText("هزینه خرید محصولات: %s" %
                               _money(rep["cost_of_goods_sold"]))
        self.profit_card.setText("سود فروش: %s" % _money(rep["gross_profit"]))
        self.exp_card.setText("هزینه‌های دوره: %s" % _money(rep["total_expenses"]))
        self.net_card.setText("خالص دوره: %s" % _money(rep["net_profit"]))
        self._doctor.set_rows([
            [date_utils.to_persian_digits(str(i + 1)), d["doctor"],
             date_utils.to_persian_digits(str(d["invoice_count"])),
             _money(d["gross_sales"]), _money(d["total_cost"]),
             _money(d["profit"])]
            for i, d in enumerate(rep["summary_by_doctor"])])
        self._product.set_rows([
            [date_utils.to_persian_digits(str(i + 1)), d["product"],
             date_utils.to_persian_digits(str(d["quantity"])),
             _money(d["row_total"]), _money(d["row_cost"]),
             _money(d["profit"])]
            for i, d in enumerate(rep["summary_by_product"])])
        self._rep = rep

    def _print(self):
        start, end = self._selector.range_iso()
        rep = models.sales_profit_report(start[:10], end[:10])
        title = "گزارش فروش و سود - %s" % self._selector.label()
        sections = [
            {"kind": "cards", "cards": [
                {"label": "فروش ناخالص", "value": _money(rep["gross_sales"]),
                 "color": "#1565c0"},
                {"label": "هزینه خرید محصولات",
                 "value": _money(rep["cost_of_goods_sold"]), "color": "#c62828"},
                {"label": "سود فروش", "value": _money(rep["gross_profit"]),
                 "color": "#2e7d32"},
                {"label": "هزینه‌های دوره",
                 "value": _money(rep["total_expenses"]), "color": "#ef6c00"},
                {"label": "خالص دوره", "value": _money(rep["net_profit"]),
                 "color": "#6a1b9a"},
            ]},
            {"kind": "table", "columns": ["ردیف", "پزشک", "تعداد فاکتور",
                                          "فروش ناخالص", "هزینه خرید", "سود"],
             "rows": [[date_utils.to_persian_digits(str(i + 1)), d["doctor"],
                       date_utils.to_persian_digits(str(d["invoice_count"])),
                       _money(d["gross_sales"]), _money(d["total_cost"]),
                       _money(d["profit"])]
                      for i, d in enumerate(rep["summary_by_doctor"])]},
            {"kind": "table", "columns": ["ردیف", "محصول", "تعداد", "جمع ردیف",
                                          "هزینه خرید", "سود"],
             "rows": [[date_utils.to_persian_digits(str(i + 1)), d["product"],
                       date_utils.to_persian_digits(str(d["quantity"])),
                       _money(d["row_total"]), _money(d["row_cost"]),
                       _money(d["profit"])]
                      for i, d in enumerate(rep["summary_by_product"])]},
        ]
        print_utils.show_print_preview(self, print_utils.build_report_html(title, sections))


# --------------------------------------------------------------------------- #
# Outer page: sub-tab host
# --------------------------------------------------------------------------- #

class FinancialReportsPage(_Widgets.QWidget):
    def __init__(self, main_window=None):
        # type: (Optional[Any]) -> None
        super(FinancialReportsPage, self).__init__()
        self._main = main_window
        from ..utils import make_rtl, best_persian_font
        make_rtl(self)
        self.setFont(_Gui.QFont(best_persian_font(), 10))
        self._build_ui()

    def _build_ui(self):
        layout = _Widgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(12)
        title = _Widgets.QLabel("گزارش‌های مالی")
        title.setProperty("role", "page-title")
        title.setStyleSheet("")
        title.setAlignment(_Core.Qt.AlignCenter)
        layout.addWidget(title)

        self.tabs = _Widgets.QTabWidget()
        self.tabs.setLayoutDirection(_Core.Qt.RightToLeft)
        self.daily_receipts = _DailyReceiptsTab(self)
        self.monthly_receipts = _MonthlyReceiptsTab(self)
        self.daily_expenses = _DailyExpensesTab(self)
        self.monthly_expenses = _MonthlyExpensesTab(self)
        self.sales_profit = _SalesProfitTab(self)
        self.tabs.addTab(self.daily_receipts, "دریافتی روزانه")
        self.tabs.addTab(self.monthly_receipts, "دریافتی ماهیانه")
        self.tabs.addTab(self.daily_expenses, "هزینه روزانه")
        self.tabs.addTab(self.monthly_expenses, "هزینه ماهیانه")
        self.tabs.addTab(self.sales_profit, "فروش و سود")
        layout.addWidget(self.tabs)
