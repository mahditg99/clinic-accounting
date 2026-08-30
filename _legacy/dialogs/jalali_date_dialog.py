# -*- coding: utf-8 -*-
"""Self-contained Jalali (Shamsi) date selector dialog.

Provides:
  - :class:`JalaliDateEdit`: a compact line edit with YYYY/MM/DD format hint,
    accepts Persian/English digits, validated on focus loss.
  - :func:`pick_jalali_date`: modal picker returning 'YYYY/MM/DD' or None.
"""
from __future__ import annotations

from typing import Optional, Tuple

from ..utils import Qt
from .. import date_utils


_Widgets = Qt.QtWidgets
_Core = Qt.QtCore
_Gui = Qt.QtGui


class JalaliDateEdit(_Widgets.QWidget):
    """Line edit with a '...' button to open a picker. Value is Jalali 'YYYY/MM/DD'."""

    def __init__(self, parent=None, initial=None):
        # type: (Optional[_Widgets.QWidget], Optional[str]) -> None
        super(JalaliDateEdit, self).__init__(parent)
        _Core.QCoreApplication.processEvents  # noqa
        from ..utils import make_rtl, best_persian_font
        make_rtl(self)
        layout = _Widgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.line = _Widgets.QLineEdit()
        self.line.setAlignment(_Core.Qt.AlignRight)
        self.line.setFont(_Gui.QFont(best_persian_font(), 10))
        self.line.setPlaceholderText("۱۳۸۰/۰۱/۰۱")
        self.btn = _Widgets.QPushButton("...")
        self.btn.setFixedWidth(28)
        layout.addWidget(self.line)
        layout.addWidget(self.btn)
        self.btn.clicked.connect(self._open_picker)
        self.line.editingFinished.connect(self._normalize)
        if initial:
            self.line.setText(initial)
        else:
            self.line.setText(date_utils.today_jalali_str())

    def _open_picker(self):
        result = pick_jalali_date(self, self.value())
        if result is not None:
            self.line.setText(result)

    def _normalize(self):
        text = self.line.text().strip()
        if text == "":
            return
        try:
            iso = date_utils.jalali_str_to_iso(text)
            if iso is None:
                self.line.setText(date_utils.today_jalali_str())
                return
        except ValueError as exc:
            from ..utils import error_msg
            error_msg(self, str(exc))
            self.line.setText(date_utils.today_jalali_str())
            return
        self.line.setText(date_utils.iso_to_jalali_persian_str(iso))

    def value(self):
        # type: () -> str
        """Returns the Jalali string in English digits (YYYY/MM/DD)."""
        return date_utils.to_english_digits(self.line.text().strip())

    def text_persian(self):
        # type: () -> str
        return date_utils.to_persian_digits(self.line.text().strip())

    def iso_value(self):
        # type: () -> Optional[str]
        try:
            return date_utils.jalali_str_to_iso(self.value())
        except ValueError:
            return None

    def set_value(self, jalali_str):
        # type: (Optional[str]) -> None
        if jalali_str:
            self.line.setText(jalali_str)


def _leap_jalali(jy):
    # type: (int) -> bool
    # Delegate to the verified implementation in date_utils.
    return date_utils.is_jalali_leap(jy)


def pick_jalali_date(parent=None, initial=None):
    # type: (Optional[_Widgets.QWidget], Optional[str]) -> Optional[str]
    """Open a modal Jalali date picker dialog. Returns 'YYYY/MM/DD' or None."""
    from ..utils import make_rtl, best_persian_font, error_msg
    dlg = _Widgets.QDialog(parent)
    make_rtl(dlg)
    dlg.setWindowTitle("انتخاب تاریخ شمسی")
    dlg.setLayoutDirection(_Core.Qt.RightToLeft)
    layout = _Widgets.QFormLayout(dlg)
    font = _Gui.QFont(best_persian_font(), 11)

    year_spin = _Widgets.QSpinBox()
    month_spin = _Widgets.QSpinBox()
    day_spin = _Widgets.QSpinBox()
    for w in (year_spin, month_spin, day_spin):
        w.setFont(font)
        w.setAlignment(_Core.Qt.AlignCenter)
    year_spin.setRange(1300, 1500)
    month_spin.setRange(1, 12)
    day_spin.setRange(1, 31)
    year_spin.setValue(1380)
    month_spin.setValue(1)
    day_spin.setValue(1)

    # Set initial.
    if initial:
        tup = date_utils.jalali_str_to_jalali_tuple(initial)
        if tup is not None:
            year_spin.setValue(tup[0])
            month_spin.setValue(tup[1])
            day_spin.setValue(tup[2])

    def validate_days():
        m = month_spin.value()
        if m <= 6:
            day_spin.setMaximum(31)
        elif m <= 11:
            day_spin.setMaximum(30)
        else:
            day_spin.setMaximum(30 if _leap_jalali(year_spin.value()) else 29)
        if day_spin.value() > day_spin.maximum():
            day_spin.setValue(day_spin.maximum())

    month_spin.valueChanged.connect(validate_days)
    year_spin.valueChanged.connect(validate_days)
    validate_days()

    layout.addRow("سال", year_spin)
    layout.addRow("ماه", month_spin)
    layout.addRow("روز", day_spin)

    btns = _Widgets.QDialogButtonBox(
        _Widgets.QDialogButtonBox.Ok | _Widgets.QDialogButtonBox.Cancel)
    ok_btn = btns.button(_Widgets.QDialogButtonBox.Ok)
    cancel_btn = btns.button(_Widgets.QDialogButtonBox.Cancel)
    if ok_btn is not None:
        ok_btn.setText("تأیید")
    if cancel_btn is not None:
        cancel_btn.setText("انصراف")
    btns.accepted.connect(dlg.accept)
    btns.rejected.connect(dlg.reject)
    layout.addRow(btns)

    if dlg.exec_() == _Widgets.QDialog.Accepted:
        try:
            jy = year_spin.value()
            jm = month_spin.value()
            jd = day_spin.value()
            # validate via round-trip gregorian conversion.
            date_utils.jalali_to_gregorian(jy, jm, jd)
            return date_utils.format_jalali(jy, jm, jd)
        except Exception as exc:
            error_msg(parent, "تاریخ نامعتبر: %s" % str(exc))
            return None
    return None
