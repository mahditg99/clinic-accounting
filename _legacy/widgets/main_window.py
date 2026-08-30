# -*- coding: utf-8 -*-
"""Main window — commercial shell: gradient app bar + sidebar navigation.

The native QTabWidget tab bar is hidden and replaced by a styled sidebar that
drives the same QTabWidget. Keeping ``self.tabs`` as a QTabWidget preserves the
existing API (:meth:`count`, :meth:`tabText`, :meth:`widget`) that pages and
tests rely on.
"""
from __future__ import annotations

from typing import Optional

from ..utils import Qt
from .. import settings as settings_mod
from .. import date_utils
from .invoice_page import InvoicePage
from .archive_page import ArchivePage
from .products_page import ProductsPage
from .patients_page import PatientsPage
from .daily_report_page import DailyReportPage
from .income_expense_page import IncomeExpensePage
from .expenses_page import ExpensesPage
from .doctor_report_page import DoctorReportPage
from .financial_reports_page import FinancialReportsPage
from .doctors_page import DoctorsPage
from .settings_page import SettingsPage

_Widgets = Qt.QtWidgets
_Core = Qt.QtCore
_Gui = Qt.QtGui


TAB_NEW_INVOICE = "فاکتور جدید"
TAB_ARCHIVE = "آرشیو فاکتورها"
TAB_PRODUCTS = "فهرست محصولات"
TAB_PATIENTS = "پرونده‌ها"
TAB_DAILY = "گزارش‌گیری روزانه"
TAB_INCOME = "گزارش درآمد/هزینه"
TAB_EXPENSES = "هزینه‌ها"
TAB_FINANCIAL = "گزارش‌های مالی"
TAB_DOCTORS = "گزارش پزشکان"
TAB_DOCTORS_LIST = "فهرست پزشکان"
TAB_SETTINGS = "تنظیمات"

# Sidebar order == tab order (drives setCurrentIndex by row).
_ORDER = [TAB_NEW_INVOICE, TAB_ARCHIVE, TAB_PRODUCTS, TAB_PATIENTS,
          TAB_DAILY, TAB_INCOME, TAB_EXPENSES, TAB_FINANCIAL,
          TAB_DOCTORS, TAB_DOCTORS_LIST, TAB_SETTINGS]


class MainWindow(_Widgets.QMainWindow):
    def __init__(self):
        # type: () -> None
        super(MainWindow, self).__init__()
        from ..utils import make_rtl, best_persian_font
        make_rtl(self)
        self.setLayoutDirection(_Core.Qt.RightToLeft)
        self.setFont(_Gui.QFont(best_persian_font(), 10))
        self.update_window_title()
        self.resize(1180, 800)

        # ---------------- Shell ----------------
        central = _Widgets.QWidget()
        self.setCentralWidget(central)
        root = _Widgets.QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # App bar (gradient brand strip).
        root.addWidget(self._build_app_bar())
        root.addLayout(self._build_body())

    # ------------------------------------------------------------------ #
    # Shell construction
    # ------------------------------------------------------------------ #
    def _build_app_bar(self):
        # type: () -> _Widgets.QFrame
        from ..theme import app_bar_title
        bar = _Widgets.QFrame()
        bar.setObjectName("appBar")
        bar.setFixedHeight(60)
        lay = _Widgets.QHBoxLayout(bar)
        lay.setContentsMargins(0, 0, 6, 0)
        lay.setSpacing(8)
        app_title = settings_mod.get_setting("app_title", "آذران طب")
        lay.addWidget(app_bar_title(app_title, "حسابداری کلینیک"))
        lay.addStretch(1)
        date_lbl = _Widgets.QLabel("امروز: " + date_utils.today_jalali_str())
        date_lbl.setObjectName("appDate")
        date_lbl.setStyleSheet("")
        date_lbl.setAlignment(_Core.Qt.AlignVCenter)
        lay.addWidget(date_lbl, 0, _Core.Qt.AlignRight)
        lay.addSpacing(18)
        return bar

    def _build_body(self):
        # type: () -> _Widgets.QHBoxLayout
        from ..theme import sidebar_nav
        body = _Widgets.QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        # Sidebar navigation (drives the hidden-tabbar QTabWidget).
        self.sidebar = sidebar_nav(list(_ORDER))
        self.sidebar.setFixedWidth(210)
        self.sidebar.currentRowChanged.connect(self._on_sidebar_changed)
        body.addWidget(self.sidebar)

        # Content host: a padded surface holding the (tab-bar-hidden) tabs.
        host = _Widgets.QWidget()
        host_lay = _Widgets.QVBoxLayout(host)
        host_lay.setContentsMargins(16, 16, 16, 16)
        host_lay.setSpacing(0)

        self.tabs = _Widgets.QTabWidget()
        self.tabs.setLayoutDirection(_Core.Qt.RightToLeft)
        self.tabs.setTabPosition(_Widgets.QTabWidget.North)
        # Native tab bar is hidden; navigation is via the sidebar.
        self.tabs.tabBar().setVisible(False)

        self.invoice_page = InvoicePage(self)
        self.archive_page = ArchivePage(self)
        self.products_page = ProductsPage(self)
        self.patients_page = PatientsPage(self)
        self.daily_page = DailyReportPage(self)
        self.income_page = IncomeExpensePage(self)
        self.expenses_page = ExpensesPage(self)
        self.financial_page = FinancialReportsPage(self)
        self.doctor_page = DoctorReportPage(self)
        self.doctors_page = DoctorsPage(self)
        self.settings_page = SettingsPage(self)

        self.tabs.addTab(self.invoice_page, TAB_NEW_INVOICE)
        self.tabs.addTab(self.archive_page, TAB_ARCHIVE)
        self.tabs.addTab(self.products_page, TAB_PRODUCTS)
        self.tabs.addTab(self.patients_page, TAB_PATIENTS)
        self.tabs.addTab(self.daily_page, TAB_DAILY)
        self.tabs.addTab(self.income_page, TAB_INCOME)
        self.tabs.addTab(self.expenses_page, TAB_EXPENSES)
        self.tabs.addTab(self.financial_page, TAB_FINANCIAL)
        self.tabs.addTab(self.doctor_page, TAB_DOCTORS)
        self.tabs.addTab(self.doctors_page, TAB_DOCTORS_LIST)
        self.tabs.addTab(self.settings_page, TAB_SETTINGS)

        self.tabs.currentChanged.connect(self._on_tab_changed)
        host_lay.addWidget(self.tabs)
        body.addWidget(host, 1)
        return body

    # ------------------------------------------------------------------ #
    # Navigation
    # ------------------------------------------------------------------ #
    def _on_sidebar_changed(self, row):
        # type: (int) -> None
        if 0 <= row < self.tabs.count():
            self.tabs.setCurrentIndex(row)

    def _on_tab_changed(self, index):
        # type: (int) -> None
        # Keep the sidebar highlight in sync (block its signal recursion).
        if self.sidebar.currentRow() != index:
            self.sidebar.blockSignals(True)
            self.sidebar.setCurrentRow(index)
            self.sidebar.blockSignals(False)
        widget = self.tabs.widget(index)
        try:
            if widget is self.archive_page:
                self.archive_page.refresh()
            elif widget is self.products_page:
                self.products_page.refresh()
            elif widget is self.patients_page:
                self.patients_page.refresh()
            elif widget is self.daily_page:
                pass
            elif widget is self.income_page:
                self.income_page._show_report()  # noqa
            elif widget is self.expenses_page:
                self.expenses_page.refresh()
            elif widget is self.doctor_page:
                self.doctor_page.refresh_doctors()
            elif widget is self.doctors_page:
                self.doctors_page.refresh()
            elif widget is self.invoice_page:
                self.invoice_page.refresh()
            elif widget is self.settings_page:
                self.settings_page._load_settings()  # noqa
        except Exception:
            pass

    def update_window_title(self):
        # type: () -> None
        app_title = settings_mod.get_setting("app_title", "آذران طب")
        self.setWindowTitle("نرم‌افزار حسابداری کلینیک - %s" % app_title)

    def refresh_other_pages(self):
        # type: () -> None
        """Called after invoice changes to refresh dependent pages."""
        try:
            self.archive_page.refresh()
            self.products_page.refresh()
            self.patients_page.refresh()
        except Exception:
            pass

    def show_new_invoice_with_edit(self, invoice_id):
        # type: (int) -> None
        self.tabs.setCurrentWidget(self.invoice_page)
        self.invoice_page.load_invoice_for_edit(invoice_id)