# -*- coding: utf-8 -*-
"""Patient search dialog: search active patients or create a new one."""
from __future__ import annotations

from typing import Optional

from ..utils import Qt
from .. import models
from .patient_form_dialog import PatientFormDialog

_Widgets = Qt.QtWidgets
_Core = Qt.QtCore
_Gui = Qt.QtGui


class _PatientsModel(_Core.QAbstractTableModel):
    HEADERS = ["شماره پرونده", "نام و نام خانوادگی"]

    def __init__(self, rows=None):
        # type: (Optional[list]) -> None
        super(_PatientsModel, self).__init__()
        self._rows = rows or []

    def set_rows(self, rows):
        # type: (list) -> None
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

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
        row = self._rows[index.row()]
        if role == _Core.Qt.DisplayRole:
            if index.column() == 0:
                return row[0]["file_no"]
            if index.column() == 1:
                return "%s %s" % (row[0]["first_name"], row[0]["last_name"])
        elif role == _Core.Qt.UserRole:
            return row[0]["id"]
        return None


class PatientSearchDialog(_Widgets.QDialog):
    """Modal search/select dialog title: "جستجوی پرونده"."""

    def __init__(self, parent=None):
        # type: (Optional[_Widgets.QWidget]) -> None
        super(PatientSearchDialog, self).__init__(parent)
        from ..utils import make_rtl, best_persian_font
        make_rtl(self)
        self.setWindowTitle("جستجوی پرونده")
        self.setMinimumWidth(520)
        self.setMinimumHeight(420)
        font = _Gui.QFont(best_persian_font(), 11)
        self.setFont(font)
        self._selected_patient = None  # type: Optional[dict]

        layout = _Widgets.QVBoxLayout(self)

        # Search row.
        search_row = _Widgets.QHBoxLayout()
        self.search_edit = _Widgets.QLineEdit()
        self.search_edit.setAlignment(_Core.Qt.AlignRight)
        self.search_edit.setPlaceholderText("جستجو ...")
        self.search_edit.returnPressed.connect(self._do_search)
        self.by_file_radio = _Widgets.QRadioButton("شماره پرونده")
        self.by_name_radio = _Widgets.QRadioButton("نام یا نام خانوادگی")
        self.by_file_radio.setChecked(True)
        search_row.addWidget(_Widgets.QLabel("جستجو:"))
        search_row.addWidget(self.search_edit)
        search_row.addWidget(self.by_file_radio)
        search_row.addWidget(self.by_name_radio)
        self.search_btn = _Widgets.QPushButton("جستجو")
        self.search_btn.clicked.connect(self._do_search)
        search_row.addWidget(self.search_btn)
        layout.addLayout(search_row)

        # Table.
        self.model = _PatientsModel()
        self.proxy = _Core.QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterKeyColumn(-1)
        self.table = _Widgets.QTableView()
        self.table.setModel(self.proxy)
        self.table.setSelectionBehavior(_Widgets.QTableView.SelectRows)
        self.table.setSelectionMode(_Widgets.QTableView.SingleSelection)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(_Widgets.QTableView.NoEditTriggers)
        self.table.doubleClicked.connect(self._on_select)
        self.table.verticalHeader().setDefaultSectionSize(26)
        layout.addWidget(self.table)

        # Count label.
        self.count_label = _Widgets.QLabel("تعداد بیمار: ۰")
        self.count_label.setAlignment(_Core.Qt.AlignRight)
        layout.addWidget(self.count_label)

        # Buttons.
        btn_row = _Widgets.QHBoxLayout()
        self.new_btn = _Widgets.QPushButton("ایجاد پرونده")
        self.select_btn = _Widgets.QPushButton("انتخاب")
        self.close_btn = _Widgets.QPushButton("بستن")
        self.new_btn.clicked.connect(self._on_new)
        self.select_btn.clicked.connect(self._on_select)
        self.close_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.new_btn)
        btn_row.addWidget(self.select_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(self.close_btn)
        layout.addLayout(btn_row)

        self._do_search()

    def _do_search(self):
        from ..date_utils import to_persian_digits
        text = self.search_edit.text().strip()
        by_file = self.by_file_radio.isChecked()
        rows = models.search_active_patients(text, by_file)
        # Wrap each row in a single-item list (matches the model convention).
        wrapped = [[r] for r in rows]
        self.model.set_rows(wrapped)
        self.count_label.setText("تعداد بیمار: %s" %
                                 to_persian_digits(str(len(rows))))

    def _on_new(self):
        dlg = PatientFormDialog(self)
        if dlg.exec_() == _Widgets.QDialog.Accepted and dlg.patient_id() is not None:
            self._do_search()
            # auto-select the new patient.
            rows = self.model._rows  # noqa
            for i, r in enumerate(rows):
                if r[0]["id"] == dlg.patient_id():
                    idx = self.model.index(i, 0)
                    sel = self.table.selectionModel()
                    sel.select(idx, _Core.QItemSelectionModel.ClearAndSelect |
                               _Core.QItemSelectionModel.Rows)
                    break

    def _on_select(self):
        idx = self.table.currentIndex()
        if not idx.isValid():
            from ..utils import error_msg
            error_msg(self, "یک پرونده انتخاب کنید.")
            return
        src_idx = self.proxy.mapToSource(idx)
        rows = self.model._rows  # noqa
        if 0 <= src_idx.row() < len(rows):
            self._selected_patient = rows[src_idx.row()][0]
            self.accept()

    def selected_patient(self):
        # type: () -> Optional[dict]
        return self._selected_patient
