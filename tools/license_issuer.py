# -*- coding: utf-8 -*-
"""AzaranTeb license issuer — VENDOR TOOL, never ship this to customers.

GUI:      python tools/license_issuer.py
CLI:      python tools/license_issuer.py --hw ABCDE-FGHIJ-KLMNP-QRSTU \
                                              --name "کلینیک آذر" --expires 1406-06-08 \
                                              --out license.key
          python tools/license_issuer.py --print-hwid
          python tools/license_issuer.py --verify license.key
          python tools/license_issuer.py --gen-keys

The private key lives in ``keys/issuer_private.json``.  The matching public
key is embedded in ``app/license.py``; if you regenerate the pair you must
paste the new modulus there and rebuild the exe, or every license issued
before that moment stops working.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import date_utils              # noqa: E402
from app import license as lic          # noqa: E402
from app import rsa_lite                # noqa: E402
from app.utils import Qt                # noqa: E402

_W, _Core, _Gui = Qt.QtWidgets, Qt.QtCore, Qt.QtGui

KEY_DIR = os.path.join(ROOT, "keys")
PRIVATE_PATH = os.path.join(KEY_DIR, "issuer_private.json")


# --------------------------------------------------------------------------- #
# Key handling
# --------------------------------------------------------------------------- #

def load_private(path=None):
    # type: (str) -> dict
    try:
        with open(path or PRIVATE_PATH, "r", encoding="utf-8") as fh:
            return rsa_lite.key_from_json(fh.read())
    except Exception:
        return {}


def save_private(keys, path=None):
    # type: (dict, str) -> str
    path = path or PRIVATE_PATH
    folder = os.path.dirname(path)
    if folder and not os.path.isdir(folder):
        os.makedirs(folder)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(rsa_lite.key_to_json(keys, private=True))
    try:
        os.chmod(path, 0o600)
    except Exception:
        pass
    return path


def new_keypair(bits=2048):
    # type: (int) -> dict
    return rsa_lite.generate_keypair(bits)


def private_matches_app(keys):
    # type: (dict) -> bool
    """True when this private key signs licenses the shipped exe will accept."""
    try:
        return rsa_lite.fingerprint(int(keys["n"])) == lic.public_fingerprint()
    except Exception:
        return False


def issue(hw_code, customer, expires_iso, private_keys=None):
    # type: (str, str, str, dict) -> str
    """Build the license token.  ``expires_iso`` empty/None => perpetual."""
    keys = private_keys if private_keys is not None else load_private()
    if "d" not in keys:
        raise RuntimeError("کلید خصوصی پیدا نشد؛ اول از تب «کلیدها» یک جفت‌کلید بسازید.")
    code = lic.normalize_code(hw_code)
    if not code:
        raise ValueError("کد سخت‌افزاری معتبر نیست (باید ۲۰ نویسه در ۴ گروه باشد).")
    payload = lic.make_payload(code, customer, date.today().isoformat(),
                               (expires_iso or "")[:10] or None)
    return lic.build_token(payload, keys)


def parse_expiry(text):
    # type: (str) -> str
    """Accept an ISO or a Jalali date and return ISO.

    A Jalali year like ``1406-06-08`` is also a *valid* ISO date (year 1406
    CE), so the ISO branch only wins when the year is in a plausible modern
    range; anything older is read as a Solar-Hijri date.
    """
    text = (text or "").strip()
    if not text:
        return ""
    try:
        d = date.fromisoformat(text[:10])
        if 1900 <= d.year <= 2200:
            return text[:10]
    except Exception:
        pass
    iso = date_utils.jalali_str_to_iso(text)
    if iso:
        return iso
    raise ValueError("تاریخ را نمی‌شناسم: %s" % text)


def _fa(number):
    # type: (int) -> str
    return date_utils.to_persian_digits(str(number))


# --------------------------------------------------------------------------- #
# GUI
# --------------------------------------------------------------------------- #

class IssuerWindow(_W.QWidget):
    """Three tabs: issue a license, manage the key pair, instructions."""

    def __init__(self, parent=None):
        super().__init__(parent)
        from app.ui import fields as F
        self.F = F
        self.setLayoutDirection(_Core.Qt.RightToLeft)
        self.setWindowTitle("ابزار صدور لایسنس — نبض کلینیک")
        self.resize(720, 620)
        v = _W.QVBoxLayout(self)
        v.setContentsMargins(18, 16, 18, 16)
        v.setSpacing(10)
        title = _W.QLabel("ابزار صدور لایسنس سخت‌افزاری")
        title.setProperty("role", "page-title")
        sub = _W.QLabel("این برنامه فقط دست فروشنده است. آن را برای مشتری نفرستید.")
        sub.setObjectName("sectionSub")
        v.addWidget(title)
        v.addWidget(sub)
        tabs = _W.QTabWidget()
        tabs.addTab(self._issue_tab(), "صدور لایسنس")
        tabs.addTab(self._keys_tab(), "کلیدها")
        tabs.addTab(self._help_tab(), "راهنما")
        v.addWidget(tabs, 1)

    # ---------------- issue tab ----------------
    def _issue_tab(self):
        page = _W.QWidget()
        g = _W.QVBoxLayout(page)
        g.setContentsMargins(18, 16, 18, 16)
        g.setSpacing(10)

        self.hw = _W.QLineEdit()
        self.hw.setLayoutDirection(_Core.Qt.LeftToRight)
        self.hw.setAlignment(_Core.Qt.AlignCenter)
        self.hw.setPlaceholderText("ABCDE-FGHIJ-KLMNP-QRSTU")
        f = self.hw.font()
        f.setBold(True)
        f.setLetterSpacing(_Gui.QFont.AbsoluteSpacing, 1.5)
        self.hw.setFont(f)
        self.hw_hint = _W.QLabel("")
        self.hw_hint.setObjectName("sectionSub")
        self.hw.textChanged.connect(self._on_hw)

        self.name = _W.QLineEdit()
        self.name.setPlaceholderText("مثلاً کلینیک دندان‌پزشکی آذر")

        self.perp = _W.QCheckBox("بدون انقضا (دائمی)")
        self.perp.toggled.connect(self._on_perp)
        self.exp = self.F.JalaliDateEdit(
            iso=(date.today() + timedelta(days=365)).isoformat())
        self.exp_lbl = _W.QLabel("")
        self.exp_lbl.setObjectName("sectionSub")
        self.exp.dateChanged.connect(lambda _i: self._sync_exp_label())

        quick = _W.QHBoxLayout()
        quick.setSpacing(6)
        for label, days in (("۶ ماه", 182), ("۱ سال", 365), ("۲ سال", 730),
                            ("۵ سال", 1826)):
            b = _W.QPushButton(label)
            b.setProperty("variant", "outline")
            b.setProperty("btnsize", "xs")
            b.setCursor(_Core.Qt.PointingHandCursor)
            b.clicked.connect(lambda _c=False, d=days: self._quick(d))
            quick.addWidget(b)
        quick.addStretch(1)

        self.out = _W.QPlainTextEdit()
        self.out.setReadOnly(True)
        self.out.setMaximumHeight(96)
        self.status = _W.QLabel("آماده")
        self.status.setObjectName("sectionSub")
        self.status.setWordWrap(True)

        for lab, wid in (("کد سخت‌افزاری مشتری", self.hw),
                         ("نام مشتری (روی لایسنس درج می‌شود)", self.name)):
            l = _W.QLabel(lab)
            l.setProperty("role", "flabel")
            g.addWidget(l)
            g.addWidget(wid)
        g.addLayout(quick)
        lp = _W.QLabel("اعتبار")
        lp.setProperty("role", "flabel")
        g.addWidget(lp)
        row = _W.QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(self.perp)
        row.addWidget(self.exp, 1)
        g.addLayout(row)
        g.addWidget(self.exp_lbl)
        g.addWidget(self.out)
        g.addWidget(self.status)

        btns = _W.QHBoxLayout()
        btns.setSpacing(8)
        from app.theme import primary
        self.b_save = _W.QPushButton("ساخت و ذخیرهٔ فایل لایسنس")
        primary(self.b_save, 0)
        self.b_save.setProperty("btnsize", "sm")
        self.b_save.setCursor(_Core.Qt.PointingHandCursor)
        self.b_save.clicked.connect(self._save)
        self.b_copy = _W.QPushButton("کپی متن لایسنس")
        self.b_copy.setProperty("variant", "outline")
        self.b_copy.setProperty("btnsize", "sm")
        self.b_copy.setCursor(_Core.Qt.PointingHandCursor)
        self.b_copy.clicked.connect(self._copy)
        self.b_mine = _W.QPushButton("کد سخت‌افزاری همین دستگاه")
        self.b_mine.setProperty("variant", "ghost")
        self.b_mine.setProperty("btnsize", "xs")
        self.b_mine.setCursor(_Core.Qt.PointingHandCursor)
        self.b_mine.clicked.connect(lambda: self.hw.setText(lic.hardware_code()))
        for b in (self.b_save, self.b_copy, self.b_mine):
            btns.addWidget(b)
        btns.addStretch(1)
        g.addLayout(btns)
        g.addStretch(1)
        self._sync_exp_label()
        return page

    def _on_hw(self, text):
        code = lic.normalize_code(text)
        if code:
            self.hw_hint.setText("✓ کد معتبر: " + code)
            self.hw_hint.setStyleSheet("color:#2e8b6a;")
        elif text.strip():
            self.hw_hint.setText("کد باید ۲۰ نویسه باشد (۴ گروه ۵تایی).")
            self.hw_hint.setStyleSheet("color:#c03b4a;")
        else:
            self.hw_hint.setText("")

    def _quick(self, days):
        self.perp.setChecked(False)
        self.exp.set_iso((date.today() + timedelta(days=days)).isoformat())

    def _on_perp(self, on):
        self.exp.set_enabled_all(not on)
        self._sync_exp_label()

    def _sync_exp_label(self):
        if self.perp.isChecked():
            self.exp_lbl.setText("این لایسنس هیچ‌وقت منقضی نمی‌شود.")
            self.exp_lbl.setStyleSheet("color:#5d7385;")
            return
        iso = self.exp.iso()
        if not iso:
            self.exp_lbl.setText("تاریخ انقضا را انتخاب کنید.")
            return
        try:
            d = date.fromisoformat(iso)
        except Exception:
            return
        days = (d - date.today()).days
        self.exp_lbl.setText("%s — %s روز اعتبار" % (
            date_utils.iso_to_jalali_persian_str(iso), _fa(days)))
        self.exp_lbl.setStyleSheet("color:%s" % ("#c03b4a" if days <= 0 else "#5d7385"))

    def _make_token(self):
        """Build the token, and always leave a truthful status line behind."""
        try:
            expires = "" if self.perp.isChecked() else self.exp.iso()
            tok = issue(self.hw.text(), self.name.text(), expires)
        except Exception as exc:
            self._fail(exc)
            raise
        self.out.setPlainText(tok)
        self.status.setText("لایسنس ساخته شد. حالا آن را ذخیره یا کپی کنید.")
        self.status.setStyleSheet("color:#2e8b6a;")
        return tok

    def _fail(self, exc):
        self.status.setText(str(exc))
        self.status.setStyleSheet("color:#c03b4a;")

    def _save(self):
        try:
            tok = self._make_token()
        except Exception:
            return  # _make_token already surfaced the reason
        path, _ = _W.QFileDialog.getSaveFileName(
            self, "ذخیرهٔ فایل لایسنس", "license.key",
            "فایل لایسنس (*.key *.txt);;همهٔ فایل‌ها (*)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(tok + "\n")
        except Exception as exc:
            self._fail(exc)
            return
        self.status.setText("ذخیره شد: %s — این فایل را کنار AzaranTeb.exe "
                            "در دستگاه مشتری بگذارید." % path)
        self.status.setStyleSheet("color:#2e8b6a;")

    def _copy(self):
        tok = self.out.toPlainText().strip()
        try:
            tok = tok or self._make_token()
        except Exception:
            return
        _W.QApplication.clipboard().setText(tok)
        self.status.setText("متن لایسنس در کلیپ‌بورد است؛ می‌توانید مستقیم در "
                            "واتساپ/ایمیل بچسبانید.")
        self.status.setStyleSheet("color:#2e8b6a;")

    # ---------------- keys tab ----------------
    def _keys_tab(self):
        page = _W.QWidget()
        g = _W.QVBoxLayout(page)
        g.setContentsMargins(18, 16, 18, 16)
        g.setSpacing(10)
        keys = load_private()
        if keys:
            ok = private_matches_app(keys)
            info = _W.QLabel("کلید خصوصی: %s" % PRIVATE_PATH)
            info.setObjectName("sectionSub")
            state = _W.QLabel("اثر انگشت کلید: %s — %s" % (
                rsa_lite.fingerprint(keys["n"]),
                "هم‌خوان با برنامه ✓" if ok else
                "با کلید داخل برنامه هم‌خوان نیست! بلوک کلید عمومی را در "
                "app/license.py جایگزین و exe را بازسازی کنید."))
            state.setWordWrap(True)
            state.setStyleSheet("color:%s" % ("#2e8b6a" if ok else "#c03b4a"))
            g.addWidget(info)
            g.addWidget(state)
        else:
            warn = _W.QLabel("کلید خصوصی یافت نشد. روی «ساخت جفت‌کلید جدید» بزنید.")
            warn.setObjectName("loginErr")
            warn.setWordWrap(True)
            g.addWidget(warn)

        plab = _W.QLabel("کلید عمومی که داخل برنامه (app/license.py) است:")
        plab.setProperty("role", "flabel")
        pub = _W.QPlainTextEdit()
        pub.setReadOnly(True)
        pub.setMaximumHeight(120)
        pub.setPlainText(json.dumps({"n": lic.PUB_N_HEX, "e": lic.PUB_E},
                                    indent=2, sort_keys=True))
        g.addWidget(plab)
        g.addWidget(pub)

        b_copy = _W.QPushButton("کپی بلوک PUBLIC_KEY برای app/license.py")
        b_copy.setProperty("variant", "outline")
        b_copy.setProperty("btnsize", "sm")
        b_copy.setCursor(_Core.Qt.PointingHandCursor)
        b_copy.clicked.connect(lambda: _W.QApplication.clipboard().setText(
            'PUB_N_HEX = "%s"\nPUB_E = %d\nKEY_FINGERPRINT = "%s"' % (
                lic.PUB_N_HEX, lic.PUB_E, lic.public_fingerprint())))
        g.addWidget(b_copy, 0, _Core.Qt.AlignRight)

        b_new = _W.QPushButton("ساخت جفت‌کلید جدید")
        b_new.setProperty("variant", "danger")
        b_new.setProperty("btnsize", "sm")
        b_new.setCursor(_Core.Qt.PointingHandCursor)
        b_new.clicked.connect(self._regen)
        g.addWidget(b_new, 0, _Core.Qt.AlignRight)

        danger = _W.QLabel("هشدار: فایل keys/issuer_private.json را هرگز به مشتری "
                           "ندهید و داخل پوشهٔ dist کپی نکنید. اگر آن را گم کنید، "
                           "دیگر نمی‌توانید لایسنس صادر کنید.")
        danger.setObjectName("loginErr")
        danger.setWordWrap(True)
        g.addWidget(danger)
        g.addStretch(1)
        return page

    def _regen(self):
        box = _W.QMessageBox(self)
        box.setIcon(_W.QMessageBox.Warning)
        box.setLayoutDirection(_Core.Qt.RightToLeft)
        box.setWindowTitle("ساخت جفت‌کلید جدید")
        box.setText("با کلید جدید، همهٔ لایسنس‌های صادرشدهٔ قبلی بی‌اعتبار می‌شوند.")
        box.setInformativeText("فقط در صورتی ادامه دهید که می‌خواهید از صفر شروع "
                               "کنید و آمادهٔ بازسازی exe هستید.")
        box.addButton("ادامه", _W.QMessageBox.AcceptRole)
        box.addButton("انصراف", _W.QMessageBox.RejectRole)
        if box.exec_() != _W.QMessageBox.Accepted:
            return
        _W.QApplication.setOverrideCursor(_Gui.QCursor(_Core.Qt.WaitCursor))
        _W.QApplication.processEvents()
        try:
            keys = new_keypair()
            save_private(keys)
        finally:
            _W.QApplication.restoreOverrideCursor()
        dlg = _W.QMessageBox(self)
        dlg.setLayoutDirection(_Core.Qt.RightToLeft)
        dlg.setWindowTitle("کلید تازه")
        dlg.setText("کلید خصوصی ساخته شد: %s" % PRIVATE_PATH)
        dlg.setInformativeText(
            "این سه خط را در app/license.py جایگزین کنید و سپس exe را بازسازی "
            "کنید:\n\nPUB_N_HEX = \"%x\"\nPUB_E = %d\nKEY_FINGERPRINT = \"%s\"" % (
                keys["n"], keys["e"], rsa_lite.fingerprint(keys["n"])))
        dlg.exec_()

    # ---------------- help tab ----------------
    def _help_tab(self):
        page = _W.QWidget()
        g = _W.QVBoxLayout(page)
        g.setContentsMargins(18, 16, 18, 16)
        steps = [
            ("۱. کد سخت‌افزاری را بگیرید",
             "برنامه را روی دستگاه مشتری اجرا کنید. اگر لایسنسی نباشد، پنجرهٔ "
             "«فعال‌سازی نرم‌افزار» باز می‌شود و کد دستگاه را نشان می‌دهد. مشتری "
             "همان کد را با دکمهٔ کپی برای شما می‌فرستد."),
            ("۲. لایسنس بسازید",
             "در تب «صدور لایسنس» کد را بچسبانید، نام کلینیک را بنویسید، مدت "
             "اعتبار را انتخاب کنید و «ساخت و ذخیرهٔ فایل لایسنس» را بزنید."),
            ("۳. فایل را برسانید",
             "فایل license.key را (با واتساپ، ایمیل یا فلش) برای مشتری بفرستید. "
             "نام فایل مهم است: license.key"),
            ("۴. مشتری فعال کند",
             "در همان پنجرهٔ فعال‌سازی، دکمهٔ «انتخاب فایل لایسنس…» را بزند و "
             "فایل را انتخاب کند. برنامه خودش فایل را کنار AzaranTeb.exe "
             "می‌گذارد و وارد می‌شود. (می‌تواند فایل را دستی هم کنار exe بگذارد.)"),
            ("تمدید",
             "برای تمدید، همین مراحل را با تاریخ جدید تکرار کنید؛ فایل جدید جای "
             "قبلی را می‌گیرد."),
            ("نکته",
             "لایسنس به MachineGuid ویندوز بسته است. با عوض‌کردن قطعه‌ها "
             "(هارد، رم، کارت شبکه) لایسنس معتبر می‌ماند؛ با نصب مجدد ویندوز "
             "یا کپی کردن پوشه روی دستگاه دیگر، بی‌اعتبار می‌شود."),
        ]
        for head, body in steps:
            h = _W.QLabel(head)
            h.setObjectName("sectionTitle")
            b = _W.QLabel(body)
            b.setObjectName("sectionSub")
            b.setWordWrap(True)
            g.addWidget(h)
            g.addWidget(b)
            g.addSpacing(6)
        g.addStretch(1)
        return page


def bootstrap_app():
    """Scaling + fonts + theme, shared by the GUI and the layout probes."""
    from app.utils import apply_app_font, load_app_fonts, setup_scaling
    setup_scaling()
    app = _W.QApplication.instance() or _W.QApplication(sys.argv)
    app.setLayoutDirection(_Core.Qt.RightToLeft)
    load_app_fonts()
    apply_app_font(size=10)
    try:
        app.setStyle("Fusion")
    except Exception:
        pass
    from app.theme import apply_theme
    apply_theme(app)
    return app


def run_gui():
    # type: () -> int
    app = bootstrap_app()
    win = IssuerWindow()
    win.show()
    return app.exec_()


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main(argv=None):
    # type: (list) -> int
    ap = argparse.ArgumentParser(description="صدور لایسنس سخت‌افزاری نبض کلینیک")
    ap.add_argument("--hw", help="کد سخت‌افزاری دستگاه مشتری")
    ap.add_argument("--name", default="", help="نام مشتری/کلینیک")
    ap.add_argument("--expires", default="", help="تاریخ انقضا (۱۴۰۵-۰۶-۰۸ یا 2026-08-30)")
    ap.add_argument("--perpetual", action="store_true", help="بدون انقضا")
    ap.add_argument("--out", help="مسیر ذخیرهٔ فایل license.key")
    ap.add_argument("--key", default=PRIVATE_PATH, help="مسیر کلید خصوصی")
    ap.add_argument("--print-hwid", action="store_true", help="کد همین دستگاه")
    ap.add_argument("--verify", metavar="FILE", help="اعتبارسنجی یک فایل لایسنس")
    ap.add_argument("--gen-keys", action="store_true", help="ساخت جفت‌کلید جدید")
    ap.add_argument("--bits", type=int, default=2048)
    ap.add_argument("--gui", action="store_true", help="اجرای پنجرهٔ گرافیکی")
    args = ap.parse_args(argv)

    if args.gui or not any((args.hw, args.print_hwid, args.verify, args.gen_keys)):
        return run_gui()

    if args.print_hwid:
        print(lic.hardware_code())
        return 0

    if args.gen_keys:
        keys = new_keypair(args.bits)
        save_private(keys, args.key)
        print("کلید خصوصی: %s" % (args.key or PRIVATE_PATH))
        print("PUB_N_HEX = \"%x\"" % keys["n"])
        print("PUB_E = %d" % keys["e"])
        print("KEY_FINGERPRINT = \"%s\"" % rsa_lite.fingerprint(keys["n"]))
        return 0

    if args.verify:
        with open(args.verify, "r", encoding="utf-8") as fh:
            token = fh.read().strip()
        st = lic.verify_token(token)
        print("امضا: %s" % ("معتبر" if st.ok else "نامعتبر (%s)" % st.code))
        if st.ok:
            print("دستگاه: %s | همین دستگاه: %s | %s" % (
                st.payload.get("hw"), lic.hardware_code(),
                "مطابق ✓" if st.payload.get("hw") == lic.hardware_code() else "متفاوت ✗"))
            print("مشتری: %s | انقضا: %s" % (
                st.payload.get("name"), st.payload.get("expires") or "دائمی"))
        return 0 if st.ok else 2

    if not args.hw:
        ap.error("--hw لازم است")
    keys = load_private(args.key)
    try:
        expires = "" if args.perpetual else parse_expiry(args.expires)
        token = issue(args.hw, args.name, expires, keys)
    except (ValueError, RuntimeError) as exc:
        sys.stderr.write("%s\n" % exc)
        return 2
    if args.out:
        try:
            with open(args.out, "w", encoding="utf-8") as fh:
                fh.write(token + "\n")
        except Exception as exc:
            sys.stderr.write("خطا در نوشتن فایل: %s\n" % exc)
            return 2
        print("نوشته شد: %s" % args.out)
    else:
        print(token)
    return 0


if __name__ == "__main__":
    sys.exit(main())
