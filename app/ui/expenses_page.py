# -*- coding: utf-8 -*-
"""Expenses CRUD page — mirrors webapp/templates/expenses.html."""
from __future__ import annotations

from ..utils import Qt, confirm_msg, error_msg
from .. import models, settings as settings_mod, date_utils, money_utils
from . import fields as F
from ..theme import card, primary, success

_Core = Qt.QtCore
_Gui = Qt.QtGui
_W = Qt.QtWidgets


class ExpensesPage(_W.QWidget):
    def __init__(self, window):
        super().__init__(window)
        self.window_ = window
        self.setLayoutDirection(_Core.Qt.RightToLeft)

        outer = _W.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        area, v = F.page_shell()
        outer.addWidget(area)
        v.addWidget(F.page_header("مدیریت هزینه‌ها"))

        # ---------------- Add card ----------------
        add_box = _W.QWidget()
        g = _W.QGridLayout(add_box)
        g.setSpacing(8)
        g.addWidget(_W.QLabel("تاریخ (شمسی)"), 0, 0)
        self.new_date = F.JalaliDateEdit(iso=date_utils.today_iso())
        g.addWidget(self.new_date, 1, 0)
        g.addWidget(_W.QLabel("دسته"), 0, 1)
        self.new_cat = _W.QComboBox()
        self.new_cat.setMinimumWidth(130)
        g.addWidget(self.new_cat, 1, 1)
        g.addWidget(_W.QLabel("مبلغ (تومان)"), 0, 2)
        self.new_amount = F.MoneyEdit()
        self.new_amount.setMinimumWidth(140)
        g.addWidget(self.new_amount, 1, 2)
        g.addWidget(_W.QLabel("توضیحات"), 0, 3)
        self.new_desc = F.FaLineEdit()
        g.addWidget(self.new_desc, 1, 3)
        add_btn = success(_W.QPushButton("ثبت هزینه"), 110)
        add_btn.clicked.connect(self._add)
        g.addWidget(add_btn, 1, 4)
        g.setColumnStretch(3, 1)
        v.addWidget(card(add_box))

        # ---------------- Filter card ----------------
        flt_box = _W.QWidget()
        fh = _W.QHBoxLayout(flt_box)
        fh.setContentsMargins(0, 0, 0, 0)
        fh.setSpacing(8)
        fh.addWidget(_W.QLabel("از تاریخ"))
        self.date_from = F.JalaliDateEdit()
        fh.addWidget(self.date_from)
        fh.addWidget(_W.QLabel("تا تاریخ"))
        self.date_to = F.JalaliDateEdit()
        fh.addWidget(self.date_to)
        fh.addWidget(_W.QLabel("دسته"))
        self.cat_filter = _W.QComboBox()
        self.cat_filter.setMinimumWidth(120)
        fh.addWidget(self.cat_filter)
        flt_btn = primary(_W.QPushButton("فیلتر"), 100)
        flt_btn.clicked.connect(self._reload)
        fh.addWidget(flt_btn)
        fh.addStretch(1)
        v.addWidget(card(flt_box))
        self.date_from.dateChanged.connect(lambda _: self._reload())
        self.date_to.dateChanged.connect(lambda _: self._reload())
        self.cat_filter.currentIndexChanged.connect(lambda _: self._reload())

        # ---------------- Table card ----------------
        t_box = _W.QWidget()
        tv = _W.QVBoxLayout(t_box)
        tv.setContentsMargins(0, 0, 0, 0)
        tv.setSpacing(8)
        self.title_lbl = F.card_title("فهرست هزینه‌ها")
        tv.addWidget(self.title_lbl)
        self.table = F.make_table(
            ["تاریخ", "دسته", "مبلغ", "توضیحات", "عملیات"],
            widths=[122, 132, 122, 300, 90], stretch=3)
        # Lazy action widgets (visible rows only) — see archive page.
        self.table.set_row_widget_factory(4, self._make_actions)
        self.table.setMinimumHeight(360)
        tv.addWidget(self.table)
        v.addWidget(card(t_box))
        v.addStretch(1)

    # ------------------------------------------------------------------ #
    def refresh(self):
        self._fill_categories()
        self._reload()

    def _fill_categories(self):
        cats = settings_mod.get_expense_categories()
        cur_new = self.new_cat.currentText()
        cur_flt = self.cat_filter.currentText()
        self.new_cat.clear()
        self.new_cat.addItems(cats)
        if cur_new in cats:
            self.new_cat.setCurrentText(cur_new)
        self.cat_filter.clear()
        self.cat_filter.addItem("همه")
        self.cat_filter.addItems(cats)
        if cur_flt and (cur_flt == "همه" or cur_flt in cats):
            self.cat_filter.setCurrentText(cur_flt)

    def _add(self):
        amount = self.new_amount.value()
        if amount <= 0:
            error_msg(self, "مبلغ باید بزرگ‌تر از صفر باشد.")
            return
        iso = self.new_date.iso() or date_utils.today_iso()
        models.add_expense(amount, self.new_desc.text().strip(), iso,
                           self.new_cat.currentText() or "متفرقه")
        self.new_amount.clear()
        self.new_desc.clear()
        self._reload()

    def _reload(self):
        category = self.cat_filter.currentText()
        if category == "همه":
            category = None
        rows = models.list_expenses(
            self.date_from.iso() or None,
            self.date_to.iso() or None,
            category)
        self.title_lbl.setText("فهرست هزینه‌ها (%s مورد)" % F.fa(len(rows)))
        model = self.table.model()
        model.removeRows(0, model.rowCount())
        for r in rows:
            items = [
                self._cell(date_utils.iso_to_jalali_persian_str(
                    r["expense_date"]), payload=r["id"]),
                self._cell(r["category"]),
                self._cell(money_utils.format_money_persian(r["amount"])),
                self._cell(r["description"] or ""),
                self._cell(""),
            ]
            model.appendRow(items)
        F.resort(self.table)
        self.table.schedule_fit()

    def _cell(self, text, payload=None):
        return F.make_item(text, payload=payload)

    def _make_actions(self, rr):
        """Row delete button, built lazily for visible rows only. The
        expense id rides in the hidden payload of column 0, so sorting
        can't desync the button from its record."""
        model = self.table.model()
        item = model.item(rr, 0)
        if item is None:
            return None
        raw = item.data(F.ROW_ID)
        if raw is None:
            return None
        exp_id = int(raw)
        # Wrap in a container: a bare index widget is stretched to the
        # full cell rect, which would inflate the compact button again.
        btns = _W.QWidget()
        h = _W.QHBoxLayout(btns)
        h.setContentsMargins(2, 0, 2, 0)
        btn = _W.QPushButton("حذف")
        btn.setProperty("variant", "link")
        btn.setProperty("btnsize", "xs")
        btn.setProperty("tone", "danger")
        btn.setCursor(_Core.Qt.PointingHandCursor)
        btn.clicked.connect(lambda _=False, i=exp_id: self._delete(i))
        h.addWidget(btn, 0, _Core.Qt.AlignVCenter)
        h.addStretch(1)
        return btns

    def _delete(self, expense_id):
        if not confirm_msg(self, "این هزینه حذف شود؟"):
            return
        models.delete_expense(expense_id)
        self._reload()
