# -*- coding: utf-8 -*-
"""پرونده‌ها - Patient files page."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..utils import Qt
from .. import models, date_utils
from ..dialogs.patient_form_dialog import PatientFormDialog

_Widgets = Qt.QtWidgets
_Core = Qt.QtCore
_Gui = Qt.QtGui


COLUMNS = ["شماره پرونده", "نام", "نام خانوادگی", "جنسیت",
           "تعداد فاکتور", "وضعیت"]


class _PatientsModel(_Core.QAbstractTableModel):
    HEADERS = COLUMNS

    def __init__(self):
        # type: () -> None
        super(_PatientsModel, self).__init__()
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
                return date_utils.to_persian_digits(r["file_no"])
            if col == 1:
                return r["first_name"]
            if col == 2:
                return r["last_name"]
            if col == 3:
                g = r["gender"]
                return {"male": "آقا", "female": "خانم"}.get(g, "—")
            if col == 4:
                return date_utils.to_persian_digits(str(r["invoice_count"]))
            if col == 5:
                return "فعال" if r["is_active"] else "غیرفعال"
        if role == _Core.Qt.TextAlignmentRole:
            if col in (0, 3, 4, 5):
                return _Core.Qt.AlignCenter
            return _Core.Qt.AlignRight | _Core.Qt.AlignVCenter
        if role == _Core.Qt.UserRole:
            return r["id"]
        return None


class PatientsPage(_Widgets.QWidget):
    def __init__(self, main_window=None):
        # type: (Optional[Any]) -> None
        super(PatientsPage, self).__init__()
        self._main = main_window
        from ..utils import make_rtl, best_persian_font
        make_rtl(self)
        self.setFont(_Gui.QFont(best_persian_font(), 10))
        self._model = _PatientsModel()
        self._proxy = _Core.QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterKeyColumn(-1)
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        from ..theme import card, section_title, primary, success, danger
        layout = _Widgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(12)

        title = _Widgets.QLabel("پرونده‌ها")
        title.setProperty("role", "page-title")
        title.setStyleSheet("")
        title.setAlignment(_Core.Qt.AlignCenter)
        layout.addWidget(title)

        # ---------------- Search + actions card ----------------
        act_holder = _Widgets.QWidget()
        al = _Widgets.QVBoxLayout(act_holder)
        al.setContentsMargins(0, 0, 0, 0)
        al.setSpacing(10)

        al.addWidget(section_title("جستجوی پرونده‌ها", "بر اساس شماره پرونده یا نام"))

        search_row = _Widgets.QHBoxLayout()
        search_row.addWidget(_Widgets.QLabel("جستجو:"))
        self.search_edit = _Widgets.QLineEdit()
        self.search_edit.setAlignment(_Core.Qt.AlignRight)
        self.search_edit.setPlaceholderText("شماره پرونده یا نام")
        self.search_edit.textChanged.connect(self._apply_search)
        search_row.addWidget(self.search_edit, 1)
        al.addLayout(search_row)

        actions = _Widgets.QHBoxLayout()
        actions.setSpacing(6)
        self.new_btn = success(_Widgets.QPushButton("ایجاد پرونده"), 130)
        self.new_btn.clicked.connect(self._new_patient)
        self.edit_btn = primary(_Widgets.QPushButton("ویرایش پرونده"), 130)
        self.edit_btn.clicked.connect(self._edit_patient)
        self.delete_btn = danger(_Widgets.QPushButton("حذف / غیرفعال"), 150)
        self.delete_btn.clicked.connect(self._delete_patient)
        self.refresh_btn = _Widgets.QPushButton("بروزرسانی")
        self.refresh_btn.clicked.connect(self.refresh)
        for b in (self.new_btn, self.edit_btn, self.delete_btn,
                  self.refresh_btn):
            actions.addWidget(b)
        actions.addStretch(1)
        al.addLayout(actions)
        layout.addWidget(card(act_holder))

        # ---------------- Table card ----------------
        table_holder = _Widgets.QWidget()
        tl = _Widgets.QVBoxLayout(table_holder)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(8)
        head = _Widgets.QHBoxLayout()
        head.addWidget(section_title("فهرست پرونده‌ها"))
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
        tl.addWidget(self.table, 1)

        self.count_label = _Widgets.QLabel("تعداد رکورد: ۰")
        self.count_label.setAlignment(_Core.Qt.AlignRight)
        tl.addWidget(self.count_label)
        layout.addWidget(card(table_holder), 1)

    def refresh(self):
        # type: () -> None
        self._all_rows = models.list_patients(active_only=False)
        self._model.set_rows(self._all_rows)
        self._apply_search()
        self.count_label.setText("تعداد رکورد: %s" %
                                 date_utils.to_persian_digits(str(len(self._all_rows))))

    def _apply_search(self):
        text = self.search_edit.text().strip()
        if text == "":
            self._proxy.setFilterFixedString("")
            return
        self._proxy.setFilterFixedString(text)

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

    def _new_patient(self):
        dlg = PatientFormDialog(self)
        if dlg.exec_() == _Widgets.QDialog.Accepted:
            self.refresh()

    def _edit_patient(self):
        from ..utils import error_msg
        pid = self._selected_id()
        if pid is None:
            error_msg(self, "یک پرونده انتخاب کنید.")
            return
        patient = models.get_patient(pid)
        if patient is None:
            return
        dlg = PatientFormDialog(self, existing=patient)
        if dlg.exec_() == _Widgets.QDialog.Accepted:
            self.refresh()

    def _delete_patient(self):
        from ..utils import error_msg, confirm_msg, info_msg
        pid = self._selected_id()
        if pid is None:
            error_msg(self, "یک پرونده انتخاب کنید.")
            return
        if models.patient_has_invoices(pid):
            info_msg(self,
                     "این پرونده دارای فاکتور است و حذف کامل آن امکان‌پذیر نیست. "
                     "می‌توانید آن را غیرفعال کنید.")
            if confirm_msg(self, "پرونده غیرفعال شود؟"):
                models.deactivate_patient(pid)
                info_msg(self, "پرونده غیرفعال شد.")
                self.refresh()
            return
        if confirm_msg(self, "این پرونده حذف شود؟ این عمل قابل بازگشت است."):
            models.delete_patient(pid)
            info_msg(self, "پرونده حذف شد.")
            self.refresh()
