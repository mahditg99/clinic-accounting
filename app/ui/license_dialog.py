# -*- coding: utf-8 -*-
"""License dialogs: the blocking activation gate and the details viewer.

Both dialogs are RTL Persian and reuse the app theme (``card`` / ``badge`` /
``loginErr`` / button variants) so they read as part of the product rather
than as a Windows error box.
"""
from __future__ import annotations

from typing import Any, Optional

from ..utils import Qt, load_app_fonts
from .. import license as lic
from .. import date_utils
from . import fields as F

_Core = Qt.QtCore
_Gui = Qt.QtGui
_W = Qt.QtWidgets

# Right-to-left mark: forces a QLabel paragraph to RTL so digit-only values
# (dates, day counts) do not drift to the visual left edge.
_RLM = "‏"

_EXTRA_QSS = """
QLineEdit#hwCode { background: #f2f8fb; color: #073d4e; border: 1px solid #b9d3de; }
QLabel#licHint { color: #5d7385; font-size: 12px; }
"""


def _copy_to_clipboard(text):
    # type: (str) -> None
    try:
        _W.QApplication.clipboard().setText(text or "")
    except Exception:
        pass


def _flash(button, label="کپی شد ✓"):
    # type: (Any, str) -> None
    orig = getattr(button, "_orig_text", None)
    if orig is None:
        orig = button.text()
        button._orig_text = orig
    button.setText(label)
    _Core.QTimer.singleShot(1400, lambda: button.setText(orig))


def _jalali(iso):
    # type: (Optional[str]) -> str
    if not iso:
        return "—"
    try:
        return date_utils.iso_to_jalali_persian_str(str(iso)[:10])
    except Exception:
        return str(iso)


def _hw_field(code):
    # type: (str) -> _W.QWidget
    """Big read-only, selectable hardware code + a copy button."""
    box = _W.QWidget()
    h = _W.QHBoxLayout(box)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(8)
    edit = _W.QLineEdit(code or lic.hardware_code())
    edit.setObjectName("hwCode")
    edit.setReadOnly(True)
    edit.setAlignment(_Core.Qt.AlignCenter)
    # The code itself is Latin; keep it LTR so the groups never re-order.
    edit.setLayoutDirection(_Core.Qt.LeftToRight)
    f = edit.font()
    f.setPointSize(15)
    f.setBold(True)
    f.setLetterSpacing(_Gui.QFont.AbsoluteSpacing, 2.0)
    edit.setFont(f)
    edit.setCursorPosition(0)
    btn = _W.QPushButton("کپی")
    btn.setProperty("variant", "outline")
    btn.setProperty("btnsize", "sm")
    btn.setCursor(_Core.Qt.PointingHandCursor)
    btn.clicked.connect(lambda _c=False, e=edit, b=btn: (
        _copy_to_clipboard(e.text()), _flash(b)))
    h.addWidget(edit, 1)
    h.addWidget(btn, 0)
    return box


def _banner(text):
    # type: (str) -> _W.QLabel
    lbl = _W.QLabel(text)
    lbl.setObjectName("loginErr")
    lbl.setWordWrap(True)
    lbl.setAlignment(_Core.Qt.AlignRight | _Core.Qt.AlignVCenter)
    return lbl


def _ok_banner(text):
    # type: (str) -> _W.QLabel
    lbl = _W.QLabel(text)
    lbl.setObjectName("badge")
    lbl.setProperty("role", "success")
    lbl.setWordWrap(True)
    lbl.setAlignment(_Core.Qt.AlignRight | _Core.Qt.AlignVCenter)
    return lbl


def _row(label_text, value_text, mono=False):
    # type: (str, str, bool) -> _W.QWidget
    row = _W.QWidget()
    h = _W.QHBoxLayout(row)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(10)
    lab = _W.QLabel(label_text)
    lab.setProperty("role", "flabel")
    lab.setMinimumWidth(120)
    val = _W.QLabel(value_text)
    val.setWordWrap(True)
    # A wrapped QLabel lays a digits-only string ("۱۴۰۵/۰۶/۱۵") out as an LTR
    # paragraph, so it drifts to the visual LEFT even inside an RTL dialog.
    # A leading RLM pins the paragraph direction to RTL -> hugs the right edge
    # like every other value here.
    val.setText(_RLM + value_text)
    val.setTextInteractionFlags(_Core.Qt.TextSelectableByMouse)
    if mono:
        val.setAlignment(_Core.Qt.AlignRight)
        f = val.font()
        f.setBold(True)
        val.setFont(f)
    h.addWidget(lab, 0)
    h.addWidget(val, 1)
    return row


def _button(text, variant="ghost", handler=None, primary_width=None):
    # type: (str, str, Any, Optional[int]) -> _W.QPushButton
    b = _W.QPushButton(text)
    if primary_width is not None:
        from ..theme import primary
        primary(b, primary_width)
    else:
        b.setProperty("variant", variant)
    b.setProperty("btnsize", "sm")
    b.setCursor(_Core.Qt.PointingHandCursor)
    if handler is not None:
        b.clicked.connect(handler)
    return b


class _Shell(_W.QDialog):
    """Common frame: RTL, Vazirmatn, a white card with a fixed heading and a
    replaceable content layout (``self.body``)."""

    def __init__(self, title, subtitle, parent=None):
        # type: (str, str, Any) -> None
        super().__init__(parent)
        load_app_fonts()
        self.setLayoutDirection(_Core.Qt.RightToLeft)
        self.setWindowTitle(title)
        avail = _W.QApplication.desktop().availableGeometry()
        self.setMinimumWidth(min(620, avail.width() - 80))
        self.resize(min(620, avail.width() - 80), 470)
        try:
            self.setStyleSheet(self.styleSheet() + _EXTRA_QSS)
        except Exception:
            pass

        outer = _W.QVBoxLayout(self)
        outer.setContentsMargins(22, 20, 22, 20)
        card = _W.QFrame()
        card.setObjectName("card")
        cv = _W.QVBoxLayout(card)
        cv.setContentsMargins(26, 22, 26, 22)
        cv.setSpacing(10)
        head = _W.QLabel(title)
        head.setObjectName("sectionTitle")
        sub = _W.QLabel(subtitle)
        sub.setObjectName("sectionSub")
        sub.setWordWrap(True)
        cv.addWidget(head)
        cv.addWidget(sub)
        cv.addSpacing(6)
        self.body = _W.QVBoxLayout()  # cleared/rebuilt by LicenseDetailsDialog
        self.body.setSpacing(10)
        cv.addLayout(self.body)
        outer.addWidget(card, 1)
        self.card = card

    def add_footer(self, buttons):
        # type: (list) -> None
        self.body.addSpacing(4)
        h = _W.QHBoxLayout()
        h.setSpacing(8)
        for b in buttons:
            h.addWidget(b)
        h.addStretch(1)
        self.body.addLayout(h)

    def clear_body(self):
        # type: () -> None
        _clear_layout(self.body)


def _clear_layout(lay):
    # type: (Any) -> None
    while lay.count():
        item = lay.takeAt(0)
        w = item.widget()
        if w is not None:
            w.setParent(None)
            w.deleteLater()
            continue
        sub = item.layout()
        if sub is not None:
            _clear_layout(sub)
            sub.deleteLater()


class ActivationDialog(_Shell):
    """Shown instead of the app when the license is missing/invalid."""

    def __init__(self, status=None, parent=None):
        # type: (Any, Any) -> None
        status = status or lic.verify()
        super().__init__(
            "فعال‌سازی نرم‌افزار",
            "این نسخه از «نبض کلینیک» با لایسنس سخت‌افزاری اجرا می‌شود. "
            "برای ادامه، فایل لایسنسِ همین دستگاه را وارد کنید.")
        self.status = status
        self.final_status = None  # type: Any

        self.banner = _banner(status.message)
        self.body.addWidget(self.banner)

        lab = _W.QLabel("کد سخت‌افزاری این دستگاه")
        lab.setProperty("role", "flabel")
        self.body.addWidget(lab)
        self.body.addWidget(_hw_field(status.hw or lic.hardware_code()))

        hint = _W.QLabel("این کد را برای فروشنده بفرستید (پیامک، واتساپ یا ایمیل) "
                         "تا فایل «license.key» مخصوص همین دستگاه صادر شود؛ سپس همان "
                         "فایل را با دکمهٔ پایین انتخاب کنید.")
        hint.setObjectName("licHint")
        hint.setWordWrap(True)
        self.body.addWidget(hint)

        self.err = _banner("")
        self.err.setVisible(False)
        self.body.addWidget(self.err)

        self.body.addStretch(1)
        self.add_footer([
            _button("انتخاب فایل لایسنس…", handler=self._pick, primary_width=0),
            _button("خروج", handler=self.reject),
        ])
        # Focus the primary action without stealing the tab order.
        for child in self.card.findChildren(_W.QPushButton):
            if child.text().startswith("انتخاب"):
                child.setFocus()
                break

    def _pick(self):
        path, _ = _W.QFileDialog.getOpenFileName(
            self, "فایل لایسنس را انتخاب کنید", lic.license_dir(),
            "فایل لایسنس (license.key *.key *.txt);;همهٔ فایل‌ها (*)")
        if not path:
            return
        st = lic.install_license(path)
        self.status = st
        if st.ok:
            self.final_status = st
            self.accept()
            return
        self.banner.setText(st.message)
        self.err.setText("فایل انتخاب‌شده معتبر نیست: " + path)
        self.err.setVisible(True)


class LicenseDetailsDialog(_Shell):
    """Read-only view of the current license (sidebar footer action)."""

    def __init__(self, parent=None, status=None):
        # type: (Any, Any) -> None
        super().__init__(
            "مجوز نرم‌افزار",
            "اطلاعات لایسنسِ این دستگاه. اگر لایسنس را تمدید یا جایگزین کردید، "
            "از «بارگذاری لایسنس جدید» استفاده کنید.")
        self.status = status or lic.verify()
        self._build(self.status)

    def _build(self, st):
        self.clear_body()
        badge = _W.QLabel("معتبر" if st.ok else "نامعتبر")
        badge.setObjectName("badge")
        badge.setProperty("role", "success" if st.ok else "danger")
        badge.setAlignment(_Core.Qt.AlignCenter)
        self.body.addWidget(badge, 0, _Core.Qt.AlignRight)
        self.body.addWidget(_ok_banner("لایسنس این دستگاه معتبر است.") if st.ok
                            else _banner(st.message))
        p = st.payload or {}
        self.body.addWidget(_row("مشتری", p.get("name") or "—"))
        self.body.addWidget(_row("تاریخ صدور", _jalali(p.get("issued"))))
        if p.get("expires"):
            self.body.addWidget(_row("تاریخ انقضا", _jalali(p.get("expires"))))
            if st.days_left is not None and st.days_left >= 0:
                self.body.addWidget(_row("باقی‌مانده",
                                         "%s روز" % F.fa(st.days_left)))
            elif st.days_left is not None:
                self.body.addWidget(_row("باقی‌مانده", "منقضی شده"))
        else:
            self.body.addWidget(_row("تاریخ انقضا", "بدون محدودیت (دائمی)"))
        lab = _W.QLabel("کد سخت‌افزاری این دستگاه")
        lab.setProperty("role", "flabel")
        self.body.addWidget(lab)
        self.body.addWidget(_hw_field(st.hw or lic.hardware_code()))
        self.body.addStretch(1)
        self.add_footer([
            _button("بارگذاری لایسنس جدید…", handler=self._reload, primary_width=0),
            _button("بستن", handler=self.accept),
        ])

    def _reload(self):
        path, _ = _W.QFileDialog.getOpenFileName(
            self, "فایل لایسنس را انتخاب کنید", lic.license_dir(),
            "فایل لایسنس (license.key *.key *.txt);;همهٔ فایل‌ها (*)")
        if not path:
            return
        st = lic.install_license(path)
        self.status = st
        self._build(st)


def show_license_details(parent=None):
    # type: (Any) -> Any
    dlg = LicenseDetailsDialog(parent)
    dlg.exec_()
    return dlg.status
