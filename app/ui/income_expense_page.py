# -*- coding: utf-8 -*-
"""Income / expense report — mirrors webapp/templates/income_expense.html."""
from __future__ import annotations

from ..utils import Qt, error_msg
from .. import models, date_utils, money_utils
from . import fields as F
from . import printing
from ..theme import card, primary

_Core = Qt.QtCore
_W = Qt.QtWidgets


class IncomeExpensePage(_W.QWidget):
    def __init__(self, window):
        super().__init__(window)
        self.window_ = window
        self.setLayoutDirection(_Core.Qt.RightToLeft)
        self._rep = None

        outer = _W.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        area, v = F.page_shell()
        outer.addWidget(area)

        print_btn = _W.QPushButton("چاپ گزارش")
        print_btn.clicked.connect(self._print_report)
        v.addWidget(F.page_header("گزارش درآمد / هزینه", "", [print_btn]))

        # ---------------- Filter card ----------------
        box = _W.QWidget()
        h = _W.QHBoxLayout(box)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)
        h.addWidget(_W.QLabel("از تاریخ"))
        self.date_from = F.JalaliDateEdit()
        self.date_from.setMinimumWidth(140)
        h.addWidget(self.date_from)
        h.addSpacing(8)
        h.addWidget(_W.QLabel("تا تاریخ"))
        self.date_to = F.JalaliDateEdit(iso=date_utils.today_iso())
        self.date_to.setMinimumWidth(140)
        h.addWidget(self.date_to)
        show_btn = primary(_W.QPushButton("نمایش"), 110)
        show_btn.clicked.connect(self._show_report)
        h.addWidget(show_btn)
        h.addStretch(1)
        v.addWidget(card(box))

        # ---------------- Tiles ----------------
        self.tiles = F.tile_row([
            ("فروش (فاکتورها)", "۰", "info"),
            ("دریافتی", "۰", "success"),
            ("هزینه", "۰", "danger"),
            ("سود (دریافتی − هزینه)", "۰", "success"),
            ("بستانکار (قابل دریافت)", "۰", "warning"),
        ])
        v.addWidget(self.tiles)
        v.addWidget(F.muted(
            "سود دوره = مجموع دریافتیها منهای مجموع هزینهها. مبلغ «بستانکار» "
            "پولی است که هنوز از بیماران دریافت نشده (دارایی کلینیک) و از سود "
            "کم نمیشود."))

        # ---------------- Two side-by-side tables ----------------
        row = _W.QHBoxLayout()
        row.setSpacing(12)
        d_box = _W.QWidget()
        dv = _W.QVBoxLayout(d_box)
        dv.setContentsMargins(0, 0, 0, 0)
        dv.setSpacing(8)
        dv.addWidget(F.card_title("خلاصه پزشکان"))
        self.doctor_table = F.make_table(["پزشک", "جمع"],
                                         widths=[150, 130], stretch=0)
        self.doctor_table.setMinimumHeight(220)
        dv.addWidget(self.doctor_table)
        row.addWidget(card(d_box), 1)

        e_box = _W.QWidget()
        ev = _W.QVBoxLayout(e_box)
        ev.setContentsMargins(0, 0, 0, 0)
        ev.setSpacing(8)
        ev.addWidget(F.card_title("هزینه‌ها"))
        self.expense_table = F.make_table(
            ["تاریخ", "دسته", "مبلغ", "توضیحات"],
            widths=[122, 132, 122, 200], stretch=3)
        self.expense_table.setMinimumHeight(220)
        ev.addWidget(self.expense_table)
        row.addWidget(card(e_box), 1)
        v.addLayout(row)
        v.addStretch(1)

    # ------------------------------------------------------------------ #
    def refresh(self):
        self._show_report()

    def _show_report(self):
        df = self.date_from.iso() or None
        dt = self.date_to.iso() or None
        rep = models.income_expense_report(df, dt)
        self._rep = rep
        F.set_rows(self.doctor_table,
                   [[d["doctor"], money_utils.format_money_persian(d["total"])]
                    for d in rep["doctor_summary"]])
        F.set_rows(self.expense_table,
                   [[date_utils.iso_to_jalali_persian_str(e["expense_date"]),
                     e["category"],
                     money_utils.format_money_persian(e["amount"]),
                     e["description"] or ""]
                    for e in rep["expenses"]])
        vals = [w for w in self.tiles.findChildren(_W.QLabel)
                if w.objectName() == "statValue"]
        texts = [rep["sales"], rep["income"], rep["expense"], rep["profit"],
                 rep["receivable"]]
        for lab, num in zip(vals, texts):
            lab.setText(money_utils.format_money_persian(num))

    # ------------------------------------------------------------------ #
    def _print_report(self):
        if self._rep is None:
            self._show_report()
        rep = self._rep
        if rep is None:
            return
        df = self.date_from.iso()
        dt = self.date_to.iso()
        title = "گزارش درآمد / هزینه"
        if df or dt:
            title += " (%s تا %s)" % (
                date_utils.iso_to_jalali_persian_str(df) if df else "—",
                date_utils.iso_to_jalali_persian_str(dt) if dt else "—")
        sections = [
            {"kind": "cards", "cards": [
                {"label": "فروش", "value": money_utils.format_money_persian(
                    rep["sales"]), "color": "#0d6e8c"},
                {"label": "دریافتی", "value": money_utils.format_money_persian(
                    rep["income"]), "color": "#2e8b6a"},
                {"label": "هزینه", "value": money_utils.format_money_persian(
                    rep["expense"]), "color": "#c03b4a"},
                {"label": "سود", "value": money_utils.format_money_persian(
                    rep["profit"]), "color": "#2e8b6a"},
                {"label": "بستانکار", "value": money_utils.format_money_persian(
                    rep["receivable"]), "color": "#b97a1c"},
            ]},
            {"kind": "table", "title": "خلاصه پزشکان",
             "columns": ["پزشک", "جمع"],
             "rows": [[d["doctor"],
                       money_utils.format_money_persian(d["total"])]
                      for d in rep["doctor_summary"]]},
            {"kind": "table", "title": "هزینه‌ها",
             "columns": ["تاریخ", "دسته", "مبلغ", "توضیحات"],
             "rows": [[date_utils.iso_to_jalali_persian_str(e["expense_date"]),
                       e["category"], money_utils.format_money_persian(
                           e["amount"]), e["description"] or ""]
                      for e in rep["expenses"]]},
        ]
        printing.show_print_preview(self, printing.build_report_html(
            title, sections))
