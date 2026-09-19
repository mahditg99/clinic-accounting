# -*- coding: utf-8 -*-
"""Doctor report page — mirrors webapp/templates/doctor_report.html."""
from __future__ import annotations

from ..utils import Qt, error_msg
from .. import models, date_utils, money_utils
from . import fields as F
from . import printing
from ..theme import card, primary

_Core = Qt.QtCore
_W = Qt.QtWidgets


class DoctorReportPage(_W.QWidget):
    def __init__(self, window):
        super().__init__(window)
        self.window_ = window
        self.setLayoutDirection(_Core.Qt.RightToLeft)
        self._mode = None   # "referral" | "single"
        self._rep = None

        outer = _W.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        area, v = F.page_shell()
        outer.addWidget(area)

        print_btn = _W.QPushButton("چاپ گزارش")
        print_btn.clicked.connect(self._print_report)
        v.addWidget(F.page_header("گزارش پزشکان", "", [print_btn]))

        # ---------------- Filter card ----------------
        box = _W.QWidget()
        h = _W.QHBoxLayout(box)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)
        h.addWidget(_W.QLabel("پزشک"))
        self.doctor_combo = F.SearchComboBox(placeholder="جستجوی پزشک…")
        self.doctor_combo.setMinimumWidth(160)
        h.addWidget(self.doctor_combo)
        h.addWidget(_W.QLabel("از تاریخ"))
        self.date_from = F.JalaliDateEdit()
        h.addWidget(self.date_from)
        h.addWidget(_W.QLabel("تا تاریخ"))
        self.date_to = F.JalaliDateEdit()
        h.addWidget(self.date_to)
        show_btn = primary(_W.QPushButton("نمایش"), 110)
        show_btn.clicked.connect(self._show_report)
        h.addWidget(show_btn)
        h.addStretch(1)
        v.addWidget(card(box))

        # ---------------- Tiles (single doctor) ----------------
        self.tiles = F.tile_row([
            ("جمع فروش", "۰", "info"),
            ("دریافتی", "۰", "success"),
            ("باقی مانده", "۰", "warning"),
            ("جمع هزینه", "۰", "danger"),
            ("سود", "۰", "success"),
        ])
        v.addWidget(self.tiles)

        # ---------------- Referral summary table ----------------
        self.ref_title = F.card_title("خلاصه معرفی پزشکان")
        ref_box = _W.QWidget()
        rv = _W.QVBoxLayout(ref_box)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(8)
        rv.addWidget(self.ref_title)
        self.referral_table = F.make_table(
            ["پزشک", "آخرین فاکتور", "جمع فروش", "دریافتی", "باقی مانده"],
            widths=[150, 125, 120, 118, 115], stretch=0)
        self.referral_table.setMinimumHeight(300)
        rv.addWidget(self.referral_table)
        self.ref_card = card(ref_box)
        v.addWidget(self.ref_card)

        # ---------------- Invoices table (single doctor) ----------------
        inv_box = _W.QWidget()
        iv = _W.QVBoxLayout(inv_box)
        iv.setContentsMargins(0, 0, 0, 0)
        iv.setSpacing(8)
        iv.addWidget(F.card_title("فاکتورهای پزشک"))
        self.invoices_table = F.make_table(
            ["شماره", "بیمار", "تاریخ", "جمع", "دریافتی", "باقی مانده"],
            widths=[85, 150, 110, 105, 105, 115], stretch=1)
        self.invoices_table.setMinimumHeight(300)
        iv.addWidget(self.invoices_table)
        self._inv_pager = F.ListPager(self.invoices_table)
        self._inv_pager.configure(
            key_fn=self._inv_sort_key, sortable=(0, 1, 2, 3, 4, 5),
            on_render=self._append_inv_row)
        iv.addWidget(self._inv_pager.pager)
        self.inv_card = card(inv_box)
        v.addWidget(self.inv_card)
        v.addStretch(1)

    @staticmethod
    def _inv_sort_key(r, col):
        if col == 0:
            return int(r["invoice_no"])
        if col == 1:
            return F.en(r["patient_name"] or "").lower()
        if col == 2:
            return r["issued_at"] or ""  # ISO is chronological
        if col == 3:
            return int(r["total_amount"])
        if col == 4:
            return int(r["total_received"])
        if col == 5:
            return int(r["remaining"])
        return 0

    def _append_inv_row(self, r):
        self.invoices_table.model().appendRow([
            F.make_item(r["invoice_no"]),
            F.make_item(r["patient_name"]),
            F.make_item(date_utils.iso_to_jalali_persian_str(r["issued_at"])),
            F.make_item(money_utils.format_money_persian(r["total_amount"])),
            F.make_item(money_utils.format_money_persian(r["total_received"])),
            F.make_item(money_utils.format_money_persian(r["remaining"])),
        ])

    # ------------------------------------------------------------------ #
    def refresh(self):
        self._fill_doctors()
        self._show_report()

    def _fill_doctors(self):
        cur = self.doctor_combo.currentData()
        self.doctor_combo.clear()
        self.doctor_combo.addItem("همه پزشکان", _Core.QVariant("all"))
        self.doctor_combo.addItem("بدون معرف", _Core.QVariant("none"))
        for d in models.list_doctors_with_id():
            if d["name"] == "بدون معرف":
                continue
            self.doctor_combo.addItem(F.fa(d["name"]), _Core.QVariant(d["id"]))
        if cur is not None:
            idx = self.doctor_combo.findData(_Core.QVariant(cur))
            if idx >= 0:
                self.doctor_combo.setCurrentIndex(idx)

    def _show_report(self):
        df = self.date_from.iso() or None
        dt = self.date_to.iso() or None
        sel = self.doctor_combo.currentData()
        if sel in (None, "all"):
            self._mode = "referral"
            rep = models.doctor_referral_report(None, df, dt)
            self._rep = rep
            self._show_referral(rep)
        elif sel == "none":
            self._mode = "referral"
            rep = models.doctor_referral_report("none", df, dt)
            self._rep = rep
            self._show_referral(rep)
        else:
            self._mode = "single"
            rep = models.doctor_report(int(sel), df, dt)
            self._rep = rep
            self.ref_card.setVisible(False)
            self.tiles.setVisible(True)
            self.inv_card.setVisible(True)
            vals = [w for w in self.tiles.findChildren(_W.QLabel)
                    if w.objectName() == "statValue"]
            for lab, num in zip(vals, (rep["total_sales"],
                                       rep["total_received"],
                                       rep["total_remaining"],
                                       rep["total_cost"],
                                       rep["total_profit"])):
                lab.setText(money_utils.format_money_persian(num))
            self._inv_pager.set_items(rep["invoices_summary"],
                                      reset_page=True)

    def _show_referral(self, rep):
        self.tiles.setVisible(False)
        self.inv_card.setVisible(False)
        self.ref_card.setVisible(True)
        F.set_rows(self.referral_table,
                   [[r["doctor_name"],
                     date_utils.iso_to_jalali_persian_str(
                         r["last_invoice_date"]) if r.get("last_invoice_date")
                     else "—",
                     money_utils.format_money_persian(r["total_sum"]),
                     money_utils.format_money_persian(r["paid_sum"]),
                     money_utils.format_money_persian(r["remaining"])]
                    for r in rep["rows"]])

    # ------------------------------------------------------------------ #
    def _print_report(self):
        df = self.date_from.iso() or None
        dt = self.date_to.iso() or None
        sel = self.doctor_combo.currentData()
        title = "گزارش پزشکان"
        sections = []
        if sel in (None, "all"):
            rep = models.doctor_referral_report(None, df, dt)
            rows = self._referral_rows(rep)
            sections = [{"kind": "table", "title": "خلاصه معرفی پزشکان",
                         "columns": ["پزشک", "آخرین فاکتور", "جمع فروش",
                                     "دریافتی", "باقی مانده"], "rows": rows}]
        elif sel == "none":
            rep = models.doctor_referral_report("none", df, dt)
            rows = self._referral_rows(rep)
            title = "گزارش بدون معرف"
            sections = [{"kind": "table", "title": "خلاصه معرفی (بدون معرف)",
                         "columns": ["پزشک", "آخرین فاکتور", "جمع فروش",
                                     "دریافتی", "باقی مانده"], "rows": rows}]
        else:
            rep = models.doctor_report(int(sel), df, dt)
            title = "گزارش پزشک %s" % rep["doctor_name"]
            sections = [
                {"kind": "cards", "cards": [
                    {"label": "جمع فروش", "value": money_utils.
                     format_money_persian(rep["total_sales"]),
                     "color": "#0d6e8c"},
                    {"label": "دریافتی", "value": money_utils.
                     format_money_persian(rep["total_received"]),
                     "color": "#2e8b6a"},
                    {"label": "باقی مانده", "value": money_utils.
                     format_money_persian(rep["total_remaining"]),
                     "color": "#b97a1c"},
                    {"label": "جمع هزینه", "value": money_utils.
                     format_money_persian(rep["total_cost"]),
                     "color": "#c03b4a"},
                    {"label": "سود", "value": money_utils.
                     format_money_persian(rep["total_profit"]),
                     "color": "#2e8b6a"},
                ]},
                {"kind": "table", "title": "فاکتورهای پزشک",
                 "columns": ["شماره", "بیمار", "تاریخ", "جمع", "دریافتی",
                             "باقی مانده"],
                 "rows": [[r["invoice_no"], r["patient_name"],
                           date_utils.iso_to_jalali_persian_str(
                               r["issued_at"]),
                           money_utils.format_money_persian(r["total_amount"]),
                           money_utils.format_money_persian(
                               r["total_received"]),
                           money_utils.format_money_persian(r["remaining"])]
                          for r in rep["invoices_summary"]]},
            ]
        printing.show_print_preview(
            self, printing.build_report_html(title, sections))

    @staticmethod
    def _referral_rows(rep):
        return [[r["doctor_name"],
                 date_utils.iso_to_jalali_persian_str(r["last_invoice_date"])
                 if r.get("last_invoice_date") else "—",
                 money_utils.format_money_persian(r["total_sum"]),
                 money_utils.format_money_persian(r["paid_sum"]),
                 money_utils.format_money_persian(r["remaining"])]
                for r in rep["rows"]]
