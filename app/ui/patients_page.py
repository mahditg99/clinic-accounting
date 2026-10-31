# -*- coding: utf-8 -*-
"""Patients page — mirrors webapp/templates/patients.html."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..utils import Qt, warning_msg, confirm_msg, error_msg
from .. import models
from . import fields as F
from ..theme import card, primary, success, danger

_Core = Qt.QtCore
_Gui = Qt.QtGui
_W = Qt.QtWidgets

_GENDER_TO_FA = {"male": "آقا", "female": "خانم", "": ""}
_FA_TO_GENDER = {"آقا": "male", "خانم": "female", "": ""}


class PatientsPage(_W.QWidget):
    def __init__(self, window):
        super().__init__(window)
        self.window_ = window
        self.setLayoutDirection(_Core.Qt.RightToLeft)
        self._editing_id = None  # type: Optional[int]
        self._all = []  # type: List[Dict[str, Any]]
        self._total = 0

        outer = _W.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        area, v = F.page_shell()
        outer.addWidget(area)

        v.addWidget(F.page_header("پرونده‌های بیماران", "مدیریت پرونده‌های بیماران"))
        v.addWidget(self._build_form_card())
        v.addWidget(self._build_table_card())
        v.addStretch(1)

    # ------------------------------------------------------------------ #
    def _build_form_card(self):
        box = _W.QWidget()
        v = _W.QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)
        self.form_title = F.card_title("ثبت پرونده جدید")
        v.addWidget(self.form_title)

        grid = _W.QGridLayout()
        grid.setSpacing(8)
        self.file_no = F.FaLineEdit()
        self.file_no.setMaxLength(12)
        self.first = _W.QLineEdit()
        self.first.setLayoutDirection(_Core.Qt.RightToLeft)
        self.last = _W.QLineEdit()
        self.last.setLayoutDirection(_Core.Qt.RightToLeft)
        self.gender = _W.QComboBox()
        self.gender.addItems(["—", "آقا", "خانم"])
        F.style_combo(self.gender)
        self.phone = F.FaLineEdit()
        self.phone.setMaxLength(15)
        self.address = _W.QLineEdit()
        self.address.setLayoutDirection(_Core.Qt.RightToLeft)
        fields = [("شماره پرونده", self.file_no), ("نام", self.first),
                  ("نام خانوادگی", self.last), ("جنسیت", self.gender),
                  ("تلفن", self.phone), ("آدرس", self.address)]
        for i, (label, w) in enumerate(fields):
            col = (i % 3) * 2
            row = i // 3
            lab = _W.QLabel(label)
            lab.setStyleSheet("color:#5d7385; font-size:11px; font-weight:700;")
            grid.addWidget(lab, row * 2, col)
            grid.addWidget(w, row * 2 + 1, col, 1, 2)
        v.addLayout(grid)

        row = _W.QHBoxLayout()
        self.err = _W.QLabel("")
        self.err.setStyleSheet("color:#c03b4a; font-size:11px;")
        row.addWidget(self.err)
        row.addStretch(1)
        self.cancel_btn = _W.QPushButton("انصراف")
        self.cancel_btn.clicked.connect(self._reset_form)
        self.cancel_btn.hide()
        self.save_btn = success(_W.QPushButton("ثبت پرونده"), 130)
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
        head.addWidget(F.card_title("فهرست پرونده‌ها"))
        head.addStretch(1)
        self.filter_edit = F.SearchEdit(placeholder="جستجو در شماره یا نام…")
        self.filter_edit.setFixedWidth(260)
        head.addWidget(self.filter_edit)
        v.addLayout(head)

        self.table = F.make_table(
            ["شماره پرونده", "نام", "نام خانوادگی", "تلفن", "جنسیت",
             "تعداد فاکتور", "وضعیت", "عملیات"],
            widths=[125, 120, 140, 150, 95, 120, 95, 210])
        # Lazy action widgets (see archive page): visible rows only.
        self.table.set_row_widget_factory(7, self._make_actions)
        self.table.setMinimumHeight(320)
        v.addWidget(self.table)
        # Client-side paging + whole-list column sort.
        self.pager = F.ListPager(self.table)
        self.pager.configure(
            key_fn=self._sort_key, sortable=(0, 1, 2, 3, 4, 5),
            on_render=self._append_row)
        v.addWidget(self.pager.pager)
        self.count_lbl = _W.QLabel("")
        self.count_lbl.setStyleSheet("color:#5d7385; font-size:11px;")
        v.addWidget(self.count_lbl)
        self.filter_edit.textChanged.connect(self._apply_filter)
        return card(box)

    # Column -> comparable for whole-list sort (Persian digits folded).
    @staticmethod
    def _sort_key(p, col):
        if col == 0:
            return int("".join(c for c in F.en(str(p["file_no"]))
                               if c.isdigit()) or 0)
        if col == 1:
            return F.en(p["first_name"] or "").lower()
        if col == 2:
            return F.en(p["last_name"] or "").lower()
        if col == 3:
            # `or 0`: one empty phone used to raise and silently cancel
            # the whole sort.
            return int("".join(c for c in F.en(p["phone"] or "")
                               if c.isdigit()) or 0)
        if col == 4:
            return _GENDER_TO_FA.get(p["gender"], "")
        if col == 5:
            return int(p["invoice_count"])
        return 0

    def _apply_filter(self, _text=None):
        q = self.filter_edit.text()
        self.pager.set_query(
            lambda p: F.match_words(q, p["file_no"], p["first_name"],
                                    p["last_name"], p["phone"] or "",
                                    _GENDER_TO_FA.get(p["gender"], ""),
                                    str(p["invoice_count"])))
        self._update_count()

    # ------------------------------------------------------------------ #
    # Data
    # ------------------------------------------------------------------ #
    def refresh(self):
        self._all = models.list_patients()
        self._total = len(self._all)
        # Keep the current page across re-visits; typing search (reset_page)
        # is handled by _apply_filter only.
        self.pager.set_items(self._all, reset_page=False)
        self._update_count()

    def _append_row(self, p):
        model = self.table.model()
        active = bool(p["is_active"])
        items = [self._cell(F.fa(p["file_no"]), payload=p),
                 self._cell(p["first_name"]),
                 self._cell(p["last_name"]),
                 self._cell(F.fa(p["phone"] or "")),
                 self._cell(_GENDER_TO_FA.get(p["gender"], "")),
                 self._cell(F.fa(p["invoice_count"]))]
        status = self._cell("فعال" if active else "غیرفعال")
        status.setForeground(_Gui.QColor("#2e8b6a" if active else "#5d7385"))
        items.append(status)
        items.append(self._cell(""))
        model.appendRow(items)

    def _shown_total(self):
        return len(self.pager.visible_items())

    def _update_count(self):
        shown = self._shown_total()
        self.count_lbl.setText("نمایش %s پرونده از %s" % (
            F.fa(shown), F.fa(self._total)))
        if shown == 0 and self.filter_edit.text().strip():
            self.count_lbl.setText("موردی با این جستجو یافت نشد.")

    def _cell(self, text, payload=None):
        return F.make_item(text, payload=payload)

    def _make_actions(self, r):
        """Row buttons, built lazily for visible rows only. The patient dict
        rides along in the hidden payload so sorting can't desync them."""
        model = self.table.model()
        item = model.item(r, 0)
        if item is None:
            return None
        p = item.data(F.ROW_ID)
        if not isinstance(p, dict):
            return None
        pid = p["id"]
        active = bool(p["is_active"])
        btn_row = _W.QWidget()
        h = _W.QHBoxLayout(btn_row)
        h.setContentsMargins(2, 0, 2, 0)
        h.setSpacing(4)
        b_edit = _W.QPushButton("ویرایش")
        b_edit.setProperty("variant", "link")
        b_edit.setProperty("btnsize", "xs")
        b_edit.setCursor(_Core.Qt.PointingHandCursor)
        b_edit.clicked.connect(lambda _=False, pid=pid: self._load_for_edit(pid))
        h.addWidget(b_edit, 0, _Core.Qt.AlignVCenter)
        if active:
            b_deact = _W.QPushButton("غیرفعال")
            b_deact.setProperty("variant", "link")
            b_deact.setProperty("btnsize", "xs")
            b_deact.setProperty("tone", "warn")
            b_deact.setCursor(_Core.Qt.PointingHandCursor)
            b_deact.clicked.connect(lambda _=False, pid=pid: self._deactivate(pid))
            h.addWidget(b_deact, 0, _Core.Qt.AlignVCenter)
        else:
            b_act = _W.QPushButton("فعال‌سازی")
            b_act.setProperty("variant", "link")
            b_act.setProperty("btnsize", "xs")
            b_act.setCursor(_Core.Qt.PointingHandCursor)
            b_act.clicked.connect(lambda _=False, pid=pid: self._activate(pid))
            h.addWidget(b_act, 0, _Core.Qt.AlignVCenter)
        if not int(p["invoice_count"]):
            b_del = _W.QPushButton("حذف")
            b_del.setProperty("variant", "link")
            b_del.setProperty("btnsize", "xs")
            b_del.setProperty("tone", "danger")
            b_del.setCursor(_Core.Qt.PointingHandCursor)
            b_del.clicked.connect(lambda _=False, pid=pid: self._delete(pid))
            h.addWidget(b_del, 0, _Core.Qt.AlignVCenter)
        h.addStretch(1)
        return btn_row

    # ------------------------------------------------------------------ #
    # Actions
    # ------------------------------------------------------------------ #
    def _reset_form(self):
        self._editing_id = None
        self.file_no.clear()
        self.file_no.setEnabled(True)
        self.first.clear()
        self.last.clear()
        self.gender.setCurrentIndex(0)
        self.phone.clear()
        self.address.clear()
        self.err.setText("")
        self.form_title.setText("ثبت پرونده جدید")
        self.save_btn.setText("ثبت پرونده")
        self.cancel_btn.hide()

    def _load_for_edit(self, patient_id):
        p = models.get_patient(patient_id)
        if p is None:
            return
        self._editing_id = patient_id
        self.file_no.setText(F.fa(p["file_no"]))
        self.file_no.setEnabled(False)
        self.first.setText(p["first_name"])
        self.last.setText(p["last_name"])
        self.gender.setCurrentText(_GENDER_TO_FA.get(p["gender"], "—"))
        self.phone.setText(F.fa(p["phone"] or ""))
        self.address.setText(p["address"] or "")
        self.err.setText("")
        self.form_title.setText("ویرایش پرونده")
        self.save_btn.setText("ذخیره تغییرات")
        self.cancel_btn.show()

    def _save(self):
        file_no = self.file_no.value().strip()
        first = self.first.text().strip()
        last = self.last.text().strip()
        gender = _FA_TO_GENDER.get(self.gender.currentText(), "")
        phone = self.phone.value().strip()
        address = self.address.text().strip()
        if not file_no or not first or not last:
            self.err.setText("شماره پرونده، نام و نام خانوادگی الزامی است.")
            return
        if models.file_no_exists(file_no, exclude_id=self._editing_id):
            self.err.setText("این شماره پرونده قبلاً ثبت شده است.")
            return
        try:
            if self._editing_id is None:
                models.create_patient(file_no, first, last, gender, phone, address)
            else:
                models.update_patient(self._editing_id, first, last, gender,
                                      phone, address)
        except Exception as exc:
            error_msg(self, str(exc))
            return
        self._reset_form()
        self.refresh()

    def _deactivate(self, patient_id):
        if confirm_msg(self, "پرونده این بیمار غیرفعال شود؟"):
            models.deactivate_patient(patient_id)
            self.refresh()

    def _activate(self, patient_id):
        models.activate_patient(patient_id)
        self.refresh()

    def _delete(self, patient_id):
        if models.patient_has_invoices(patient_id):
            warning_msg(self, "این پرونده دارای فاکتور است و قابل حذف نیست؛ "
                              "می‌توانید آن را غیرفعال کنید.")
            return
        if confirm_msg(self, "پرونده برای همیشه حذف شود؟ این عمل برگشت‌پذیر نیست."):
            models.delete_patient(patient_id)
            self.refresh()
