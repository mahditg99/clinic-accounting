# -*- coding: utf-8 -*-
"""Create / edit patient dialog."""
from __future__ import annotations

from typing import Optional

from ..utils import Qt
from .. import models

_Widgets = Qt.QtWidgets
_Core = Qt.QtCore
_Gui = Qt.QtGui


class PatientFormDialog(_Widgets.QDialog):
    """Modal dialog to create a patient file.

    Returns the new patient id via :meth:`patient_id` when accepted.
    """

    def __init__(self, parent=None, existing=None):
        # type: (Optional[_Widgets.QWidget], Optional[dict]) -> None
        super(PatientFormDialog, self).__init__(parent)
        from ..utils import make_rtl, best_persian_font, error_msg
        make_rtl(self)
        self.setWindowTitle("ایجاد پرونده")
        self._existing = existing
        self._new_id = None  # type: Optional[int]
        font = _Gui.QFont(best_persian_font(), 11)
        self.setFont(font)

        form = _Widgets.QFormLayout(self)
        self.file_no = _Widgets.QLineEdit()
        self.file_no.setAlignment(_Core.Qt.AlignRight)
        self.first_name = _Widgets.QLineEdit()
        self.first_name.setAlignment(_Core.Qt.AlignRight)
        self.last_name = _Widgets.QLineEdit()
        self.last_name.setAlignment(_Core.Qt.AlignRight)
        self.gender_combo = _Widgets.QComboBox()
        self.gender_combo.addItem("—", "")  # noqa
        self.gender_combo.addItem("آقا", "male")
        self.gender_combo.addItem("خانم", "female")
        for w in (self.file_no, self.first_name, self.last_name, self.gender_combo):
            w.setFont(font)

        form.addRow("شماره پرونده", self.file_no)
        form.addRow("نام", self.first_name)
        form.addRow("نام خانوادگی", self.last_name)
        form.addRow("جنسیت", self.gender_combo)

        if existing is not None:
            self.file_no.setText(str(existing.get("file_no", "")))
            self.first_name.setText(str(existing.get("first_name", "")))
            self.last_name.setText(str(existing.get("last_name", "")))
            gender = existing.get("gender", "") or ""
            for i in range(self.gender_combo.count()):
                if self.gender_combo.itemData(i) == gender:
                    self.gender_combo.setCurrentIndex(i)
                    break
            self.setWindowTitle("ویرایش پرونده")
            self.file_no.setReadOnly(True)

        btns = _Widgets.QDialogButtonBox(
            _Widgets.QDialogButtonBox.Ok | _Widgets.QDialogButtonBox.Cancel)
        btns.button(_Widgets.QDialogButtonBox.Ok).setText("ایجاد پرونده")
        btns.button(_Widgets.QDialogButtonBox.Cancel).setText("بستن")
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        form.addRow(btns)

    def _on_accept(self):
        from ..utils import error_msg
        file_no = self.file_no.text().strip()
        fn = self.first_name.text().strip()
        ln = self.last_name.text().strip()
        gender = self.gender_combo.currentData()
        if file_no == "":
            error_msg(self, "شماره پرونده الزامی است.")
            return
        if fn == "" or ln == "":
            error_msg(self, "نام و نام خانوادگی الزامی است.")
            return
        if self._existing is None:
            if models.file_no_exists(file_no):
                error_msg(self, "شماره پرونده تکراری است.")
                return
            try:
                self._new_id = models.create_patient(file_no, fn, ln, gender)
            except ValueError as exc:
                error_msg(self, str(exc))
                return
        else:
            pid = int(self._existing["id"])
            models.update_patient(pid, fn, ln, gender)
            self._new_id = pid
        self.accept()

    def patient_id(self):
        # type: () -> Optional[int]
        return self._new_id
