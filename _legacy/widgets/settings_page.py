# -*- coding: utf-8 -*-
"""تنظیمات - Settings page."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..utils import Qt
from .. import settings as settings_mod, models, date_utils

_Widgets = Qt.QtWidgets
_Core = Qt.QtCore
_Gui = Qt.QtGui


class _MethodsModel(_Core.QAbstractTableModel):
    HEADERS = ["روش پرداخت"]

    def __init__(self):
        # type: () -> None
        super(_MethodsModel, self).__init__()
        self._rows = []  # type: List[str]

    def set_rows(self, rows):
        # type: (List[str]) -> None
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def rows(self):
        # type: () -> List[str]
        return self._rows

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
        if role == _Core.Qt.DisplayRole:
            return self._rows[index.row()]
        if role == _Core.Qt.TextAlignmentRole:
            return _Core.Qt.AlignRight | _Core.Qt.AlignVCenter
        return None


class _CategoriesModel(_MethodsModel):
    HEADERS = ["دسته‌بندی"]


class SettingsPage(_Widgets.QWidget):
    def __init__(self, main_window=None):
        # type: (Optional[Any]) -> None
        super(SettingsPage, self).__init__()
        self._main = main_window
        from ..utils import make_rtl, best_persian_font
        make_rtl(self)
        self.setFont(_Gui.QFont(best_persian_font(), 10))
        self._methods_model = _MethodsModel()
        self._categories_model = _CategoriesModel()
        self._build_ui()
        self._load_settings()

    def _build_ui(self):
        layout = _Widgets.QVBoxLayout(self)
        title = _Widgets.QLabel("تنظیمات")
        title.setStyleSheet("font-size:16px; font-weight:bold;")
        title.setAlignment(_Core.Qt.AlignCenter)
        layout.addWidget(title)

        # General settings.
        general = _Widgets.QGroupBox("تنظیمات عمومی")
        g_layout = _Widgets.QFormLayout(general)
        self.app_title_edit = _Widgets.QLineEdit()
        self.app_title_edit.setAlignment(_Core.Qt.AlignRight)
        g_layout.addRow("عنوان برنامه", self.app_title_edit)
        self.version_label = _Widgets.QLabel("—")
        g_layout.addRow("نسخه", self.version_label)
        self.update_date_chk = _Widgets.QCheckBox(
            "در صورت آپدیت فاکتور، تاریخ فاکتور نیز آپدیت شود")
        g_layout.addRow(self.update_date_chk)
        self.show_doctor_chk = _Widgets.QCheckBox("نمایش نام پزشک در فاکتور چاپی")
        g_layout.addRow(self.show_doctor_chk)
        size_row = _Widgets.QHBoxLayout()
        self.size_a4 = _Widgets.QRadioButton("A4")
        self.size_a5 = _Widgets.QRadioButton("A5")
        self.size_a4.setChecked(True)
        size_row.addWidget(self.size_a4)
        size_row.addWidget(self.size_a5)
        size_row.addStretch(1)
        g_layout.addRow("اندازه چاپ", size_row)
        self.save_general_btn = _Widgets.QPushButton("ذخیره تنظیمات عمومی")
        self.save_general_btn.clicked.connect(self._save_general)
        g_layout.addRow(self.save_general_btn)
        layout.addWidget(general)

        # Payment methods.
        pay_group = _Widgets.QGroupBox("روش‌های پرداخت")
        pay_layout = _Widgets.QVBoxLayout(pay_group)
        add_pay_row = _Widgets.QHBoxLayout()
        add_pay_row.addWidget(_Widgets.QLabel("روش پرداخت:"))
        self.new_method_edit = _Widgets.QLineEdit()
        self.new_method_edit.setAlignment(_Core.Qt.AlignRight)
        add_pay_row.addWidget(self.new_method_edit, 1)
        self.add_method_btn = _Widgets.QPushButton("اضافه کن")
        self.add_method_btn.clicked.connect(self._add_method)
        add_pay_row.addWidget(self.add_method_btn)
        self.del_method_btn = _Widgets.QPushButton("حذف")
        self.del_method_btn.clicked.connect(self._delete_method)
        add_pay_row.addWidget(self.del_method_btn)
        pay_layout.addLayout(add_pay_row)

        self.methods_table = _Widgets.QTableView()
        self.methods_table.setModel(self._methods_model)
        self.methods_table.setSelectionBehavior(_Widgets.QTableView.SelectRows)
        self.methods_table.setSelectionMode(_Widgets.QTableView.SingleSelection)
        self.methods_table.setEditTriggers(_Widgets.QTableView.NoEditTriggers)
        self.methods_table.horizontalHeader().setStretchLastSection(True)
        self.methods_table.verticalHeader().setVisible(False)
        self.methods_table.verticalHeader().setDefaultSectionSize(26)
        pay_layout.addWidget(self.methods_table)
        layout.addWidget(pay_group)

        # Expense categories.
        cat_group = _Widgets.QGroupBox("دسته‌بندی هزینه‌ها")
        cat_layout = _Widgets.QVBoxLayout(cat_group)
        add_cat_row = _Widgets.QHBoxLayout()
        add_cat_row.addWidget(_Widgets.QLabel("دسته‌بندی:"))
        self.new_category_edit = _Widgets.QLineEdit()
        self.new_category_edit.setAlignment(_Core.Qt.AlignRight)
        add_cat_row.addWidget(self.new_category_edit, 1)
        self.add_category_btn = _Widgets.QPushButton("اضافه کن")
        self.add_category_btn.clicked.connect(self._add_category)
        add_cat_row.addWidget(self.add_category_btn)
        self.del_category_btn = _Widgets.QPushButton("حذف")
        self.del_category_btn.clicked.connect(self._delete_category)
        add_cat_row.addWidget(self.del_category_btn)
        cat_layout.addLayout(add_cat_row)

        self.categories_table = _Widgets.QTableView()
        self.categories_table.setModel(self._categories_model)
        self.categories_table.setSelectionBehavior(_Widgets.QTableView.SelectRows)
        self.categories_table.setSelectionMode(_Widgets.QTableView.SingleSelection)
        self.categories_table.setEditTriggers(_Widgets.QTableView.NoEditTriggers)
        self.categories_table.horizontalHeader().setStretchLastSection(True)
        self.categories_table.verticalHeader().setVisible(False)
        self.categories_table.verticalHeader().setDefaultSectionSize(26)
        cat_layout.addWidget(self.categories_table)
        layout.addWidget(cat_group)

        layout.addStretch(1)

    # ------------------------------------------------------------------ #
    def _load_settings(self):
        self.app_title_edit.setText(settings_mod.get_setting("app_title", "آذران طب"))
        self.version_label.setText(settings_mod.get_setting("version", "1.0.0"))
        self.update_date_chk.setChecked(
            settings_mod.get_setting("update_invoice_date_on_edit", "0") == "1")
        self.show_doctor_chk.setChecked(
            settings_mod.get_setting("show_doctor_in_print", "0") == "1")
        size = settings_mod.get_setting("print_size", "A4")
        if size == "A5":
            self.size_a5.setChecked(True)
        else:
            self.size_a4.setChecked(True)
        self._refresh_methods()
        self._refresh_categories()

    def _save_general(self):
        from ..utils import info_msg
        settings_mod.set_setting("app_title", self.app_title_edit.text().strip())
        settings_mod.set_setting("update_invoice_date_on_edit",
                                  "1" if self.update_date_chk.isChecked() else "0")
        settings_mod.set_setting("show_doctor_in_print",
                                  "1" if self.show_doctor_chk.isChecked() else "0")
        settings_mod.set_setting("print_size",
                                  "A5" if self.size_a5.isChecked() else "A4")
        info_msg(self, "تنظیمات ذخیره شد.")
        if self._main is not None:
            try:
                self._main.update_window_title()
            except Exception:
                pass

    # Payment methods.
    def _refresh_methods(self):
        self._methods_model.set_rows(settings_mod.get_payment_methods())

    def _add_method(self):
        from ..utils import error_msg, info_msg
        name = self.new_method_edit.text().strip()
        if name == "":
            error_msg(self, "روش پرداخت را وارد کنید.")
            return
        methods = settings_mod.get_payment_methods()
        if name in methods:
            error_msg(self, "این روش پرداخت قبلاً وجود دارد.")
            return
        methods.append(name)
        settings_mod.set_payment_methods(methods)
        self.new_method_edit.setText("")
        self._refresh_methods()
        info_msg(self, "روش پرداخت اضافه شد.")

    def _delete_method(self):
        from ..utils import error_msg, confirm_msg, info_msg
        idx = self.methods_table.currentIndex()
        if not idx.isValid():
            error_msg(self, "یک روش پرداخت انتخاب کنید.")
            return
        rows = self._methods_model.rows()
        method = rows[idx.row()]
        if settings_mod.is_payment_method_used(method):
            info_msg(self, "این روش در پرداخت‌ها استفاده شده و حذف آن ممکن نیست. "
                           "می‌توانید آن را در انتهای لیست نگه دارید.")
            return
        if confirm_msg(self, "این روش پرداخت حذف شود؟"):
            methods = [m for m in rows if m != method]
            settings_mod.set_payment_methods(methods)
            self._refresh_methods()
            info_msg(self, "روش پرداخت حذف شد.")

    # Expense categories.
    def _refresh_categories(self):
        self._categories_model.set_rows(settings_mod.get_expense_categories())

    def _add_category(self):
        from ..utils import error_msg, info_msg
        name = self.new_category_edit.text().strip()
        if name == "":
            error_msg(self, "نام دسته‌بندی را وارد کنید.")
            return
        cats = settings_mod.get_expense_categories()
        if name in cats:
            error_msg(self, "این دسته‌بندی قبلاً وجود دارد.")
            return
        cats.append(name)
        settings_mod.set_expense_categories(cats)
        self.new_category_edit.setText("")
        self._refresh_categories()
        info_msg(self, "دسته‌بندی اضافه شد.")

    def _delete_category(self):
        from ..utils import error_msg, confirm_msg, info_msg
        idx = self.categories_table.currentIndex()
        if not idx.isValid():
            error_msg(self, "یک دسته‌بندی انتخاب کنید.")
            return
        rows = self._categories_model.rows()
        category = rows[idx.row()]
        if settings_mod.is_expense_category_used(category):
            info_msg(self, "این دسته‌بندی در هزینه‌ها استفاده شده و حذف آن "
                           "امکان‌پذیر نیست.")
            return
        if confirm_msg(self, "این دسته‌بندی حذف شود؟"):
            cats = [c for c in rows if c != category]
            settings_mod.set_expense_categories(cats)
            self._refresh_categories()
            info_msg(self, "دسته‌بندی حذف شد.")
