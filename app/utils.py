# -*- coding: utf-8 -*-
"""Shared UI helpers + Qt-binding detection (PySide2 preferred, PyQt5 fallback).

Importing :mod:`app.utils` exposes a single module ``Qt`` that aliases the
rest of the application to the available binding. Use ``Qt.QtCore``,
``Qt.QtGui``, ``Qt.QtWidgets``, ``Qt.QtPrintSupport`` consistently.
"""
from __future__ import annotations

import os
import types
from typing import Any

Qt = types.ModuleType("Qt")  # type: ignore

_BINDING = None  # type: Any

try:
    from PySide2 import QtCore, QtGui, QtWidgets  # type: ignore
    from PySide2 import QtPrintSupport  # type: ignore
    _BINDING = "PySide2"
    Qt.QtCore = QtCore
    Qt.QtGui = QtGui
    Qt.QtWidgets = QtWidgets
    Qt.QtPrintSupport = QtPrintSupport
except Exception:  # pragma: no cover - fallback path
    try:
        from PyQt5 import QtCore, QtGui, QtWidgets  # type: ignore
        from PyQt5 import QtPrintSupport  # type: ignore
        _BINDING = "PyQt5"
        # Provide PyQt5 objects under a PySide2-style API.
        Qt.QtCore = QtCore
        Qt.QtGui = QtGui
        Qt.QtWidgets = QtWidgets
        Qt.QtPrintSupport = QtPrintSupport
        # Align a couple of signal/slot naming quirks.
        QtCore.Signal = QtCore.pyqtSignal  # type: ignore[attr-defined]
        QtCore.Slot = QtCore.pyqtSlot  # type: ignore[attr-defined]
        QtCore.Property = QtCore.pyqtProperty  # type: ignore[attr-defined]
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "نمی‌توان PySide2 یا PyQt5 را بارگذاری کرد. "
            "لطفاً یکی از آن‌ها را نصب کنید: pip install PySide2"
        ) from exc

try:  # optional: used for the sidebar's SVG nav icons
    from PySide2 import QtSvg  # type: ignore
    Qt.QtSvg = QtSvg
except Exception:
    try:
        from PyQt5 import QtSvg  # type: ignore
        Qt.QtSvg = QtSvg
    except Exception:
        Qt.QtSvg = None


def binding_name():
    # type: () -> str
    return _BINDING  # type: ignore[return-value]


# --------------------------------------------------------------------------- #
# Bundled resources (fonts) — works in dev and in a PyInstaller onedir exe.
# --------------------------------------------------------------------------- #

def resource_path(rel):
    # type: (str) -> str
    """Absolute path to a file bundled relative to the project root (dev) or
    the PyInstaller extraction dir (frozen)."""
    import os
    import sys as _sys
    if getattr(_sys, "frozen", False):
        base = getattr(_sys, "_MEIPASS",
                       os.path.dirname(os.path.abspath(_sys.executable)))
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *rel.split("/"))


# --------------------------------------------------------------------------- #
# Display scaling (fixes clipped text/icons on 125% / 150% Windows screens)
# --------------------------------------------------------------------------- #

def system_scale_factor():
    # type: () -> float
    """Windows system DPI as a scale factor (1.0 at 96 DPI, 1.25 at 120...)."""
    if os.name != "nt":
        return 1.0
    try:
        import ctypes
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
        hdc = ctypes.windll.user32.GetDC(0)
        dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)  # LOGPIXELSX
        ctypes.windll.user32.ReleaseDC(0, hdc)
        if dpi and dpi > 96:
            return round(dpi / 96.0, 4)
    except Exception:
        pass
    return 1.0


def setup_scaling():
    # type: () -> float
    """Uniform fractional high-DPI scaling — call BEFORE QApplication exists.

    Qt 5.15's AA_EnableHighDpiScaling rounds the auto factor to an integer,
    so on a 125% laptop fixed-px layouts stay at 100% while point-size fonts
    grow with the system DPI -> oversized clipped text/icons. Instead we pin
    the font DPI to 96 (so px and pt share one rhythm, exactly like the web
    UI) and scale *everything* uniformly with QT_SCALE_FACTOR = dpi/96.
    Returns the factor applied (1.0 on a standard 96-DPI screen).
    """
    factor = system_scale_factor()
    if not os.environ.get("QT_SCALE_FACTOR") and factor > 1.0:
        os.environ["QT_SCALE_FACTOR"] = repr(factor)
    os.environ.setdefault("QT_FONT_DPI", "96")
    try:
        Qt.QtCore.QCoreApplication.setAttribute(
            Qt.QtCore.Qt.AA_UseHighDpiPixmaps, True)
    except Exception:
        pass
    return float(os.environ.get("QT_SCALE_FACTOR", "1.0"))


# Font selection. The web UI ships Vazirmatn (self-hosted woff2); we load the
# very same file at startup so both interfaces render with the same face.
# Tahoma remains the safe fallback on machines where the load fails.
_PERSIAN_FONT_STACK = ["Vazirmatn", "Vazir", "IRANSans", "Tahoma", "Segoe UI",
                       "Arial"]

_FONTS_LOADED = False


def load_app_fonts():
    # type: () -> bool
    """Register the bundled Vazirmatn with Qt (idempotent).

    The web ships a woff2; Qt 5.15's FreeType cannot decode that container,
    so we bundle a plain-converted TTF (same variable outlines) and load it
    first. The woff2 stays as a forward-compatible fallback.
    """
    global _FONTS_LOADED
    if _FONTS_LOADED:
        return True
    _FONTS_LOADED = True
    for rel in ("app/resources/fonts/Vazirmatn.ttf",
                "webapp/static/fonts/Vazirmatn-var.woff2"):
        path = resource_path(rel)
        if not os.path.exists(path):
            continue
        try:
            ident = QtGui.QFontDatabase.addApplicationFont(path)
        except Exception:
            continue
        if ident >= 0 and QtGui.QFontDatabase.applicationFontFamilies(ident):
            return True
    return False


def best_persian_font():
    # type: () -> str
    from .database import get_connection  # local import to avoid cycles
    app = QtWidgets.QApplication.instance()
    if app is not None:
        fdb = QtGui.QFontDatabase()
        available = set(fdb.families())
        for fam in _PERSIAN_FONT_STACK:
            # QFontDatabase returns lowercased comparisons otherwise.
            for have in available:
                if have.lower() == fam.lower():
                    return have
    return "Tahoma"


def apply_app_font(size=10):
    # type: (int) -> None
    app = QtWidgets.QApplication.instance()
    if app is None:
        return
    fam = best_persian_font()
    f = QtGui.QFont(fam, size)
    # The web UI's base size is 14px; match it regardless of system DPI font
    # settings so both interfaces share the same rhythm.
    f.setPixelSize(14)
    app.setFont(f)


def make_rtl(widget):
    # type: (Any) -> None
    widget.setLayoutDirection(QtCore.Qt.RightToLeft)


def heading_label(text):
    # type: (str) -> QtWidgets.QLabel
    lbl = QtWidgets.QLabel(text)
    lbl.setStyleSheet(
        "QLabel{font-weight:bold; font-size:13px; padding:4px;}")
    make_rtl(lbl)
    lbl.setAlignment(QtCore.Qt.AlignCenter)
    return lbl


def money_label(value):
    # type: (int) -> QtWidgets.QLabel
    from .money_utils import format_money_persian
    lbl = QtWidgets.QLabel(format_money_persian(value))
    make_rtl(lbl)
    lbl.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
    lbl.setFont(QtGui.QFont(best_persian_font(), 11))
    return lbl


def info_msg(parent, text, title="اطلاع"):  # noqa
    # type: (Any, str, str) -> None
    box = QtWidgets.QMessageBox(parent)
    make_rtl(box)
    box.setIcon(QtWidgets.QMessageBox.Information)
    box.setWindowTitle("اطلاع")
    box.setText(text)
    box.exec_()


def warning_msg(parent, text, title="هشدار"):  # noqa
    # type: (Any, str, str) -> None
    box = QtWidgets.QMessageBox(parent)
    make_rtl(box)
    box.setIcon(QtWidgets.QMessageBox.Warning)
    box.setWindowTitle("هشدار")
    box.setText(text)
    box.exec_()


def error_msg(parent, text, title="خطا"):  # noqa
    # type: (Any, str, str) -> None
    box = QtWidgets.QMessageBox(parent)
    make_rtl(box)
    box.setIcon(QtWidgets.QMessageBox.Critical)
    box.setWindowTitle("خطا")
    box.setText(text)
    box.exec_()


def confirm_msg(parent, text, title="تأیید"):  # noqa
    # type: (Any, str, str) -> bool
    box = QtWidgets.QMessageBox(parent)
    make_rtl(box)
    box.setIcon(QtWidgets.QMessageBox.Question)
    box.setWindowTitle("تأیید")
    box.setText(text)
    box.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
    box.setDefaultButton(QtWidgets.QMessageBox.No)
    # Translate button labels to Persian.
    yes_btn = box.button(QtWidgets.QMessageBox.Yes)
    no_btn = box.button(QtWidgets.QMessageBox.No)
    if yes_btn is not None:
        yes_btn.setText("بله")
    if no_btn is not None:
        no_btn.setText("خیر")
    return box.exec_() == QtWidgets.QMessageBox.Yes


def yes_no_dialog(parent, text):
    # type: (Any, str) -> bool
    return confirm_msg(parent, text)


def money_edit_validator():
    # type: () -> QtGui.QRegExpValidator
    # Allow optional leading sign + digits (no decimals) - Persian digits handled at parse.
    rx = QtCore.QRegExp("^[0-9۰-۹]*$")
    return QtGui.QRegExpValidator(rx)


def int_validator(min_value=0, max_value=999999999):
    # type: (int, int) -> QtGui.QIntValidator
    v = QtGui.QIntValidator(min_value, max_value)
    return v


def make_money_lineedit():
    # type: () -> QtWidgets.QLineEdit
    le = QtWidgets.QLineEdit()
    le.setAlignment(QtCore.Qt.AlignRight)
    le.setValidator(money_edit_validator())
    make_rtl(le)
    return le


def make_qty_lineedit():
    # type: () -> QtWidgets.QLineEdit
    le = QtWidgets.QLineEdit()
    le.setAlignment(QtCore.Qt.AlignRight)
    le.setValidator(QtGui.QIntValidator(1, 999999999))
    make_rtl(le)
    return le


def table_count_label(text):
    # type: (str) -> QtWidgets.QLabel
    lbl = QtWidgets.QLabel(text)
    make_rtl(lbl)
    lbl.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
    lbl.setStyleSheet("QLabel{color:#555; padding:2px 6px;}")
    lbl.setFont(QtGui.QFont(best_persian_font(), 10))
    return lbl
