# -*- coding: utf-8 -*-
"""Archive page — mirrors webapp/templates/archive.html."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..utils import Qt, confirm_msg, info_msg
from .. import models, date_utils, money_utils
from . import fields as F
from . import printing
from ..theme import card, primary

_Core = Qt.QtCore
_Gui = Qt.QtGui
_W = Qt.QtWidgets

# The archive is paged at the SQL level: with 500+ invoices, loading (and
# rendering) one page instead of the whole table is what keeps the page
# opening instantly and search-as-you-type responsive.
PAGE_SIZE = 50

# Header column -> SQL sort key. Sorting runs in the database over the
# WHOLE filtered set, then re-paginates — not just the visible page.
_SORT_KEYS = {
    0: "invoice_no",
    1: "file_no",
    2: "patient",
    3: "issued_at",
    4: "total",
    5: "paid",
    6: "remaining",
    7: "doctor",
}


class ArchivePage(_W.QWidget):
    def __init__(self, window):
        super().__init__(window)
        self.window_ = window
        self.setLayoutDirection(_Core.Qt.RightToLeft)
        self._page = 0  # 0-based page index into the filtered archive
        self._sort_key = None  # type: Optional[str]
        self._sort_desc = False
        self._sort_col = -1  # type: int  # last header col the user sorted on
        self._sort_order = _Core.Qt.AscendingOrder

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
        self.doctor_combo = F.SearchComboBox(placeholder="جستجوی پزشک…")
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
        btn.clicked.connect(self._on_filter_changed)
        grid.addWidget(btn, 1, 4)
        self.search.textChanged.connect(lambda _: self._on_filter_changed())
        self.doctor_combo.currentIndexChanged.connect(
            lambda _: self._on_filter_changed())
        self.date_from.dateChanged.connect(lambda _: self._on_filter_changed())
        self.date_to.dateChanged.connect(lambda _: self._on_filter_changed())
        return card(box)

    def _on_filter_changed(self):
        # Any filter change restarts browsing from the first page.
        self._page = 0
        self._reload()

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
        # Header clicks sort the WHOLE filtered dataset in SQL, then page.
        self.table.set_external_sort(self._on_header_sort)
        self.table.setMinimumHeight(360)
        v.addWidget(self.table)
        # Direct-jump pager: « ‹ [صفحه ▾] از N › » + range label.
        self.pager = F.PagerRow()
        self.pager.page_requested.connect(self._on_page)
        v.addWidget(self.pager)
        return card(box)

    def _on_page(self, p):
        self._page = p
        self._reload()

    def _on_header_sort(self, col, order):
        key = _SORT_KEYS.get(col)
        if key is None:
            # «عملیات» (or any unmapped column): put the arrow back on the
            # sort actually in effect — the header must not advertise a
            # sort the SQL never ran.
            F.set_sort_state(self.table, self._sort_col, self._sort_order)
            return
        self._sort_col = col
        self._sort_order = order
        self._sort_key = key
        self._sort_desc = (order == _Core.Qt.DescendingOrder)
        self._page = 0
        self._reload()

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
        date_from = self.date_from.iso() or None
        date_to = self.date_to.iso() or None
        search_text = self.search.text().strip()
        total = models.count_archive_invoices(
            doctor_filter=doctor_filter, date_from=date_from,
            date_to=date_to, search_text=search_text)
        pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        if self._page >= pages:
            self._page = pages - 1
        if self._page < 0:
            self._page = 0
        rows = models.list_archive_invoices(
            doctor_filter=doctor_filter,
            date_from=date_from,
            date_to=date_to,
            search_text=search_text,
            limit=PAGE_SIZE, offset=self._page * PAGE_SIZE,
            sort_key=self._sort_key, sort_desc=self._sort_desc)
        self._rows = rows
        self.title_lbl.setText("فاکتورها (%s مورد)" % F.fa(total))
        first = self._page * PAGE_SIZE + 1 if total else 0
        last = min(total, (self._page + 1) * PAGE_SIZE)
        self.pager.set_state(self._page, pages, first, last, total)
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
        # Single shared builder with the post-save preview (printing.py).
        printing.show_invoice_preview(self, invoice_id)

    def _void(self, invoice_id):
        if not confirm_msg(self, "ابطال فاکتور، موجودی کالاها را برمی‌گرداند. "
                                 "ادامه می‌دهید؟"):
            return
        models.soft_delete_invoice(invoice_id)
        info_msg(self, "فاکتور ابطال شد.")
        self._reload()
