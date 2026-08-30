# -*- coding: utf-8 -*-
"""Design system for Azaran Teb desktop — mirrors webapp/static/style.css.

The web UI ("نبض کلینیک" / Clinic Pulse) is the source of truth: a clinical
mist canvas (#eef3f7), white chart-paper cards, chart-navy ink (#0f2433), a
calm cerulean-teal primary (#0d6e8c) and a single signature accent — ECG
pulse red (#e24c5a) — on card-title ticks, the register ribbon and "today".

The QSS below reproduces the web tokens 1:1 so the desktop app reads as the
same product. Builder helpers set the objectName / dynamic properties that
the stylesheet targets.
"""
from __future__ import annotations

from typing import Any, List, Optional

from .utils import Qt

_Widgets = Qt.QtWidgets
_Core = Qt.QtCore


# --------------------------------------------------------------------------- #
# Palette (identical to the web :root custom properties)
# --------------------------------------------------------------------------- #
CANVAS = "#eef3f7"
SURFACE = "#ffffff"
SURFACE2 = "#f4f8fa"
INK = "#0f2433"
INK_SOFT = "#31485a"
MUTED = "#5d7385"
LINE = "#dbe4ea"
LINE_STRONG = "#c6d3dc"
RULE = "#b3c4cf"

PRIMARY = "#0d6e8c"
PRIMARY_DARK = "#095469"
PRIMARY_DEEP = "#073d4e"
PRIMARY_TINT = "#e2f1f6"
PRIMARY_SOFT = "#c4e0ea"

PULSE = "#e24c5a"
PULSE_DARK = "#c23444"
PULSE_TINT = "#fdedee"

SUCCESS = "#2e8b6a"
SUCCESS_TINT = "#e4f3ec"
DANGER = "#c03b4a"
DANGER_TINT = "#fbe9eb"
WARN = "#b97a1c"
WARN_TINT = "#fbf1dd"
INFO = "#3a6b86"
INFO_TINT = "#e5eef3"

# stat-tile / sum-card role -> (rule-or-bg, border, value color)
_TONES = {
    "info": (INFO_TINT, "#c5d9e3", INFO),
    "success": (SUCCESS_TINT, "#bfe0d1", SUCCESS),
    "danger": (DANGER_TINT, "#f0c6cb", DANGER),
    "warn": (WARN_TINT, "#ecd5a8", WARN),
    "warning": (WARN_TINT, "#ecd5a8", WARN),
    "accent": (PRIMARY_TINT, PRIMARY_SOFT, PRIMARY),
    "positive": (SUCCESS_TINT, "#bfe0d1", SUCCESS),
    "negative": (DANGER_TINT, "#f0c6cb", DANGER),
}
# stat tiles: the 3px top rule carries the role color; the value stays ink.
_RULES = {
    "info": INFO,
    "success": SUCCESS,
    "positive": SUCCESS,
    "danger": DANGER,
    "negative": DANGER,
    "warn": WARN,
    "warning": WARN,
    "accent": PRIMARY,
}


def _tone(role):
    return _TONES.get(role or "info", _TONES["info"])


# --------------------------------------------------------------------------- #
# Builder helpers
# --------------------------------------------------------------------------- #

def card(widget=None, parent=None):
    # type: (Optional[Any], Optional[Any]) -> Any
    """Wrap *widget* (or a new empty container) in a white card QFrame."""
    frame = Qt.QtWidgets.QFrame(parent)
    frame.setObjectName("card")
    if widget is not None:
        lay = Qt.QtWidgets.QVBoxLayout(frame)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(10)
        lay.addWidget(widget)
    return frame


def section_title(text, subtitle=None):
    # type: (str, Optional[str]) -> Any
    """A bold deep-teal section heading with an optional muted subtitle."""
    title = Qt.QtWidgets.QLabel(text)
    title.setObjectName("sectionTitle")
    if subtitle:
        sub = Qt.QtWidgets.QLabel(subtitle)
        sub.setObjectName("sectionSub")
        box = Qt.QtWidgets.QWidget()
        box.setLayoutDirection(_Core.Qt.RightToLeft)
        v = Qt.QtWidgets.QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        v.addWidget(title)
        v.addWidget(sub)
        return box
    return title


def stat_tile(title, value="—", role="info"):
    # type: (str, Any, str) -> Any
    """A KPI tile like the web's .stat: white card, 3px colored top rule,
    small muted label, large ink value (role only colors the rule)."""
    box = Qt.QtWidgets.QFrame()
    box.setObjectName("stat")
    box.setProperty("role", role)
    v = Qt.QtWidgets.QVBoxLayout(box)
    v.setContentsMargins(17, 15, 17, 15)
    v.setSpacing(6)
    lab = Qt.QtWidgets.QLabel(title)
    lab.setObjectName("statLabel")
    val = Qt.QtWidgets.QLabel(str(value))
    val.setObjectName("statValue")
    val.setProperty("role", role)
    v.addWidget(lab)
    v.addWidget(val)
    return box


def badge(text, role="info"):
    # type: (str, str) -> Any
    """A small colored pill (e.g. وضعیت)."""
    lbl = Qt.QtWidgets.QLabel(text)
    lbl.setObjectName("badge")
    lbl.setProperty("role", role)
    lbl.setAlignment(_Core.Qt.AlignCenter)
    return lbl


def primary(button, width=140):
    # type: (Any, int) -> Any
    """Mark *button* as the emphasized primary action."""
    button.setProperty("variant", "primary")
    button.setMinimumWidth(width)
    return button


def success(button, width=140):
    # type: (Any, int) -> Any
    button.setProperty("variant", "success")
    button.setMinimumWidth(width)
    return button


def danger(button, width=140):
    # type: (Any, int) -> Any
    button.setProperty("variant", "danger")
    button.setMinimumWidth(width)
    return button


class _SumCardLabel(Qt.QtWidgets.QLabel):
    """QLabel that renders ``"label: value"`` like the web's .sum-card:
    a small muted caption above a large colored figure. Keeps the plain
    ``setText()`` API so callers stay unchanged."""

    def __init__(self, text="", tone="info", parent=None):
        super().__init__(text, parent)
        self._tone = tone or "info"
        self.setObjectName("sumCard")
        self.setProperty("tone", self._tone)
        self.setAlignment(_Core.Qt.AlignRight | _Core.Qt.AlignVCenter)
        self.setText(text)

    def setText(self, text):  # noqa: N802 (Qt naming)
        s = str(text or "")
        lbl, val = s, ""
        for sep in (": ", "： "):
            if sep in s:
                i = s.index(sep)
                lbl, val = s[:i], s[i + len(sep):]
                break
        _, _, val_color = _tone(self._tone)
        if val:
            html = ("<div style='line-height:135%%'>"
                    "<span style='font-size:12px;font-weight:600;color:%s;'>%s</span>"
                    "<br><span style='font-size:18px;font-weight:900;color:%s;'>%s</span>"
                    "</div>") % (MUTED, lbl, val_color, val)
        else:
            html = ("<div style='line-height:135%%'>"
                    "<span style='font-size:12px;font-weight:600;color:%s;'>%s</span>"
                    "</div>") % (MUTED, lbl)
        super().setText(html)


def sum_card(text, tone="info"):
    # type: (str, str) -> Any
    """A colored summary counter card (web .sum-card)."""
    return _SumCardLabel(text, tone)


def make_totals_label(role):
    # type: (str) -> Any
    """Invoice total summary-card label. role in total/paid/remaining."""
    tone = {"total": "info", "paid": "success", "remaining": "warn"}.get(role, "info")
    lbl = _SumCardLabel("", tone)
    lbl.setMinimumHeight(54)
    return lbl


def sidebar_nav(items):
    # type: (List[str]) -> Any
    """A styled vertical navigation list for the main shell."""
    lst = Qt.QtWidgets.QListWidget()
    lst.setObjectName("sideNav")
    lst.setLayoutDirection(_Core.Qt.RightToLeft)
    lst.setVerticalScrollBarPolicy(_Core.Qt.ScrollBarAlwaysOff)
    lst.setHorizontalScrollBarPolicy(_Core.Qt.ScrollBarAlwaysOff)
    lst.setFrameShape(Qt.QtWidgets.QFrame.NoFrame)
    for label in items:
        lst.addItem(label)
    lst.setCurrentRow(0)
    return lst


def app_bar_title(text, subtitle=None):
    # type: (str, Optional[str]) -> Any
    """Sidebar brand block (web .sidebar .brand)."""
    box = Qt.QtWidgets.QWidget()
    box.setObjectName("sideBrand")
    v = Qt.QtWidgets.QVBoxLayout(box)
    v.setContentsMargins(16, 20, 16, 18)
    v.setSpacing(2)
    t = Qt.QtWidgets.QLabel(text)
    t.setObjectName("brand")
    v.addWidget(t)
    if subtitle:
        s = Qt.QtWidgets.QLabel(subtitle)
        s.setObjectName("brandSub")
        v.addWidget(s)
    return box


# --------------------------------------------------------------------------- #
# Entry points
# --------------------------------------------------------------------------- #

def _check_url():
    # type: () -> str
    """Absolute forward-slash path to the bundled checkmark SVG (QSS url())."""
    try:
        from .utils import resource_path
        return resource_path("app/resources/check.svg").replace("\\", "/")
    except Exception:
        return ""


def build_stylesheet():
    # type: () -> str
    return _QSS.replace("%CHECK%", _check_url())


def apply_theme(app=None):
    # type: (Optional[Any]) -> None
    """Apply the global stylesheet to *app* (or the active instance)."""
    a = app or Qt.QtWidgets.QApplication.instance()
    if a is None:
        return
    a.setStyleSheet(build_stylesheet())


# --------------------------------------------------------------------------- #
# QSS — tokens mirrored from webapp/static/style.css
# --------------------------------------------------------------------------- #

_QSS = """
/* ============ Clinic Pulse design system ============ */

QMainWindow, QDialog {
    background: #eef3f7;
}
QWidget {
    color: #0f2433;
}

/* ----- Sidebar (light chart-paper, airy) ----- */
QWidget#sideBrand {
    background: transparent;
    border-bottom: 1px solid #dbe4ea;
}
QLabel#brand {
    color: #0f2433;
    font-size: 15px;
    font-weight: 800;
}
QLabel#brandSub {
    color: #5d7385;
    font-size: 11px;
}
QListWidget#sideNav {
    background: transparent;
    border: none;
    padding: 10px 0 16px 0;
    outline: 0;
}
QListWidget#sideNav::item {
    color: #52707f;
    border-radius: 9px;
    padding: 9px 14px;
    margin: 2px 9px;
    font-size: 13px;
    font-weight: 600;
    border-right: 3px solid transparent;
}
QListWidget#sideNav::item:hover {
    background: #f4f8fa;
    color: #0d6e8c;
}
QListWidget#sideNav::item:selected {
    background: #e2f1f6;
    color: #073d4e;
    font-weight: 800;
    border-right: 3px solid #0d6e8c;
}
QListWidget#sideNav::item:disabled {
    color: #8aa0ad;
    background: transparent;
    border: none;
    padding: 16px 18px 4px 18px;
    margin: 0;
    font-size: 10.5px;
    font-weight: 700;
    letter-spacing: .6px;
}
QWidget#sideFoot { background: transparent; border-top: 1px solid #dbe4ea; }
QLabel#versionFoot { color: #8aa0ad; font-size: 11px; padding: 12px 18px; }

/* ----- Top bar (white, page title + date chip + user box) ----- */
QFrame#topBar {
    background: #ffffff;
    border: none;
    border-bottom: 1px solid #dbe4ea;
}
QLabel#pageTitle {
    color: #0f2433;
    font-size: 18px;
    font-weight: 900;
}
QLabel#pageSub {
    color: #5d7385;
    font-size: 12px;
}
QLabel#dateChip {
    background: #e2f1f6;
    color: #073d4e;
    border: 1px solid #c4e0ea;
    border-radius: 14px;
    padding: 5px 14px;
    font-size: 12.5px;
    font-weight: 700;
}
QLabel#userName {
    color: #0f2433;
    font-size: 13px;
    font-weight: 700;
}

/* ----- Cards ----- */
QFrame#card {
    background: #ffffff;
    border: 1px solid #dbe4ea;
    border-radius: 14px;
}
QFrame#card[role="bare"] {
    background: transparent;
    border: none;
    border-radius: 0;
    padding: 0;
}

/* ----- Section headings ----- */
QLabel#sectionTitle {
    color: #073d4e;
    font-size: 15px;
    font-weight: 800;
}
QLabel#cardTitle {
    color: #073d4e;
    font-size: 14.5px;
    font-weight: 800;
    background: transparent;
    border: none;
}
QLabel#sectionSub {
    color: #5d7385;
    font-size: 12px;
}
QLabel[role="page-title"] {
    color: #0f2433;
    font-size: 18px;
    font-weight: 900;
}
/* the pulse tick: card titles open with a short ECG dash (web .card-title::before) */
QFrame#cardTick {
    background: #e24c5a;
    border: none;
    border-radius: 2px;
}

/* ----- KPI tiles (white + colored top rule) ----- */
QFrame#stat {
    background: #ffffff;
    border: 1px solid #dbe4ea;
    border-top: 3px solid #0d6e8c;
    border-radius: 14px;
}
QFrame#stat[role="positive"] { border-top-color: #2e8b6a; }
QFrame#stat[role="success"]  { border-top-color: #2e8b6a; }
QFrame#stat[role="negative"] { border-top-color: #c03b4a; }
QFrame#stat[role="danger"]   { border-top-color: #c03b4a; }
QFrame#stat[role="warning"]  { border-top-color: #b97a1c; }
QFrame#stat[role="warn"]     { border-top-color: #b97a1c; }
QFrame#stat[role="info"]     { border-top-color: #3a6b86; }
QFrame#stat[role="accent"]   { border-top-color: #0d6e8c; }
QLabel#statLabel {
    color: #5d7385;
    font-size: 12.5px;
    font-weight: 600;
    background: transparent;
    border: none;
}
QLabel#statValue {
    color: #0f2433;
    font-size: 23px;
    font-weight: 900;
    background: transparent;
    border: none;
}

/* ----- Badges / pills ----- */
QLabel#badge {
    border-radius: 11px;
    padding: 3px 11px;
    font-size: 12px;
    font-weight: 700;
}
QLabel#badge[role="success"] { background: #e4f3ec; color: #2e8b6a; }
QLabel#badge[role="danger"]  { background: #fbe9eb; color: #c03b4a; }
QLabel#badge[role="info"]    { background: #e5eef3; color: #3a6b86; }
QLabel#badge[role="warn"], QLabel#badge[role="warning"] { background: #fbf1dd; color: #b97a1c; }
QLabel#badge[role="muted"]   { background: #f4f8fa; color: #5d7385; }

/* ----- Buttons (web .btn) ----- */
QPushButton {
    background: transparent;
    color: #5d7385;
    border: 1px solid #c6d3dc;
    border-radius: 9px;
    padding: 8px 17px;
    min-height: 20px;
    font-weight: 700;
    font-size: 13.5px;
}
QPushButton:hover { background: #f4f8fa; color: #0f2433; border-color: #b3c4cf; }
QPushButton:pressed { background: #e6edf2; }
QPushButton:disabled { color: #9db0bc; background: transparent; border-color: #dbe4ea; }
QPushButton:focus { outline: none; border: 1px solid #0d6e8c; }
QPushButton[variant="primary"] {
    background: #0d6e8c; color: #ffffff; border: 1px solid #0d6e8c;
}
QPushButton[variant="primary"]:hover { background: #095469; border-color: #095469; color: #ffffff; }
QPushButton[variant="primary"]:pressed { background: #073d4e; }
QPushButton[variant="primary"]:disabled { background: #9cc3d1; border-color: #9cc3d1; color: #eef6f9; }
QPushButton[variant="success"] {
    background: #2e8b6a; color: #ffffff; border: 1px solid #2e8b6a;
}
QPushButton[variant="success"]:hover { background: #257055; border-color: #257055; color: #ffffff; }
QPushButton[variant="success"]:pressed { background: #1d5a44; }
QPushButton[variant="danger"] {
    background: #c03b4a; color: #ffffff; border: 1px solid #c03b4a;
}
QPushButton[variant="danger"]:hover { background: #a52d3b; border-color: #a52d3b; color: #ffffff; }
QPushButton[variant="danger"]:pressed { background: #8c2532; }
QPushButton[variant="warn"] {
    background: #b97a1c; color: #ffffff; border: 1px solid #b97a1c;
}
QPushButton[variant="warn"]:hover { background: #9c6717; border-color: #9c6717; color: #ffffff; }
QPushButton[variant="outline"] {
    background: #ffffff; color: #0d6e8c; border: 1px solid #0d6e8c;
}
QPushButton[variant="outline"]:hover { background: #e2f1f6; color: #095469; }
QPushButton[variant="ghost"] {
    background: transparent; color: #5d7385; border: 1px solid #c6d3dc;
}
QPushButton[variant="ghost"]:hover { background: #f4f8fa; color: #0f2433; }
QPushButton[variant="link"] {
    background: transparent; border: 1px solid transparent;
    color: #0d6e8c; padding: 5px 9px; font-weight: 600;
}
QPushButton[variant="link"]:hover { background: #e2f1f6; color: #095469; }
QPushButton[variant="link"][tone="danger"] { color: #c03b4a; }
QPushButton[variant="link"][tone="danger"]:hover { background: #fbe9eb; color: #a52d3b; }
QPushButton[variant="link"][tone="warn"] { color: #b97a1c; }
QPushButton[variant="link"][tone="warn"]:hover { background: #fbf1dd; }
/* compact link buttons used inside table action columns
   NOTE: the property is called btnsize, NOT size — QWidget already has a
   real QSize property named "size", so a QSS [size="xs"] selector compares
   that QSize against a string and NEVER matches. */
QPushButton[variant="link"][btnsize="xs"] {
    padding: 3px 8px; font-size: 12px; font-weight: 600; min-height: 0;
    border-radius: 7px;
}

/* ----- Inputs ----- */
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox,
QDateTimeEdit, QDateEdit, QComboBox {
    background: #ffffff;
    border: 1px solid #c6d3dc;
    border-radius: 9px;
    padding: 8px 12px;
    font-size: 13.5px;
    color: #0f2433;
    selection-background-color: #c4e0ea;
    selection-color: #073d4e;
}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover { border-color: #b3c4cf; }
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus,
QDateTimeEdit:focus {
    border: 1px solid #0d6e8c;
}
QLineEdit:disabled, QComboBox:disabled { color: #9db0bc; background: #f4f8fa; }
QLineEdit[role="invalid"] { border: 1px solid #c03b4a; }
QComboBox::drop-down { border: none; width: 26px; }
QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #5d7385;
    margin-right: 6px;
}
QComboBox QAbstractItemView {
    background: #ffffff;
    border: 1px solid #c6d3dc;
    border-radius: 9px;
    selection-background-color: #e2f1f6;
    selection-color: #073d4e;
    outline: 0;
    padding: 4px;
}
QLabel[role="flabel"] {
    color: #31485a;
    font-size: 12.5px;
    font-weight: 600;
    background: transparent;
    border: none;
}

/* ----- Tables (web table.tbl) ----- */
QTableView {
    background: #ffffff;
    alternate-background-color: #f6f9fb;
    border: none;
    gridline-color: transparent;
    selection-background-color: #d7e9f0;
    selection-color: #073d4e;
    outline: none;
    font-size: 13.5px;
}
QTableView::item {
    padding: 7px 12px;
    border-bottom: 1px solid #dbe4ea;
    color: #0f2433;
}
QTableView::item:hover { background: #e2f1f6; }
QTableView::item:selected { background: #d7e9f0; color: #073d4e; }
QHeaderView::section {
    background: #f4f8fa;
    color: #5d7385;
    border: none;
    border-bottom: 2px solid #b3c4cf;
    padding: 9px 12px;
    font-size: 12px;
    font-weight: 700;
}
QTableView QTableCornerButton::section {
    background: #f4f8fa;
    border: none;
}
/* Settings list editor rows (web .list-row): each option in its own
   bordered box so items read as separate entries. */
QFrame#listRow {
    background: #f7fafc;
    border: 1px solid #dbe4ea;
    border-radius: 9px;
}
/* header: click-to-sort. Paint the sort arrows explicitly so they stay
   visible under the styled ::section background. */
QHeaderView { background: #f4f8fa; border: none; }
QHeaderView::up-arrow {
    width: 0; height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 5px solid #0d6e8c;
}
QHeaderView::down-arrow {
    width: 0; height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #0d6e8c;
}

/* ----- Patient-search autocomplete popup (invoice page) ----- */
QListView#pickerPopup {
    background: #ffffff;
    border: 1px solid #c6d3dc;
    border-radius: 9px;
    padding: 4px;
    outline: 0;
}
QListView#pickerPopup::item {
    padding: 8px 12px;
    border-radius: 7px;
    color: #0f2433;
    background: transparent;
    border: none;
}
QListView#pickerPopup::item:selected {
    background: #e2f1f6;
    color: #073d4e;
}

/* ----- Tabs (web .tabs: underline style) ----- */
QTabWidget::pane {
    border: none;
    border-top: 2px solid #dbe4ea;
    background: transparent;
    top: -1px;
}
QTabBar { background: transparent; }
QTabBar::tab {
    background: transparent;
    color: #5d7385;
    border: none;
    border-bottom: 3px solid transparent;
    padding: 9px 16px;
    margin-right: 2px;
    font-weight: 600;
    font-size: 13.5px;
}
QTabBar::tab:selected {
    color: #0d6e8c;
    border-bottom: 3px solid #0d6e8c;
}
QTabBar::tab:hover:!selected { color: #0f2433; }

/* ----- Group boxes / sections ----- */
QGroupBox {
    background: #ffffff;
    border: 1px solid #dbe4ea;
    border-radius: 14px;
    margin-top: 14px;
    padding: 16px 12px 10px 12px;
    font-weight: 700;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 6px;
    color: #0d6e8c;
}

/* ----- Scrollbars (thin clinical) ----- */
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #c6d3dc; min-height: 24px; border-radius: 4px; }
QScrollBar::handle:vertical:hover { background: #b3c4cf; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: #c6d3dc; min-width: 24px; border-radius: 4px; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollArea { background: transparent; border: none; }
QStackedWidget { background: transparent; }

/* ----- Misc ----- */
QCheckBox, QRadioButton { spacing: 7px; background: transparent; border: none; }
QCheckBox::indicator, QRadioButton::indicator {
    width: 16px; height: 16px;
    border: 1px solid #c6d3dc; border-radius: 4px;
    background: #ffffff;
}
QCheckBox::indicator:hover, QRadioButton::indicator:hover { border-color: #0d6e8c; }
QCheckBox::indicator:checked {
    background: #0d6e8c; border-color: #0d6e8c;
    image: url("%CHECK%");
}
QRadioButton::indicator { border-radius: 9px; }
QRadioButton::indicator:checked {
    border-color: #0d6e8c;
    background: qradialgradient(cx:0.5, cy:0.5, radius:0.55, fp:0.5, fy:0.5,
        stop:0 #0d6e8c, stop:0.42 #0d6e8c, stop:0.5 #ffffff, stop:1 #ffffff);
}
QToolTip {
    background: #0f2433; color: #eef3f7; border: none;
    padding: 5px 9px; border-radius: 9px;
}
QStatusBar { background: #ffffff; color: #5d7385; border-top: 1px solid #dbe4ea; }
QMenu { background: #ffffff; border: 1px solid #c6d3dc; border-radius: 9px; padding: 4px; }
QMenu::item { padding: 7px 18px; border-radius: 7px; }
QMenu::item:selected { background: #e2f1f6; color: #073d4e; }
QMessageBox { background: #ffffff; }
QSplitter::handle { background: #dbe4ea; }
QLabel#emptyState {
    color: #5d7385;
    font-size: 13.5px;
    padding: 30px 10px;
    background: transparent;
    border: none;
}

/* ----- Jalali calendar popup (web .jdate-picker) ----- */
QWidget#calPopup {
    background: #ffffff;
    border: 1px solid #c6d3dc;
    border-radius: 9px;
}
QLabel#calMonth {
    color: #0f2433;
    font-size: 13px;
    font-weight: 700;
    background: transparent;
    border: none;
}
QLabel#calWd {
    color: #5d7385;
    font-size: 11px;
    font-weight: 600;
    background: transparent;
    border: none;
}
QToolButton#calNav {
    background: #ffffff;
    color: #31485a;
    border: 1px solid #c6d3dc;
    border-radius: 7px;
    padding: 3px 7px;
    font-size: 11px;
    font-weight: 600;
}
QToolButton#calNav:hover { background: #e2f1f6; }
QToolButton#calNav:pressed { background: #c4e0ea; }
QPushButton#calDay {
    background: transparent;
    color: #0f2433;
    border: 1px solid transparent;
    border-radius: 7px;
    padding: 0px;
    margin: 0px;
    min-width: 30px; max-width: 30px;
    min-height: 26px; max-height: 26px;
    font-size: 12.5px;
    font-weight: 400;
}
QPushButton#calDay:hover { background: #e2f1f6; border-color: #e2f1f6; }
QPushButton#calDay[today="true"] {
    border: 1px solid #e24c5a;
    color: #c23444;
    font-weight: 700;
}
QPushButton#calDay[variant="primary"] {
    background: #0d6e8c; color: #ffffff; border: 1px solid #0d6e8c;
    font-weight: 700;
}
QPushButton#calDay[variant="primary"]:hover { background: #095469; }

/* ----- Summary counter cards (web .sum-card) ----- */
QLabel#sumCard {
    border-radius: 10px;
    padding: 12px 15px;
    background: #ffffff;
    border: 1px solid #dbe4ea;
    color: #0f2433;
}
QLabel#sumCard[tone="info"]    { background: #e5eef3; color: #3a6b86; border-color: #c5d9e3; }
QLabel#sumCard[tone="success"] { background: #e4f3ec; color: #2e8b6a; border-color: #bfe0d1; }
QLabel#sumCard[tone="danger"]  { background: #fbe9eb; color: #c03b4a; border-color: #f0c6cb; }
QLabel#sumCard[tone="warn"], QLabel#sumCard[tone="warning"] {
    background: #fbf1dd; color: #b97a1c; border-color: #ecd5a8;
}
QLabel#sumCard[tone="accent"]  { background: #e2f1f6; color: #0d6e8c; border-color: #c4e0ea; }
QLabel#sumCard[role="total"]    { background: #e5eef3; color: #3a6b86; border-color: #c5d9e3; }
QLabel#sumCard[role="paid"]     { background: #e4f3ec; color: #2e8b6a; border-color: #bfe0d1; }
QLabel#sumCard[role="remaining"]{ background: #fbf1dd; color: #b97a1c; border-color: #ecd5a8; }

/* ----- Dashboard pulse hero (web .pulse-hero: white card, ink figures) ----- */
QFrame#hero {
    background: #ffffff;
    border: 1px solid #dbe4ea;
    border-radius: 14px;
}
QLabel#heroLabel {
    color: #5d7385; font-size: 12.5px; font-weight: 700;
    background: transparent; border: none;
}
QLabel#heroValue {
    color: #0f2433; font-size: 38px; font-weight: 900;
    background: transparent; border: none;
}
QLabel#heroUnit {
    color: #5d7385; font-size: 14px; font-weight: 600;
    background: transparent; border: none;
}
QLabel#heroRow {
    color: #5d7385; font-size: 13px; font-weight: 600;
    background: transparent;
    border: none;
    border-bottom: 1px dashed #dbe4ea;
    padding: 8px 0px;
}
QLabel#heroRowVal {
    color: #0f2433; font-size: 16px; font-weight: 800;
    background: transparent;
    border: none;
    border-bottom: 1px dashed #dbe4ea;
    padding: 8px 0px;
}
QLabel#heroRowLast, QLabel#heroRowValLast { border-bottom: none; }

/* ----- Quick-access tiles (web .quick) ----- */
QFrame#quick {
    background: #ffffff;
    border: 1px solid #dbe4ea;
    border-radius: 9px;
}
QFrame#quick:hover {
    background: #e2f1f6;
    border-color: #c4e0ea;
}
QLabel#qIco {
    background: #e2f1f6;
    border: none;
    border-radius: 10px;
}
QFrame#quick:hover QLabel#qIco { background: #ffffff; }
QLabel#qTitle {
    color: #0f2433; font-size: 13.5px; font-weight: 800;
    background: transparent; border: none;
}
QLabel#qSub {
    color: #5d7385; font-size: 11.5px;
    background: transparent; border: none;
}

/* ----- Login (web .login-wrap: deep-teal masthead + white card) ----- */
QDialog#loginDlg {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #0f4a5e, stop:.55 #093a4b, stop:1 #062631);
}
QLabel#lmEyebrow {
    color: #9fc4d2; font-size: 12px; font-weight: 700; letter-spacing: .4px;
    background: transparent; border: none;
}
QLabel#lmTitle {
    color: #ffffff; font-size: 34px; font-weight: 900;
    background: transparent; border: none;
}
QFrame#lmStamp {
    background: rgba(13, 110, 140, 0.16);
    border: 1px solid rgba(196, 224, 234, 0.45);
    border-radius: 11px;
}
QLabel#lmStampLbl {
    color: #9fc4d2; font-size: 10.5px; font-weight: 700; letter-spacing: .4px;
    background: transparent; border: none;
}
QLabel#lmStampDate {
    color: #ffffff; font-size: 24px; font-weight: 900;
    background: transparent; border: none;
}
QFrame#loginCard {
    background: #ffffff;
    border: 1px solid rgba(255, 255, 255, 0.5);
    border-radius: 18px;
}
QLabel#loginTitle {
    color: #0f2433; font-size: 20px; font-weight: 900;
    background: transparent; border: none;
}
QLabel#loginSub {
    color: #5d7385; font-size: 13px;
    background: transparent; border: none;
}
QLabel#loginErr {
    background: #fbe9eb; color: #96242f; border: 1px solid #f0c2c8;
    border-radius: 9px; padding: 8px 12px; font-size: 12.5px;
}
"""


__all__ = [
    "build_stylesheet", "apply_theme",
    "card", "section_title", "stat_tile", "badge",
    "primary", "success", "danger",
    "make_totals_label", "sum_card",
    "sidebar_nav", "app_bar_title",
]
