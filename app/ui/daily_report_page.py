# -*- coding: utf-8 -*-
"""Daily report page — mirrors webapp/templates/daily_report.html."""
from __future__ import annotations

from ..utils import Qt, error_msg
from .. import models, date_utils, money_utils
from . import fields as F
from . import printing
from ..theme import card, primary

_Core = Qt.QtCore
_W = Qt.QtWidgets


class DailyReportPage(_W.QWidget):
    def __init__(self, window):
        super().__init__(window)
        self.window_ = window
        self.setLayoutDirection(_Core.Qt.RightToLeft)
        self._iso = date_utils.today_iso()

        outer = _W.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        area, v = F.page_shell()
        outer.addWidget(area)

        print_btn = _W.QPushButton("چاپ گزارش")
        print_btn.clicked.connect(self._print_report)
        v.addWidget(F.page_header("گزارش روزانه", "", [print_btn]))

        # ---------------- Filter card ----------------
        box = _W.QWidget()
        h = _W.QHBoxLayout(box)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)
        h.addWidget(_W.QLabel("تاریخ (شمسی)"))
        self.date_edit = F.JalaliDateEdit(iso=date_utils.today_iso())
        self.date_edit.setMinimumWidth(150)
        h.addWidget(self.date_edit)
        show_btn = primary(_W.QPushButton("نمایش"), 110)
        show_btn.clicked.connect(self._show_report)
        h.addWidget(show_btn)
        h.addStretch(1)
        v.addWidget(card(box))

        # ---------------- Tiles ----------------
        self.sales_tile = F.tile_row([("فروش امروز", "۰", "info"),
                                      ("دریافتی امروز", "۰", "success"),
                                      ("باقی مانده", "۰", "warning"),
                                      ("تعداد پرداخت", "۰", "accent")])
        v.addWidget(self.sales_tile)

        # ---------------- By-method table ----------------
        m_box = _W.QWidget()
        mv = _W.QVBoxLayout(m_box)
        mv.setContentsMargins(0, 0, 0, 0)
        mv.setSpacing(8)
        mv.addWidget(F.card_title("دریافت‌ها به تفکیک روش پرداخت"))
        self.method_table = F.make_table(["روش پرداخت", "تعداد", "جمع مبلغ"],
                                         widths=[150, 80, 130], stretch=0)
        self.method_table.setMinimumHeight(140)
        mv.addWidget(self.method_table)
        v.addWidget(card(m_box))

        # ---------------- Payments detail ----------------
        d_box = _W.QWidget()
        dv = _W.QVBoxLayout(d_box)
        dv.setContentsMargins(0, 0, 0, 0)
        dv.setSpacing(8)
        dv.addWidget(F.card_title("جزئیات پرداخت‌ها"))
        self.detail_table = F.make_table(
            ["تاریخ", "زمان", "پرداخت‌کننده", "مبلغ", "روش", "شماره فاکتور"],
            widths=[116, 75, 150, 115, 90, 125], stretch=2)
        self.detail_table.setMinimumHeight(260)
        dv.addWidget(self.detail_table)
        v.addWidget(card(d_box))
        v.addStretch(1)

    # ------------------------------------------------------------------ #
    def refresh(self):
        self._show_report()

    def _show_report(self):
        iso = self.date_edit.iso()
        if not iso:
            error_msg(self, "تاریخ معتبر وارد کنید.")
            return
        self._iso = iso
        rep = models.daily_report(iso)
        self._rep = rep
        F.set_rows(self.method_table,
                   [[m["method"], m["count"],
                     money_utils.format_money_persian(m["total"])]
                    for m in rep["by_method"]])
        F.set_rows(self.detail_table,
                   [[date_utils.iso_to_jalali_persian_str(p["paid_at"]),
                     date_utils.to_persian_digits(str(p["paid_at"])[11:16]),
                     p["patient_name"] or "—",
                     money_utils.format_money_persian(p["amount"]),
                     p["method"],
                     F.fa(p["invoice_no"]) if p["invoice_no"] else "—"]
                    for p in rep["payments"]])
        self._set_tiles(rep)

    def _set_tiles(self, rep):
        vals = self.sales_tile.findChildren(_W.QLabel)
        # stat_tile order: label,value per tile — set the value labels.
        labels = [w for w in vals if w.objectName() == "statValue"]
        texts = [money_utils.format_money_persian(rep["sales"]),
                 money_utils.format_money_persian(rep["total"]),
                 money_utils.format_money_persian(rep["remaining"]),
                 F.fa(len(rep["payments"]))]
        for lab, txt in zip(labels, texts):
            lab.setText(txt)

    # ------------------------------------------------------------------ #
    def _print_report(self):
        iso = self.date_edit.iso()
        if not iso:
            error_msg(self, "تاریخ معتبر وارد کنید.")
            return
        rep = models.daily_report(iso)
        jdate = date_utils.iso_to_jalali_persian_str(iso)
        sections = [
            {"kind": "text", "text": "فروش: %s — دریافتی: %s — باقی مانده: %s" % (
                money_utils.format_money_persian(rep["sales"]),
                money_utils.format_money_persian(rep["total"]),
                money_utils.format_money_persian(rep["remaining"]))},
            {"kind": "table", "title": "دریافت‌ها به تفکیک روش پرداخت",
             "columns": ["روش پرداخت", "تعداد", "جمع مبلغ"],
             "rows": [[m["method"], F.fa(m["count"]),
                       money_utils.format_money_persian(m["total"])]
                      for m in rep["by_method"]]},
            {"kind": "table", "title": "جزئیات پرداخت‌ها",
             "columns": ["تاریخ", "زمان", "پرداخت‌کننده", "مبلغ", "روش",
                         "شماره فاکتور"],
             "rows": [[date_utils.iso_to_jalali_persian_str(p["paid_at"]),
                       date_utils.to_persian_digits(str(p["paid_at"])[11:16]),
                       p["patient_name"] or "—",
                       money_utils.format_money_persian(p["amount"]),
                       p["method"],
                       F.fa(p["invoice_no"]) if p["invoice_no"] else "—"]
                      for p in rep["payments"]]},
        ]
        printing.show_print_preview(
            self, printing.build_report_html("گزارش روزانه - %s" % jdate,
                                             sections))
