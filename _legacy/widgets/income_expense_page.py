# -*- coding: utf-8 -*-
"""گزارش درآمد/هزینه - Income / expense report page + expense entry."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..utils import Qt
from .. import models, date_utils, money_utils
from ..dialogs.jalali_date_dialog import JalaliDateEdit
from . import print_utils

_Widgets = Qt.QtWidgets
_Core = Qt.QtCore
_Gui = Qt.QtGui


class _DoctorSummaryModel(_Core.QAbstractTableModel):
    HEADERS = ["پزشک", "مجموع"]

    def __init__(self):
        # type: () -> None
        super(_DoctorSummaryModel, self).__init__()
        self._rows = []

    def set_rows(self, rows):
        # type: (list) -> None
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

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
                return r["doctor"]
            if index.column() == 1:
                return money_utils.format_money_persian(r["total"])
        if role == _Core.Qt.TextAlignmentRole:
            if index.column() == 1:
                return _Core.Qt.AlignCenter
            return _Core.Qt.AlignRight | _Core.Qt.AlignVCenter
        return None


class IncomeExpensePage(_Widgets.QWidget):
    def __init__(self, main_window=None):
        # type: (Optional[Any]) -> None
        super(IncomeExpensePage, self).__init__()
        self._main = main_window
        from ..utils import make_rtl, best_persian_font
        make_rtl(self)
        self.setFont(_Gui.QFont(best_persian_font(), 10))
        self._doctor_model = _DoctorSummaryModel()
        self._build_ui()
        self._show_report()

    def _build_ui(self):
        from ..theme import card, section_title, primary, sum_card
        layout = _Widgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(12)

        title = _Widgets.QLabel("گزارش درآمد/هزینه")
        title.setProperty("role", "page-title")
        title.setStyleSheet("")
        title.setAlignment(_Core.Qt.AlignCenter)
        layout.addWidget(title)

        # ---------------- Range + summary card ----------------
        ctrl_holder = _Widgets.QWidget()
        cl = _Widgets.QVBoxLayout(ctrl_holder)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(10)
        cl.addWidget(section_title("محدوده گزارش", "دریافتی، هزینه و بستانکار"))

        rng = _Widgets.QHBoxLayout()
        rng.setSpacing(6)
        rng.addWidget(_Widgets.QLabel("از تاریخ:"))
        self.date_from = JalaliDateEdit(self, initial="")
        rng.addWidget(self.date_from)
        rng.addWidget(_Widgets.QLabel("تا تاریخ:"))
        self.date_to = JalaliDateEdit(self, initial=date_utils.today_jalali_str())
        rng.addWidget(self.date_to)
        self.show_btn = primary(_Widgets.QPushButton("نمایش گزارش"), 130)
        self.show_btn.clicked.connect(self._show_report)
        self.print_btn = _Widgets.QPushButton("چاپ گزارش")
        self.print_btn.clicked.connect(self._print_report)
        rng.addWidget(self.show_btn)
        rng.addWidget(self.print_btn)
        rng.addStretch(1)
        cl.addLayout(rng)

        cards = _Widgets.QHBoxLayout()
        cards.setSpacing(10)
        self.income_card = sum_card("دریافتی: ۰", "success")
        self.expense_card = sum_card("هزینه: ۰", "danger")
        self.receivable_card = sum_card("بستانکار: ۰", "warn")
        for c in (self.income_card, self.expense_card, self.receivable_card):
            cards.addWidget(c, 1)
        cl.addLayout(cards)
        layout.addWidget(card(ctrl_holder))

        # ---------------- Doctor summary card ----------------
        doc_holder = _Widgets.QWidget()
        dol = _Widgets.QVBoxLayout(doc_holder)
        dol.setContentsMargins(0, 0, 0, 0)
        dol.setSpacing(8)
        dol.addWidget(section_title("خلاصه پزشکان"))
        self.doctor_table = _Widgets.QTableView()
        self.doctor_table.setModel(self._doctor_model)
        self.doctor_table.setEditTriggers(_Widgets.QTableView.NoEditTriggers)
        self.doctor_table.horizontalHeader().setStretchLastSection(True)
        self.doctor_table.verticalHeader().setVisible(False)
        self.doctor_table.verticalHeader().setDefaultSectionSize(30)
        dol.addWidget(self.doctor_table, 1)
        layout.addWidget(card(doc_holder), 1)

    def _show_report(self):
        from ..utils import error_msg
        date_from = self.date_from.iso_value()
        date_to = self.date_to.iso_value()
        try:
            report = models.income_expense_report(date_from, date_to)
        except Exception as exc:
            error_msg(self, "خطا در اجرای گزارش: %s" % str(exc))
            return
        self.income_card.setText("دریافتی: %s" %
                                 money_utils.format_money_persian(report["income"]))
        self.expense_card.setText("هزینه: %s" %
                                   money_utils.format_money_persian(report["expense"]))
        self.receivable_card.setText(
            "بستانکار: %s" % money_utils.format_money_persian(report["receivable"]))
        self._doctor_model.set_rows(report["doctor_summary"])

    def _print_report(self):
        from ..utils import error_msg
        date_from = self.date_from.iso_value()
        date_to = self.date_to.iso_value()
        report = models.income_expense_report(date_from, date_to)
        d_from = date_utils.iso_to_jalali_persian_str(date_from) if date_from else ""
        d_to = date_utils.iso_to_jalali_persian_str(date_to) if date_to else ""
        title = "گزارش درآمد/هزینه"
        if d_from or d_to:
            title += " (%s تا %s)" % (d_from or "—", d_to or "—")
        sections = [
            {"kind": "cards", "cards": [
                {"label": "دریافتی", "value": money_utils.format_money_persian(report["income"]),
                 "color": "#2e7d32"},
                {"label": "هزینه", "value": money_utils.format_money_persian(report["expense"]),
                 "color": "#c62828"},
                {"label": "بستانکار", "value": money_utils.format_money_persian(report["receivable"]),
                 "color": "#ef6c00"},
            ]},
            {"kind": "table", "columns": ["ردیف", "تاریخ", "مبلغ", "توضیحات"],
             "rows": [[date_utils.to_persian_digits(str(i + 1)),
                       date_utils.iso_to_jalali_persian_str(e["expense_date"]),
                       money_utils.format_money_persian(e["amount"]),
                       e["description"] or ""]
                      for i, e in enumerate(report["expenses"])]},
            {"kind": "table", "columns": ["پزشک", "مجموع"],
             "rows": [[d["doctor"], money_utils.format_money_persian(d["total"])]
                      for d in report["doctor_summary"]]},
        ]
        html = print_utils.build_report_html(title, sections)
        print_utils.show_print_preview(self, html)
