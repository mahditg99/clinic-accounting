# -*- coding: utf-8 -*-
"""Product sales report — mirrors webapp/templates/product_sales.html."""
from __future__ import annotations

from ..utils import Qt
from .. import models, date_utils, money_utils
from . import fields as F
from . import printing
from ..theme import card, primary

_Core = Qt.QtCore
_W = Qt.QtWidgets


class ProductSalesPage(_W.QWidget):
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
        v.addWidget(F.page_header("گزارش فروش محصولات", "", [print_btn]))

        # ---------------- Filter card ----------------
        box = _W.QWidget()
        h = _W.QHBoxLayout(box)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)
        h.addWidget(_W.QLabel("از تاریخ"))
        self.date_from = F.JalaliDateEdit()
        self.date_from.setMinimumWidth(140)
        h.addWidget(self.date_from)
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
            ("جمع فروش", "۰", "info"),
            ("قیمت تمام‌شده", "۰", "success"),
            ("سود", "۰", "success"),
            ("تعداد کل (عدد)", "۰", "accent"),
        ])
        v.addWidget(self.tiles)

        # ---------------- Table ----------------
        t_box = _W.QWidget()
        tv = _W.QVBoxLayout(t_box)
        tv.setContentsMargins(0, 0, 0, 0)
        tv.setSpacing(8)
        self.title_lbl = F.card_title("فروش به تفکیک محصول")
        tv.addWidget(self.title_lbl)
        self.table = F.make_table(
            ["محصول", "تعداد", "فروش", "قیمت تمام‌شده", "سود"],
            widths=[180, 80, 115, 145, 110], stretch=0)
        self.table.setMinimumHeight(360)
        tv.addWidget(self.table)
        v.addWidget(card(t_box))
        v.addStretch(1)

    # ------------------------------------------------------------------ #
    def refresh(self):
        self._show_report()

    def _show_report(self):
        df = self.date_from.iso() or None
        dt = self.date_to.iso() or None
        rep = models.product_sales_report(df, dt)
        self._rep = rep
        F.set_rows(self.table,
                   [[r["title"], r["quantity"],
                     money_utils.format_money_persian(r["row_total"]),
                     money_utils.format_money_persian(r["row_cost"]),
                     money_utils.format_money_persian(r["profit"])]
                    for r in rep["rows"]])
        self.title_lbl.setText("فروش به تفکیک محصول (%s ردیف)" %
                               F.fa(len(rep["rows"])))
        vals = [w for w in self.tiles.findChildren(_W.QLabel)
                if w.objectName() == "statValue"]
        for lab, num in zip(vals, (rep["total_revenue"], rep["total_cost"],
                                   rep["total_profit"])):
            lab.setText(money_utils.format_money_persian(num))
        if len(vals) > 3:
            vals[3].setText(F.fa(rep["total_quantity"]))

    # ------------------------------------------------------------------ #
    def _print_report(self):
        df = self.date_from.iso() or None
        dt = self.date_to.iso() or None
        rep = models.product_sales_report(df, dt)
        title = "گزارش فروش محصولات"
        if df or dt:
            title += " (%s تا %s)" % (
                date_utils.iso_to_jalali_persian_str(df) if df else "—",
                date_utils.iso_to_jalali_persian_str(dt) if dt else "—")
        sections = [
            {"kind": "cards", "cards": [
                {"label": "جمع فروش", "value": money_utils.
                 format_money_persian(rep["total_revenue"]), "color": "#0d6e8c"},
                {"label": "قیمت تمام‌شده", "value": money_utils.
                 format_money_persian(rep["total_cost"]), "color": "#2e8b6a"},
                {"label": "سود", "value": money_utils.
                 format_money_persian(rep["total_profit"]), "color": "#2e8b6a"},
                {"label": "تعداد کل", "value": F.fa(rep["total_quantity"]),
                 "color": "#333"},
            ]},
            {"kind": "table", "title": "فروش به تفکیک محصول",
             "columns": ["محصول", "تعداد", "فروش", "قیمت تمام‌شده", "سود"],
             "rows": [[r["title"], F.fa(r["quantity"]),
                       money_utils.format_money_persian(r["row_total"]),
                       money_utils.format_money_persian(r["row_cost"]),
                       money_utils.format_money_persian(r["profit"])]
                      for r in rep["rows"]]},
        ]
        printing.show_print_preview(
            self, printing.build_report_html(title, sections))
