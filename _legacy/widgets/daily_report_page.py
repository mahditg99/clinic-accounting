# -*- coding: utf-8 -*-
"""گزارش‌گیری روزانه - Daily report page (payments of the day)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..utils import Qt
from .. import models, date_utils, money_utils
from ..dialogs.jalali_date_dialog import JalaliDateEdit
from . import print_utils

_Widgets = Qt.QtWidgets
_Core = Qt.QtCore
_Gui = Qt.QtGui


class _SummaryModel(_Core.QAbstractTableModel):
    HEADERS = ["ردیف", "عنوان / روش پرداخت", "جمع کل"]

    def __init__(self):
        # type: () -> None
        super(_SummaryModel, self).__init__()
        self._rows = []  # type: List[Dict[str, Any]]

    def set_rows(self, rows):
        # type: (List[Dict[str, Any]]) -> None
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
        col = index.column()
        if role == _Core.Qt.DisplayRole:
            if col == 0:
                return date_utils.to_persian_digits(str(index.row() + 1))
            if col == 1:
                return r["method"]
            if col == 2:
                return money_utils.format_money_persian(r["total"])
        if role == _Core.Qt.TextAlignmentRole:
            if col in (0, 2):
                return _Core.Qt.AlignCenter
            return _Core.Qt.AlignRight | _Core.Qt.AlignVCenter
        return None


class _DetailModel(_Core.QAbstractTableModel):
    HEADERS = ["ردیف", "روش پرداخت", "زمان", "مبلغ", "شماره فاکتور",
               "شماره پرونده", "نام بیمار"]

    def __init__(self):
        # type: () -> None
        super(_DetailModel, self).__init__()
        self._rows = []  # type: List[Dict[str, Any]]

    def set_rows(self, rows):
        # type: (List[Dict[str, Any]]) -> None
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
        col = index.column()
        if role == _Core.Qt.DisplayRole:
            if col == 0:
                return date_utils.to_persian_digits(str(index.row() + 1))
            if col == 1:
                return r["method"]
            if col == 2:
                # paid_at is ISO datetime.
                return date_utils.to_persian_digits(
                    str(r["paid_at"])[11:16] if str(r["paid_at"])[11:16] else "")
            if col == 3:
                return money_utils.format_money_persian(r["amount"])
            if col == 4:
                return date_utils.to_persian_digits(str(r["invoice_no"]))
            if col == 5:
                return date_utils.to_persian_digits(r["file_no"])
            if col == 6:
                return r["patient_name"]
        if role == _Core.Qt.TextAlignmentRole:
            if col in (0, 2, 3, 4, 5):
                return _Core.Qt.AlignCenter
            return _Core.Qt.AlignRight | _Core.Qt.AlignVCenter
        return None


class DailyReportPage(_Widgets.QWidget):
    def __init__(self, main_window=None):
        # type: (Optional[Any]) -> None
        super(DailyReportPage, self).__init__()
        self._main = main_window
        from ..utils import make_rtl, best_persian_font
        make_rtl(self)
        self.setFont(_Gui.QFont(best_persian_font(), 10))
        self._summary_model = _SummaryModel()
        self._detail_model = _DetailModel()
        self._build_ui()

    def _build_ui(self):
        from ..theme import card, section_title, primary, sum_card
        layout = _Widgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(12)

        title = _Widgets.QLabel("گزارش‌گیری روزانه")
        title.setProperty("role", "page-title")
        title.setStyleSheet("")
        title.setAlignment(_Core.Qt.AlignCenter)
        layout.addWidget(title)

        # ---------------- Controls card ----------------
        ctrl_holder = _Widgets.QWidget()
        cl = _Widgets.QVBoxLayout(ctrl_holder)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(10)
        cl.addWidget(section_title("گزارش روز", "دریافتی‌ها و روش‌های پرداخت در تاریخ انتخابی"))

        ctrl = _Widgets.QHBoxLayout()
        ctrl.setSpacing(6)
        ctrl.addWidget(_Widgets.QLabel("تاریخ:"))
        self.date_edit = JalaliDateEdit(self, initial=date_utils.today_jalali_str())
        ctrl.addWidget(self.date_edit)
        self.show_btn = primary(_Widgets.QPushButton("نمایش گزارش"), 130)
        self.show_btn.clicked.connect(self._show_report)
        self.print_btn = _Widgets.QPushButton("چاپ گزارش")
        self.print_btn.clicked.connect(self._print_report)
        ctrl.addWidget(self.show_btn)
        ctrl.addWidget(self.print_btn)
        ctrl.addStretch(1)
        cl.addLayout(ctrl)

        self.total_label = sum_card("مجموع دریافتی: ۰", "success")
        cl.addWidget(self.total_label)
        layout.addWidget(card(ctrl_holder))

        # ---------------- Summary table card ----------------
        sum_holder = _Widgets.QWidget()
        sl = _Widgets.QVBoxLayout(sum_holder)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(8)
        sl.addWidget(section_title("خلاصه بر اساس روش پرداخت"))
        self.summary_table = _Widgets.QTableView()
        self.summary_table.setModel(self._summary_model)
        self.summary_table.setEditTriggers(_Widgets.QTableView.NoEditTriggers)
        self.summary_table.horizontalHeader().setStretchLastSection(True)
        self.summary_table.verticalHeader().setVisible(False)
        self.summary_table.verticalHeader().setDefaultSectionSize(30)
        sl.addWidget(self.summary_table, 1)
        layout.addWidget(card(sum_holder), 1)

        # ---------------- Detail table card ----------------
        det_holder = _Widgets.QWidget()
        dl = _Widgets.QVBoxLayout(det_holder)
        dl.setContentsMargins(0, 0, 0, 0)
        dl.setSpacing(8)
        dl.addWidget(section_title("مشخصات پرداخت‌ها"))
        self.detail_table = _Widgets.QTableView()
        self.detail_table.setModel(self._detail_model)
        self.detail_table.setEditTriggers(_Widgets.QTableView.NoEditTriggers)
        self.detail_table.horizontalHeader().setStretchLastSection(True)
        self.detail_table.verticalHeader().setVisible(False)
        self.detail_table.verticalHeader().setDefaultSectionSize(30)
        dl.addWidget(self.detail_table, 1)
        layout.addWidget(card(det_holder), 1)

    def _iso_date(self):
        # type: () -> Optional[str]
        return self.date_edit.iso_value()

    def _show_report(self):
        from ..utils import error_msg
        iso = self._iso_date()
        if iso is None:
            error_msg(self, "تاریخ معتبر وارد کنید.")
            return
        report = models.daily_report(iso)
        self._summary_model.set_rows(report["by_method"])
        self._detail_model.set_rows(report["payments"])
        self.total_label.setText(
            "مجموع دریافتی: %s" % money_utils.format_money_persian(report["total"]))
        self._report_total = report["total"]
        self._report_date_iso = iso

    def _print_report(self):
        from ..utils import error_msg, info_msg
        iso = self._iso_date()
        if iso is None:
            error_msg(self, "تاریخ معتبر وارد کنید.")
            return
        report = models.daily_report(iso)
        jalali_date = date_utils.iso_to_jalali_persian_str(iso)
        title = "گزارش روزانه - تاریخ %s" % jalali_date
        sections = [
            {"kind": "text", "text": "مجموع دریافتی: %s تومان" %
                money_utils.format_money_persian(report["total"])},
            {"kind": "table", "columns": ["ردیف", "روش پرداخت", "جمع کل"],
             "rows": [[date_utils.to_persian_digits(str(i + 1)), s["method"],
                       money_utils.format_money_persian(s["total"])]
                      for i, s in enumerate(report["by_method"])]},
            {"kind": "table", "columns": ["ردیف", "روش پرداخت", "زمان", "مبلغ",
                                          "شماره فاکتور", "شماره پرونده",
                                          "نام بیمار"],
             "rows": [[date_utils.to_persian_digits(str(i + 1)), p["method"],
                       str(p["paid_at"])[11:16],
                       money_utils.format_money_persian(p["amount"]),
                       date_utils.to_persian_digits(str(p["invoice_no"])),
                       date_utils.to_persian_digits(p["file_no"]),
                       p["patient_name"]]
                      for i, p in enumerate(report["payments"])]},
        ]
        html = print_utils.build_report_html(title, sections)
        print_utils.show_print_preview(self, html)
