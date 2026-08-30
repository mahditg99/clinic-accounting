# -*- coding: utf-8 -*-
"""Archive page — mirrors webapp/templates/archive.html."""
from __future__ import annotations

from typing import Any, Dict, List

from ..utils import Qt, confirm_msg, info_msg
from .. import models, settings as settings_mod, date_utils, money_utils
from . import fields as F
from . import printing
from ..theme import card, primary

_Core = Qt.QtCore
_Gui = Qt.QtGui
_W = Qt.QtWidgets


class ArchivePage(_W.QWidget):
    def __init__(self, window):
        super().__init__(window)
        self.window_ = window
        self.setLayoutDirection(_Core.Qt.RightToLeft)

        outer = _W.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        area, v = F.page_shell()
        outer.addWidget(area)
        v.addWidget(F.page_header("آرشیو فاکتورها",
                                  "جستجو و مدیریت فاکتورهای ثبت‌شده"))
        v.addWidget(self._build_filter_card())
        v.addWidget(self._build_table_card())
        v.addStretch(1)
        self._reload()

    # ------------------------------------------------------------------ #
    def _build_filter_card(self):
        box = _W.QWidget()
        grid = _W.QGridLayout(box)
        grid.setSpacing(8)
        grid.addWidget(_W.QLabel("پزشک"), 0, 0)
        self.doctor_combo = _W.QComboBox()
        self.doctor_combo.setMinimumWidth(150)
        grid.addWidget(self.doctor_combo, 1, 0)
        grid.addWidget(_W.QLabel("از تاریخ"), 0, 1)
        self.date_from = F.JalaliDateEdit()
        grid.addWidget(self.date_from, 1, 1)
        grid.addWidget(_W.QLabel("تا تاریخ"), 0, 2)
        self.date_to = F.JalaliDateEdit()
        grid.addWidget(self.date_to, 1, 2)
        grid.addWidget(_W.QLabel("جستجو (نام، شماره پرونده، شماره فاکتور)"),
                       0, 3)
        # NOTE: placeholder must be a kwarg — SearchEdit("…") would set the
        # line-edit *text* (QLineEdit(text, parent) overload) and filter out
        # every row.
        self.search = F.SearchEdit(placeholder="جستجو…")
        self.search.setMinimumWidth(220)
        grid.addWidget(self.search, 1, 3)
        btn = primary(_W.QPushButton("اعمال فیلتر"), 110)
        btn.clicked.connect(self._reload)
        grid.addWidget(btn, 1, 4)
        self.search.textChanged.connect(lambda _: self._reload())
        self.doctor_combo.currentIndexChanged.connect(lambda _: self._reload())
        self.date_from.dateChanged.connect(lambda _: self._reload())
        self.date_to.dateChanged.connect(lambda _: self._reload())
        return card(box)

    def _build_table_card(self):
        box = _W.QWidget()
        v = _W.QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)
        self.title_lbl = F.card_title("فاکتورها")
        v.addWidget(self.title_lbl)
        self.table = F.make_table(
            ["شماره", "شماره پرونده", "بیمار", "تاریخ صدور", "جمع کل",
             "پرداخت‌شده", "باقی مانده", "پزشک", "عملیات"],
            widths=[85, 125, 160, 125, 105, 120, 110, 132, 210])
        # Lazy action widgets: only visible rows get real buttons, so a
        # 600-invoice archive opens in a blink instead of building 1800.
        self.table.set_row_widget_factory(8, self._make_actions)
        self.table.setMinimumHeight(360)
        v.addWidget(self.table)
        return card(box)

    # ------------------------------------------------------------------ #
    def refresh(self):
        self._fill_doctors()
        self._reload()

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

    def _reload(self):
        raw = self.doctor_combo.currentData()
        doctor_filter = "all" if raw is None else raw
        if doctor_filter == "all":
            doctor_filter = None
        rows = models.list_archive_invoices(
            doctor_filter=doctor_filter,
            date_from=self.date_from.iso() or None,
            date_to=self.date_to.iso() or None,
            search_text=self.search.text().strip())
        self._rows = rows
        self.title_lbl.setText("فاکتورها (%s مورد)" % F.fa(len(rows)))
        model = self.table.model()
        model.removeRows(0, model.rowCount())
        for r in rows:
            items = [
                self._cell(F.fa(r["invoice_no"]), payload=r["id"]),
                self._cell(F.fa(r["file_no"])),
                self._cell(r["patient_name"]),
                self._cell(date_utils.iso_to_jalali_persian_str(r["issued_at"])),
                self._cell(money_utils.format_money_persian(r["total_amount"])),
                self._cell(money_utils.format_money_persian(r["paid_sum"])),
                self._cell(money_utils.format_money_persian(r["remaining"])),
                self._cell(F.fa(r["doctor_name"] or "بدون معرف")),
                self._cell(""),
            ]
            if int(r["remaining"]) > 0:
                items[6].setForeground(_Gui.QColor("#c03b4a"))
            else:
                items[6].setForeground(_Gui.QColor("#2e8b6a"))
            model.appendRow(items)
        F.resort(self.table)
        self.table.schedule_fit()

    def _cell(self, text, payload=None):
        return F.make_item(text, payload=payload)

    def _make_actions(self, rr):
        """Build the row's action buttons (called lazily for visible rows).
        The invoice id travels with the row via the hidden payload, so the
        buttons stay correct even after the user re-sorts the table."""
        model = self.table.model()
        item = model.item(rr, 0)
        if item is None:
            return None
        raw = item.data(F.ROW_ID)
        if raw is None:
            return None
        inv_id = int(raw)
        btns = _W.QWidget()
        h = _W.QHBoxLayout(btns)
        h.setContentsMargins(2, 0, 2, 0)
        h.setSpacing(4)
        b_view = _W.QPushButton("مشاهده / چاپ")
        b_view.setProperty("variant", "link")
        b_view.setProperty("btnsize", "xs")
        b_view.setCursor(_Core.Qt.PointingHandCursor)
        b_view.clicked.connect(lambda _=False, i=inv_id: self._show(i))
        b_edit = _W.QPushButton("ویرایش")
        b_edit.setProperty("variant", "link")
        b_edit.setProperty("btnsize", "xs")
        b_edit.setCursor(_Core.Qt.PointingHandCursor)
        b_edit.clicked.connect(
            lambda _=False, i=inv_id: self.window_.show_invoice_edit(i))
        b_void = _W.QPushButton("ابطال")
        b_void.setProperty("variant", "link")
        b_void.setProperty("btnsize", "xs")
        b_void.setProperty("tone", "danger")
        b_void.setCursor(_Core.Qt.PointingHandCursor)
        b_void.clicked.connect(lambda _=False, i=inv_id: self._void(i))
        # AlignVCenter: index widgets are stretched to the full cell by
        # default, which re-inflates the compact xs buttons to row height.
        h.addWidget(b_view, 0, _Core.Qt.AlignVCenter)
        h.addWidget(b_edit, 0, _Core.Qt.AlignVCenter)
        h.addWidget(b_void, 0, _Core.Qt.AlignVCenter)
        h.addStretch(1)
        return btns

    # ------------------------------------------------------------------ #
    def _show(self, invoice_id):
        inv = models.get_invoice(invoice_id)
        if inv is None:
            return
        items = models.list_invoice_items(invoice_id)
        paid = models.invoice_paid_sum(invoice_id)
        html = printing.build_invoice_html({
            "app_title": settings_mod.get_setting("app_title", "آذران طب"),
            "invoice_no": inv["invoice_no"],
            "issued_at": inv["issued_at"],
            "patient_name": "%s %s" % (inv["first_name"], inv["last_name"]),
            "file_no": inv["file_no"],
            "doctor_name": inv.get("doctor_name") or "",
            "show_doctor": settings_mod.get_setting("show_doctor_in_print",
                                                    "0") == "1",
            "notes": inv.get("notes") or "",
            "rows": [{"title": it["title"], "unit_price": it["unit_price"],
                      "quantity": it["quantity"], "row_total": it["row_total"]}
                     for it in items],
            "total": int(inv["total_amount"]),
            "paid": paid,
            "remaining": int(inv["total_amount"]) - paid,
        })
        printing.show_print_preview(self, html)

    def _void(self, invoice_id):
        if not confirm_msg(self, "ابطال فاکتور، موجودی کالاها را برمی‌گرداند. "
                                 "ادامه می‌دهید؟"):
            return
        models.soft_delete_invoice(invoice_id)
        info_msg(self, "فاکتور ابطال شد.")
        self._reload()
