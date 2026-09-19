# -*- coding: utf-8 -*-
"""HTML invoice/report printing helpers using QTextDocument (v2 UI).

Self-contained copy of the legacy widgets/print_utils so app/ui has no
dependency on the old package; adds build_proforma_html() matching the web's
print-preview modal (پیش‌فاکتور + notes + optional doctor name).
"""
from __future__ import annotations

from typing import Any, Optional, Sequence

from ..utils import Qt
from .. import date_utils, money_utils

_Widgets = Qt.QtWidgets
_Core = Qt.QtCore
_Gui = Qt.QtGui
_Print = Qt.QtPrintSupport


def _esc(text):
    # type: (str) -> str
    s = str(text) if text is not None else ""
    s = s.replace("&", chr(0x26) + "amp;")
    s = s.replace("<", chr(0x26) + "lt;")
    s = s.replace(">", chr(0x26) + "gt;")
    s = s.replace('"', chr(0x26) + "quot;")
    return s


def _money(value):
    # type: (int) -> str
    return money_utils.format_money_persian(value)


def _jalali(value):
    # type: (Optional[str]) -> str
    return date_utils.iso_to_jalali_persian_str(value)


def _print_font():
    # type: () -> str
    try:
        from ..utils import best_persian_font
        return best_persian_font()
    except Exception:
        return "Tahoma"


# Palette mirrors the web's print sheet (deep teal ink, pulse-red accent).
_INK = "#14222c"
_TEAL = "#073d4e"
_ACCENT = "#e24c5a"
_MUTED = "#5d7385"
_LINE = "#c6d3dc"
_ZEBRA = "#f6f9fb"

# Qt5 rich-text facts (verified by parsing QPdfWriter glyph positions):
#  * `direction:` inside <style> is ignored; the HTML `dir="rtl"` attribute
#    IS honoured per block (it flips default alignment and the bidi base).
#  * BUT table columns and inline-block flows ALWAYS advance left-to-right
#    no matter what `dir` says (Qt6 added RTL tables; Qt5 never did).
#    Hence every horizontal structure below is emitted in REVERSED source
#    order so it visually reads right-to-left.
#  * ALIGNMENT IS LOGICAL, NOT PHYSICAL (dir x align matrix probed): inside
#    a dir='rtl' table/cell, HTML `left` renders at the PHYSICAL RIGHT and
#    `right` at the physical LEFT; `center` is unaffected; default td =
#    right-flush, default th = centered, body-level BARE divs = always
#    physical left (they ignore dir/align entirely). Number columns that
#    must sit at the physical left therefore say text-align:right, and
#    right-flush text cells say text-align:left (or nothing, for td).
def _doc_style(font_name=None):
    # type: (Optional[str]) -> str
    font_name = font_name or _print_font()
    return (
        "<style>"
        "body{font-family:'%s'; color:%s;}"
        "table{border-collapse:collapse;}"
        "th{background:%s; color:#ffffff; font-size:12px; padding:6px 8px;}"
        "td{font-size:12.5px; padding:5px 8px; border-bottom:1px solid %s;}"
        "</style>" % (font_name, _INK, _TEAL, "#dbe4ea"))


def _invoice_doc(app_title, subtitle, inv_no, issued, file_no, patient,
                 doctor_name, notes, rows, total, paid, remaining,
                 payments=None):
    # type: (str, str, str, str, str, str, str, str, Sequence, int, int, int, Optional[Sequence]) -> str
    """Desktop mirror of the web invoice print sheet (invoice_detail.html).

    Qt5 facts (measured from QPdfWriter glyph coordinates):
     * table columns and inline blocks ALWAYS flow left-to-right whatever
       `dir` says -> every horizontal structure is emitted in REVERSED
       source order, so the element that must appear rightmost is emitted
       LAST;
     * the `direction:` CSS property is ignored (dir attr + explicit
       text-align are honoured per block);
     * the document is laid out at its own textWidth unless _doc_print
       pins it to the page.
    """
    font = _print_font()
    inv_no = date_utils.to_persian_digits(str(inv_no))
    file_no = date_utils.to_persian_digits(str(file_no))
    issued = date_utils.to_persian_digits(str(issued))

    # ---- letterhead: heading block (right) + number clip (left) --------- #
    # Meta chips in a 3-cell strip (web .inv-meta flex row). Emitted in
    # reversed source order: پرونده cell last so it lands rightmost.
    chip_css = (f"width:180px;border:none;padding:0 16px;"
                f"font-size:12px;color:{_MUTED};")
    chips = (
        f"<td dir='rtl' style='{chip_css}'>پزشک معالج: "
        f"<b style='color:{_INK};'>{_esc(doctor_name)}</b></td>"
        if doctor_name
        else "<td style='width:180px;border:none;'></td>")
    chips += (
        f"<td dir='rtl' style='{chip_css}'>تاریخ صدور: "
        f"<b style='color:{_INK};'>{_esc(issued)}</b></td>"
        f"<td dir='rtl' style='{chip_css}'>شماره پرونده: "
        f"<b style='color:{_INK};'>{_esc(file_no)}</b></td>")
    right_block = (
        f"<div style='font-size:13px;font-weight:bold;color:{_TEAL};'>"
        f"{_esc(app_title)} &nbsp;&nbsp;—&nbsp;&nbsp; {_esc(subtitle)}</div>"
        f"<div style='font-size:22px;font-weight:bold;color:{_INK};'>"
        f"{_esc(patient) or '—'}</div>"
        "<table dir='rtl' width='540' cellspacing='0' cellpadding='0'>"
        f"<tr>{chips}</tr></table>")
    clip = (
        f"<td valign='top' dir='rtl' width='165' style='width:165px;"
        f"text-align:center;border:1px solid {_LINE};background:#eef4f7;"
        f"padding:10px 14px;'>"
        f"<div style='font-size:10.5px;font-weight:bold;color:{_TEAL};'>"
        f"شماره فاکتور</div>"
        f"<div style='font-size:21px;font-weight:bold;color:{_TEAL};'>"
        f"{inv_no}</div>"
        f"<div style='font-size:11.5px;font-weight:bold;color:{_TEAL};"
        f"margin-top:4px;'>"
        f"{_esc(issued)}</div></td>")
    head = (
        "<table dir='rtl' width='745' cellspacing='0' cellpadding='0'><tr>"
        f"{clip}"
        "<td valign='top' dir='rtl' width='30' style='width:30px;"
        "border:none;'></td>"
        f"<td valign='top' dir='rtl' width='550' style='width:550px;"
        f"border:none;'>{right_block}</td></tr></table>"
        "<table dir='rtl' width='745' cellspacing='0' cellpadding='0'>"
        f"<tr><td style='border:none;background:{_LINE};height:1px;"
        "'>&nbsp;</td></tr></table>")
    # ---- notes box (sits under the heading, on the right) ---------------- #
    notes_html = ""
    if notes:
        notes_html = (
            "<table dir='rtl' width='745' cellspacing='0' cellpadding='0'>"
            "<tr><td width='285' style='width:285px;border:none;"
            "'></td>"
            f"<td dir='rtl' width='460' style='width:460px;"
            f"border:1px solid {_LINE};background:{_ZEBRA};padding:8px 12px;"
            f"font-size:12px;color:{_INK};'>{_esc(notes)}</td></tr></table>")
    # ---- items table (web columns; reversed) ----------------------------- #
    body_rows = []
    for i, r in enumerate(rows):
        bg = _ZEBRA if i % 2 else "#ffffff"
        body_rows.append(
            f"<tr style='background:{bg};'>"
            "<td dir='rtl' width='130' style='text-align:right;width:130px;"
            "font-weight:bold;'>"
            f"{_esc(_money(r['row_total']))}</td>"
            "<td dir='rtl' width='130' style='text-align:right;width:130px;'>"
            f"{_esc(_money(r['unit_price']))}</td>"
            "<td dir='rtl' width='90' style='text-align:right;width:90px;'>"
            f"{_esc(date_utils.to_persian_digits(str(r['quantity'])))}</td>"
            "<td dir='rtl' width='395' style='text-align:left;width:395px;'>"
            f"{_esc(r['title'])}</td></tr>")
    if not body_rows:
        body_rows.append(
            "<tr><td colspan='4' dir='rtl' style='text-align:center;"
            f"color:{_MUTED};'>اقلامی ثبت نشده است.</td></tr>")
    table = (
        "<table dir='rtl' width='745' cellspacing='0' cellpadding='0' "
        f"style='border:1px solid {_LINE};'>"
        f"<tr style='background:{_TEAL};'>"
        "<th dir='rtl' width='130' style='text-align:right;padding:6px 8px;"
        "width:130px;'>جمع (تومان)</th>"
        "<th dir='rtl' width='130' style='text-align:right;padding:6px 8px;"
        "width:130px;'>فی (تومان)</th>"
        "<th dir='rtl' width='90' style='text-align:right;padding:6px 8px;"
        "width:90px;'>تعداد</th>"
        "<th dir='rtl' width='395' style='text-align:left;padding:6px 8px;"
        "width:395px;'>نام کالا / خدمت</th>"
        f"</tr>{''.join(body_rows)}</table>")
    # ---- settlement ledger (lower-LEFT, like the web) -------------------- #
    rem_color = "#c03b4a" if int(remaining) > 0 else "#2e8b6a"
    totals = (
        "<table dir='rtl' width='745' cellspacing='0' cellpadding='0'><tr>"
        "<td valign='top' dir='rtl' width='340' style='width:340px;"
        "padding:0;border:none;'>"
        "<table dir='rtl' width='340' cellspacing='0' cellpadding='0' "
        f"style='border:1px solid {_LINE};'>"
        "<tr>"
        "<td dir='rtl' style='text-align:right;font-weight:bold;padding:7px"
        f" 10px;width:165px;'>{_esc(_money(total))}</td>"
        "<td dir='rtl' style='background:#eef4f7;padding:"
        "7px 10px;width:175px;'>جمع کل</td></tr>"
        "<tr>"
        "<td dir='rtl' style='text-align:right;font-weight:bold;padding:7px"
        f" 10px;color:#2e8b6a;width:165px;'>{_esc(_money(paid))}</td>"
        "<td dir='rtl' style='background:#eef4f7;padding:"
        "7px 10px;width:175px;'>پرداخت‌شده</td></tr>"
        "<tr>"
        "<td dir='rtl' style='text-align:right;font-weight:bold;font-size:"
        f"15px;padding:7px 10px;border-bottom:none;color:{rem_color};"
        f"width:165px;'>{_esc(_money(remaining))}</td>"
        "<td dir='rtl' style='background:#eef4f7;padding:"
        "7px 10px;font-weight:bold;border-bottom:none;width:175px;'>"
        "باقی‌مانده</td></tr>"
        "</table></td>"
        "<td width='405' style='width:405px;padding:0;border:none;'>"
        "</td></tr></table>")
    # ---- payments table --------------------------------------------------- #
    pay_html = ""
    if payments:
        prows = []
        for i, p in enumerate(payments):
            bg = _ZEBRA if i % 2 else "#ffffff"
            prows.append(
                f"<tr style='background:{bg};'>"
                "<td dir='rtl' width='150' style='text-align:right;width:150px;"
                f"font-weight:bold;'>{_esc(_money(int(p['amount'])))}</td>"
                "<td dir='rtl' width='595' style='width:595px;'>"
                f"{_esc(p.get('method') or '—')}</td></tr>")
        # Qt5 ignores text-align/dir on BARE body-level divs (probe-proven:
        # such blocks always flow from the left margin) — only blocks inside
        # a dir='rtl' table cell honour right alignment. So the heading
        # rides a one-cell table like every other heading in this doc.
        pay_html = (
            "<table dir='rtl' width='745' cellspacing='0' cellpadding='0'>"
            f"<tr><td dir='rtl' width='745' style='width:745px;"
            f"border:none;font-size:13.5px;font-weight:"
            f"bold;color:{_INK};'>پرداخت‌ها</td></tr></table>"
            "<table dir='rtl' width='745' cellspacing='0' cellpadding='0' "
            f"style='border:1px solid {_LINE};'>"
            f"<tr style='background:{_TEAL};'>"
            "<th dir='rtl' width='150' style='text-align:right;padding:6px"
            " 8px;width:150px;'>مبلغ</th>"
            "<th dir='rtl' width='595' style='text-align:left;padding:6px"
            " 8px;width:595px;'>روش پرداخت</th>"
            f"</tr>{''.join(prows)}</table>")
    gap = "<div style='font-size:10px;'>&nbsp;</div>"
    gap_sm = "<div style='font-size:5px;'>&nbsp;</div>"
    return (
        "<html><head>" + _doc_style(font) + "</head>"
        f"<body dir='rtl' style=\"font-family:'{font}'; color:{_INK};"
        " text-align:right;\">"
        + head
        + (gap_sm + notes_html if notes_html else "")
        + gap + table + gap + totals
        + (gap + pay_html if pay_html else "")
        + "</body></html>")


def build_invoice_html(invoice):
    # type: (dict) -> str
    """invoice dict keys: app_title, invoice_no, issued_at (ISO),
    patient_name, file_no, doctor_name(optional), rows (list of dicts with
    title, unit_price, quantity, row_total), total, paid, remaining,
    show_doctor (bool), notes(optional)."""
    return _invoice_doc(
        invoice.get("app_title", "آذران طب"), "فاکتور",
        str(invoice.get("invoice_no", "")),
        _jalali(invoice.get("issued_at")),
        str(invoice.get("file_no", "")),
        invoice.get("patient_name", ""),
        invoice.get("doctor_name", "") if invoice.get("show_doctor") else "",
        invoice.get("notes", "") or "",
        invoice.get("rows", []) or [],
        int(invoice.get("total", 0)), int(invoice.get("paid", 0)),
        int(invoice.get("remaining", 0)),
        invoice.get("payments") or None)


def build_proforma_html(data):
    # type: (dict) -> str
    """Unsaved invoice preview (mirrors the web's buildPrintHTML).
    Keys: app_title, invoice_no, issued_jalali (display str), patient_name,
    file_no, doctor_name, show_doctor, notes, rows, total, paid."""
    total = int(data.get("total", 0))
    paid = int(data.get("paid", 0))
    return _invoice_doc(
        data.get("app_title", "آذران طب"), "پیش‌فاکتور",
        str(data.get("invoice_no", "")), data.get("issued_jalali", ""),
        str(data.get("file_no", "")), data.get("patient_name", "—"),
        data.get("doctor_name", "") if data.get("show_doctor") else "",
        data.get("notes", "") or "",
        data.get("rows", []) or [], total, paid, total - paid,
        data.get("payments") or None)


def build_saved_invoice_html(invoice_id, show_doctor=None):
    # type: (int, Optional[bool]) -> Optional[str]
    """Print HTML for a persisted invoice — the single builder behind the
    archive's «مشاهده / چاپ» and the post-save print preview.

    ``show_doctor``: explicit choice for this print; ``None`` falls back to
    the settings-page value (which is only the *default*, see
    show_invoice_preview)."""
    from .. import models, settings as settings_mod
    inv = models.get_invoice(invoice_id)
    if inv is None:
        return None
    items = models.list_invoice_items(invoice_id)
    paid = models.invoice_paid_sum(invoice_id)
    if show_doctor is None:
        show_doctor = settings_mod.get_setting("show_doctor_in_print",
                                               "0") == "1"
    return build_invoice_html({
        "app_title": settings_mod.get_setting("app_title", "آذران طب"),
        "invoice_no": inv["invoice_no"],
        "issued_at": inv["issued_at"],
        "patient_name": "%s %s" % (inv["first_name"], inv["last_name"]),
        "file_no": inv["file_no"],
        "doctor_name": inv.get("doctor_name") or "",
        "show_doctor": bool(show_doctor),
        "notes": inv.get("notes") or "",
        "rows": [{"title": it["title"], "unit_price": it["unit_price"],
                  "quantity": it["quantity"], "row_total": it["row_total"]}
                 for it in items],
        "payments": [{"method": p["method"], "amount": int(p["amount"])}
                     for p in models.list_payments(invoice_id)],
        "total": int(inv["total_amount"]),
        "paid": paid,
        "remaining": int(inv["total_amount"]) - paid,
    })


def _ask_show_doctor(parent):
    # type: (Any) -> Optional[bool]
    """Per-print choice for «نام پزشک در چاپ»; the settings-page toggle only
    decides which button is the default. None = user cancelled."""
    from .. import settings as settings_mod
    default = settings_mod.get_setting("show_doctor_in_print", "0") == "1"
    box = _Widgets.QMessageBox(parent)
    box.setWindowTitle("پیش‌نمایش چاپ")
    box.setText("نام پزشک معالج در این فاکتور چاپ شود؟")
    box.setIcon(_Widgets.QMessageBox.Question)
    box.setLayoutDirection(_Core.Qt.RightToLeft)
    b_yes = box.addButton("با نام پزشک", _Widgets.QMessageBox.AcceptRole)
    b_no = box.addButton("بدون نام پزشک", _Widgets.QMessageBox.DestructiveRole)
    b_cancel = box.addButton("انصراف", _Widgets.QMessageBox.RejectRole)
    box.setDefaultButton(b_yes if default else b_no)
    box.exec_()
    clicked = box.clickedButton()
    if clicked is b_cancel or clicked is None:
        return None
    return clicked is b_yes


def show_invoice_preview(parent, invoice_id):
    # type: (Any, int) -> bool
    """Ask whether the doctor's name should appear (settings value = the
    default button), then open the A4-portrait print preview for a saved
    invoice. Returns True when the preview was shown."""
    from .. import models
    inv = models.get_invoice(invoice_id)
    if inv is None:
        return False
    show_doctor = None
    doc_name = (inv.get("doctor_name") or "").strip()
    if doc_name and doc_name != "بدون معرف":
        show_doctor = _ask_show_doctor(parent)
        if show_doctor is None:
            return False
    html = build_saved_invoice_html(invoice_id, show_doctor=show_doctor)
    if html:
        show_print_preview(parent, html)
        return True
    return False


def _make_doc(html):
    # type: (str) -> Any
    """QTextDocument with the app's Persian face as the base font so Qt
    shapes Arabic/Persian joins correctly even if a CSS family lookup fails."""
    doc = _Gui.QTextDocument()
    try:
        f = _Gui.QFont(_print_font())
        f.setPixelSize(13)
        doc.setDefaultFont(f)
    except Exception:
        pass
    doc.setHtml(html)
    return doc


def _printer_mode():
    # type: () -> Any
    """QPrinter.HighResolution works everywhere it is exposed; never crash
    the preview if a binding reshuffles the enum (Qt6 scoped modes)."""
    qps = _Print.QPrinter
    for holder in (qps, getattr(qps, "PrinterMode", None)):
        v = getattr(holder, "HighResolution", None)
        if v is not None:
            return v
    return 0


def _portrait_value():
    # type: () -> Optional[Any]
    """Portrait orientation constant for the active binding.

    Qt5: QPrinter.Portrait (PyQt5) / QPrinter.PageOrientation.Portrait
    (PySide2).  There is *no* Qt.Portrait in Qt5 — reading it off QtCore.Qt
    raised AttributeError and crashed the archive preview.
    Qt6 (defensive): QPageLayout.Orientation.Portrait.
    """
    qps = _Print.QPrinter
    v = getattr(qps, "Portrait", None)          # PyQt5
    if v is not None:
        return v
    po = getattr(qps, "PageOrientation", None)  # PySide2 / newer PyQt5
    v = getattr(po, "Portrait", None)
    if v is not None:
        return v
    gl = getattr(_Gui, "QPageLayout", None)     # Qt6-style fallback
    v = getattr(getattr(gl, "Orientation", None), "Portrait", None)
    return v


def _setup_a4_portrait(printer):
    # type: (_Print.QPrinter) -> None
    try:
        printer.setPaperSize(_Print.QPrinter.A4)
    except Exception:
        pass
    orient = _portrait_value()
    if orient is not None:
        try:
            printer.setPageOrientation(orient)
        except Exception:
            # Portrait is the QPrinter default anyway; a failed enum call
            # must never take the whole preview down with it.
            pass


_RASTER_DPI = 300  # print quality when a page must go out as an image
_RASTER_BANDS = 8  # horizontal strips per page — see _raster_print


def _paint_ctx():
    # type: () -> Any
    ctx = _Gui.QAbstractTextDocumentLayout.PaintContext()
    try:
        pal = _Widgets.QApplication.palette()
        black = _Gui.QColor(0, 0, 0)
        for role in (_Gui.QPalette.Text, _Gui.QPalette.WindowText):
            pal.setBrush(role, _Gui.QBrush(black))
        ctx.palette = pal
    except Exception:
        pass
    return ctx


def _draw_vector(layout, painter, ctx, pw, ph, scale, total, printer):
    # type: (Any, Any, Any, float, float, float, float, Any) -> None
    """Vector pages for Qt's own engines (QPdfWriter / PdfFormat), which
    shape and embed Vazirmatn correctly.  CSS-space (96dpi) layout scaled
    to the device resolution; page model = clip + translate per page."""
    y = 0.0
    first = True
    while y < total:
        if not first:
            printer.newPage()
        first = False
        ctx.clip = _Core.QRectF(0.0, y, pw, ph)
        ctx.clipRect = _Core.QRectF(0.0, 0.0, pw, ph)
        painter.save()
        painter.scale(scale, scale)
        painter.translate(0.0, -y)
        layout.draw(painter, ctx)
        painter.restore()
        y += ph


def _raster_print(layout, ctx, printer, pw, ph, dev_w, dev_h, total):
    # type: (Any, Any, Any, float, float, float, float, float) -> None
    """Physical printer drivers AND the preview engine receive each page as
    a 300dpi image.  Measured field bug: GDI cannot see fonts loaded via
    QFontDatabase.addApplicationFont, so printing the invoice to e.g.
    Microsoft Print to PDF as live text came out Tahoma-substituted with
    every Persian letter unjoined and unreadable.  A raster page is
    pixel-identical to the on-screen preview on ANY driver, Canon included.

    Three measured constraints shape this function:
      * page images render while the printer painter is CLOSED — a QImage
        QPainter nested inside a live GDI painter aborts the page
        (EndPage failed 0x…211xxx);
      * one full-page 2479x3508 blit still dies in EndPage on the XPS /
        Print-to-PDF spooler for content-dense invoices, while the SAME
        image blitted in horizontal bands passes every time (determin-
        istic A/B measured: full FAIL at any payload, bands 4/8/16 OK)
        — so each page goes down as _RASTER_BANDS strip copies;
      * printer.newPage() between the pages while the painter is open.
    """
    s = float(_RASTER_DPI) / 96.0
    pages = []
    y = 0.0
    while y < total:
        if total - y < 2:
            break
        # ALWAYS a full-page canvas (rest stays white): a short last image
        # scaled onto a full page rect would stretch the invoice.
        img = _Gui.QImage(int(round(pw * s)), int(round(ph * s)),
                          _Gui.QImage.Format_RGB32)
        img.fill(_Gui.QColor("#ffffff"))
        ip = _Gui.QPainter(img)
        try:
            ip.setRenderHint(_Gui.QPainter.Antialiasing, True)
            ip.setRenderHint(_Gui.QPainter.TextAntialiasing, True)
            ip.scale(s, s)
            ctx.clip = _Core.QRectF(0.0, y, pw, ph)
            ctx.clipRect = _Core.QRectF(0.0, 0.0, pw, ph)
            ip.save()
            ip.translate(0.0, -y)
            layout.draw(ip, ctx)
            ip.restore()
        finally:
            ip.end()
        pages.append(img)
        y += ph
    if not pages:  # empty document: one blank page beats an aborted one
        img = _Gui.QImage(int(round(pw * s)), int(round(ph * s)),
                          _Gui.QImage.Format_RGB32)
        img.fill(_Gui.QColor("#ffffff"))
        pages.append(img)
    painter = _Gui.QPainter(printer)
    if not painter.isActive():
        painter.begin(printer)
    try:
        for idx, img in enumerate(pages):
            if idx:
                printer.newPage()
            painter.setRenderHint(_Gui.QPainter.SmoothPixmapTransform,
                                  False)
            ih = img.height()
            iw = img.width()
            bh = max(1, ih // _RASTER_BANDS)
            for k in range(_RASTER_BANDS):
                top = k * bh
                if top >= ih:
                    break
                hgt = min(bh, ih - top)
                # separate strip COPY: sharing one big buffer between
                # several live StretchDIBits was the failing pattern
                band = img.copy(0, top, iw, hgt)
                painter.drawImage(
                    _Core.QRectF(0.0, dev_h * top / float(ih),
                                 dev_w, dev_h * hgt / float(ih)),
                    band,
                    _Core.QRectF(0, 0, iw, hgt))
    finally:
        painter.end()


def _doc_print(doc, printer):
    # type: (Any, Any) -> None
    """Paginate doc across printer at the full content width.

    Everything is laid out once in a 96dpi CSS space (the printer page size
    converted by logicalDpiX — printer state is NEVER mutated mid-paint;
    an old setResolution() call here is what blanked the preview dialog),
    then handed to the engine that can render it faithfully.

    Qt5 OutputFormat (PyQt5 gotchas, both probed on the shipped binding):
    QPrinter.PdfFormat == 1 (Qt's internal PDF engine, which embeds the
    application font and is vector-safe); QPrinter.PrinterFormat == 0 (a
    real GDI driver) and its *name* is unexposed, and ScreenResolution is
    also == 0 but that's a ColorMode constant — so the driver mode is
    exactly ``fmt != PdfFormat`` on a QPrinter.
     * vector manual draw for QPdfWriter / QPrinter.PdfFormat (Qt-internal
       engines know the bundled Vazirmatn and embed it),
     * 300dpi raster pages for the driver mode (fmt 0) — physical printers
       AND Microsoft Print to PDF, whose GDI pipeline cannot see
       addApplicationFont faces and substitutes Tahoma, shredding Persian
       text into unreadable disconnected letters (the exact field bug).
    If the whole manual scheme fails we still fall back to doc.print_().
    """
    _P = _Print.QPrinter
    try:
        vector = type(printer).__name__ == "QPdfWriter"
        if not vector:
            fmt = int(printer.outputFormat())
            vector = fmt == int(_P.PdfFormat)
        dpi = float(printer.logicalDpiX()) or 96.0
        dev_w = float(printer.width())
        dev_h = float(printer.height())
        pw = dev_w * 96.0 / dpi
        ph = dev_h * 96.0 / dpi
        if pw <= 100 or ph <= 100:
            raise ValueError("printer size unreadable")
        doc.setTextWidth(pw)
        layout = doc.documentLayout()
        if vector:
            # Only the vector branch binds the layout to the printer.
            # The raster pages need no binding at all: every font in the
            # doc is pixel-sized, so metrics are device-independent
            # (measured identical renders with and without it).
            try:
                layout.setPaintDevice(printer)
            except Exception:
                pass
        total = float(layout.documentSize().height())
        if total <= 0:
            total = ph
        ctx = _paint_ctx()
        if not vector:
            # Raster: every page image is rendered while NO printer
            # painter is active, then one open/close cycle blits them —
            # nesting a QImage QPainter inside a live GDI painter aborts
            # the page (measured EndPage failure).
            _raster_print(layout, ctx, printer, pw, ph, dev_w, dev_h,
                          total)
            return
        painter = _Gui.QPainter(printer)
        if not painter.isActive():
            painter.begin(printer)
        try:
            _draw_vector(layout, painter, ctx, pw, ph, dpi / 96.0,
                         total, printer)
        finally:
            painter.end()
    except Exception:
        doc.print_(printer)


def show_print_preview(parent, html):
    # type: (Any, str) -> None
    doc = _make_doc(html)
    printer = _Print.QPrinter(_printer_mode())
    # Configure paper/orientation BEFORE the dialog is built, so its
    # initial page geometry already reflects A4 portrait.
    _setup_a4_portrait(printer)
    preview = _Print.QPrintPreviewDialog(printer, parent)

    def render_preview(p):
        # type: (_Print.QPrinter) -> None
        _doc_print(doc, p)

    preview.paintRequested.connect(render_preview)
    preview.setWindowModality(_Core.Qt.ApplicationModal)
    preview.resize(_preview_size(parent))
    preview.exec_()


def _preview_size(parent):
    # type: (Any) -> Any
    """A generous but screen-aware preview window: ~85% of the display the
    parent (or the primary screen) is on."""
    screen = None
    try:
        if parent is not None:
            win = parent.window()
            if win is not None:
                screen = _Widgets.QApplication.screenAt(
                    win.frameGeometry().center())
        if screen is None:
            screen = _Widgets.QApplication.primaryScreen()
        avail = screen.availableGeometry()
        return _Core.QSize(min(1240, int(avail.width() * 0.85)),
                           min(860, int(avail.height() * 0.85)))
    except Exception:
        return _Core.QSize(1100, 800)


def print_html_direct(parent, html):
    # type: (Any, str) -> None
    doc = _make_doc(html)
    printer = _Print.QPrinter(_printer_mode())
    _setup_a4_portrait(printer)
    dlg = _Print.QPrintDialog(printer, parent)
    if dlg.exec_() == _Widgets.QDialog.Accepted:
        _doc_print(doc, printer)


def build_report_html(title, sections):
    # type: (str, Sequence[Any]) -> str
    """Generic report HTML.

    sections: list of dicts, each {'kind':'table'|'cards'|'text',
               'columns':[...], 'rows':[[...],...], 'cards':[{'label','value','color'}],
               'text':str}.
    """
    font = _print_font()
    body = ["<html><head>%s</head>" % _doc_style(font),
            "<body dir='rtl' style='font-family:\"%s\"; color:%s; "
            "text-align:right;'>" % (font, _INK),
            # body-level divs ignore dir/text-align (Qt5); centre via cell.
            "<table dir='rtl' width='745' cellspacing='0' cellpadding='0'>"
            f"<tr><td dir='rtl' width='745' style='width:745px;border:none;"
            "text-align:center;font-size:19px;font-weight:bold;'>"
            f"<span style='color:{_TEAL};'>{_esc(title)}</span>"
            "</td></tr></table>"]
    for sec in sections:
        kind = sec.get("kind", "text")
        if kind == "text":
            body.append("<table dir='rtl' width='745' cellspacing='0' "
                        "cellpadding='0'><tr><td dir='rtl' width='745' "
                        "style='width:745px;border:none;font-size:12px;"
                        "color:%s;'>%s</td></tr></table>"
                        % (_MUTED, _esc(sec.get("text", ""))))
        elif kind == "cards":
            card_html = []
            for c in sec["cards"]:
                color = c.get("color", "#333")
                card_html.append(
                    "<div dir='rtl' style='display:inline-block; padding:10px 14px; "
                    "margin-right:10px; border:2px solid %s; color:%s; "
                    "font-weight:bold; font-size:13px;'>"
                    "%s: %s</div>" % (_esc(color), _esc(color),
                                       _esc(c["label"]),
                                       _esc(str(c["value"]))))
            # Qt5 flows inline blocks left-to-right; reversed source order
            # puts the FIRST logical card on the right, RTL-style. The
            # wrapper must be a dir='rtl' CELL (bare divs ignore it).
            body.append(
                "<table dir='rtl' width='745' cellspacing='0' cellpadding='0'"
                "><tr><td dir='rtl' width='745' style='width:745px;"
                "border:none;'>%s</td></tr></table>"
                % "".join(reversed(card_html)))
        elif kind == "table":
            cols = sec["columns"]
            if sec.get("title"):
                body.append(
                    "<table dir='rtl' width='745' cellspacing='0' "
                    "cellpadding='0'><tr><td dir='rtl' width='745' "
                    "style='width:745px;border:none;font-size:13px;"
                    "font-weight:bold;'>%s</td></tr></table>"
                    % _esc(sec["title"]))
            # Columns are emitted REVERSED (see _invoice_doc note): Qt5
            # always lays table cells out left-to-right regardless of `dir`.
            header = "".join(
                "<th dir='rtl' style='text-align:left;padding:6px 8px;'>"
                "%s</th>" % _esc(c) for c in reversed(list(cols)))
            rows_html = []
            for i, row in enumerate(sec.get("rows", [])):
                bg = _ZEBRA if i % 2 else "#ffffff"
                cells = []
                for j in reversed(range(len(cols))):
                    val = row[j] if j < len(row) else ""
                    cells.append("<td dir='rtl' style='padding:5px 8px;'>"
                                 "%s</td>" % _esc(str(val)))
                rows_html.append("<tr style='background:%s'>%s</tr>"
                                 % (bg, "".join(cells)))
            body.append("<table dir='rtl' width='745' cellspacing='0' "
                        "cellpadding='0' style='border:1px solid %s;'>"
                        "<tr style='background:%s'>%s</tr>%s</table>" % (
                            _LINE, _TEAL, header, "".join(rows_html)))
    body.append("</body></html>")
    return "".join(body)
