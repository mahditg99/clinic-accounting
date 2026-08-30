# -*- coding: utf-8 -*-
"""هزینه‌ها - Expenses page (entry + list), moved out of the income/expense report."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..utils import Qt
from .. import models, date_utils, money_utils, settings as settings_mod
from ..dialogs.jalali_date_dialog import JalaliDateEdit

_Widgets = Qt.QtWidgets
_Core = Qt.QtCore
_Gui = Qt.QtGui


class _ExpenseModel(_Core.QAbstractTableModel):
    HEADERS = ["ردیف", "تاریخ", "مبلغ", "دسته‌بندی", "توضیحات"]

    def __init__(self):
        # type: () -> None
        super(_ExpenseModel, self).__init__()
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
        col = index.column()
        if role == _Core.Qt.DisplayRole:
            if col == 0:
                return date_utils.to_persian_digits(str(index.row() + 1))
            if col == 1:
                return date_utils.iso_to_jalali_persian_str(r["expense_date"])
            if col == 2:
                return money_utils.format_money_persian(r["amount"])
            if col == 3:
                return r.get("category") or "متفرقه"
            if col == 4:
                return r["description"] or ""
        if role == _Core.Qt.TextAlignmentRole:
            if col in (0, 1, 2, 3):
                return _Core.Qt.AlignCenter
            return _Core.Qt.AlignRight | _Core.Qt.AlignVCenter
        if role == _Core.Qt.UserRole:
            return r["id"]
        return None


class ExpensesPage(_Widgets.QWidget):
    def __init__(self, main_window=None):
        # type: (Optional[Any]) -> None
        super(ExpensesPage, self).__init__()
        self._main = main_window
        from ..utils import make_rtl, best_persian_font
        make_rtl(self)
        self.setFont(_Gui.QFont(best_persian_font(), 10))
        self._model = _ExpenseModel()
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        from ..theme import card, section_title, success, danger
        layout = _Widgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(12)

        title = _Widgets.QLabel("هزینه‌ها")
        title.setProperty("role", "page-title")
        title.setStyleSheet("")
        title.setAlignment(_Core.Qt.AlignCenter)
        layout.addWidget(title)

        # ---------------- Entry card ----------------
        add_holder = _Widgets.QWidget()
        al = _Widgets.QVBoxLayout(add_holder)
        al.setContentsMargins(0, 0, 0, 0)
        al.setSpacing(10)
        al.addWidget(section_title("ثبت هزینه", "ثبت یا حذف یک هزینه جدید"))

        row = _Widgets.QHBoxLayout()
        row.setSpacing(6)
        row.addWidget(_Widgets.QLabel("مبلغ:"))
        self.exp_amount = _Widgets.QLineEdit()
        self.exp_amount.setPlaceholderText("تومان")
        self.exp_amount.setAlignment(_Core.Qt.AlignRight)
        self.exp_amount.setValidator(
            _Gui.QRegExpValidator(_Core.QRegExp("^[0-9۰-۹,،]*$")))
        self.exp_amount.returnPressed.connect(self._add_expense)
        row.addWidget(self.exp_amount)
        row.addWidget(_Widgets.QLabel("دسته‌بندی:"))
        self.category_combo = _Widgets.QComboBox()
        for c in settings_mod.get_expense_categories():
            self.category_combo.addItem(c)
        row.addWidget(self.category_combo)
        row.addWidget(_Widgets.QLabel("توضیحات:"))
        self.exp_desc = _Widgets.QLineEdit()
        self.exp_desc.setAlignment(_Core.Qt.AlignRight)
        row.addWidget(self.exp_desc, 1)
        row.addWidget(_Widgets.QLabel("تاریخ:"))
        self.exp_date = JalaliDateEdit(self, initial=date_utils.today_jalali_str())
        row.addWidget(self.exp_date)
        self.exp_add_btn = success(_Widgets.QPushButton("ثبت هزینه"), 120)
        self.exp_add_btn.clicked.connect(self._add_expense)
        self.exp_del_btn = danger(_Widgets.QPushButton("حذف هزینه"), 120)
        self.exp_del_btn.clicked.connect(self._delete_expense)
        row.addWidget(self.exp_add_btn)
        row.addWidget(self.exp_del_btn)
        al.addLayout(row)
        layout.addWidget(card(add_holder))

        # ---------------- List card ----------------
        list_holder = _Widgets.QWidget()
        ll = _Widgets.QVBoxLayout(list_holder)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(8)
        head = _Widgets.QHBoxLayout()
        head.addWidget(section_title("لیست هزینه‌ها"))
        head.addStretch(1)
        ll.addLayout(head)

        self.expense_table = _Widgets.QTableView()
        self.expense_table.setModel(self._model)
        self.expense_table.setSelectionBehavior(_Widgets.QTableView.SelectRows)
        self.expense_table.setSelectionMode(_Widgets.QTableView.SingleSelection)
        self.expense_table.setEditTriggers(_Widgets.QTableView.NoEditTriggers)
        self.expense_table.horizontalHeader().setStretchLastSection(True)
        self.expense_table.verticalHeader().setVisible(False)
        self.expense_table.verticalHeader().setDefaultSectionSize(30)
        ll.addWidget(self.expense_table, 1)

        self.count_label = _Widgets.QLabel("تعداد رکورد: ۰")
        self.count_label.setAlignment(_Core.Qt.AlignRight)
        ll.addWidget(self.count_label)
        layout.addWidget(card(list_holder), 1)

    def _refresh_categories(self):
        cur = self.category_combo.currentText()
        self.category_combo.clear()
        for c in settings_mod.get_expense_categories():
            self.category_combo.addItem(c)
        if cur:
            idx = self.category_combo.findText(cur)
            if idx >= 0:
                self.category_combo.setCurrentIndex(idx)

    def refresh(self):
        # type: () -> None
        self._refresh_categories()
        rows = models.list_expenses()
        self._model.set_rows(rows)
        self.count_label.setText("تعداد رکورد: %s" %
                                 date_utils.to_persian_digits(str(len(rows))))

    def _add_expense(self):
        from ..utils import error_msg, info_msg
        amount = money_utils.parse_money(self.exp_amount.text())
        if amount is None or amount <= 0:
            error_msg(self, "مبلغ هزینه نامعتبر است.")
            return
        desc = self.exp_desc.text().strip()
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
        self.exp_amount.setText("")
        self.exp_desc.setText("")
        self.refresh()

    def _delete_expense(self):
        from ..utils import error_msg, confirm_msg, info_msg
        idx = self.expense_table.currentIndex()
        if not idx.isValid():
            error_msg(self, "یک هزینه را انتخاب کنید.")
            return
        eid = int(self._model.rows()[idx.row()]["id"])
        if confirm_msg(self, "این هزینه حذف شود؟"):
            models.delete_expense(eid)
            info_msg(self, "هزینه حذف شد.")
            self.refresh()