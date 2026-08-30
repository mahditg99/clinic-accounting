# -*- coding: utf-8 -*-
"""فهرست محصولات - Products page."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..utils import Qt
from .. import models, date_utils, money_utils

_Widgets = Qt.QtWidgets
_Core = Qt.QtCore
_Gui = Qt.QtGui


COLUMNS = ["ردیف", "نام محصول", "قیمت خرید", "قیمت فروش",
           "موجودی", "سطح هشدار", "وضعیت", "توضیحات"]


class _ProductsModel(_Core.QAbstractTableModel):
    HEADERS = COLUMNS

    def __init__(self):
        # type: () -> None
        super(_ProductsModel, self).__init__()
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
                return r["title"]
            if col == 2:
                return money_utils.format_money_persian(r["purchase_price"])
            if col == 3:
                return money_utils.format_money_persian(r["sale_price"])
            if col == 4:
                return date_utils.to_persian_digits(str(r["stock"]))
            if col == 5:
                return date_utils.to_persian_digits(str(r["low_stock_warning"]))
            if col == 6:
                return "فعال" if int(r["is_active"]) == 1 else "غیرفعال"
            if col == 7:
                return r["description"] or ""
        if role == _Core.Qt.TextAlignmentRole:
            if col in (0, 2, 3, 4, 5, 6):
                return _Core.Qt.AlignCenter
            return _Core.Qt.AlignRight | _Core.Qt.AlignVCenter
        if role == _Core.Qt.UserRole:
            return r["id"]
        if role == _Core.Qt.BackgroundRole:
            # highlight low-stock rows.
            try:
                if int(r["stock"]) <= int(r["low_stock_warning"]):
                    bg = _Gui.QColor(int(r["stock"]) <= 0 and 255 or 255,
                                     int(r["stock"]) <= 0 and 200 or 235,
                                     int(r["stock"]) <= 0 and 200 or 200)
                    return bg
            except Exception:
                pass
        return None


class ProductsPage(_Widgets.QWidget):
    def __init__(self, main_window=None):
        # type: (Optional[Any]) -> None
        super(ProductsPage, self).__init__()
        self._main = main_window
        from ..utils import make_rtl, best_persian_font
        make_rtl(self)
        self.setFont(_Gui.QFont(best_persian_font(), 10))
        self._model = _ProductsModel()
        self._proxy = _Core.QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._model)
        self._show_inactive = False
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        from ..theme import card, section_title, primary, success, danger
        layout = _Widgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(12)

        title = _Widgets.QLabel("فهرست محصولات")
        title.setProperty("role", "page-title")
        title.setStyleSheet("")
        title.setAlignment(_Core.Qt.AlignCenter)
        layout.addWidget(title)

        body = _Widgets.QHBoxLayout()
        body.setSpacing(12)

        # ---------------- Form card (left) ----------------
        form_holder = _Widgets.QWidget()
        fl = _Widgets.QVBoxLayout(form_holder)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.setSpacing(8)
        fl.addWidget(section_title("ثبت / ویرایش محصول"))

        self.title_edit = _Widgets.QLineEdit()
        self.title_edit.setAlignment(_Core.Qt.AlignRight)
        self.purchase_edit = _Widgets.QLineEdit()
        self.purchase_edit.setAlignment(_Core.Qt.AlignRight)
        self.purchase_edit.setValidator(
            _Gui.QRegExpValidator(_Core.QRegExp("^[0-9۰-۹,،]*$")))
        self.sale_edit = _Widgets.QLineEdit()
        self.sale_edit.setAlignment(_Core.Qt.AlignRight)
        self.sale_edit.setValidator(
            _Gui.QRegExpValidator(_Core.QRegExp("^[0-9۰-۹,،]*$")))
        self.stock_edit = _Widgets.QLineEdit()
        self.stock_edit.setAlignment(_Core.Qt.AlignRight)
        self.stock_edit.setValidator(_Gui.QIntValidator(0, 999999999))
        self.low_edit = _Widgets.QLineEdit()
        self.low_edit.setAlignment(_Core.Qt.AlignRight)
        self.low_edit.setValidator(_Gui.QIntValidator(0, 999999999))
        self.desc_edit = _Widgets.QLineEdit()
        self.desc_edit.setAlignment(_Core.Qt.AlignRight)

        form = _Widgets.QFormLayout()
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(8)
        form.addRow("نام محصول", self.title_edit)
        form.addRow("قیمت خرید (تومان)", self.purchase_edit)
        form.addRow("قیمت فروش (تومان)", self.sale_edit)
        form.addRow("موجودی", self.stock_edit)
        form.addRow("سطح هشدار", self.low_edit)
        form.addRow("توضیحات", self.desc_edit)
        fl.addLayout(form)

        # Action buttons.
        self.add_btn = success(_Widgets.QPushButton("اضافه کن"))
        self.add_btn.clicked.connect(self._add)
        self.update_btn = primary(_Widgets.QPushButton("ویرایش"))
        self.update_btn.clicked.connect(self._apply_update)
        self.delete_btn = danger(_Widgets.QPushButton("حذف / غیرفعال"))
        self.delete_btn.clicked.connect(self._delete)
        self.restock_btn = _Widgets.QPushButton("ثبت مجدد با قیمت جدید")
        self.restock_btn.clicked.connect(self._restock_new_price)
        row1 = _Widgets.QHBoxLayout()
        row1.addWidget(self.add_btn)
        row1.addWidget(self.update_btn)
        fl.addLayout(row1)
        row2 = _Widgets.QHBoxLayout()
        row2.addWidget(self.delete_btn)
        row2.addWidget(self.restock_btn)
        fl.addLayout(row2)

        form_card = card(form_holder)
        form_card.setFixedWidth(380)
        body.addWidget(form_card)

        # ---------------- Table card (right) ----------------
        table_holder = _Widgets.QWidget()
        tl = _Widgets.QVBoxLayout(table_holder)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(8)

        head = _Widgets.QHBoxLayout()
        head.addWidget(section_title("لیست محصولات"))
        head.addStretch(1)
        self.refresh_btn = _Widgets.QPushButton("بروزرسانی")
        self.refresh_btn.clicked.connect(self.refresh)
        head.addWidget(self.refresh_btn)
        tl.addLayout(head)

        # Show-inactive checkbox.
        self.show_inactive_chk = _Widgets.QCheckBox(
            "نمایش محصولات غیرفعال / بدون موجودی")
        self.show_inactive_chk.stateChanged.connect(self._on_show_inactive)
        tl.addWidget(self.show_inactive_chk)

        # Table.
        self.table = _Widgets.QTableView()
        self.table.setModel(self._proxy)
        self.table.setSelectionBehavior(_Widgets.QTableView.SelectRows)
        self.table.setSelectionMode(_Widgets.QTableView.SingleSelection)
        self.table.setEditTriggers(_Widgets.QTableView.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.selectionModel().selectionChanged.connect(self._on_row_selected)
        tl.addWidget(self.table, 1)

        self.count_label = _Widgets.QLabel("تعداد رکورد: ۰")
        self.count_label.setAlignment(_Core.Qt.AlignRight)
        tl.addWidget(self.count_label)

        table_card = card(table_holder)
        body.addWidget(table_card, 1)
        layout.addLayout(body)

    def _on_show_inactive(self, _state):
        self._show_inactive = self.show_inactive_chk.isChecked()
        self.refresh()

    def refresh(self):
        # type: () -> None
        rows = models.list_products(active_only=not self._show_inactive)
        self._model.set_rows(rows)
        self.count_label.setText("تعداد رکورد: %s" %
                                 date_utils.to_persian_digits(str(len(rows))))

    def _selected_id(self):
        # type: () -> Optional[int]
        idx = self.table.currentIndex()
        if not idx.isValid():
            return None
        src = self._proxy.mapToSource(idx)
        r = self._model.rows()
        if 0 <= src.row() < len(r):
            return int(r[src.row()]["id"])
        return None

    def _selected_row(self):
        # type: () -> Optional[Dict[str, Any]]
        pid = self._selected_id()
        if pid is None:
            return None
        for row in self._model.rows():
            if row["id"] == pid:
                return row
        return None

    def _on_row_selected(self):
        r = self._selected_row()
        if r is None:
            return
        self.title_edit.setText(r["title"])
        self.purchase_edit.setText(
            date_utils.to_persian_digits(str(r["purchase_price"])))
        self.sale_edit.setText(
            date_utils.to_persian_digits(str(r["sale_price"])))
        self.stock_edit.setText(date_utils.to_persian_digits(str(r["stock"])))
        self.low_edit.setText(
            date_utils.to_persian_digits(str(r["low_stock_warning"])))
        self.desc_edit.setText(r["description"] or "")

    def _collect(self):
        # type: () -> Optional[Dict[str, Any]]
        from ..utils import error_msg
        title = self.title_edit.text().strip()
        if title == "":
            error_msg(self, "نام محصول الزامی است.")
            return None
        purchase = money_utils.parse_money(self.purchase_edit.text())
        sale = money_utils.parse_money(self.sale_edit.text())
        stock = money_utils.parse_int(self.stock_edit.text(), 0)
        low = money_utils.parse_int(self.low_edit.text(), 0)
        if purchase is None:
            error_msg(self, "قیمت خرید الزامی است.")
            return None
        if sale is None:
            error_msg(self, "قیمت فروش الزامی است.")
            return None
        if purchase < 0:
            error_msg(self, "قیمت خرید نمی‌تواند منفی باشد.")
            return None
        if sale < 0:
            error_msg(self, "قیمت فروش نمی‌تواند منفی باشد.")
            return None
        if stock < 0:
            error_msg(self, "موجودی نمی‌تواند منفی باشد.")
            return None
        return {
            "title": title,
            "purchase_price": purchase,
            "sale_price": sale,
            "stock": stock,
            "low": low,
            "desc": self.desc_edit.text().strip(),
        }

    def _add(self):
        from ..utils import error_msg, info_msg
        data = self._collect()
        if data is None:
            return
        try:
            models.add_product(data["title"], data["purchase_price"],
                               data["sale_price"], data["stock"], data["low"],
                               data["desc"])
        except Exception as exc:
            error_msg(self, "خطا در ثبت محصول: %s" % str(exc))
            return
        info_msg(self, "محصول اضافه شد.")
        self._clear_form()
        self.refresh()

    def _apply_update(self):
        from ..utils import error_msg, info_msg
        pid = self._selected_id()
        if pid is None:
            error_msg(self, "یک محصول را از جدول انتخاب کنید.")
            return
        data = self._collect()
        if data is None:
            return
        try:
            models.update_product(pid, data["title"], data["purchase_price"],
                                  data["sale_price"], data["stock"], data["low"],
                                  data["desc"])
        except Exception as exc:
            error_msg(self, "خطا در ویرایش محصول: %s" % str(exc))
            return
        info_msg(self, "محصول ویرایش شد.")
        self._clear_form()
        self.refresh()

    def _delete(self):
        from ..utils import error_msg, confirm_msg, info_msg
        pid = self._selected_id()
        if pid is None:
            error_msg(self, "یک محصول را از جدول انتخاب کنید.")
            return
        if models.product_used_in_invoices(pid):
            info_msg(self,
                     "این محصول در فاکتورها استفاده شده است و حذف کامل آن "
                     "امکان‌پذیر نیست. می‌توانید آن را غیرفعال کنید.")
            if confirm_msg(self, "این محصول غیرفعال شود؟"):
                models.deactivate_product(pid)
                info_msg(self, "محصول غیرفعال شد.")
        else:
            if confirm_msg(self, "این محصول حذف شود؟"):
                models.hard_delete_product(pid)
                info_msg(self, "محصول حذف شد.")
            else:
                return
        self._clear_form()
        self.refresh()

    def _restock_new_price(self):
        """Open the form pre-filled with the selected product name only,
        so the user can enter a new purchase price, sale price and stock
        (creates a NEW product record per the stock-batch rule)."""
        r = self._selected_row()
        if r is None:
            from ..utils import error_msg
            error_msg(self, "ابتدا یک محصول را از جدول انتخاب کنید.")
            return
        self._clear_form()
        self.title_edit.setText(r["title"])
        self.purchase_edit.setFocus()

    def _clear_form(self):
        self.title_edit.setText("")
        self.purchase_edit.setText("")
        self.sale_edit.setText("")
        self.stock_edit.setText("")
        self.low_edit.setText("")
        self.desc_edit.setText("")
