# -*- coding: utf-8 -*-
"""Shared widget toolkit for the v2 desktop UI.

Mirrors the behaviour of ``webapp/static/app.js`` so the desktop app feels
identical to the browser UI:

* :class:`FaLineEdit`   — shows Persian digits while typing (data-fadigits).
* :class:`MoneyEdit`    — Persian digits + ٬ thousands separators (data-money).
* :class:`QtyEdit`      — digits-only Persian input (data-fanum).
* :class:`SearchEdit`   — live filter box with clear button.
* :class:`JalaliDateEdit` — read-only Jalali date field + calendar popup.
* :class:`TimeEdit`     — HH:MM field with Persian digits.
* table / header helpers used by every page.

All values are *stored* as Latin digits; only the display is Persian.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Iterable, List, Optional, Sequence

from ..utils import Qt, best_persian_font
from .. import date_utils, money_utils

_Core = Qt.QtCore
_Gui = Qt.QtGui
_W = Qt.QtWidgets

# --------------------------------------------------------------------------- #
# Digit plumbing (same tables as webapp/static/app.js)
# --------------------------------------------------------------------------- #
_EN = "0123456789"
_FA = "۰۱۲۳۴۵۶۷۸۹"
_AR = "٠١٢٣٤٥٦٧٨٩"
_TO_FA = str.maketrans(_EN + _AR, _FA + _FA)
_TO_EN = str.maketrans(_FA + _AR, _EN + _EN)

FA_MONTHS = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
             "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
FA_WEEKDAYS = ["ش", "ی", "د", "س", "چ", "پ", "ج"]


def fa(text: Any) -> str:
    """Any value -> Persian-digit display string."""
    return str(text).translate(_TO_FA)


def en(text: Any) -> str:
    """Persian/Arabic digits in *text* -> Latin digits."""
    return str(text).translate(_TO_EN)


def _digits_only(text: str) -> str:
    return "".join(c for c in en(text) if c.isdigit())


def match_words(query, *fields):
    # type: (str, str) -> bool
    """Row filter identical to the web's makeRowFilter: every typed word must
    appear somewhere in the joined fields; digit-script and ZWNJ insensitive."""
    q = en(query or "").replace("\u200c", " ").strip().lower()
    words = [w for w in q.split() if w]
    if not words:
        return True
    hay = " ".join(en(f or "").replace("\u200c", " ").lower() for f in fields)
    return all(w in hay for w in words)


def money_text(value: Optional[int]) -> str:
    """int -> '۱۲٬۳۴۵' display."""
    return money_utils.format_money_persian(value)


# --------------------------------------------------------------------------- #
# Line edits
# --------------------------------------------------------------------------- #

class FaLineEdit(_W.QLineEdit):
    """Line edit that renders Latin/Arabic digits as Persian while typing.

    1:1 digit mapping keeps the caret stable; letters/spaces pass through.
    ``value()`` always returns Latin digits (what the DB stores).
    """

    def __init__(self, parent=None, placeholder=""):
        super().__init__(parent)
        self.setLayoutDirection(_Core.Qt.RightToLeft)
        if placeholder:
            self.setPlaceholderText(placeholder)
        self._guard = False
        self.textChanged.connect(self._on_changed)

    def _on_changed(self, text):
        if self._guard:
            return
        mapped = text.translate(_TO_FA)
        if mapped != text:
            self._guard = True
            pos = self.cursorPosition()
            self.setText(mapped)
            self.setSelection(min(pos, len(mapped)), 0)
            self._guard = False

    def value(self):
        # type: () -> str
        """Text with digits folded back to Latin."""
        return en(self.text())


class SearchEdit(FaLineEdit):
    """Filter box like the web's ``#patientFilter``: clear button + live text."""

    def __init__(self, parent=None, placeholder="جستجو…"):
        super().__init__(parent, placeholder)
        self.setClearButtonEnabled(True)


class MoneyEdit(_W.QLineEdit):
    """Money input: Persian digits + ٬ separators, integer Toman value out."""

    def __init__(self, parent=None, placeholder=""):
        super().__init__(parent)
        self.setLayoutDirection(_Core.Qt.RightToLeft)
        self.setAlignment(_Core.Qt.AlignRight | _Core.Qt.AlignVCenter)
        if placeholder:
            self.setPlaceholderText(placeholder)
        self._guard = False
        self.textChanged.connect(self._on_changed)

    def _on_changed(self, text):
        if self._guard:
            return
        digits = _digits_only(text)
        want = money_utils.format_money_persian(int(digits)) if digits else ""
        if want != text:
            self._guard = True
            # Caret: count *digits* before it in the old text, re-place after
            # the same number of digits in the new text.
            pos = self.cursorPosition()
            nd = len(_digits_only(text[:pos])) if pos > 0 else 0
            self.setText(want)
            newpos = len(want)
            if nd:
                seen = 0
                for i, ch in enumerate(want):
                    if ch in _FA + _EN + _AR:
                        seen += 1
                        if seen == nd:
                            newpos = i + 1
                            break
            self.setSelection(min(newpos, len(want)), 0)
            self._guard = False

    def value(self):
        # type: () -> int
        return money_utils.parse_money(self.text()) or 0

    def set_value(self, amount):
        # type: (Optional[int]) -> None
        self._guard = True
        self.setText(money_text(amount) if amount not in (None, "") else "")
        self._guard = False


class QtyEdit(MoneyEdit):
    """Integer quantity: Persian digits, no separators."""

    def _on_changed(self, text):
        if self._guard:
            return
        digits = _digits_only(text)
        want = fa(digits)
        if want != text:
            self._guard = True
            pos = self.cursorPosition()
            nd = len(_digits_only(text[:pos])) if pos > 0 else 0
            self.setText(want)
            p = min(nd, len(want))
            self.setSelection(p, 0)
            self._guard = False

    def value(self):
        # type: () -> int
        d = _digits_only(self.text())
        return int(d) if d else 0

    def set_value(self, amount):
        self._guard = True
        self.setText(fa(str(int(amount))) if amount not in (None, "") else "")
        self._guard = False


class TimeEdit(FaLineEdit):
    """HH:MM time field with Persian digits (Latin out)."""

    def __init__(self, parent=None, initial="12:00"):
        super().__init__(parent)
        self.setAlignment(_Core.Qt.AlignCenter)
        self.setMaxLength(5)
        self.setText(fa(initial))

    def time_str(self):
        # type: () -> str
        d = _digits_only(self.text())
        if len(d) == 3:
            d = "0" + d
        if len(d) != 4:
            return "12:00"
        hh = min(int(d[:2]), 23)
        mm = min(int(d[2:]), 59)
        return "%02d:%02d" % (hh, mm)

    def set_time_str(self, value):
        # type: (str) -> None
        self.setText(fa(value or "12:00"))


# --------------------------------------------------------------------------- #
# Jalali date picker (mirrors the web's data-jdate calendar popup)
# --------------------------------------------------------------------------- #

class _JalaliCalendarPopup(_W.QWidget):
    """Compact month grid for the Persian calendar."""

    picked = _Core.Signal(object)  # datetime.date

    def __init__(self, parent=None, selected=None):
        super().__init__(parent, _Core.Qt.Popup)
        self.setLayoutDirection(_Core.Qt.RightToLeft)
        self._selected = selected or date.today()
        jy, jm, jd = date_utils.gregorian_to_jalali(
            self._selected.year, self._selected.month, self._selected.day)
        self._vy, self._vm = jy, jm
        self.build()

    def build(self):
        self.setObjectName("calPopup")
        v = _W.QVBoxLayout(self)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(6)

        nav = _W.QHBoxLayout()
        self._lbl = _W.QLabel()
        self._lbl.setObjectName("calMonth")
        self._lbl.setAlignment(_Core.Qt.AlignCenter)
        b_prev_y = self._nav_btn("‹سال")
        b_prev = self._nav_btn("‹")
        b_next = self._nav_btn("›")
        b_next_y = self._nav_btn("سال›")
        b_prev_y.clicked.connect(lambda: self._shift(12))
        b_prev.clicked.connect(lambda: self._shift(1))
        b_next.clicked.connect(lambda: self._shift(-1))
        b_next_y.clicked.connect(lambda: self._shift(-12))
        nav.addWidget(b_prev_y); nav.addWidget(b_prev)
        nav.addWidget(self._lbl, 1)
        nav.addWidget(b_next); nav.addWidget(b_next_y)
        v.addLayout(nav)

        self._grid = _W.QGridLayout()
        self._grid.setSpacing(3)
        for col, wd in enumerate(FA_WEEKDAYS):
            lab = _W.QLabel(wd)
            lab.setObjectName("calWd")
            lab.setAlignment(_Core.Qt.AlignCenter)
            self._grid.addWidget(lab, 0, col)
        v.addLayout(self._grid)

        today_row = _W.QHBoxLayout()
        btn_today = self._nav_btn("امروز")
        btn_today.clicked.connect(self._pick_today)
        today_row.addStretch(1)
        today_row.addWidget(btn_today)
        v.addLayout(today_row)
        self._rebuild_days()

    def _nav_btn(self, text):
        b = _W.QToolButton()
        b.setObjectName("calNav")
        b.setText(text)
        b.setCursor(_Core.Qt.PointingHandCursor)
        return b

    def _shift(self, months):
        idx = (self._vy - 1) * 12 + (self._vm - 1) + months
        self._vy, self._vm = idx // 12 + 1, idx % 12 + 1
        self._rebuild_days()

    def _pick_today(self):
        self.picked.emit(date.today())
        self.close()

    def _rebuild_days(self):
        self._lbl.setText("%s %s" % (FA_MONTHS[self._vm - 1], fa(self._vy)))
        while self._grid.count() > 7:
            it = self._grid.takeAt(self._grid.count() - 1)
            w = it.widget()
            if w:
                w.deleteLater()
        first_g = date(*date_utils.jalali_to_gregorian(self._vy, self._vm, 1))
        days = date_utils._jal_month_lengths(self._vy)[self._vm - 1]
        # Python weekday(): Mon=0..Sun=6 ; Persian week starts Saturday(5).
        offset = (first_g.weekday() + 2) % 7
        today = date.today()
        for d in range(1, days + 1):
            g = date(*date_utils.jalali_to_gregorian(self._vy, self._vm, d))
            btn = _W.QPushButton(fa(d))
            btn.setObjectName("calDay")
            btn.setFixedSize(30, 26)
            btn.setCursor(_Core.Qt.PointingHandCursor)
            if g == self._selected:
                btn.setProperty("variant", "primary")
            elif g == today:
                btn.setProperty("today", True)
            btn.clicked.connect(lambda _=False, gg=g: self._pick(gg))
            self._grid.addWidget(btn, 1 + (d - 1 + offset) // 7,
                                 (d - 1 + offset) % 7)

    def _pick(self, g):
        self.picked.emit(g)
        self.close()


class JalaliDateEdit(_W.QWidget):
    """Read-only Jalali display + calendar button; ISO Latin value out."""

    dateChanged = _Core.Signal(str)  # 'YYYY-MM-DD'

    def __init__(self, parent=None, iso=""):
        super().__init__(parent)
        self._iso = ""  # type: str
        h = _W.QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)
        self.edit = _W.QLineEdit()
        self.edit.setLayoutDirection(_Core.Qt.RightToLeft)
        self.edit.setAlignment(_Core.Qt.AlignCenter)
        self.edit.setReadOnly(True)
        self.edit.setCursorPosition(0)
        self.btn = _W.QToolButton()
        self.btn.setText("📅" if _has_glyph("📅") else "تقویم")
        self.btn.clicked.connect(self._open)
        h.addWidget(self.edit, 1)
        h.addWidget(self.btn)
        if iso:
            self.set_iso(iso)
        else:
            self._show_iso(None)

    def _open(self):
        sel = self.as_date() or date.today()
        pop = _JalaliCalendarPopup(self, sel)
        pop.picked.connect(self._on_pick)
        pop.adjustSize()
        pop.move(self.btn.mapToGlobal(_Core.QPoint(0, self.btn.height())))
        pop.show()  # Qt.Popup grabs input and closes on click-outside

    def _on_pick(self, g):
        self.set_iso(g.isoformat())

    def set_iso(self, iso):
        # type: (str) -> None
        iso = (iso or "")[:10]
        if iso != self._iso:
            self._iso = iso
            self._show_iso(iso or None)
            self.dateChanged.emit(iso)

    def _show_iso(self, iso_or_none):
        if iso_or_none:
            self.edit.setText(fa(date_utils.iso_to_jalali_str(iso_or_none)))
        else:
            self.edit.setText("")

    def iso(self):
        # type: () -> str
        return self._iso

    def as_date(self):
        # type: () -> Optional[date]
        try:
            return date_utils.parse_iso_date(self._iso) if self._iso else None
        except Exception:
            return None

    def set_enabled_all(self, on):
        self.edit.setEnabled(on)
        self.btn.setEnabled(on)


def _has_glyph(ch):
    try:
        return _Gui.QFont("Segoe UI Symbol").glyphCount(ch) > 0
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# Layout / table helpers
# --------------------------------------------------------------------------- #

class CardTitle(_W.QWidget):
    """Card heading like the web's .card-title: pulse-red tick + deep-teal
    text. Keeps a ``setText()``/``text()`` API so pages can treat it as a
    label."""

    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.setLayoutDirection(_Core.Qt.RightToLeft)
        h = _W.QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(9)
        tick = _W.QFrame()
        tick.setObjectName("cardTick")
        tick.setFixedWidth(18)
        tick.setFixedHeight(3)
        self._lab = _W.QLabel(text)
        self._lab.setObjectName("cardTitle")
        h.addWidget(tick, 0, _Core.Qt.AlignVCenter)
        h.addWidget(self._lab, 0, _Core.Qt.AlignVCenter)
        h.addStretch(1)

    def setText(self, text):  # noqa: N802
        self._lab.setText(text)

    def text(self):
        return self._lab.text()


def card_title(text):
    # type: (str) -> Any
    """Card heading like the web's .card-title (tick + deep-teal bold)."""
    return CardTitle(text)


def page_header(title, subtitle="", actions=()):
    # type: (str, str, Sequence) -> _W.QWidget
    """Action toolbar for the top of a page. The page title itself lives in
    the shell's top bar (like the web), so only trailing action buttons are
    rendered here; with no actions the widget collapses to zero height."""
    box = _W.QWidget()
    h = _W.QHBoxLayout(box)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(8)
    h.addStretch(1)
    for btn in actions:
        h.addWidget(btn)
    if not actions:
        box.setFixedHeight(0)
    return box


_NUM_KEY = _Core.Qt.UserRole        # int sort key (hidden from display)
_NUM_DISP = _Core.Qt.UserRole + 1   # Persian display string, restored post-sort
_ROW_ID = _Core.Qt.UserRole + 2     # hidden data-row id for lazy action cells
ROW_ID = _ROW_ID                    # public alias for page factories


def make_item(text, align_right=True, payload=None):
    # type: (Any, bool, Any) -> Any
    """QStandardItem for tables: Persian display + numeric sort key.

    ``payload`` stores a hidden data-row id (Qt.UserRole+2) so lazy action
    widgets (set_row_widget_factory) can find their record even after the
    user re-sorts the table.

    NOTE: QStandardItem has *one* slot for EditRole/DisplayRole — writing an
    int to EditRole replaces the displayed text with Latin digits. So the
    numeric key lives under Qt.UserRole and _TableModel.sort() swaps it in
    only for the duration of the sort, restoring the Persian string after.
    """
    disp = fa(text)
    it = _Gui.QStandardItem(disp)
    it.setEditable(False)
    if payload is not None:
        it.setData(_Core.QVariant(payload), _ROW_ID)
    if align_right:
        # Visual right edge: in these RTL tables Qt mirrors AlignLeft to the
        # right side (AlignRight would paint on the LEFT — see _rtlprobe).
        it.setTextAlignment(_Core.Qt.AlignLeft | _Core.Qt.AlignVCenter)
    s = en(text).replace("\u066c", "").replace(",", "").replace(" ", "")
    if s and (s.isdigit() or (s[0] == "-" and s[1:].isdigit())):
        try:
            it.setData(_Core.QVariant(int(s)), _NUM_KEY)
            it.setData(_Core.QVariant(disp), _NUM_DISP)
        except Exception:
            pass
    return it


class _TableModel(_Gui.QStandardItemModel):
    """QStandardItemModel that sorts numeric columns by value while every
    cell keeps its Persian display string (see make_item's role note)."""

    def sort(self, column, order=None):
        # type: (int, Any) -> None
        if order is None:
            order = _Core.Qt.AscendingOrder
        items = []
        for r in range(self.rowCount()):
            it = self.item(r, column)
            items.append(it)
            if it is not None:
                num = it.data(_NUM_KEY)
                if num is not None:
                    it.setData(_Core.QVariant(num))  # temp DisplayRole=int
        _Gui.QStandardItemModel.sort(self, column, order)
        for it in items:
            if it is not None:
                disp = it.data(_NUM_DISP)
                if disp is not None:
                    it.setData(_Core.QVariant(disp))  # back to Persian


def _apply_sort(view, col, order):
    # type: (Any, int, Any) -> None
    if col is None or col < 0:
        view._sort_col = -1
        return
    ext = getattr(view, "_ext_sort_cb", None)
    view._sort_col = col
    view._sort_order = order
    if ext is not None:
        # External (SQL) sort: the page reloads the *whole* dataset sorted
        # and re-paginates it — sorting only the visible page would lie.
        ext(col, order)
        return
    # Persistent index widgets follow their rows through the sort; the
    # lazy fit pass then just re-positions what is visible.
    view.model().sort(col, order)
    view.schedule_fit()


def resort(view):
    # type: (Any) -> None
    """Re-apply the active header sort after a page refilled its rows."""
    col = getattr(view, "_sort_col", -1)
    order = getattr(view, "_sort_order", _Core.Qt.AscendingOrder)
    if getattr(view, "_ext_sort_cb", None) is not None:
        # Rows already arrive sorted from SQL — sync the header indicator
        # only (never client-sort, never re-enter the callback).
        hdr = view.horizontalHeader()
        hdr.blockSignals(True)
        if col is not None and col >= 0:
            hdr.setSortIndicator(col, order)
        hdr.blockSignals(False)
        return
    if col is not None and col >= 0:
        view.model().sort(col, order)
        view.schedule_fit()


def set_sort_state(view, col, order):
    # type: (Any, int, Any) -> None
    """Silently set the active sort state + header indicator. Used to revert
    clicks on non-sortable columns, or to pre-mark the default sort."""
    view._sort_col = -1 if col is None else col
    view._sort_order = order
    hdr = view.horizontalHeader()
    hdr.blockSignals(True)
    hdr.setSortIndicator(view._sort_col, order)
    hdr.blockSignals(False)


class _PulseTable(_W.QTableView):
    """QTableView that keeps index widgets (row action buttons) sized to
    their cell rect.

    Qt only re-fits an index widget when its row's top is > 0; row 0 and
    partially visible rows keep the stale sizeHint captured while the page
    was still hidden (before QSS polish -> too short, buttons clipped).
    Re-fitting on show/resize/scroll guarantees the compact buttons always
    sit inside their row at every resolution.

    Scaling guards for big tables (hundreds of rows):
    * ``schedule_fit`` coalesces every request in the same event-loop pass
      into ONE fit run (without it, a 600-row refill scheduled 600 full
      passes — O(n²), ~55 seconds on the archive page).
    * ``fit_index_widgets`` only touches rows currently visible in the
      viewport; scrolled-to rows get fitted by the scroll hook below.
    * ``set_row_widget_factory`` switches a column to LAZY widgets: rows
      inside the viewport (+buffer) get real widgets built on demand and
      rows scrolled far out of view are recycled via setIndexWidget(None).
      The view's own indexWidget() is the only registry — and since Qt
      moves persistent editors *with their rows* on sort (verified by
      _sorttest.py), it can never desync from the data.
    """

    _RW_BUFFER = 30  # rows kept alive above/below the viewport

    def set_row_widget_factory(self, col, factory):
        # type: (int, Any) -> None
        self._rw_col = col
        self._rw_factory = factory
        self.schedule_fit()

    def set_external_sort(self, callback):
        # type: (Any) -> None
        """Header clicks call ``callback(col, order)`` instead of sorting
        the in-memory model — for paged tables whose rows come from SQL,
        so the sort spans the *whole* dataset, not just the visible page."""
        self._ext_sort_cb = callback

    def schedule_fit(self):
        if not getattr(self, "_fit_pending", False):
            self._fit_pending = True
            _Core.QTimer.singleShot(0, self._run_fit)

    def _run_fit(self):
        self._fit_pending = False
        self.fit_index_widgets()

    def _visible_rows(self):
        model = self.model()
        n = model.rowCount()
        if n == 0:
            return 0, -1
        vp = self.viewport().rect()
        vh = self.verticalHeader()
        top = vh.visualIndexAt(vp.top())
        bottom = vh.visualIndexAt(vp.bottom())
        if top < 0:
            top = 0
        if bottom < 0:
            bottom = n - 1
        r0 = max(0, min(top, bottom) - self._RW_BUFFER)
        r1 = min(n - 1, max(top, bottom) + self._RW_BUFFER)
        return r0, r1

    def fit_index_widgets(self):
        model = self.model()
        if model is None:
            return
        factory = getattr(self, "_rw_factory", None)
        col = getattr(self, "_rw_col", -1)
        r0, r1 = self._visible_rows()
        retry = False
        if factory is not None and col >= 0:
            # indexWidget() is the registry: create for visible rows,
            # recycle (setIndexWidget(None) -> Qt deletes) for far rows.
            for rr in range(model.rowCount()):
                idx = model.index(rr, col)
                w = self.indexWidget(idx)
                inside = r0 <= rr <= r1
                if w is None:
                    if inside:
                        w = factory(rr)
                        if w is not None:
                            self.setIndexWidget(idx, w)
                            # Qt re-stomps row-0 editors back to their
                            # sizeHint on every deferred items-layout (the
                            # stale-sizeHint bug this class exists for).
                            # An event filter keeps the container pinned to
                            # its cell rect no matter who resizes it.
                            w._rw_pidx = _Core.QPersistentModelIndex(idx)
                            w.installEventFilter(self)
                elif not inside:
                    self.setIndexWidget(idx, None)
                    w = None
                if w is not None:
                    rect = self.visualRect(idx)
                    if rect.isValid() and not rect.isEmpty():
                        w.setGeometry(rect)
                        if factory is not None:
                            # freshly created via setIndexWidget: polish the
                            # buttons (QSS sizes) and settle the inner layout
                            # NOW, not on the next event-loop pass
                            if not getattr(w, "_rw_polished", False):
                                for ch in w.findChildren(_W.QWidget):
                                    ch.ensurePolished()
                                w.ensurePolished()
                                w._rw_polished = True
                            if w.layout() is not None:
                                w.layout().activate()
                    elif inside and self.isVisible():
                        # Qt's deferred items-layout hasn't settled yet —
                        # try once more after it runs (only while visible;
                        # showEvent re-fits hidden pages when they appear).
                        retry = True
            if retry:
                self.schedule_fit()
            return
        for r in range(r0, r1 + 1):
            for c in range(model.columnCount()):
                idx = model.index(r, c)
                w = self.indexWidget(idx)
                if w is not None:
                    if getattr(w, "_rw_pidx", None) is None:
                        # pin eagerly-created widgets too (pages that call
                        # setIndexWidget directly) against the row-0 stomp
                        w._rw_pidx = _Core.QPersistentModelIndex(idx)
                        w.installEventFilter(self)
                    rect = self.visualRect(idx)
                    if rect.isValid() and not rect.isEmpty():
                        w.setGeometry(rect)
                    elif self.isVisible():
                        retry = True
        if retry:
            self.schedule_fit()

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        # one-shot after the layout pass settles the viewport size
        self.schedule_fit()

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self.schedule_fit()

    def eventFilter(self, obj, event):  # noqa: N802
        # Keep lazily-created action containers pinned to their cell rect:
        # Qt's deferred items-layout re-stomps editors (notably row 0) back
        # to their pre-polish sizeHint AFTER our fit pass runs.
        if event.type() == _Core.QEvent.Resize and \
                getattr(obj, "_rw_pidx", None) is not None \
                and not getattr(self, "_pinning", False):
            idx = obj._rw_pidx
            if idx.isValid():
                rect = self.visualRect(_Core.QModelIndex(idx))
                if rect.isValid() and not rect.isEmpty() \
                        and obj.size() != rect.size():
                    self._pinning = True
                    try:
                        obj.setGeometry(rect)
                        if obj.layout() is not None:
                            obj.layout().activate()
                    finally:
                        self._pinning = False
        return _W.QTableView.eventFilter(self, obj, event)


def make_table(headers, num_cols=(), widths=None, stretch=None):
    # type: (Sequence[str], Iterable[int], Optional[Sequence[int]], Optional[int]) -> Any
    """QTableView + QStandardItemModel, RTL, read-only, row selection.

    Every column header is click-to-sort (like the web's table headers):
    first click sorts ascending, second toggles descending. ``widths`` sets
    each column's fixed width; the table shows a horizontal scrollbar when
    the viewport is narrower than the columns (nothing gets clipped).
    ``stretch`` names a column (usually the text/name one) that absorbs all
    leftover width — like an HTML table at 100% — so money columns never get
    a huge empty column while names stay cramped.
    """
    view = _PulseTable()
    view.setLayoutDirection(_Core.Qt.RightToLeft)
    model = _TableModel(0, len(headers))
    model.setHorizontalHeaderLabels(list(headers))
    view.setModel(model)
    view.setEditTriggers(_W.QAbstractItemView.NoEditTriggers)
    view.setSelectionBehavior(_W.QAbstractItemView.SelectRows)
    view.setSelectionMode(_W.QAbstractItemView.SingleSelection)
    view.setAlternatingRowColors(True)
    view.setShowGrid(False)
    view.verticalHeader().setVisible(False)
    view.verticalHeader().setDefaultSectionSize(34)
    hdr = view.horizontalHeader()
    # Pages that size *every* column (action-column tables) get a fixed layout
    # + horizontal scrollbar when narrow (never clipped). Tables without
    # explicit widths keep the old stretch-to-fill behaviour.
    fixed = bool(widths and len(widths) >= len(headers))
    hdr.setStretchLastSection(stretch is None and not fixed)
    hdr.setSectionsClickable(True)
    hdr.setSectionsMovable(False)
    hdr.setHighlightSections(False)
    hdr.setSortIndicatorShown(True)
    hdr.setCursor(_Core.Qt.PointingHandCursor)
    hdr.viewport().setCursor(_Core.Qt.PointingHandCursor)
    # RTL mirroring: Qt resolves AlignLeft/AlignRight against the widget's
    # layoutDirection. These headers are RightToLeft, so AlignLeft is the
    # *visual right* edge (AlignRight would paint the text on the left —
    # verified by _rtlprobe.py pixel measurements).
    hdr.setDefaultAlignment(_Core.Qt.AlignLeft | _Core.Qt.AlignVCenter)
    view._sort_col = -1
    view._sort_order = _Core.Qt.AscendingOrder
    hdr.sortIndicatorChanged.connect(
        lambda col, order, v=view: _apply_sort(v, col, order))
    if widths:
        for i, w in enumerate(widths):
            if i < len(headers):
                hdr.resizeSection(i, w)
    if stretch is not None and 0 <= stretch < len(headers):
        hdr.setSectionResizeMode(stretch, _W.QHeaderView.Stretch)
    view._num_cols = set(num_cols)
    view._col_count = len(headers)
    # Refit index widgets after every refill/scroll: during _reload the
    # view's layout for freshly inserted rows is still queued, so Qt's own
    # setIndexWidget sizing falls back to a stale (pre-polish) sizeHint and
    # the compact action buttons end up clipped inside their cells.
    # schedule_fit coalesces bursts (one pass per event-loop iteration).
    model.rowsInserted.connect(lambda *_a: view.schedule_fit())
    model.modelReset.connect(view.schedule_fit)
    view.verticalScrollBar().valueChanged.connect(
        lambda *_a: view.schedule_fit())
    view.horizontalScrollBar().valueChanged.connect(
        lambda *_a: view.schedule_fit())
    return view


def set_rows(view, rows):
    # type: (Any, Sequence[Sequence[Any]]) -> None
    """Fill a make_table() view. Callers pass display strings; ints render as
    Persian digits automatically. Numeric-looking text sorts by value."""
    model = view.model()
    model.removeRows(0, model.rowCount())
    for row in rows:
        items = [make_item(val) for val in row]
        model.appendRow(items)
    resort(view)


class PagerRow(_W.QWidget):
    """Paging strip with DIRECT page jump (no one-by-one walking):
    «first ‹prev [صفحه ▾] next› »last» plus a «نمایش ۵۱ تا ۱۰۰ از ۵۸۹»
    info label. The page chooser is a combo listing every page, so jumping
    from 1 to 12 is a single pick. Emits page_requested(0-based page)."""

    page_requested = _Core.Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setLayoutDirection(_Core.Qt.RightToLeft)
        self._page = 0
        self._pages = 1
        self._guard = False
        h = _W.QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)
        self.first_btn = self._nav_btn("«")
        self.prev_btn = self._nav_btn("‹")
        self.next_btn = self._nav_btn("›")
        self.last_btn = self._nav_btn("»")
        self.first_btn.clicked.connect(lambda: self._jump(0))
        self.prev_btn.clicked.connect(lambda: self._jump(self._page - 1))
        self.next_btn.clicked.connect(lambda: self._jump(self._page + 1))
        self.last_btn.clicked.connect(lambda: self._jump(self._pages - 1))
        self.combo = _W.QComboBox()
        self.combo.setMinimumWidth(86)
        self.combo.currentIndexChanged.connect(self._on_combo)
        of_lbl = _W.QLabel("از")
        of_lbl.setStyleSheet("color:#5d7385; font-size:11px;")
        self.total_pages_lbl = _W.QLabel("۱")
        self.total_pages_lbl.setStyleSheet("color:#5d7385; font-size:11px;")
        self.info = _W.QLabel("")
        self.info.setStyleSheet("color:#5d7385; font-size:11px;")
        h.addWidget(self.first_btn)
        h.addWidget(self.prev_btn)
        h.addWidget(self.combo)
        h.addWidget(of_lbl)
        h.addWidget(self.total_pages_lbl)
        h.addWidget(self.next_btn)
        h.addWidget(self.last_btn)
        h.addStretch(1)
        h.addWidget(self.info)

    @staticmethod
    def _nav_btn(text):
        b = _W.QPushButton(text)
        b.setProperty("variant", "link")
        b.setProperty("btnsize", "xs")
        b.setFixedWidth(34)
        b.setCursor(_Core.Qt.PointingHandCursor)
        return b

    def _jump(self, p0):
        if 0 <= p0 < self._pages and p0 != self._page:
            self.page_requested.emit(p0)

    def _on_combo(self, idx):
        if not self._guard and idx >= 0:
            self._jump(idx)

    def set_state(self, page, pages, first, last, total):
        """Refresh the strip (never emits page_requested).

        page is 0-based; first/last are the 1-based display range of the
        current slice (pass 0/0 when total == 0).
        """
        self._pages = max(1, int(pages))
        self._page = min(max(0, int(page)), self._pages - 1)
        self.first_btn.setEnabled(self._page > 0)
        self.prev_btn.setEnabled(self._page > 0)
        self.next_btn.setEnabled(self._page < self._pages - 1)
        self.last_btn.setEnabled(self._page < self._pages - 1)
        self.total_pages_lbl.setText(fa(self._pages))
        self._guard = True
        try:
            if self.combo.count() != self._pages:
                self.combo.clear()
                for i in range(self._pages):
                    self.combo.addItem("صفحه %s" % fa(i + 1))
            self.combo.setCurrentIndex(self._page)
        finally:
            self._guard = False
        if total <= 0:
            self.info.setText("هیچ موردی یافت نشد")
        else:
            self.info.setText("نمایش %s تا %s از %s" % (
                fa(first), fa(last), fa(total)))


def row_of(view, row):
    # type: (Any, int) -> List[str]
    model = view.model()
    return [model.item(row, c).text() if model.item(row, c) else ""
            for c in range(model.columnCount())]


def selected_row(view):
    # type: (Any) -> int
    idx = view.selectionModel().selectedRows()
    return idx[0].row() if idx else -1


def vline():
    sp = _W.QFrame()
    sp.setFrameShape(_W.QFrame.VLine)
    sp.setStyleSheet("color:#dbe4ea;")
    return sp


def hline():
    sp = _W.QFrame()
    sp.setFrameShape(_W.QFrame.HLine)
    sp.setStyleSheet("color:#dbe4ea;")
    return sp


def scroll_area():
    area = _W.QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(_W.QFrame.NoFrame)
    area.setHorizontalScrollBarPolicy(_Core.Qt.ScrollBarAlwaysOff)
    return area


def page_shell():
    """Returns (scroll_area, content_layout) for a page body."""
    area = scroll_area()
    inner = _W.QWidget()
    inner.setLayoutDirection(_Core.Qt.RightToLeft)
    v = _W.QVBoxLayout(inner)
    v.setContentsMargins(4, 4, 4, 4)
    v.setSpacing(14)
    area.setWidget(inner)
    return area, v


def tile_row(tiles):
    # type: (Sequence) -> Any
    """Row of KPI tiles like the web's .card-grid.

    *tiles* is a sequence of ``(label, value, role)`` tuples; role in
    info/success/danger/warning/accent (see theme.stat_tile).
    """
    from ..theme import stat_tile
    box = _W.QWidget()
    h = _W.QHBoxLayout(box)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(10)
    for title, value, role in tiles:
        h.addWidget(stat_tile(title, value, role), 1)
    return box


def muted(text):
    # type: (str) -> Any
    lab = _W.QLabel(text)
    lab.setObjectName("sectionSub")
    lab.setStyleSheet("")
    lab.setWordWrap(True)
    return lab


def field_row(label_widget, field_widget, label_min=90):
    h = _W.QHBoxLayout()
    lab = _W.QLabel(label_widget) if isinstance(label_widget, str) else label_widget
    if isinstance(lab, _W.QLabel):
        lab.setProperty("role", "flabel")
        lab.setMinimumWidth(label_min)
    h.addWidget(lab)
    h.addWidget(field_widget, 1)
    return h


# --------------------------------------------------------------------------- #
# ECG pulse traces (the web design's signature accent)
# --------------------------------------------------------------------------- #

# register-ribbon tile: one heartbeat per 132px, 12px tall (web --ecg-tile)
_RIBBON_PTS = [(0, 8), (44, 8), (48, 2), (53, 11), (58, 0), (62, 6),
               (65, 8), (132, 8)]
# dashboard hero trace: 600x44 viewBox (web .ph-ecg)
_HERO_PTS = [(0, 26), (170, 26), (179, 13), (190, 33), (203, 7), (212, 22),
             (219, 26), (600, 26)]
# login masthead rule: 440x26 viewBox (web .lm-rule)
_RULE_PTS = [(0, 17), (150, 17), (158, 7), (168, 23), (179, 2), (188, 14),
             (195, 17), (440, 17)]


def _poly(points, sx, sy):
    path = _Gui.QPainterPath()
    path.moveTo(points[0][0] * sx, points[0][1] * sy)
    for x, y in points[1:]:
        path.lineTo(x * sx, y * sy)
    return path


class EcgRibbon(_W.QWidget):
    """The 12px white strip with a repeating pulse-red ECG trace that runs
    across the top of the working area (web .register-ribbon)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(12)

    def paintEvent(self, event):  # noqa: N802
        p = _Gui.QPainter(self)
        p.setRenderHint(_Gui.QPainter.Antialiasing, True)
        p.fillRect(self.rect(), _Gui.QColor("#ffffff"))
        w = self.width()
        tile = _poly(_RIBBON_PTS, 1.0, 1.0)
        pen = _Gui.QPen(_Gui.QColor("#e24c5a"), 1.6)
        pen.setJoinStyle(_Core.Qt.RoundJoin)
        pen.setCapStyle(_Core.Qt.RoundCap)
        p.setPen(pen)
        p.setBrush(_Core.Qt.NoBrush)
        x = 0
        while x < w:
            p.save()
            p.translate(x, 0)
            p.drawPath(tile)
            p.restore()
            x += 132
        p.setPen(_Gui.QPen(_Gui.QColor("#dbe4ea"), 1))
        p.drawLine(0, self.height() - 1, w, self.height() - 1)
        p.end()


class EcgTrace(_W.QWidget):
    """A single stretch-to-fit heartbeat (web .ph-ecg / .lm-rule)."""

    def __init__(self, parent=None, variant="hero", height=44):
        super().__init__(parent)
        self._pts = {"hero": _HERO_PTS, "rule": _RULE_PTS}[variant]
        self._vb = (600.0, 44.0) if variant == "hero" else (440.0, 26.0)
        self._pulse_only = variant == "rule"
        self.setMinimumHeight(height)
        self.setSizePolicy(_W.QSizePolicy.Expanding, _W.QSizePolicy.Expanding)

    def paintEvent(self, event):  # noqa: N802
        p = _Gui.QPainter(self)
        p.setRenderHint(_Gui.QPainter.Antialiasing, True)
        sx = self.width() / self._vb[0]
        sy = self.height() / self._vb[1]
        path = _poly(self._pts, sx, sy)
        if not self._pulse_only:
            pen = _Gui.QPen(_Gui.QColor("#c6d3dc"), 1.5)
            pen.setJoinStyle(_Core.Qt.RoundJoin)
            pen.setCapStyle(_Core.Qt.RoundCap)
            p.setPen(pen)
            p.drawPath(path)
        pen = _Gui.QPen(_Gui.QColor("#e24c5a"), 2.0)
        pen.setJoinStyle(_Core.Qt.RoundJoin)
        pen.setCapStyle(_Core.Qt.RoundCap)
        p.setPen(pen)
        p.drawPath(path)
        p.end()
