# -*- coding: utf-8 -*-
"""Dashboard page — mirrors webapp/templates/dashboard.html (pulse hero)."""
from __future__ import annotations

from ..utils import Qt
from .. import models, database, date_utils, money_utils
from . import fields as F
from ..theme import card

_Core = Qt.QtCore
_Gui = Qt.QtGui
_W = Qt.QtWidgets

_QUICK = [
    ("فاکتور جدید", "ثبت خدمت یا محصول", "invoice",
     '<path d="M12 5v14M5 12h14"/>'),
    ("پرونده‌ها", "جستجوی بیماران", "patients",
     '<circle cx="9" cy="8" r="3.2"/>'
     '<path d="M3 20c.6-3.4 3-5 6-5s5.4 1.6 6 5"/>'
     '<path d="M16 3.5a3.2 3.2 0 0 1 1 6.2M17.5 15.1c2 .5 3.2 1.9 3.5 4.4"/>'),
    ("آرشیو فاکتورها", "مرور و چاپ", "archive",
     '<rect x="3" y="4" width="18" height="4" rx="1.5"/>'
     '<path d="M5 8v11a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8M10 12h4"/>'),
    ("گزارش روزانه", "خلاصه هر روز", "daily",
     '<rect x="3" y="5" width="18" height="16" rx="2"/>'
     '<path d="M8 3v4M16 3v4M3 10h18"/>'),
]


class _QuickTile(_W.QFrame):
    """Web .quick: icon square + title/sub, clickable."""

    def __init__(self, title, sub, inner, on_click, parent=None):
        super().__init__(parent)
        self.setObjectName("quick")
        self.setCursor(_Core.Qt.PointingHandCursor)
        self._on_click = on_click
        h = _W.QHBoxLayout(self)
        h.setContentsMargins(14, 12, 14, 12)
        h.setSpacing(12)
        ico = _W.QLabel()
        ico.setObjectName("qIco")
        ico.setFixedSize(38, 38)
        ico.setAlignment(_Core.Qt.AlignCenter)
        pm = None
        from .shell import _svg_icon
        pm = _svg_icon(inner, "#0d6e8c", px=20)
        if pm is not None:
            ico.setPixmap(pm)
        tv = _W.QVBoxLayout()
        tv.setSpacing(0)
        t = _W.QLabel(title)
        t.setObjectName("qTitle")
        s = _W.QLabel(sub)
        s.setObjectName("qSub")
        tv.addWidget(t)
        tv.addWidget(s)
        h.addWidget(ico, 0, _Core.Qt.AlignVCenter)
        h.addLayout(tv, 1)

    def mousePressEvent(self, ev):  # noqa: N802
        if ev.button() == _Core.Qt.LeftButton:
            self._on_click()
        super().mousePressEvent(ev)


class DashboardPage(_W.QWidget):
    def __init__(self, window):
        super().__init__(window)
        self.window_ = window
        self.setLayoutDirection(_Core.Qt.RightToLeft)
        area, v = F.page_shell()
        outer = _W.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(area)

        v.addWidget(self._build_hero())

        grid = _W.QHBoxLayout()
        grid.setSpacing(16)
        grid.addWidget(self._build_method_card(), 1)
        grid.addWidget(self._build_quick_card(), 1)
        v.addLayout(grid)

        v.addWidget(self._build_low_stock_card())
        v.addStretch(1)

    # ------------------------------------------------------------------ #
    def _build_hero(self):
        """Web .pulse-hero: white card, big ink figure + ECG trace, ledger."""
        hero = _W.QFrame()
        hero.setObjectName("hero")
        h = _W.QHBoxLayout(hero)
        h.setContentsMargins(24, 20, 24, 14)
        h.setSpacing(28)

        main = _W.QWidget()
        mv = _W.QVBoxLayout(main)
        mv.setContentsMargins(0, 0, 0, 0)
        mv.setSpacing(2)
        lab = _W.QLabel("دریافتی امروز")
        lab.setObjectName("heroLabel")
        vrow = _W.QHBoxLayout()
        vrow.setSpacing(8)
        self.hero_value = _W.QLabel("۰")
        self.hero_value.setObjectName("heroValue")
        unit = _W.QLabel("تومان")
        unit.setObjectName("heroUnit")
        vrow.addWidget(self.hero_value, 0, _Core.Qt.AlignBottom)
        vrow.addWidget(unit, 0, _Core.Qt.AlignBottom)
        vrow.addStretch(1)
        mv.addLayout(vrow)
        mv.addWidget(F.EcgTrace(variant="hero", height=44), 1)
        h.addWidget(main, 3)

        div = _W.QFrame()
        div.setFrameShape(_W.QFrame.VLine)
        div.setStyleSheet("color:#dbe4ea;")
        h.addWidget(div)

        ledger = _W.QWidget()
        ledger.setFixedWidth(280)
        lgv = _W.QVBoxLayout(ledger)
        lgv.setContentsMargins(0, 6, 0, 6)
        lgv.setSpacing(0)
        self.ledger_rows = {}
        specs = [("invoices", "فاکتورهای امروز"),
                 ("patients", "بیماران فعال"),
                 ("all_invoices", "کل فاکتورها"),
                 ("receivable", "بستانکار کل — بدهی بیماران")]
        for i, (key, label) in enumerate(specs):
            row = _W.QHBoxLayout()
            t = _W.QLabel(label)
            t.setObjectName("heroRowLast" if i == len(specs) - 1 else "heroRow")
            val = _W.QLabel("—")
            val.setObjectName("heroRowValLast" if i == len(specs) - 1
                              else "heroRowVal")
            row.addWidget(t)
            row.addStretch(1)
            row.addWidget(val)
            lgv.addLayout(row)
            self.ledger_rows[key] = val
        h.addWidget(ledger, 2)
        hero.setMinimumHeight(150)
        return hero

    def _build_method_card(self):
        box = _W.QWidget()
        v = _W.QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)
        v.addWidget(F.card_title("دریافتی امروز بر اساس روش پرداخت"))
        self.method_table = F.make_table(["روش پرداخت", "تعداد", "مبلغ (تومان)"],
                                         num_cols=(1, 2),
                                         widths=[150, 80, 130], stretch=0)
        self.method_table.setMinimumHeight(180)
        self.method_empty = _W.QLabel(
            "هنوز پرداختی امروز ثبت نشده — برای شروع، فاکتور جدید بسازید.")
        self.method_empty.setObjectName("emptyState")
        self.method_empty.setAlignment(_Core.Qt.AlignCenter)
        self.method_empty.setWordWrap(True)
        v.addWidget(self.method_table)
        v.addWidget(self.method_empty)
        return card(box)

    def _build_quick_card(self):
        box = _W.QWidget()
        v = _W.QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)
        v.addWidget(F.card_title("دسترسی سریع"))
        grid = _W.QGridLayout()
        grid.setSpacing(10)
        for i, (title, sub, key, inner) in enumerate(_QUICK):
            tile = _QuickTile(title, sub, inner,
                              lambda k=key: self.window_.goto(k))
            grid.addWidget(tile, i // 2, i % 2)
        v.addLayout(grid)
        v.addStretch(1)
        return card(box)

    def _build_low_stock_card(self):
        box = _W.QWidget()
        v = _W.QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)
        v.addWidget(F.card_title("محصولات رو به اتمام یا بدون موجودی"))
        self.low_table = F.make_table(
            ["نام محصول", "قیمت فروش", "موجودی", "سطح هشدار", "وضعیت"],
            num_cols=(1, 2, 3),
            widths=[180, 125, 100, 125, 100], stretch=0)
        self.low_table.setMinimumHeight(160)
        self.low_empty = _W.QLabel("موجودی همه محصولات کافی است.")
        self.low_empty.setObjectName("emptyState")
        self.low_empty.setAlignment(_Core.Qt.AlignCenter)
        v.addWidget(self.low_table)
        v.addWidget(self.low_empty)
        return card(box)

    # ------------------------------------------------------------------ #
    def refresh(self):
        today = date_utils.today_iso()
        daily = models.daily_report(today)
        self.hero_value.setText(money_utils.format_money_persian(daily["total"]))

        rows = [[m["method"], m["count"],
                 money_utils.format_money_persian(m["total"])]
                for m in daily["by_method"]]
        F.set_rows(self.method_table, rows)
        self.method_table.setVisible(bool(rows))
        self.method_empty.setVisible(not rows)

        patients = [p for p in models.list_patients() if p["is_active"]]
        products = models.list_products(active_only=True)
        low = [p for p in products
               if int(p["stock"]) <= int(p["low_stock_warning"] or 0)]
        archive = models.list_archive_invoices(date_from=today, date_to=today)
        conn = database.get_connection()
        try:
            invoice_count = conn.execute(
                "SELECT COUNT(*) FROM invoices WHERE is_deleted = 0"
            ).fetchone()[0]
            receivable = conn.execute(
                "SELECT COALESCE(SUM(i.total_amount),0) - "
                "(SELECT COALESCE(SUM(pm.amount),0) FROM payments pm "
                " JOIN invoices i2 ON i2.id = pm.invoice_id "
                " WHERE i2.is_deleted = 0) "
                "FROM invoices i WHERE i.is_deleted = 0").fetchone()[0]
        finally:
            conn.close()
        self.ledger_rows["invoices"].setText(F.fa(len(archive)))
        self.ledger_rows["patients"].setText(F.fa(len(patients)))
        self.ledger_rows["all_invoices"].setText(F.fa(invoice_count))
        self.ledger_rows["receivable"].setText(
            money_utils.format_money_persian(int(receivable)))

        model = self.low_table.model()
        model.removeRows(0, model.rowCount())
        for p in low:
            out = int(p["stock"]) <= 0
            status = "بدون موجودی" if out else "کم"
            items = [
                _cell(p["title"]),
                _cell(money_utils.format_money_persian(p["sale_price"])),
                _cell(F.fa(p["stock"])),
                _cell(F.fa(p["low_stock_warning"])),
                _cell(status),
            ]
            tone = _Gui.QColor("#fbe9eb" if out else "#fbf1dd")
            for it in items:
                it.setBackground(tone)
            items[4].setForeground(_Gui.QColor("#c03b4a" if out else "#b97a1c"))
            model.appendRow(items)
        F.resort(self.low_table)
        self.low_table.setVisible(bool(low))
        self.low_empty.setVisible(not low)


def _cell(text):
    return F.make_item(text)
