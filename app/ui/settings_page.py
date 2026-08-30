# -*- coding: utf-8 -*-
"""Settings page — mirrors webapp/templates/settings.html."""
from __future__ import annotations

import datetime as _dt
import os
import shutil

from ..utils import Qt, confirm_msg, error_msg, info_msg
from .. import database, settings as settings_mod, date_utils, money_utils
from . import fields as F
from ..theme import card, primary, success

_Core = Qt.QtCore
_Gui = Qt.QtGui
_W = Qt.QtWidgets


class _ListEditor(_W.QWidget):
    """Editable name list (web's .list-editor): rows + add input + save."""

    def __init__(self, parent=None, add_placeholder=""):
        super().__init__(parent)
        v = _W.QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)
        self.rows_box = _W.QWidget()
        self.rows_lay = _W.QVBoxLayout(self.rows_box)
        self.rows_lay.setContentsMargins(0, 0, 0, 0)
        self.rows_lay.setSpacing(6)
        v.addWidget(self.rows_box)
        h = _W.QHBoxLayout()
        h.setSpacing(8)
        # keyword on purpose: FaLineEdit(str) would hit the QLineEdit(text)
        # overload and pre-fill the box instead of showing a placeholder.
        self.input = F.FaLineEdit(placeholder=add_placeholder)
        h.addWidget(self.input, 1)
        add_btn = _W.QPushButton("افزودن")
        add_btn.clicked.connect(self._add)
        h.addWidget(add_btn)
        v.addLayout(h)
        self._items = []

    def set_items(self, items):
        self._items = list(items)
        self._render()

    def items(self):
        return list(self._items)

    def _add(self):
        val = self.input.value().strip()
        if not val:
            error_msg(self, "مقدار را وارد کنید.")
            return
        if val in self._items:
            error_msg(self, "این مورد قبلا وجود دارد.")
            return
        self._items.append(val)
        self.input.clear()
        self._render()

    def _remove(self, idx):
        if 0 <= idx < len(self._items):
            del self._items[idx]
            self._render()

    def _render(self):
        while self.rows_lay.count():
            item = self.rows_lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        for i, name in enumerate(self._items):
            row = _W.QFrame()
            row.setObjectName("listRow")
            h = _W.QHBoxLayout(row)
            h.setContentsMargins(10, 6, 10, 6)
            h.setSpacing(8)
            lab = _W.QLabel(name)
            h.addWidget(lab, 1)
            btn = _W.QPushButton("حذف")
            btn.setProperty("variant", "link")
            btn.setProperty("tone", "danger")
            btn.clicked.connect(lambda _=False, i=i: self._remove(i))
            h.addWidget(btn)
            self.rows_lay.addWidget(row)


class SettingsPage(_W.QWidget):
    def __init__(self, window):
        super().__init__(window)
        self.window_ = window
        self.setLayoutDirection(_Core.Qt.RightToLeft)

        outer = _W.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        area, v = F.page_shell()
        outer.addWidget(area)
        v.addWidget(F.page_header("تنظیمات"))

        # ---------------- General card ----------------
        g_box = _W.QWidget()
        gv = _W.QVBoxLayout(g_box)
        gv.setContentsMargins(0, 0, 0, 0)
        gv.setSpacing(10)
        gv.addWidget(F.card_title("تنظیمات عمومی"))
        grid = _W.QGridLayout()
        grid.setSpacing(8)
        grid.addWidget(_W.QLabel("عنوان برنامه"), 0, 0)
        self.title_edit = _W.QLineEdit()
        self.title_edit.setMinimumWidth(220)
        grid.addWidget(self.title_edit, 0, 1)
        grid.addWidget(_W.QLabel("اندازه چاپ"), 0, 2)
        self.size_combo = _W.QComboBox()
        self.size_combo.addItems(["A4", "A5"])
        grid.addWidget(self.size_combo, 0, 3)
        gv.addLayout(grid)
        self.chk_update_date = _W.QCheckBox(
            "به‌روزرسانی تاریخ صدور هنگام ویرایش فاکتور")
        self.chk_show_doctor = _W.QCheckBox("نمایش نام پزشک در چاپ")
        gv.addWidget(self.chk_update_date)
        gv.addWidget(self.chk_show_doctor)
        self.version_lbl = F.muted("")
        gv.addWidget(self.version_lbl)
        save_btn = primary(_W.QPushButton("ذخیره تنظیمات"), 140)
        save_btn.clicked.connect(self._save_general)
        gv.addWidget(save_btn, 0, _Core.Qt.AlignRight)
        v.addWidget(card(g_box))

        # ---------------- Payment methods ----------------
        m_box = _W.QWidget()
        mv = _W.QVBoxLayout(m_box)
        mv.setContentsMargins(0, 0, 0, 0)
        mv.setSpacing(10)
        mv.addWidget(F.card_title("روش‌های پرداخت"))
        self.methods_editor = _ListEditor(add_placeholder="روش پرداخت جدید")
        mv.addWidget(self.methods_editor)
        m_save = success(_W.QPushButton("ذخیره روش‌های پرداخت"), 170)
        m_save.clicked.connect(self._save_methods)
        mv.addWidget(m_save, 0, _Core.Qt.AlignRight)
        v.addWidget(card(m_box))

        # ---------------- Expense categories ----------------
        c_box = _W.QWidget()
        cv = _W.QVBoxLayout(c_box)
        cv.setContentsMargins(0, 0, 0, 0)
        cv.setSpacing(10)
        cv.addWidget(F.card_title("دسته‌بندی هزینه‌ها"))
        self.cats_editor = _ListEditor(add_placeholder="دسته هزینه جدید")
        cv.addWidget(self.cats_editor)
        c_save = success(_W.QPushButton("ذخیره دسته‌بندی‌ها"), 160)
        c_save.clicked.connect(self._save_categories)
        cv.addWidget(c_save, 0, _Core.Qt.AlignRight)
        v.addWidget(card(c_box))

        # ---------------- Backup card ----------------
        b_box = _W.QWidget()
        bv = _W.QVBoxLayout(b_box)
        bv.setContentsMargins(0, 0, 0, 0)
        bv.setSpacing(10)
        head = _W.QHBoxLayout()
        head.addWidget(F.card_title("پشتیبان‌گیری"))
        head.addWidget(F.muted("نسخه امن از کل اطلاعات"))
        head.addStretch(1)
        bv.addLayout(head)
        bv.addWidget(F.muted(
            "هر پشتیبان یک فایل کامل پایگاه داده است. پیش از بازیابی، به‌طور "
            "خودکار از وضعیت فعلی پشتیبان ساخته می‌شود."))
        mk_btn = primary(_W.QPushButton("تهیه پشتیبان فوری"), 160)
        mk_btn.clicked.connect(self._make_backup)
        bv.addWidget(mk_btn, 0, _Core.Qt.AlignRight)
        self.backup_table = F.make_table(
            ["تاریخ", "ساعت", "حجم", "فایل", "عملیات"],
            widths=[115, 85, 115, 320, 170])
        self.backup_table.setMinimumHeight(240)
        bv.addWidget(self.backup_table)
        v.addWidget(card(b_box))
        v.addStretch(1)

    # ------------------------------------------------------------------ #
    def refresh(self):
        self.title_edit.setText(settings_mod.get_setting(
            "app_title", "آذران طب") or "")
        self.size_combo.setCurrentText(
            settings_mod.get_setting("print_size", "A4") or "A4")
        self.chk_update_date.setChecked(settings_mod.get_setting(
            "update_invoice_date_on_edit", "0") == "1")
        self.chk_show_doctor.setChecked(settings_mod.get_setting(
            "show_doctor_in_print", "0") == "1")
        ver = settings_mod.get_setting("version", "")
        self.version_lbl.setText(("نسخه: " + F.fa(ver)) if ver else "")
        self.methods_editor.set_items(settings_mod.get_payment_methods())
        self.cats_editor.set_items(settings_mod.get_expense_categories())
        self._reload_backups()

    # ------------------------------------------------------------------ #
    def _save_general(self):
        title = self.title_edit.text().strip()
        if title:
            settings_mod.set_setting("app_title", title)
        settings_mod.set_setting(
            "update_invoice_date_on_edit",
            "1" if self.chk_update_date.isChecked() else "0")
        settings_mod.set_setting(
            "show_doctor_in_print",
            "1" if self.chk_show_doctor.isChecked() else "0")
        settings_mod.set_setting("print_size", self.size_combo.currentText())
        self.window_.refresh_brand()
        info_msg(self, "تنظیمات ذخیره شد")

    def _save_methods(self):
        new = self.methods_editor.items()
        for old in settings_mod.get_payment_methods():
            if old not in new and settings_mod.is_payment_method_used(old):
                error_msg(self, "روش پرداخت «%s» در فاکتورها استفاده شده "
                                "و قابل حذف نیست." % old)
                return
        settings_mod.set_payment_methods(new)
        self.methods_editor.set_items(new)
        info_msg(self, "ذخیره شد.")

    def _save_categories(self):
        new = self.cats_editor.items()
        for old in settings_mod.get_expense_categories():
            if old not in new and settings_mod.is_expense_category_used(old):
                error_msg(self, "دسته «%s» در هزینه‌ها استفاده شده "
                                "و قابل حذف نیست." % old)
                return
        settings_mod.set_expense_categories(new)
        self.cats_editor.set_items(new)
        info_msg(self, "ذخیره شد.")

    # ------------------------------------------------------------------ #
    def _list_backups(self):
        bdir = database._backup_dir()
        items = []
        if os.path.isdir(bdir):
            for name in os.listdir(bdir):
                if not (name.startswith(database.BACKUP_PREFIX)
                        and name.endswith(".db")):
                    continue
                path = os.path.join(bdir, name)
                try:
                    st = os.stat(path)
                except OSError:
                    continue
                when = _dt.datetime.fromtimestamp(st.st_mtime)
                items.append({
                    "name": name, "path": path,
                    "size_kb": max(1, int(round(st.st_size / 1024.0))),
                    "date": date_utils.iso_to_jalali_persian_str(
                        when.date().isoformat()),
                    "time": when.strftime("%H:%M"),
                    "mtime": st.st_mtime,
                })
        items.sort(key=lambda b: b["mtime"], reverse=True)
        return items

    def _reload_backups(self):
        backups = self._list_backups()
        self._backups = backups
        model = self.backup_table.model()
        self.backup_table.clearSpans()
        model.removeRows(0, model.rowCount())
        if not backups:
            item = _Gui.QStandardItem(
                "هنوز پشتیبانی وجود ندارد — با دکمه بالا اولین "
                "نسخه پشتیبان را بسازید.")
            item.setEditable(False)
            model.appendRow([item] + [_Gui.QStandardItem("")
                                      for _ in range(4)])
            model.setItem(0, 0, item)
            self.backup_table.setSpan(0, 0, 1, model.columnCount())
            return
        for b in backups:
            items = [
                self._cell(b["date"]),
                self._cell(F.fa(b["time"])),
                self._cell("%s کیلوبایت" % F.fa(b["size_kb"])),
                self._cell(b["name"]),
                self._cell(""),
            ]
            model.appendRow(items)
            rr = model.rowCount() - 1
            btns = _W.QWidget()
            h = _W.QHBoxLayout(btns)
            h.setContentsMargins(2, 0, 2, 0)
            h.setSpacing(4)
            b_dl = _W.QPushButton("دانلود")
            b_dl.setProperty("variant", "link")
            b_dl.setProperty("btnsize", "xs")
            b_dl.setCursor(_Core.Qt.PointingHandCursor)
            b_dl.clicked.connect(
                lambda _=False, p=b["path"], n=b["name"]: self._download(p, n))
            b_rs = _W.QPushButton("بازیابی")
            b_rs.setProperty("variant", "link")
            b_rs.setProperty("btnsize", "xs")
            b_rs.setProperty("tone", "warn")
            b_rs.setCursor(_Core.Qt.PointingHandCursor)
            b_rs.clicked.connect(lambda _=False, p=b["path"]: self._restore(p))
            b_rm = _W.QPushButton("حذف")
            b_rm.setProperty("variant", "link")
            b_rm.setProperty("btnsize", "xs")
            b_rm.setProperty("tone", "danger")
            b_rm.setCursor(_Core.Qt.PointingHandCursor)
            b_rm.clicked.connect(lambda _=False, p=b["path"]: self._delete_b(p))
            for x in (b_dl, b_rs, b_rm):
                h.addWidget(x, 0, _Core.Qt.AlignVCenter)
            h.addStretch(1)
            self.backup_table.setIndexWidget(model.index(rr, 4), btns)
        F.resort(self.backup_table)

    def _cell(self, text):
        return F.make_item(text)

    def _make_backup(self):
        path = database._backup_db()
        if path is None:
            error_msg(self, "پشتیبان‌گیری ناموفق بود؛ پایگاه داده در دسترس نیست")
            return
        info_msg(self, "پشتیبان جدید ساخته شد")
        self._reload_backups()

    def _download(self, path, name):
        target, _ = _W.QFileDialog.getSaveFileName(self, "ذخیره پشتیبان",
                                                   name, "پایگاه داده (*.db)")
        if not target:
            return
        try:
            shutil.copy2(path, target)
        except OSError:
            error_msg(self, "ذخیره فایل ممکن نشد")
            return
        info_msg(self, "پشتیبان ذخیره شد")

    def _restore(self, path):
        if not confirm_msg(self, "اطلاعات فعلی با این پشتیبان جایگزین شود؟\n\n"
                                 "نسخه امنی از وضعیت فعلی پیش از بازیابی "
                                 "ساخته می‌شود."):
            return
        database._backup_db()
        try:
            shutil.copy2(path, database._db_path())
        except OSError:
            error_msg(self, "بازیابی ممکن نشد")
            return
        info_msg(self, "اطلاعات از پشتیبان بازیابی شد")
        self._reload_backups()

    def _delete_b(self, path):
        if not confirm_msg(self, "این پشتیبان حذف شود؟"):
            return
        try:
            os.remove(path)
        except OSError:
            error_msg(self, "حذف فایل ممکن نشد")
            return
        info_msg(self, "پشتیبان حذف شد")
        self._reload_backups()
