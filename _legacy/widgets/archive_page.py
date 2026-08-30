# -*- coding: utf-8 -*-
"""آرشیو فاکتورها - Invoice archive page."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..utils import Qt
from .. import models, settings, date_utils, money_utils
from ..dialogs.jalali_date_dialog import JalaliDateEdit
from . import print_utils

_Widgets = Qt.QtWidgets
_Core = Qt.QtCore
_Gui = Qt.QtGui


COLUMNS = ["شماره فاکتور", "شماره پرونده", "بیمار", "تاریخ صدور",
           "جمع کل", "پرداخت‌شده", "باقی مانده", "پزشک"]


class _ArchiveModel(_Core.QAbstractTableModel):
    HEADERS = COLUMNS

    def __init__(self):
        # type: () -> None
        super(_ArchiveModel, self).__init__()
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
                return date_utils.to_persian_digits(str(r["invoice_no"]))
            if col == 1:
                return date_utils.to_persian_digits(r["file_no"])
            if col == 2:
                return r["patient_name"]
            if col == 3:
                return date_utils.iso_to_jalali_persian_str(r["issued_at"])
            if col == 4:
                return money_utils.format_money_persian(r["total_amount"])
            if col == 5:
                return money_utils.format_money_persian(r["paid_sum"])
            if col == 6:
                return money_utils.format_money_persian(r["remaining"])
            if col == 7:
                doc = r.get("doctor_name") or "بدون معرف"
                return doc
        if role == _Core.Qt.TextAlignmentRole:
            if col in (0, 1, 3, 4, 5, 6):
                return _Core.Qt.AlignCenter
            return _Core.Qt.AlignRight | _Core.Qt.AlignVCenter
        if role == _Core.Qt.UserRole:
            return r["id"]
        return None


class ArchivePage(_Widgets.QWidget):
    def __init__(self, main_window=None):
        # type: (Optional[Any]) -> None
        super(ArchivePage, self).__init__()
        self._main = main_window
        from ..utils import make_rtl, best_persian_font
        make_rtl(self)
        self.setFont(_Gui.QFont(best_persian_font(), 10))
        self._model = _ArchiveModel()
        self._proxy = _Core.QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._model)
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        from ..theme import card, section_title, primary, danger
        layout = _Widgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(12)

        title = _Widgets.QLabel("آرشیو فاکتورها")
        title.setProperty("role", "page-title")
        title.setStyleSheet("")
        title.setAlignment(_Core.Qt.AlignCenter)
        layout.addWidget(title)

        # ---------------- Filter card ----------------
        filt_holder = _Widgets.QWidget()
        ff = _Widgets.QVBoxLayout(filt_holder)
        ff.setContentsMargins(0, 0, 0, 0)
        ff.setSpacing(8)

        ff.addWidget(section_title("فیلتر و جستجو", "بر اساس پزشک معالج یا محدوده تاریخ"))

        filters = _Widgets.QHBoxLayout()
        filters.setSpacing(6)
        filters.addWidget(_Widgets.QLabel("پزشک:"))
        self.doctor_combo = _Widgets.QComboBox()
        self.doctor_combo.addItem("همه", None)
        self.doctor_combo.addItem("بدون معرف", "none")
        filters.addWidget(self.doctor_combo)
        filters.addWidget(_Widgets.QLabel("از تاریخ:"))
        self.date_from = JalaliDateEdit(self, initial="")
        filters.addWidget(self.date_from)
        filters.addWidget(_Widgets.QLabel("تا تاریخ:"))
        self.date_to = JalaliDateEdit(self, initial="")
        filters.addWidget(self.date_to)
        self.filter_btn = primary(_Widgets.QPushButton("اعمال فیلتر"), 110)
        self.filter_btn.clicked.connect(self.refresh)
        filters.addWidget(self.filter_btn)
        filters.addStretch(1)
        ff.addLayout(filters)

        search_row = _Widgets.QHBoxLayout()
        search_row.addWidget(_Widgets.QLabel("جستجو:"))
        self.search_edit = _Widgets.QLineEdit()
        self.search_edit.setAlignment(_Core.Qt.AlignRight)
        self.search_edit.setPlaceholderText("نام، شماره پرونده یا شماره فاکتور")
        self.search_edit.returnPressed.connect(self.refresh)
        search_row.addWidget(self.search_edit, 1)
        ff.addLayout(search_row)

        filter_card = card(filt_holder)
        layout.addWidget(filter_card)

        # ---------------- Table card ----------------
        table_holder = _Widgets.QWidget()
        tl = _Widgets.QVBoxLayout(table_holder)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(8)

        head = _Widgets.QHBoxLayout()
        head.addWidget(section_title("فاکتورها"))
        head.addStretch(1)
        tl.addLayout(head)

        self.table = _Widgets.QTableView()
        self.table.setModel(self._proxy)
        self.table.setSelectionBehavior(_Widgets.QTableView.SelectRows)
        self.table.setSelectionMode(_Widgets.QTableView.SingleSelection)
        self.table.setEditTriggers(_Widgets.QTableView.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.doubleClicked.connect(self._view_print)
        tl.addWidget(self.table, 1)

        # Count + action buttons.
        foot = _Widgets.QHBoxLayout()
        self.count_label = _Widgets.QLabel("تعداد رکورد: ۰")
        self.count_label.setAlignment(_Core.Qt.AlignRight)
        foot.addWidget(self.count_label)
        foot.addStretch(1)
        self.view_btn = primary(_Widgets.QPushButton("مشاهده / چاپ"), 120)
        self.view_btn.clicked.connect(self._view_print)
        self.edit_btn = _Widgets.QPushButton("ویرایش فاکتور")
        self.edit_btn.clicked.connect(self._edit)
        self.delete_btn = danger(_Widgets.QPushButton("حذف / ابطال"), 120)
        self.delete_btn.clicked.connect(self._delete)
        self.refresh_btn = _Widgets.QPushButton("بروزرسانی")
        self.refresh_btn.clicked.connect(self.refresh)
        for b in (self.view_btn, self.edit_btn, self.delete_btn,
                  self.refresh_btn):
            foot.addWidget(b)
        tl.addLayout(foot)

        table_card = card(table_holder)
        layout.addWidget(table_card, 1)

    def refresh(self):
        # type: () -> None
        # Populate doctor filter.
        prev = self.doctor_combo.currentData()
        self.doctor_combo.clear()
        self.doctor_combo.addItem("همه", None)
        self.doctor_combo.addItem("بدون معرف", "none")
        for d in models.list_doctors_with_id():
            self.doctor_combo.addItem(d["name"], d["id"])
        # restore selection.
        if prev is not None:
            for i in range(self.doctor_combo.count()):
                if self.doctor_combo.itemData(i) == prev:
                    self.doctor_combo.setCurrentIndex(i)
                    break
        doctor_filter = self.doctor_combo.currentData()
        date_from_iso = self.date_from.iso_value()
        date_to_iso = self.date_to.iso_value()
        search = self.search_edit.text().strip()
        rows = models.list_archive_invoices(doctor_filter, date_from_iso,
                                             date_to_iso, search)
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

    def _view_print(self):
        from ..utils import error_msg
        inv_id = self._selected_id()
        if inv_id is None:
            error_msg(self, "یک فاکتور انتخاب کنید.")
            return
        self._print_invoice(inv_id)

    def _print_invoice(self, inv_id):
        inv = models.get_invoice(inv_id)
        if inv is None:
            return
        items = models.list_invoice_items(inv_id)
        pays = models.list_payments(inv_id)
        total = sum(int(i["row_total"]) for i in items)
        paid = sum(int(p["amount"]) for p in pays)
        rows = [dict(index=i + 1, title=it["title"], unit_price=it["unit_price"],
                     quantity=it["quantity"], row_total=it["row_total"])
                for i, it in enumerate(items)]
        app_title = settings.get_setting("app_title", "آذران طب")
        show_doctor = settings.get_setting("show_doctor_in_print", "0") == "1"
        html = print_utils.build_invoice_html({
            "app_title": app_title,
            "invoice_no": str(inv["invoice_no"]),
            "issued_at": inv["issued_at"],
            "patient_name": "%s %s" % (inv["first_name"], inv["last_name"]),
            "file_no": inv["file_no"],
            "doctor_name": inv["doctor_name"] or "",
            "rows": rows,
            "total": total,
            "paid": paid,
            "remaining": total - paid,
            "show_doctor": show_doctor,
        })
        print_utils.show_print_preview(self, html)

    def _edit(self):
        from ..utils import error_msg, info_msg
        inv_id = self._selected_id()
        if inv_id is None:
            error_msg(self, "یک فاکتور انتخاب کنید.")
            return
        self._main.show_new_invoice_with_edit(inv_id)

    def _delete(self):
        from ..utils import error_msg, confirm_msg, info_msg
        inv_id = self._selected_id()
        if inv_id is None:
            error_msg(self, "یک فاکتور انتخاب کنید.")
            return
        if not confirm_msg(self, "آیا این فاکتور ابطال شود؟ موجودی محصولات بازگردانده می‌شود."):
            return
        models.soft_delete_invoice(inv_id)
        info_msg(self, "فاکتور ابطال شد و موجودی محصولات بازگردانده شد.")
        self.refresh()
        if self._main is not None:
            try:
                self._main.refresh_other_pages()
            except Exception:
                pass
