# -*- coding: utf-8 -*-
"""Doctors page — mirrors webapp/templates/doctors.html."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..utils import Qt, confirm_msg, warning_msg
from .. import settings as settings_mod
from . import fields as F
from ..theme import card, success

_Core = Qt.QtCore
_Gui = Qt.QtGui
_W = Qt.QtWidgets


class DoctorsPage(_W.QWidget):
    def __init__(self, window):
        super().__init__(window)
        self.window_ = window
        self.setLayoutDirection(_Core.Qt.RightToLeft)
        self._editing_id = None  # type: Optional[int]
        self._all = []  # type: List[Dict[str, Any]]

        outer = _W.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        area, v = F.page_shell()
        outer.addWidget(area)
        v.addWidget(F.page_header("پزشکان", "مدیریت پزشکان معرف"))
        v.addWidget(self._build_form_card())
        v.addWidget(self._build_table_card())
        v.addStretch(1)

    # ------------------------------------------------------------------ #
    def _build_form_card(self):
        box = _W.QWidget()
        v = _W.QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)
        self.form_title = F.card_title("افزودن پزشک")
        v.addWidget(self.form_title)
        grid = _W.QGridLayout()
        grid.setSpacing(8)
        self.first = _W.QLineEdit()
        self.last = _W.QLineEdit()
        self.specialty = _W.QLineEdit()
        self.address = _W.QLineEdit()
        self.phone = F.FaLineEdit()
        self.phone.setMaxLength(15)
        for w in (self.first, self.last, self.specialty, self.address):
            w.setLayoutDirection(_Core.Qt.RightToLeft)
        specs = [("نام", self.first), ("نام خانوادگی", self.last),
                 ("تخصص", self.specialty), ("آدرس مطب", self.address),
                 ("شماره تلفن", self.phone)]
        for i, (label, w) in enumerate(specs):
            lab = _W.QLabel(label)
            lab.setStyleSheet("color:#5d7385; font-size:11px; font-weight:700;")
            grid.addWidget(lab, 0, i * 2)
            grid.addWidget(w, 1, i * 2, 1, 2)
        v.addLayout(grid)
        row = _W.QHBoxLayout()
        self.err = _W.QLabel("")
        self.err.setStyleSheet("color:#c03b4a; font-size:11px;")
        row.addWidget(self.err)
        row.addStretch(1)
        self.cancel_btn = _W.QPushButton("انصراف")
        self.cancel_btn.clicked.connect(self._reset_form)
        self.cancel_btn.hide()
        self.save_btn = success(_W.QPushButton("افزودن"), 110)
        self.save_btn.clicked.connect(self._save)
        row.addWidget(self.cancel_btn)
        row.addWidget(self.save_btn)
        v.addLayout(row)
        return card(box)

    def _build_table_card(self):
        box = _W.QWidget()
        v = _W.QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)
        head = _W.QHBoxLayout()
        head.addWidget(F.card_title("فهرست پزشکان"))
        head.addStretch(1)
        self.filter_edit = F.SearchEdit(placeholder="جستجو در نام، تخصص، تلفن…")
        self.filter_edit.setFixedWidth(260)
        self.filter_edit.textChanged.connect(lambda _: self._render())
        head.addWidget(self.filter_edit)
        v.addLayout(head)
        self.table = F.make_table(
            ["نام", "نام خانوادگی", "تخصص", "آدرس", "تلفن", "وضعیت", "عملیات"],
            widths=[130, 140, 155, 180, 150, 95, 210], stretch=3)
        self.table.setMinimumHeight(300)
        v.addWidget(self.table)
        self.count_lbl = _W.QLabel("")
        self.count_lbl.setStyleSheet("color:#5d7385; font-size:11px;")
        v.addWidget(self.count_lbl)
        return card(box)

    # ------------------------------------------------------------------ #
    def refresh(self):
        self._all = settings_mod.list_doctors(active_only=False)
        self._render()

    def _render(self):
        q = self.filter_edit.text()
        model = self.table.model()
        model.removeRows(0, model.rowCount())
        shown = 0
        no_doc = settings_mod.get_no_doctor_id()
        for d in self._all:
            first = d.get("first_name") or d["name"]
            last = d.get("last_name") or ""
            cells = [first, last, d.get("specialty") or "",
                     d.get("address") or "", d.get("phone") or ""]
            if not F.match_words(q, *cells):
                continue
            shown += 1
            active = bool(d["is_active"])
            status = "فعال" if active else "غیرفعال"
            items = [self._cell(F.fa(first)), self._cell(F.fa(last)),
                     self._cell(d.get("specialty") or "—"),
                     self._cell(d.get("address") or "—"),
                     self._cell(F.fa(d.get("phone") or "—")),
                     self._cell(status), self._cell("")]
            items[5].setForeground(_Gui.QColor("#2e8b6a" if active else "#5d7385"))
            model.appendRow(items)
            r = model.rowCount() - 1
            btns = _W.QWidget()
            h = _W.QHBoxLayout(btns)
            h.setContentsMargins(2, 0, 2, 0)
            h.setSpacing(4)
            if d["id"] == no_doc or settings_mod.is_no_doctor(d["name"]):
                lbl = _W.QLabel("پیش‌فرض")
                lbl.setStyleSheet("color:#5d7385; font-weight:700;")
                h.addWidget(lbl)
            else:
                b_edit = _W.QPushButton("ویرایش")
                b_edit.setProperty("variant", "link")
                b_edit.setProperty("btnsize", "xs")
                b_edit.setCursor(_Core.Qt.PointingHandCursor)
                b_edit.clicked.connect(lambda _=False, dd=d: self._load_for_edit(dd))
                h.addWidget(b_edit, 0, _Core.Qt.AlignVCenter)
                if active:
                    b_deact = _W.QPushButton("غیرفعال")
                    b_deact.setProperty("variant", "link")
                    b_deact.setProperty("btnsize", "xs")
                    b_deact.setProperty("tone", "warn")
                    b_deact.setCursor(_Core.Qt.PointingHandCursor)
                    b_deact.clicked.connect(
                        lambda _=False, pid=d["id"]: self._deactivate(pid))
                    h.addWidget(b_deact, 0, _Core.Qt.AlignVCenter)
                b_del = _W.QPushButton("حذف")
                b_del.setProperty("variant", "link")
                b_del.setProperty("btnsize", "xs")
                b_del.setProperty("tone", "danger")
                b_del.setCursor(_Core.Qt.PointingHandCursor)
                b_del.clicked.connect(lambda _=False, pid=d["id"]: self._delete(pid))
                h.addWidget(b_del, 0, _Core.Qt.AlignVCenter)
            h.addStretch(1)
            self.table.setIndexWidget(model.index(r, 6), btns)
        F.resort(self.table)
        self.count_lbl.setText("نمایش %s پزشک از %s" % (
            F.fa(shown), F.fa(len(self._all))))
        if shown == 0 and q:
            self.count_lbl.setText("موردی با این جستجو یافت نشد.")

    def _cell(self, text):
        return F.make_item(text)

    # ------------------------------------------------------------------ #
    def _reset_form(self):
        self._editing_id = None
        for w in (self.first, self.last, self.specialty, self.address,
                  self.phone):
            w.clear()
        self.err.setText("")
        self.form_title.setText("افزودن پزشک")
        self.save_btn.setText("افزودن")
        self.cancel_btn.hide()

    def _load_for_edit(self, d):
        self._editing_id = d["id"]
        self.first.setText(d.get("first_name") or d["name"])
        self.last.setText(d.get("last_name") or "")
        self.specialty.setText(d.get("specialty") or "")
        self.address.setText(d.get("address") or "")
        self.phone.setText(F.fa(d.get("phone") or ""))
        self.err.setText("")
        self.form_title.setText("ویرایش پزشک")
        self.save_btn.setText("ذخیره تغییرات")
        self.cancel_btn.show()

    def _save(self):
        first = self.first.text().strip()
        last = self.last.text().strip()
        if not first and not last:
            self.err.setText("نام پزشک الزامی است.")
            return
        name = ("%s %s" % (first, last)).strip()
        try:
            if self._editing_id is None:
                settings_mod.add_doctor(
                    name, self.specialty.text().strip(),
                    self.address.text().strip(), self.phone.value().strip(),
                    first, last)
            else:
                settings_mod.update_doctor(
                    self._editing_id, name, self.specialty.text().strip(),
                    self.address.text().strip(), self.phone.value().strip(),
                    first, last)
        except Exception as exc:
            self.err.setText(str(exc))
            return
        self._reset_form()
        self.refresh()

    def _deactivate(self, doctor_id):
        if confirm_msg(self, "این پزشک غیرفعال شود؟"):
            settings_mod.deactivate_doctor(doctor_id)
            self.refresh()

    def _delete(self, doctor_id):
        if settings_mod.is_doctor_used(doctor_id):
            warning_msg(self, "این پزشک در فاکتورها استفاده شده و قابل حذف "
                              "نیست؛ می‌توانید غیرفعالش کنید.")
            return
        if confirm_msg(self, "پزشک برای همیشه حذف شود؟"):
            settings_mod.hard_delete_doctor(doctor_id)
            self.refresh()
