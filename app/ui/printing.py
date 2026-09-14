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


def _doc_style(font_name="Tahoma"):
    # type: (str) -> str
    return (
        "<style>"
        "body{font-family:'%s'; direction:rtl; text-align:right;}"
        "table{border-collapse:collapse; width:100%%;}"
        "th,td{border:1px solid #888; padding:4px 6px;}"
        "th{background:#f0f0f0;}"
        ".title{font-size:20px; font-weight:bold; text-align:center;}"
        ".meta{font-size:12px; margin-top:6px;}"
        ".total{font-weight:bold; font-size:14px; margin-top:8px;}"
        "</style>" % font_name
    )


def _invoice_doc(app_title, subtitle, inv_no, issued, file_no, patient,
                 doctor_name, notes, rows, total, paid, remaining):
    # type: (str, str, str, str, str, str, str, str, Sequence, int, int, int) -> str
    rows_html = []
    for i, r in enumerate(rows):
        rows_html.append(
            "<tr><td style='text-align:center'>%s</td>"
            "<td>%s</td>"
            "<td style='text-align:left'>%s</td>"
            "<td style='text-align:center'>%s</td>"
            "<td style='text-align:left'>%s</td></tr>" % (
                date_utils.to_persian_digits(str(i + 1)),
                _esc(r["title"]),
                _esc(_money(r["unit_price"])),
                date_utils.to_persian_digits(str(r["quantity"])),
                _esc(_money(r["row_total"])),
            ))
    rows_body = "".join(rows_html) if rows_html else (
        "<tr><td colspan='5' style='text-align:center'>(بدون ردیف)</td></tr>")
    doc = (
        "<html><head>%s</head><body>"
        "<div class='title'>%s</div>"
        "<div class='meta'>"
        "<div>%s</div>"
        "<div>شماره فاکتور: <b>%s</b></div>"
        "<div>تاریخ: <b>%s</b></div>"
        "<div>شماره پرونده: <b>%s</b></div>"
        "<div>نام بیمار: <b>%s</b></div>" % (
            _doc_style(), _esc(app_title), _esc(subtitle), _esc(inv_no),
            _esc(issued), _esc(file_no), _esc(patient))
    )
    if doctor_name:
        doc += "<div>پزشک معالج: <b>%s</b></div>" % _esc(doctor_name)
    if notes:
        doc += "<div>یادداشت: %s</div>" % _esc(notes)
    doc += "</div>"
    doc += (
        "<table style='margin-top:10px'>"
        "<tr><th>ردیف</th><th>شرح</th><th>فی</th>"
        "<th>تعداد</th><th>جمع</th></tr>"
        "%s"
        "</table>"
        "<div class='total' style='margin-top:12px'>"
        "<div>جمع کل: %s تومان</div>"
        "<div>پرداخت‌شده: %s تومان</div>"
        "<div>باقی مانده: %s تومان</div>"
        "</div>"
        "</body></html>" % (rows_body, _money(total), _money(paid),
                            _money(remaining)))
    return doc


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
        int(invoice.get("remaining", 0)))


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
        data.get("rows", []) or [], total, paid, total - paid)


def build_saved_invoice_html(invoice_id):
    # type: (int) -> Optional[str]
    """Print HTML for a persisted invoice — the single builder behind the
    archive's «مشاهده / چاپ» and the post-save print preview."""
    from .. import models, settings as settings_mod
    inv = models.get_invoice(invoice_id)
    if inv is None:
        return None
    items = models.list_invoice_items(invoice_id)
    paid = models.invoice_paid_sum(invoice_id)
    return build_invoice_html({
        "app_title": settings_mod.get_setting("app_title", "آذران طب"),
        "invoice_no": inv["invoice_no"],
        "issued_at": inv["issued_at"],
        "patient_name": "%s %s" % (inv["first_name"], inv["last_name"]),
        "file_no": inv["file_no"],
        "doctor_name": inv.get("doctor_name") or "",
        "show_doctor": settings_mod.get_setting("show_doctor_in_print",
                                                "0") == "1",
        "notes": inv.get("notes") or "",
        "rows": [{"title": it["title"], "unit_price": it["unit_price"],
                  "quantity": it["quantity"], "row_total": it["row_total"]}
                 for it in items],
        "total": int(inv["total_amount"]),
        "paid": paid,
        "remaining": int(inv["total_amount"]) - paid,
    })


def show_invoice_preview(parent, invoice_id):
    # type: (Any, int) -> None
    """Open the A4-portrait print preview for a saved invoice. The preview
    dialog carries its own print button, so the user prints only if they
    want."""
    html = build_saved_invoice_html(invoice_id)
    if html:
        show_print_preview(parent, html)


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


def _doc_print(doc, printer):
    # type: (Any, Any) -> None
    """Print a document with CSS px kept at their 96dpi physical size.

    Qt lays out QTextDocument at 1 CSS px = 1 *device* px of the paint
    device.  On a QPrinter(HighResolution) (1200 dpi on Windows) that
    shrinks the whole invoice to a ~1mm-tall band of microscopic text —
    measured: 8.3x2.7in content on an 8.3x11.7 page, which is the "preview
    page is tiny" report.  Normalizing the printer's logical resolution to
    96 restores the expected sizes; text still renders vector-crisp at the
    printer's native DPI, and Qt's own paginated print() keeps multi-page
    invoices paginating (this binding does not expose the manual
    page-by-page layout-draw overload, so do not try to reimplement it).
    """
    try:
        if printer.logicalDpiX() >= 120:
            printer.setResolution(96)
    except Exception:
        pass
    doc.print_(printer)


def show_print_preview(parent, html):
    # type: (Any, str) -> None
    doc = _Gui.QTextDocument()
    doc.setHtml(html)
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
    doc = _Gui.QTextDocument()
    doc.setHtml(html)
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
    body = ["<html><head>%s</head><body>" % _doc_style(),
            "<div class='title'>%s</div>" % _esc(title)]
    for sec in sections:
        kind = sec.get("kind", "text")
        if kind == "text":
            body.append("<div class='meta'>%s</div>" % _esc(sec.get("text", "")))
        elif kind == "cards":
            card_html = []
            for c in sec["cards"]:
                color = c.get("color", "#333")
                card_html.append(
                    "<div style='display:inline-block; padding:10px 14px; "
                    "margin-left:10px; border:2px solid %s; color:%s; "
                    "font-weight:bold; font-size:14px; border-radius:6px;'>"
                    "%s: %s</div>" % (_esc(color), _esc(color),
                                       _esc(c["label"]),
                                       _esc(str(c["value"]))))
            body.append("<div style='margin:10px 0'>%s</div>" % "".join(card_html))
        elif kind == "table":
            cols = sec["columns"]
            if sec.get("title"):
                body.append("<div class='meta'><b>%s</b></div>"
                            % _esc(sec["title"]))
            header = "".join("<th>%s</th>" % _esc(c) for c in cols)
            rows_html = []
            for row in sec.get("rows", []):
                cells = []
                for i in range(len(cols)):
                    val = row[i] if i < len(row) else ""
                    cells.append("<td>%s</td>" % _esc(str(val)))
                rows_html.append("<tr>%s</tr>" % "".join(cells))
            body.append("<table style='margin-top:8px'><tr>%s</tr>%s</table>" % (
                header, "".join(rows_html)))
    body.append("</body></html>")
    return "".join(body)
