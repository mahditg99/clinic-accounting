# -*- coding: utf-8 -*-
"""Financial period report — mirrors webapp/templates/financial.html."""
from __future__ import annotations

from ..utils import Qt, error_msg
from .. import models, date_utils, money_utils
from . import fields as F
from . import printing
from ..theme import card, primary

_Core = Qt.QtCore
_W = Qt.QtWidgets

_MONTHS = F.FA_MONTHS


class FinancialReportsPage(_W.QWidget):
    def __init__(self, window):
        super().__init__(window)
        self.window_ = window
        self.setLayoutDirection(_Core.Qt.RightToLeft)
        self._data = None  # (start_iso, end_iso, receipts, expenses_rep, profit)

        outer = _W.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        area, v = F.page_shell()
        outer.addWidget(area)

        print_btn = _W.QPushButton("چاپ گزارش")
        print_btn.clicked.connect(self._print_report)
        v.addWidget(F.page_header(
            "گزارش مالی دوره",
            "خلاصه مالی ماهانه یا سالانه: دریافتی، هزینه و سود خالص",
            [print_btn]))

        # ---------------- Filter card ----------------
        box = _W.QWidget()
        h = _W.QHBoxLayout(box)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)
        h.addWidget(_W.QLabel("دوره"))
        self.period_combo = _W.QComboBox()
        self.period_combo.addItem("ماهانه", _Core.QVariant("monthly"))
        self.period_combo.addItem("سالانه", _Core.QVariant("yearly"))
        self.period_combo.setMinimumWidth(110)
        F.style_combo(self.period_combo)
        h.addWidget(self.period_combo)
        h.addWidget(_W.QLabel("سال خورشیدی"))
        self.year_edit = F.QtyEdit()
        self.year_edit.set_value(date_utils.jalali_year_now())
        self.year_edit.setMinimumWidth(90)
        h.addWidget(self.year_edit)
        h.addWidget(_W.QLabel("ماه"), 0)
        self.month_combo = _W.QComboBox()
        for i, name in enumerate(_MONTHS, 1):
            self.month_combo.addItem(name, _Core.QVariant(i))
        self.month_combo.setCurrentIndex(date_utils.jalali_month_now() - 1)
        self.month_combo.setMinimumWidth(120)
        F.style_combo(self.month_combo)
        h.addWidget(self.month_combo)
        show_btn = primary(_W.QPushButton("نمایش"), 110)
        show_btn.clicked.connect(self._show_report)
        h.addWidget(show_btn)
        h.addStretch(1)
        v.addWidget(card(box))
        self.period_combo.currentIndexChanged.connect(self._toggle_period)
        self._toggle_period()

        # ---------------- Profit card ----------------
        p_box = _W.QWidget()
        pv = _W.QVBoxLayout(p_box)
        pv.setContentsMargins(0, 0, 0, 0)
        pv.setSpacing(8)
        pv.addWidget(F.card_title("سود خالص"))
        self.profit_tiles = F.tile_row([
            ("فروش ناخالص", "۰", "info"),
            ("قیمت تمام‌شده", "۰", "warning"),
            ("سود ناخالص", "۰", "success"),
            ("هزینه‌ها", "۰", "danger"),
            ("سود خالص", "۰", "success"),
        ])
        pv.addWidget(self.profit_tiles)
        pv.addWidget(F.muted(
            "سود ناخالص = فروش − قیمت تمام‌شده؛ سود خالص = سود ناخالص − هزینه‌ها."))
        prow = _W.QHBoxLayout()
        prow.setSpacing(12)
        pd_box = _W.QWidget()
        pdv = _W.QVBoxLayout(pd_box)
        pdv.setContentsMargins(0, 0, 0, 0)
        self.doctor_profit_table = F.make_table(
            ["پزشک", "فروش", "هزینه", "سود"],
            widths=[140, 110, 110, 105], stretch=0)
        self.doctor_profit_table.setMinimumHeight(200)
        pdv.addWidget(self.doctor_profit_table)
        prow.addWidget(pd_box, 1)
        pp_box = _W.QWidget()
        ppv = _W.QVBoxLayout(pp_box)
        ppv.setContentsMargins(0, 0, 0, 0)
        self.product_profit_table = F.make_table(
            ["محصول", "تعداد", "فروش", "هزینه", "سود"],
            widths=[155, 78, 105, 105, 100], stretch=0)
        self.product_profit_table.setMinimumHeight(200)
        ppv.addWidget(self.product_profit_table)
        prow.addWidget(pp_box, 1)
        pv.addLayout(prow)
        v.addWidget(card(p_box))

        # ---------------- Receipts card ----------------
        r_box = _W.QWidget()
        rv = _W.QVBoxLayout(r_box)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(8)
        self.receipts_title = F.card_title("دریافتی")
        rv.addWidget(self.receipts_title)
        self.receipts_method_table = F.make_table(["روش", "تعداد", "مبلغ"],
                                                  widths=[120, 75, 120],
                                                  stretch=0)
        self.receipts_method_table.setMinimumHeight(120)
        rv.addWidget(self.receipts_method_table)
        self.receipts_detail_table = F.make_table(
            ["بیمار", "شماره فاکتور", "تاریخ", "زمان", "نوع پرداخت", "مبلغ"],
            widths=[150, 125, 115, 75, 120, 115], stretch=0)
        self.receipts_detail_table.setMinimumHeight(220)
        rv.addWidget(self.receipts_detail_table)
        v.addWidget(card(r_box))

        # ---------------- Expenses card ----------------
        e_box = _W.QWidget()
        ev = _W.QVBoxLayout(e_box)
        ev.setContentsMargins(0, 0, 0, 0)
        ev.setSpacing(8)
        self.expenses_title = F.card_title("هزینه‌ها")
        ev.addWidget(self.expenses_title)
        self.expenses_cat_table = F.make_table(["دسته", "تعداد", "مبلغ"],
                                               widths=[120, 75, 120],
                                               stretch=0)
        self.expenses_cat_table.setMinimumHeight(120)
        ev.addWidget(self.expenses_cat_table)
        self.expenses_detail_table = F.make_table(
            ["تاریخ", "دسته", "مبلغ", "توضیحات"],
            widths=[122, 132, 122, 200], stretch=3)
        self.expenses_detail_table.setMinimumHeight(220)
        ev.addWidget(self.expenses_detail_table)
        v.addWidget(card(e_box))
        v.addStretch(1)

    # ------------------------------------------------------------------ #
    def _toggle_period(self):
        monthly = self.period_combo.currentData() == "monthly"
        self.month_combo.setVisible(monthly)

    def refresh(self):
        self._show_report()

    def _range(self):
        # type: () -> tuple
        y = self.year_edit.value() or date_utils.jalali_year_now()
        if self.period_combo.currentData() == "yearly":
            return date_utils.jalali_year_range_iso(y)
        m = self.month_combo.currentData()
        return date_utils.jalali_month_range_iso(y, int(m))

    def _show_report(self):
        try:
            start_iso, end_iso = self._range()
        except ValueError as exc:
            error_msg(self, str(exc))
            return
        receipts = models.receipts_report(start_iso, end_iso)
        expenses_rep = models.expenses_report(start_iso, end_iso)
        profit = models.sales_profit_report(start_iso, end_iso)
        self._data = (start_iso, end_iso, receipts, expenses_rep, profit)

        vals = [w for w in self.profit_tiles.findChildren(_W.QLabel)
                if w.objectName() == "statValue"]
        for lab, num in zip(vals, (profit["gross_sales"],
                                   profit["cost_of_goods_sold"],
                                   profit["gross_profit"],
                                   profit["total_expenses"],
                                   profit["net_profit"])):
            lab.setText(money_utils.format_money_persian(num))
        F.set_rows(self.doctor_profit_table,
                   [[s["doctor"], money_utils.format_money_persian(
                       s["gross_sales"]),
                     money_utils.format_money_persian(s["total_cost"]),
                     money_utils.format_money_persian(s["profit"])]
                    for s in profit["summary_by_doctor"]])
        F.set_rows(self.product_profit_table,
                   [[s["product"], s["quantity"],
                     money_utils.format_money_persian(s["row_total"]),
                     money_utils.format_money_persian(s["row_cost"]),
                     money_utils.format_money_persian(s["profit"])]
                    for s in profit["summary_by_product"]])

        self.receipts_title.setText("دریافتی — جمع: %s" % money_utils.
                                    format_money_persian(
                                        receipts["total_received"]))
        F.set_rows(self.receipts_method_table,
                   [[s["method"], s["count"],
                     money_utils.format_money_persian(s["amount"])]
                    for s in receipts["summary_by_method"]])
        F.set_rows(self.receipts_detail_table,
                   [[p["patient_name"],
                     F.fa(p["invoice_no"]) if p["invoice_no"] else "—",
                     date_utils.iso_to_jalali_persian_str(p["paid_at"]),
                     date_utils.to_persian_digits(str(p["paid_at"])[11:16]),
                     p["method"],
                     money_utils.format_money_persian(p["amount"])]
                    for p in receipts["payment_details"]])

        self.expenses_title.setText("هزینه‌ها — جمع: %s" % money_utils.
                                    format_money_persian(
                                        expenses_rep["total_expense"]))
        F.set_rows(self.expenses_cat_table,
                   [[s["category"], s["count"],
                     money_utils.format_money_persian(s["amount"])]
                    for s in expenses_rep["summary_by_category"]])
        F.set_rows(self.expenses_detail_table,
                   [[date_utils.iso_to_jalali_persian_str(e["expense_date"]),
                     e["category"],
                     money_utils.format_money_persian(e["amount"]),
                     e["description"] or ""]
                    for e in expenses_rep["expense_details"]])

    # ------------------------------------------------------------------ #
    def _print_report(self):
        if self._data is None:
            self._show_report()
        if self._data is None:
            return
        start_iso, end_iso, receipts, expenses_rep, profit = self._data
        yearly = self.period_combo.currentData() == "yearly"
        y = F.fa(self.year_edit.value())
        period_lbl = ("سال %s" % y) if yearly else \
            ("%s %s" % (F.fa(self.month_combo.currentText()), y))
        sections = [
            {"kind": "cards", "cards": [
                {"label": "فروش ناخالص", "value":
                 money_utils.format_money_persian(profit["gross_sales"]),
                 "color": "#0d6e8c"},
                {"label": "قیمت تمام‌شده", "value":
                 money_utils.format_money_persian(
                     profit["cost_of_goods_sold"]), "color": "#b97a1c"},
                {"label": "سود ناخالص", "value":
                 money_utils.format_money_persian(profit["gross_profit"]),
                 "color": "#2e8b6a"},
                {"label": "هزینه‌ها", "value":
                 money_utils.format_money_persian(profit["total_expenses"]),
                 "color": "#c03b4a"},
                {"label": "سود خالص", "value":
                 money_utils.format_money_persian(profit["net_profit"]),
                 "color": "#2e8b6a"},
            ]},
            {"kind": "table", "title": "سود به تفکیک پزشک",
             "columns": ["پزشک", "فروش", "هزینه", "سود"],
             "rows": [[s["doctor"],
                       money_utils.format_money_persian(s["gross_sales"]),
                       money_utils.format_money_persian(s["total_cost"]),
                       money_utils.format_money_persian(s["profit"])]
                      for s in profit["summary_by_doctor"]]},
            {"kind": "table", "title": "سود به تفکیک محصول",
             "columns": ["محصول", "تعداد", "فروش", "هزینه", "سود"],
             "rows": [[s["product"], F.fa(s["quantity"]),
                       money_utils.format_money_persian(s["row_total"]),
                       money_utils.format_money_persian(s["row_cost"]),
                       money_utils.format_money_persian(s["profit"])]
                      for s in profit["summary_by_product"]]},
            {"kind": "table",
             "title": "دریافتی‌ها به تفکیک روش (جمع: %s)" % money_utils.
             format_money_persian(receipts["total_received"]),
             "columns": ["روش", "تعداد", "مبلغ"],
             "rows": [[s["method"], F.fa(s["count"]),
                       money_utils.format_money_persian(s["amount"])]
                      for s in receipts["summary_by_method"]]},
            {"kind": "table", "title": "جزئیات دریافتی‌ها",
             "columns": ["بیمار", "شماره فاکتور", "تاریخ", "زمان",
                         "نوع پرداخت", "مبلغ"],
             "rows": [[p["patient_name"],
                       F.fa(p["invoice_no"]) if p["invoice_no"] else "—",
                       date_utils.iso_to_jalali_persian_str(p["paid_at"]),
                       date_utils.to_persian_digits(str(p["paid_at"])[11:16]),
                       p["method"],
                       money_utils.format_money_persian(p["amount"])]
                      for p in receipts["payment_details"]]},
            {"kind": "table",
             "title": "هزینه‌ها به تفکیک دسته (جمع: %s)" % money_utils.
             format_money_persian(expenses_rep["total_expense"]),
             "columns": ["دسته", "تعداد", "مبلغ"],
             "rows": [[s["category"], F.fa(s["count"]),
                       money_utils.format_money_persian(s["amount"])]
                      for s in expenses_rep["summary_by_category"]]},
            {"kind": "table", "title": "جزئیات هزینه‌ها",
             "columns": ["تاریخ", "دسته", "مبلغ", "توضیحات"],
             "rows": [[date_utils.iso_to_jalali_persian_str(e["expense_date"]),
                       e["category"],
                       money_utils.format_money_persian(e["amount"]),
                       e["description"] or ""]
                      for e in expenses_rep["expense_details"]]},
        ]
        printing.show_print_preview(self, printing.build_report_html(
            "گزارش مالی دوره - %s" % period_lbl, sections))
