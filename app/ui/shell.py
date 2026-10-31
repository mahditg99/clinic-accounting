# -*- coding: utf-8 -*-
"""Application shell — mirrors the web layout (webapp/templates/base.html):

    [ sidebar (right, white) ]  [ ECG ribbon / top bar / content ]

* Sidebar: brand block, icon nav with section captions, version foot.
* Top bar: page title + sub (right), date chip + user box (left).
* Register ribbon: the 12px ECG pulse strip — the design's signature.

Login reproduces the web sign-in screen: deep-teal masthead with the ECG
rule and today's stamp beside a white sign-in card.
"""
from __future__ import annotations

from typing import Dict, Optional

from ..utils import Qt, best_persian_font, load_app_fonts
from .. import settings as settings_mod
from .. import date_utils
from .. import auth_core
from . import fields as F

_Core = Qt.QtCore
_Gui = Qt.QtGui
_W = Qt.QtWidgets

# (key, label, svg-inner) in web order; key "__cap" = section caption.
_IC_DASH = ('<rect x="3" y="3" width="7" height="9" rx="1.5"/>'
            '<rect x="14" y="3" width="7" height="5" rx="1.5"/>'
            '<rect x="14" y="12" width="7" height="9" rx="1.5"/>'
            '<rect x="3" y="16" width="7" height="5" rx="1.5"/>')
_IC_INV = ('<path d="M7 3h10a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2'
           'V5a2 2 0 0 1 2-2Z"/><path d="M9 8h6M9 12h6M9 16h4"/>')
_IC_ARCH = ('<rect x="3" y="4" width="18" height="4" rx="1.5"/>'
            '<path d="M5 8v11a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8M10 12h4"/>')
_IC_PAT = ('<circle cx="9" cy="8" r="3.2"/>'
           '<path d="M3 20c.6-3.4 3-5 6-5s5.4 1.6 6 5"/>'
           '<path d="M16 3.5a3.2 3.2 0 0 1 1 6.2M17.5 15.1c2 .5 3.2 1.9 3.5 4.4"/>')
_IC_PROD = ('<path d="M21 8.2 12 3 3 8.2v7.6L12 21l9-5.2V8.2Z"/>'
            '<path d="M3.3 8.3 12 13.5l8.7-5.2M12 21v-7.5"/>')
_IC_DAY = ('<rect x="3" y="5" width="18" height="16" rx="2"/>'
           '<path d="M8 3v4M16 3v4M3 10h18"/>')
_IC_INC = ('<line x1="3" y1="20" x2="3" y2="15"/><line x1="9" y1="20" x2="9" y2="9"/>'
           '<line x1="15" y1="20" x2="15" y2="12"/><line x1="21" y1="20" x2="21" y2="4"/>')
_IC_EXP = ('<rect x="3" y="6" width="18" height="12" rx="2"/><path d="M7 10h2"/>'
           '<circle cx="16" cy="12" r="2"/><path d="M10 6 7.5 18M14 6l2.5 12"/>')
_IC_FIN = ('<polyline points="4 17 9 11 13 14 20 6"/>'
           '<polyline points="15 6 20 6 20 11"/>')
_IC_DOCR = ('<path d="M12 3a3 3 0 0 0-3 3v2H7a2 2 0 0 0-2 2h2a2 2 0 0 0 2 2h1'
            'm6-6h2a2 2 0 0 0 0 4h-2v2a3 3 0 0 0-3 3"/><path d="M20 21H4"/>'
            '<path d="M9 13a4 4 0 0 0 6 0"/>')
_IC_DOCS = ('<circle cx="12" cy="8" r="3.2"/>'
            '<path d="M12 21V11M8 13H6a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2h1"/>'
            '<path d="M16 13h2a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-1M12 14v7"/>')
_IC_SET = ('<circle cx="12" cy="12" r="3"/>'
           '<path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 '
           '2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 '
           '2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 '
           '0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 '
           '0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 '
           '0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06'
           '.06a1.65 1.65 0 0 0 1.82.33h0a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 '
           '0v.09a1.65 1.65 0 0 0 1 1.51h0a1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 '
           '0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82v0a1.65 1.65 0 0 0 '
           '1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z"/>')

_NAV = [
    ("dashboard", "داشبورد", _IC_DASH),
    ("__cap", "عملیات روزانه", None),
    ("invoice", "فاکتور جدید", _IC_INV),
    ("archive", "آرشیو فاکتورها", _IC_ARCH),
    ("patients", "پرونده‌ها", _IC_PAT),
    ("products", "فهرست محصولات", _IC_PROD),
    ("__cap", "گزارش‌ها", None),
    ("daily", "گزارش روزانه", _IC_DAY),
    ("income_expense", "درآمد / هزینه", _IC_INC),
    ("expenses", "هزینه‌ها", _IC_EXP),
    ("financial", "گزارش‌های مالی", _IC_FIN),
    ("doctor_report", "گزارش پزشکان", _IC_DOCR),
    ("product_sales", "فروش محصولات", _IC_PROD),
    ("__cap", "مدیریت", None),
    ("doctors", "فهرست پزشکان", _IC_DOCS),
    ("settings", "تنظیمات", _IC_SET),
]

# Top-bar titles per page (webapp/templates/*.html block page_title/page_sub).
_PAGE_TITLES = {
    "dashboard": ("داشبورد", "خلاصه وضعیت امروز"),
    "invoice": ("فاکتور جدید", ""),
    "archive": ("آرشیو فاکتورها", "جستجو و مدیریت فاکتورهای ثبت‌شده"),
    "patients": ("پرونده‌های بیماران", "مدیریت پرونده‌های بیماران"),
    "products": ("فهرست محصولات", "مدیریت محصولات و موجودی انبار"),
    "daily": ("گزارش روزانه", ""),
    "income_expense": ("گزارش درآمد / هزینه", ""),
    "expenses": ("مدیریت هزینه‌ها", ""),
    "financial": ("گزارش مالی دوره",
                  "خلاصه مالی ماهانه یا سالانه: دریافتی، هزینه و سود خالص"),
    "doctor_report": ("گزارش پزشکان", ""),
    "product_sales": ("گزارش فروش محصولات", ""),
    "doctors": ("پزشکان", "مدیریت پزشکان معرف"),
    "settings": ("تنظیمات", ""),
}

_NAV_TEXT = "#52707f"
_NAV_ACTIVE = "#073d4e"

_EXTRA_QSS = """
QWidget#sideCol {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ffffff, stop:1 #f7fafb);
    border: none;
    border-left: 1px solid #dbe4ea;
}
QPushButton[btnsize="sm"] {
    padding: 5px 11px;
    font-size: 12px;
    border-radius: 7px;
    min-height: 0px;
}
QListWidget#sideNav::item { height: 40px; }
"""


def _svg_icon(inner, color, px=19):
    # type: (str, str, int) -> Optional[Qt.QtGui.QPixmap]
    """Rasterize one of the web's inline SVG icons at `px` logical pixels."""
    if not inner or Qt.QtSvg is None:
        return None
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
           'fill="none" stroke="%s" stroke-width="1.7" stroke-linecap="round" '
           'stroke-linejoin="round">%s</svg>' % (color, inner))
    try:
        renderer = Qt.QtSvg.QSvgRenderer(bytearray(svg.encode("utf-8")))
        if not renderer.isValid():
            return None
        pm = _Gui.QPixmap(px * 2, px * 2)
        pm.setDevicePixelRatio(2.0)
        pm.fill(_Core.Qt.transparent)
        painter = _Gui.QPainter(pm)
        # CRITICAL: pass the target rect in *logical* px. Without it,
        # QSvgRenderer uses the canvas' physical size (px*2) as the logical
        # rect, and the DPR-2 painter scales that again -> the icon paints at
        # 2x and only its top-left corner stays inside the pixmap (the
        # "icons are huge / clipped" bug on every screen & resolution).
        renderer.render(painter, _Core.QRectF(0, 0, px, px))
        painter.end()
        return pm
    except Exception:
        return None


def _nav_icon(inner):
    # type: (str) -> Optional[Qt.QtGui.QIcon]
    pm_n = _svg_icon(inner, _NAV_TEXT)
    if pm_n is None:
        return None
    icon = _Gui.QIcon()
    icon.addPixmap(pm_n, _Gui.QIcon.Normal)
    pm_s = _svg_icon(inner, _NAV_ACTIVE)
    if pm_s is not None:
        icon.addPixmap(pm_s, _Gui.QIcon.Selected)
    return icon


class LoginDialog(_W.QDialog):
    """Modal login — mirrors the web sign-in (masthead + white card)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        load_app_fonts()
        self.setLayoutDirection(_Core.Qt.RightToLeft)
        self.setObjectName("loginDlg")
        self.setWindowTitle("ورود به سامانه")
        _avail = _W.QApplication.desktop().availableGeometry()
        self.setFixedSize(min(780, _avail.width() - 12),
                          min(460, _avail.height() - 12))

        outer = _W.QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ---- masthead (right, deep teal) ----
        mast = _W.QWidget()
        mast.setObjectName("loginMast")
        mv = _W.QVBoxLayout(mast)
        mv.setContentsMargins(40, 40, 28, 40)
        mv.setSpacing(0)
        eyebrow = _W.QLabel("سیستم حسابداری کلینیک")
        eyebrow.setObjectName("lmEyebrow")
        title = _W.QLabel(settings_mod.get_setting("app_title", "آذران طب"))
        title.setObjectName("lmTitle")
        rule = F.EcgTrace(variant="rule", height=26)
        rule.setMinimumWidth(280)
        stamp = _W.QFrame()
        stamp.setObjectName("lmStamp")
        sv = _W.QVBoxLayout(stamp)
        sv.setContentsMargins(20, 12, 20, 12)
        sv.setSpacing(3)
        slbl = _W.QLabel("امروز")
        slbl.setObjectName("lmStampLbl")
        sdate = _W.QLabel(date_utils.iso_to_jalali_persian_str(
            date_utils.today_iso()))
        sdate.setObjectName("lmStampDate")
        sv.addWidget(slbl)
        sv.addWidget(sdate)
        mv.addWidget(eyebrow)
        mv.addSpacing(10)
        mv.addWidget(title)
        mv.addSpacing(22)
        mv.addWidget(rule)
        mv.addSpacing(24)
        mv.addWidget(stamp, 0, _Core.Qt.AlignRight)
        mv.addStretch(1)
        outer.addWidget(mast, 12)

        # ---- sign-in card (left, white) ----
        card_box = _W.QWidget()
        cb = _W.QVBoxLayout(card_box)
        cb.setContentsMargins(0, 32, 32, 32)
        card = _W.QFrame()
        card.setObjectName("loginCard")
        cv = _W.QVBoxLayout(card)
        cv.setContentsMargins(30, 28, 30, 26)
        cv.setSpacing(8)
        h1 = _W.QLabel("ورود به سامانه")
        h1.setObjectName("loginTitle")
        h1.setAlignment(_Core.Qt.AlignCenter)
        sub = _W.QLabel("برای ادامه، وارد حساب کاربری خود شوید")
        sub.setObjectName("loginSub")
        sub.setAlignment(_Core.Qt.AlignCenter)
        cv.addWidget(h1)
        cv.addWidget(sub)
        cv.addSpacing(10)
        self.user = F.FaLineEdit(placeholder="نام کاربری")
        self.pw = _W.QLineEdit()
        self.pw.setEchoMode(_W.QLineEdit.Password)
        self.pw.setPlaceholderText("رمز عبور")
        self.pw.setLayoutDirection(_Core.Qt.RightToLeft)
        self.err = _W.QLabel("")
        self.err.setObjectName("loginErr")
        self.err.setAlignment(_Core.Qt.AlignCenter)
        self.err.setVisible(False)
        btn = _W.QPushButton("ورود به دفتر")
        from ..theme import primary
        primary(btn, 0)
        btn.setProperty("btnsize", "sm")
        btn.clicked.connect(self.try_login)
        self.pw.returnPressed.connect(self.try_login)
        lab1 = _W.QLabel("نام کاربری")
        lab1.setProperty("role", "flabel")
        lab2 = _W.QLabel("رمز عبور")
        lab2.setProperty("role", "flabel")
        cv.addWidget(lab1)
        cv.addWidget(self.user)
        cv.addSpacing(4)
        cv.addWidget(lab2)
        cv.addWidget(self.pw)
        cv.addSpacing(6)
        cv.addWidget(self.err)
        cv.addWidget(btn)
        foot = _W.QLabel("نسخه دسکتاپ — آذران طب")
        foot.setObjectName("loginSub")
        foot.setAlignment(_Core.Qt.AlignCenter)
        cv.addSpacing(8)
        cv.addWidget(foot)
        cb.addWidget(card, 0, _Core.Qt.AlignVCenter)
        outer.addWidget(card_box, 9)

        self.user.setFocus()

    def try_login(self):
        auth_core.ensure_admin()
        if auth_core.verify_user(self.user.value().strip(), self.pw.text()):
            self.accept()
        else:
            self.err.setText("نام کاربری یا رمز عبور اشتباه است.")
            self.err.setVisible(True)


class ChangePasswordDialog(_W.QDialog):
    def __init__(self, parent=None, forced=False):
        super().__init__(parent)
        self.setLayoutDirection(_Core.Qt.RightToLeft)
        self.setWindowTitle("تغییر رمز پیش‌فرض" if forced else "تغییر رمز")
        self.setFixedWidth(380)
        from ..theme import card, primary
        box = _W.QWidget()
        v = _W.QVBoxLayout(box)
        v.setSpacing(8)
        if forced:
            note = _W.QLabel("رمز عبور هنوز همان رمز پیش‌فرض (admin) است. "
                             "برای حفاظت از اطلاعات بیماران، پیش از ورود "
                             "یک رمز تازه انتخاب کنید.")
            note.setWordWrap(True)
            note.setStyleSheet("color:#b06a00; font-weight:600;")
            v.addWidget(note)
        v.addWidget(_W.QLabel("رمز فعلی:"))
        self.cur = _W.QLineEdit(); self.cur.setEchoMode(_W.QLineEdit.Password)
        v.addWidget(self.cur)
        v.addWidget(_W.QLabel("رمز جدید (حداقل ۴ کاراکتر):"))
        self.new1 = _W.QLineEdit(); self.new1.setEchoMode(_W.QLineEdit.Password)
        v.addWidget(self.new1)
        v.addWidget(_W.QLabel("تکرار رمز جدید:"))
        self.new2 = _W.QLineEdit(); self.new2.setEchoMode(_W.QLineEdit.Password)
        v.addWidget(self.new2)
        self.err = _W.QLabel("")
        self.err.setStyleSheet("color:#c03b4a; font-size:11px;")
        v.addWidget(self.err)
        row = _W.QHBoxLayout()
        ok = primary(_W.QPushButton("ذخیره"), 100)
        cancel = _W.QPushButton("خروج از برنامه" if forced else "انصراف")
        ok.clicked.connect(self.save)
        cancel.clicked.connect(self.reject)
        row.addWidget(ok); row.addWidget(cancel)
        v.addLayout(row)
        outer = _W.QVBoxLayout(self)
        outer.addWidget(card(box))

    def save(self):
        if self.new1.text() != self.new2.text():
            self.err.setText("رمز جدید و تکرار آن یکسان نیستند.")
            return
        if self.new1.text() == "admin":
            self.err.setText("رمز پیش‌فرض را دوباره انتخاب نکنید.")
            return
        try:
            auth_core.change_password(self.cur.text(), self.new1.text())
        except ValueError as exc:
            self.err.setText(str(exc))
            return
        self.accept()


def _uses_default_password():
    # type: () -> bool
    stored = settings_mod.get_setting("admin_pass_hash") or ""
    return bool(stored) and auth_core.verify_password("admin", stored)


def _require_new_password(parent=None):
    # type: (Optional[_W.QWidget]) -> bool
    """Force a real password while the stock admin/admin is in place.
    False = the user declined (the app does not open)."""
    if not _uses_default_password():
        return True
    dlg = ChangePasswordDialog(parent, forced=True)
    dlg.cur.setText("admin")
    return dlg.exec_() == _W.QDialog.Accepted


class AppWindow(_W.QMainWindow):
    """Main window: white sidebar (right) + ribbon/topbar + stacked pages."""

    def __init__(self, username="admin"):
        super().__init__(None)
        self.username = username
        load_app_fonts()
        _app = _W.QApplication.instance()
        if _app is not None and "sideCol" not in _app.styleSheet():
            _apply_extra_qss(_app)
        self.setLayoutDirection(_Core.Qt.RightToLeft)
        _f = _Gui.QFont(best_persian_font())
        _f.setPixelSize(14)  # same rhythm as apply_app_font / the web's 14px
        self.setFont(_f)
        # Fit to the screen so small laptop panels (1366x768…) never push the
        # bottom of the window off-screen.
        _avail = _W.QApplication.desktop().availableGeometry(self)
        self.resize(min(1300, _avail.width() - 12),
                    min(850, _avail.height() - 12))
        self._update_title()

        central = _W.QWidget()
        self.setCentralWidget(central)
        root = _W.QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---------------- sidebar (right in RTL) ----------------
        side = _W.QWidget()
        side.setObjectName("sideCol")
        side.setFixedWidth(236)
        sv = _W.QVBoxLayout(side)
        sv.setContentsMargins(0, 0, 0, 0)
        sv.setSpacing(0)
        app_title = settings_mod.get_setting("app_title", "آذران طب")
        brand_box = _W.QWidget()
        brand_box.setObjectName("sideBrand")
        bv = _W.QVBoxLayout(brand_box)
        bv.setContentsMargins(16, 20, 16, 18)
        bv.setSpacing(2)
        self._brand_lbl = _W.QLabel(app_title)
        self._brand_lbl.setObjectName("brand")
        brand_sub = _W.QLabel("سیستم حسابداری کلینیک")
        brand_sub.setObjectName("brandSub")
        bv.addWidget(self._brand_lbl)
        bv.addWidget(brand_sub)
        sv.addWidget(brand_box)

        self.sidebar = _W.QListWidget()
        self.sidebar.setObjectName("sideNav")
        self.sidebar.setLayoutDirection(_Core.Qt.RightToLeft)
        self.sidebar.setFrameShape(_W.QFrame.NoFrame)
        # On short laptop panels (768px) the 16 nav rows must stay reachable:
        # scroll when needed instead of clipping the bottom items.
        self.sidebar.setVerticalScrollBarPolicy(_Core.Qt.ScrollBarAsNeeded)
        self.sidebar.setHorizontalScrollBarPolicy(_Core.Qt.ScrollBarAlwaysOff)
        self.sidebar.setFocusPolicy(_Core.Qt.NoFocus)
        self.sidebar.setIconSize(_Core.QSize(19, 19))
        self._keys = []
        for key, label, inner in _NAV:
            it = _W.QListWidgetItem(label)
            if key == "__cap":
                it.setFlags(_Core.Qt.NoItemFlags)
            else:
                self._keys.append(key)
                icon = _nav_icon(inner)
                if icon is not None:
                    it.setIcon(icon)
            it.setSizeHint(_Core.QSize(0, 40))
            self.sidebar.addItem(it)
        self.sidebar.currentRowChanged.connect(self._on_nav)
        sv.addWidget(self.sidebar, 1)

        foot = _W.QWidget()
        foot.setObjectName("sideFoot")
        fv = _W.QVBoxLayout(foot)
        fv.setContentsMargins(14, 6, 14, 0)
        fv.setSpacing(0)
        self._lic_btn = _W.QPushButton("مجوز نرم‌افزار")
        self._lic_btn.setProperty("variant", "link")
        self._lic_btn.setProperty("btnsize", "xs")
        self._lic_btn.setCursor(_Core.Qt.PointingHandCursor)
        self._lic_btn.clicked.connect(self.show_license)
        fv.addWidget(self._lic_btn, 0, _Core.Qt.AlignRight)
        self._version_lbl = _W.QLabel()
        self._version_lbl.setObjectName("versionFoot")
        self._update_version_foot()
        fv.addWidget(self._version_lbl)
        sv.addWidget(foot)
        root.addWidget(side)

        # ---------------- main column ----------------
        main_col = _W.QWidget()
        mc = _W.QVBoxLayout(main_col)
        mc.setContentsMargins(0, 0, 0, 0)
        mc.setSpacing(0)
        mc.addWidget(F.EcgRibbon())
        mc.addWidget(self._build_top_bar())

        self.stack = _W.QStackedWidget()
        self.pages = {}  # type: Dict[str, _W.QWidget]
        self._build_pages()
        host = _W.QWidget()
        hl = _W.QVBoxLayout(host)
        hl.setContentsMargins(26, 24, 26, 40)
        hl.addWidget(self.stack)
        mc.addWidget(host, 1)
        root.addWidget(main_col, 1)

        self.goto("dashboard")

    # ------------------------------------------------------------------ #
    def _build_top_bar(self):
        bar = _W.QFrame()
        bar.setObjectName("topBar")
        lay = _W.QHBoxLayout(bar)
        lay.setContentsMargins(26, 12, 26, 12)
        lay.setSpacing(12)
        tbox = _W.QWidget()
        tv = _W.QVBoxLayout(tbox)
        tv.setContentsMargins(0, 0, 0, 0)
        tv.setSpacing(1)
        self._page_title_lbl = _W.QLabel("")
        self._page_title_lbl.setObjectName("pageTitle")
        self._page_sub_lbl = _W.QLabel("")
        self._page_sub_lbl.setObjectName("pageSub")
        tv.addWidget(self._page_title_lbl)
        tv.addWidget(self._page_sub_lbl)
        lay.addWidget(tbox)
        lay.addStretch(1)
        chip = _W.QLabel(date_utils.iso_to_jalali_persian_str(
            date_utils.today_iso()))
        chip.setObjectName("dateChip")
        lay.addWidget(chip)
        user_lbl = _W.QLabel(self.username)
        user_lbl.setObjectName("userName")
        lay.addWidget(user_lbl)
        b_pw = _W.QPushButton("تغییر رمز")
        b_pw.setProperty("variant", "ghost")
        b_pw.setProperty("btnsize", "sm")
        b_pw.setCursor(_Core.Qt.PointingHandCursor)
        b_pw.clicked.connect(self._change_password)
        lay.addWidget(b_pw)
        b_out = _W.QPushButton("خروج")
        b_out.setProperty("variant", "ghost")
        b_out.setProperty("btnsize", "sm")
        b_out.setCursor(_Core.Qt.PointingHandCursor)
        b_out.clicked.connect(self.logout)
        lay.addWidget(b_out)
        bar.setFixedHeight(57)
        return bar

    def _build_pages(self):
        from .dashboard_page import DashboardPage
        from .invoice_page import InvoicePage
        from .archive_page import ArchivePage
        from .patients_page import PatientsPage
        from .products_page import ProductsPage
        from .daily_report_page import DailyReportPage
        from .income_expense_page import IncomeExpensePage
        from .expenses_page import ExpensesPage
        from .financial_reports_page import FinancialReportsPage
        from .doctor_report_page import DoctorReportPage
        from .product_sales_page import ProductSalesPage
        from .doctors_page import DoctorsPage
        from .settings_page import SettingsPage

        makers = [
            ("dashboard", DashboardPage),
            ("invoice", InvoicePage),
            ("archive", ArchivePage),
            ("patients", PatientsPage),
            ("products", ProductsPage),
            ("daily", DailyReportPage),
            ("income_expense", IncomeExpensePage),
            ("expenses", ExpensesPage),
            ("financial", FinancialReportsPage),
            ("doctor_report", DoctorReportPage),
            ("product_sales", ProductSalesPage),
            ("doctors", DoctorsPage),
            ("settings", SettingsPage),
        ]
        for key, cls in makers:
            w = cls(self)
            self.pages[key] = w
            self.stack.addWidget(w)

    # ------------------------------------------------------------------ #
    # Navigation
    # ------------------------------------------------------------------ #
    def _nav_index(self, row):
        """Map sidebar row -> index into self._keys (captions excluded)."""
        n = -1
        for i in range(row + 1):
            if self.sidebar.item(i).flags():
                n += 1
        return n

    def _row_for_key(self, key):
        try:
            want = self._keys.index(key)
        except ValueError:
            return -1
        n = -1
        for i in range(self.sidebar.count()):
            if self.sidebar.item(i).flags():
                n += 1
                if n == want:
                    return i
        return -1

    def _on_nav(self, row):
        it = self.sidebar.item(row)
        if it is None or not it.flags():
            return
        idx = self._nav_index(row)
        if 0 <= idx < len(self._keys):
            key = self._keys[idx]
            self.stack.setCurrentWidget(self.pages[key])
            self.set_page_title(*_PAGE_TITLES.get(key, ("", "")))
            self._on_page_shown(key)

    def _on_page_shown(self, key):
        page = self.pages.get(key)
        refresh = getattr(page, "refresh", None)
        if callable(refresh):
            try:
                refresh()
            except Exception:
                # Report it (errors.log + message) instead of leaving a
                # silently stale/blank page.
                import sys
                sys.excepthook(*sys.exc_info())

    def goto(self, key):
        row = self._row_for_key(key)
        if row >= 0:
            self.sidebar.setCurrentRow(row)

    def set_page_title(self, title, subtitle=""):
        """Top-bar heading; pages call this for dynamic titles (edit modes)."""
        self._page_title_lbl.setText(title or "")
        self._page_sub_lbl.setText(subtitle or "")
        self._page_sub_lbl.setVisible(bool(subtitle))

    # ------------------------------------------------------------------ #
    # Cross-page coordination
    # ------------------------------------------------------------------ #
    def show_invoice_edit(self, invoice_id):
        self.goto("invoice")
        self.pages["invoice"].load_invoice_for_edit(invoice_id)

    def _change_password(self):
        dlg = ChangePasswordDialog(self)
        dlg.exec_()

    def show_license(self):
        """Open the license viewer (hardware code, expiry, reload)."""
        from .license_dialog import show_license_details
        show_license_details(self)

    def logout(self):
        from ..utils import confirm_msg
        if confirm_msg(self, "خارج می‌شوید؟"):
            self.hide()
            dlg = LoginDialog()
            if dlg.exec_() == _W.QDialog.Accepted and                     _require_new_password():
                self.username = dlg.user.value().strip() or "admin"
                self._update_title()
                self.show()
            else:
                self.close()

    def _update_title(self):
        app_title = settings_mod.get_setting("app_title", "آذران طب")
        self.setWindowTitle("نرم‌افزار حسابداری کلینیک - %s" % app_title)

    def _update_version_foot(self):
        ver = settings_mod.get_setting("version", "")
        self._version_lbl.setText(("نسخه " + F.fa(ver)) if ver else "نسخه ۲.۰")

    def refresh_brand(self):
        """Re-read app_title/version settings (called from the settings page)."""
        app_title = settings_mod.get_setting("app_title", "آذران طب")
        if getattr(self, "_brand_lbl", None) is not None:
            self._brand_lbl.setText(app_title)
        self._update_title()
        self._update_version_foot()


def _apply_extra_qss(app):
    qss = app.styleSheet()
    app.setStyleSheet(qss + _EXTRA_QSS)


def run_desktop():
    """Login + main window bootstrap used by main.py."""
    load_app_fonts()
    auth_core.ensure_admin()
    dlg = LoginDialog()
    if dlg.exec_() != _W.QDialog.Accepted:
        return None
    if not _require_new_password():
        return None
    win = AppWindow(username=dlg.user.value().strip() or "admin")
    win.show()
    _license_expiry_notice(win)
    return win


def _license_expiry_notice(win):
    """One-shot, non-blocking reminder when the license is close to expiring."""
    from .. import license as lic_mod
    try:
        status = lic_mod.last_status() or lic_mod.verify()
        if not lic_mod.warns_of_expiry(status):
            return

        def _show():
            box = _W.QMessageBox(win)
            box.setWindowTitle("مهلت لایسنس")
            box.setIcon(_W.QMessageBox.Warning)
            box.setLayoutDirection(_Core.Qt.RightToLeft)
            box.setText("لایسنس این نرم‌افزار %s روز دیگر منقضی می‌شود."
                        % F.fa(status.days_left))
            box.setInformativeText(
                "برای تمدید با فروشنده تماس بگیرید؛ فایل جدید را می‌توانید از "
                "«مجوز نرم‌افزار» بارگذاری کنید.")
            box.addButton("باشه", _W.QMessageBox.AcceptRole)
            box.exec_()

        _Core.QTimer.singleShot(700, _show)
    except Exception:
        pass
