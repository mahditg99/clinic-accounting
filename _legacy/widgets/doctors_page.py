# -*- coding: utf-8 -*-
"""فهرست پزشکان - Doctors reference page (moved out of Settings).

Manages the doctors list (add / deactivate / hard-delete). Lives on its own
tab so it is not buried inside Settings.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..utils import Qt
from .. import settings as settings_mod

_Widgets = Qt.QtWidgets
_Core = Qt.QtCore
_Gui = Qt.QtGui


class _DoctorsModel(_Core.QAbstractTableModel):
    HEADERS = ["نام پزشک", "وضعیت"]

    def __init__(self):
        # type: () -> None
        super(_DoctorsModel, self).__init__()
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
        if role == _Core.Qt.DisplayRole:
            if index.column() == 0:
                return r["name"]
            if index.column() == 1:
                return "فعال" if r["is_active"] else "غیرفعال"
        if role == _Core.Qt.UserRole:
            return r["id"]
        if role == _Core.Qt.TextAlignmentRole:
            return _Core.Qt.AlignRight | _Core.Qt.AlignVCenter
        return None


class DoctorsPage(_Widgets.QWidget):
    def __init__(self, main_window=None):
        # type: (Optional[Any]) -> None
        super(DoctorsPage, self).__init__()
        self._main = main_window
        from ..utils import make_rtl, best_persian_font
        make_rtl(self)
        self.setFont(_Gui.QFont(best_persian_font(), 10))
        self._model = _DoctorsModel()
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        from ..theme import card, section_title, success, danger
        layout = _Widgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(12)

        title = _Widgets.QLabel("فهرست پزشکان")
        title.setProperty("role", "page-title")
        title.setStyleSheet("")
        title.setAlignment(_Core.Qt.AlignCenter)
        layout.addWidget(title)

        # ---------------- Add doctor card ----------------
        add_holder = _Widgets.QWidget()
        al = _Widgets.QVBoxLayout(add_holder)
        al.setContentsMargins(0, 0, 0, 0)
        al.setSpacing(10)
        al.addWidget(section_title("افزودن پزشک", "پزشکان معالج برای معرفی بیماران"))

        add_doc_row = _Widgets.QHBoxLayout()
        add_doc_row.setSpacing(6)
        add_doc_row.addWidget(_Widgets.QLabel("نام پزشک:"))
        self.new_doctor_edit = _Widgets.QLineEdit()
        self.new_doctor_edit.setPlaceholderText("نام پزشک جدید")
        self.new_doctor_edit.setAlignment(_Core.Qt.AlignRight)
        self.new_doctor_edit.returnPressed.connect(self._add_doctor)
        add_doc_row.addWidget(self.new_doctor_edit, 1)
        self.add_doctor_btn = success(_Widgets.QPushButton("اضافه کن"), 120)
        self.add_doctor_btn.clicked.connect(self._add_doctor)
        self.del_doctor_btn = danger(_Widgets.QPushButton("حذف / غیرفعال"), 150)
        self.del_doctor_btn.clicked.connect(self._delete_doctor)
        add_doc_row.addWidget(self.add_doctor_btn)
        add_doc_row.addWidget(self.del_doctor_btn)
        al.addLayout(add_doc_row)
        layout.addWidget(card(add_holder))

        # ---------------- Doctors table card ----------------
        table_holder = _Widgets.QWidget()
        tl = _Widgets.QVBoxLayout(table_holder)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(8)
        head = _Widgets.QHBoxLayout()
        head.addWidget(section_title("پزشکان موجود"))
        head.addStretch(1)
        tl.addLayout(head)

        self.doctors_table = _Widgets.QTableView()
        self.doctors_table.setModel(self._model)
        self.doctors_table.setSelectionBehavior(_Widgets.QTableView.SelectRows)
        self.doctors_table.setSelectionMode(_Widgets.QTableView.SingleSelection)
        self.doctors_table.setEditTriggers(_Widgets.QTableView.NoEditTriggers)
        self.doctors_table.horizontalHeader().setStretchLastSection(True)
        self.doctors_table.verticalHeader().setVisible(False)
        self.doctors_table.verticalHeader().setDefaultSectionSize(30)
        tl.addWidget(self.doctors_table, 1)

        self.count_label = _Widgets.QLabel("تعداد پزشک: ۰")
        self.count_label.setAlignment(_Core.Qt.AlignRight)
        tl.addWidget(self.count_label)
        layout.addWidget(card(table_holder), 1)

    def refresh(self):
        # type: () -> None
        rows = settings_mod.list_doctors(active_only=False)
        self._model.set_rows(rows)
        from .. import date_utils
        self.count_label.setText("تعداد پزشک: %s" %
                                 date_utils.to_persian_digits(str(len(rows))))

    def _selected_id(self):
        # type: () -> Optional[int]
        idx = self.doctors_table.currentIndex()
        if not idx.isValid():
            return None
        r = self._model.rows()
        if 0 <= idx.row() < len(r):
            return int(r[idx.row()]["id"])
        return None

    def _add_doctor(self):
        from ..utils import error_msg, info_msg
        name = self.new_doctor_edit.text().strip()
        if name == "":
            error_msg(self, "نام پزشک را وارد کنید.")
            return
        try:
            settings_mod.add_doctor(name)
        except Exception as exc:
            error_msg(self, "خطا در ثبت پزشک: %s" % str(exc))
            return
        self.new_doctor_edit.setText("")
        self.refresh()
        info_msg(self, "پزشک اضافه شد.")

    def _delete_doctor(self):
        from ..utils import error_msg, confirm_msg, info_msg
        idx = self.doctors_table.currentIndex()
        if not idx.isValid():
            error_msg(self, "یک پزشک انتخاب کنید.")
            return
        row = self._model.rows()[idx.row()]
        doctor_id = int(row["id"])
        name = row["name"]
        if settings_mod.is_no_doctor(name):
            info_msg(self, "این پزشک پیش‌فرض ('بدون معرف') قابل حذف نیست.")
            return
        if settings_mod.is_doctor_used(doctor_id):
            if confirm_msg(
                    self,
                    "این پزشک در فاکتورها استفاده شده است. غیرفعال شود؟"):
                settings_mod.deactivate_doctor(doctor_id)
                info_msg(self, "پزشک غیرفعال شد.")
        else:
            if confirm_msg(self, "این پزشک حذف شود؟"):
                settings_mod.hard_delete_doctor(doctor_id)
                info_msg(self, "پزشک حذف شد.")
        self.refresh()