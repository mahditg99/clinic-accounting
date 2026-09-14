# -*- coding: utf-8 -*-
"""Products page — mirrors webapp/templates/products.html."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..utils import Qt, confirm_msg, warning_msg, error_msg
from .. import models, money_utils
from . import fields as F
from ..theme import card, success

_Core = Qt.QtCore
_Gui = Qt.QtGui
_W = Qt.QtWidgets

PAGE_SIZE = 50

# Header column -> SQL sort key (whole-dataset sort, then re-page).
_SORT_KEYS = {
    0: "title",
    1: "purchase",
    2: "sale",
    3: "stock",
    4: "low",
    5: "active",
}


class ProductsPage(_W.QWidget):
    def __init__(self, window):
        super().__init__(window)
        self.window_ = window
        self.setLayoutDirection(_Core.Qt.RightToLeft)
        self._editing_id = None  # type: Optional[int]
        self._all = []  # type: List[Dict[str, Any]]
        self._page = 0
        self._sort_key = None  # type: Optional[str]
        self._sort_desc = False
        self._sort_col = -1  # type: int
        self._sort_order = _Core.Qt.AscendingOrder

        outer = _W.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        area, v = F.page_shell()
        outer.addWidget(area)
        v.addWidget(F.page_header("فهرست محصولات", "مدیریت محصولات و موجودی انبار"))
        v.addWidget(self._build_form_card())
        v.addWidget(self._build_table_card())
        v.addStretch(1)

    # ------------------------------------------------------------------ #
    def _build_form_card(self):
        box = _W.QWidget()
        v = _W.QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)
        self.form_title = F.card_title("ثبت محصول جدید")
        v.addWidget(self.form_title)
        grid = _W.QGridLayout()
        grid.setSpacing(8)
        self.title = _W.QLineEdit()
        self.title.setLayoutDirection(_Core.Qt.RightToLeft)
        self.purchase = F.MoneyEdit()
        self.sale = F.MoneyEdit()
        self.stock = F.QtyEdit()
        self.low = F.QtyEdit()
        self.desc = _W.QLineEdit()
        self.desc.setLayoutDirection(_Core.Qt.RightToLeft)
        specs = [("نام محصول", self.title, 0, 0, 1, 6),
                 ("قیمت خرید", self.purchase, 1, 0, 1, 1),
                 ("قیمت فروش", self.sale, 1, 2, 1, 1),
                 ("موجودی", self.stock, 1, 4, 1, 1),
                 ("سطح هشدار", self.low, 1, 5, 1, 1),
                 ("توضیحات", self.desc, 2, 0, 1, 6)]
        for label, w, r, c, rs, cs in specs:
            lab = _W.QLabel(label)
            lab.setStyleSheet("color:#5d7385; font-size:11px; font-weight:700;")
            grid.addWidget(lab, r * 2, c, 1, cs)
            grid.addWidget(w, r * 2 + 1, c, 1, cs)
        # fix label spans for the single-cell fields (labels above fields)
        v.addLayout(grid)
        row = _W.QHBoxLayout()
        self.err = _W.QLabel("")
        self.err.setStyleSheet("color:#c03b4a; font-size:11px;")
        row.addWidget(self.err)
        row.addStretch(1)
        self.cancel_btn = _W.QPushButton("انصراف")
        self.cancel_btn.clicked.connect(self._reset_form)
        self.cancel_btn.hide()
        self.save_btn = success(_W.QPushButton("افزودن محصول"), 140)
        self.save_btn.clicked.connect(self._save)
        row.addWidget(self.cancel_btn)
        row.addWidget(self.save_btn)
        v.addLayout(row)
        return card(box)

    def _build_table_card(self):
        box = _W.QWidget()
        v = _W.QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)
        head = _W.QHBoxLayout()
        head.addWidget(F.card_title("فهرست محصولات"))
        head.addSpacing(10)
        # Live search over name + description (SQL LIKE), like the archive.
        self.search = F.SearchEdit(placeholder="جستجوی محصول…")
        self.search.setMinimumWidth(220)
        self.search.textChanged.connect(self._on_filter_changed)
        head.addWidget(self.search)
        head.addStretch(1)
        self.show_inactive = _W.QCheckBox("نمایش غیرفعال / بدون موجودی")
        self.show_inactive.toggled.connect(lambda _: self._on_filter_changed())
        head.addWidget(self.show_inactive)
        v.addLayout(head)
        self.table = F.make_table(
            ["نام محصول", "قیمت خرید", "قیمت فروش", "موجودی", "سطح هشدار",
             "وضعیت", "عملیات"],
            widths=[265, 115, 125, 95, 125, 95, 260])
        self.table.set_external_sort(self._on_header_sort)
        self.table.setMinimumHeight(340)
        v.addWidget(self.table)
        self.pager = F.PagerRow()
        self.pager.page_requested.connect(self._on_page)
        v.addWidget(self.pager)
        self.count_lbl = _W.QLabel("")
        self.count_lbl.setStyleSheet("color:#5d7385; font-size:11px;")
        v.addWidget(self.count_lbl)
        return card(box)

    def _on_filter_changed(self):
        self._page = 0
        self.refresh()

    def _on_page(self, p):
        self._page = p
        self.refresh()

    def _on_header_sort(self, col, order):
        key = _SORT_KEYS.get(col)
        if key is None:
            F.set_sort_state(self.table, self._sort_col, self._sort_order)
            return
        self._sort_col = col
        self._sort_order = order
        self._sort_key = key
        self._sort_desc = (order == _Core.Qt.DescendingOrder)
        self._page = 0
        self.refresh()

    # ------------------------------------------------------------------ #
    def refresh(self):
        active_only = not self.show_inactive.isChecked()
        search_text = self.search.text().strip()
        total = models.count_products(active_only=active_only,
                                      search_text=search_text)
        pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        self._page = min(max(0, self._page), pages - 1)
        self._all = models.list_products(
            active_only=active_only, search_text=search_text,
            limit=PAGE_SIZE, offset=self._page * PAGE_SIZE,
            sort_key=self._sort_key, sort_desc=self._sort_desc)
        self._total = total
        first = self._page * PAGE_SIZE + 1 if total else 0
        last = min(total, (self._page + 1) * PAGE_SIZE)
        self.pager.set_state(self._page, pages, first, last, total)
        self._render()

    def _render(self):
        model = self.table.model()
        model.removeRows(0, model.rowCount())
        for p in self._all:
            stock = int(p["stock"])
            low = int(p["low_stock_warning"] or 0)
            out = stock <= 0
            is_low = (not out) and stock <= low
            if out:
                status = "بدون موجودی"
            elif is_low:
                status = "کم"
            elif p["is_active"]:
                status = "فعال"
            else:
                status = "غیرفعال"
            items = [
                self._cell(p["title"]),
                self._cell(money_utils.format_money_persian(p["purchase_price"])),
                self._cell(money_utils.format_money_persian(p["sale_price"])),
                self._cell(F.fa(stock)),
                self._cell(F.fa(low)),
                self._cell(status),
                self._cell(""),
            ]
            if out:
                tone = _Gui.QColor("#fbe9eb")
            elif is_low:
                tone = _Gui.QColor("#fbf1dd")
            else:
                tone = None
            if tone is not None:
                for it in items:
                    it.setBackground(tone)
            colors = {"بدون موجودی": "#c03b4a", "کم": "#b97a1c",
                      "فعال": "#2e8b6a", "غیرفعال": "#5d7385"}
            items[5].setForeground(_Gui.QColor(colors[status]))
            model.appendRow(items)
            r = model.rowCount() - 1
            btns = _W.QWidget()
            h = _W.QHBoxLayout(btns)
            h.setContentsMargins(2, 0, 2, 0)
            h.setSpacing(4)
            b_edit = _W.QPushButton("ویرایش")
            b_edit.setProperty("variant", "link")
            b_edit.setProperty("btnsize", "xs")
            b_edit.setCursor(_Core.Qt.PointingHandCursor)
            b_edit.clicked.connect(lambda _=False, pid=p["id"]: self._load_for_edit(pid))
            b_batch = _W.QPushButton("شارژ مجدد")
            b_batch.setProperty("variant", "link")
            b_batch.setProperty("btnsize", "xs")
            b_batch.setCursor(_Core.Qt.PointingHandCursor)
            b_batch.clicked.connect(lambda _=False, pid=p["id"]: self._new_batch(pid))
            h.addWidget(b_edit, 0, _Core.Qt.AlignVCenter)
            h.addWidget(b_batch, 0, _Core.Qt.AlignVCenter)
            if p["is_active"]:
                b_deact = _W.QPushButton("غیرفعال")
                b_deact.setProperty("variant", "link")
                b_deact.setProperty("btnsize", "xs")
                b_deact.setProperty("tone", "warn")
                b_deact.setCursor(_Core.Qt.PointingHandCursor)
                b_deact.clicked.connect(lambda _=False, pid=p["id"]: self._deactivate(pid))
                h.addWidget(b_deact, 0, _Core.Qt.AlignVCenter)
            b_del = _W.QPushButton("حذف")
            b_del.setProperty("variant", "link")
            b_del.setProperty("btnsize", "xs")
            b_del.setProperty("tone", "danger")
            b_del.setCursor(_Core.Qt.PointingHandCursor)
            b_del.clicked.connect(lambda _=False, pid=p["id"]: self._delete(pid))
            h.addWidget(b_del, 0, _Core.Qt.AlignVCenter)
            h.addStretch(1)
            self.table.setIndexWidget(model.index(r, 6), btns)
        F.resort(self.table)
        self.count_lbl.setText("مجموعاً %s محصول" % F.fa(self._total))

    def _cell(self, text):
        return F.make_item(text)

    # ------------------------------------------------------------------ #
    def _reset_form(self):
        self._editing_id = None
        self.title.clear()
        self.purchase.set_value(None)
        self.sale.set_value(None)
        self.stock.clear()
        self.low.clear()
        self.desc.clear()
        self.err.setText("")
        self.form_title.setText("ثبت محصول جدید")
        self.save_btn.setText("افزودن محصول")
        self.cancel_btn.hide()

    def _load_for_edit(self, product_id):
        p = self._find(product_id)
        if p is None:
            return
        self._editing_id = product_id
        self.title.setText(p["title"])
        self.purchase.set_value(int(p["purchase_price"]))
        self.sale.set_value(int(p["sale_price"]))
        self.stock.setText(F.fa(p["stock"]))
        self.low.setText(F.fa(p["low_stock_warning"]))
        self.desc.setText(p.get("description") or "")
        self.err.setText("")
        self.form_title.setText("ویرایش محصول")
        self.save_btn.setText("ذخیره تغییرات")
        self.cancel_btn.show()

    def _new_batch(self, product_id):
        """شارژ مجدد: prefill as a NEW product (new batch) like the web."""
        p = self._find(product_id)
        if p is None:
            return
        self._editing_id = None
        self.title.setText(p["title"])
        self.purchase.set_value(int(p["purchase_price"]))
        self.sale.set_value(int(p["sale_price"]))
        self.stock.clear()
        self.low.clear()
        self.desc.clear()
        self.err.setText("")
        self.form_title.setText("شارژ مجدد (دسته جدید): " + p["title"])
        self.save_btn.setText("افزودن دسته جدید")
        self.cancel_btn.show()

    def _find(self, product_id):
        for p in self._all:
            if p["id"] == product_id:
                return p
        return None

    def _save(self):
        try:
            if self._editing_id is None:
                models.add_product(
                    self.title.text(), self.purchase.value(), self.sale.value(),
                    self.stock.value(), self.low.value(), self.desc.text().strip())
            else:
                models.update_product(
                    self._editing_id, self.title.text(), self.purchase.value(),
                    self.sale.value(), self.stock.value(), self.low.value(),
                    self.desc.text().strip())
        except ValueError as exc:
            self.err.setText(str(exc))
            return
        except Exception as exc:
            error_msg(self, str(exc))
            return
        self._reset_form()
        self.refresh()

    def _deactivate(self, product_id):
        if confirm_msg(self, "این محصول غیرفعال شود؟"):
            models.deactivate_product(product_id)
            self.refresh()

    def _delete(self, product_id):
        if models.product_used_in_invoices(product_id):
            warning_msg(self, "این محصول در فاکتورها استفاده شده و قابل حذف "
                              "نیست؛ می‌توانید آن را غیرفعال کنید.")
            return
        if confirm_msg(self, "محصول برای همیشه حذف شود؟"):
            models.hard_delete_product(product_id)
            self.refresh()
