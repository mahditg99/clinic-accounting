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


def show_print_preview(parent, html):
    # type: (Any, str) -> None
    doc = _Gui.QTextDocument()
    doc.setHtml(html)
    printer = _Print.QPrinter(_Print.QPrinter.HighResolution)
    preview = _Print.QPrintPreviewDialog(printer, parent)
    printer.setPaperSize(_Print.QPrinter.A4)
    printer.setPageOrientation(_Core.Qt.Portrait)

    def render_preview(p):
        # type: (_Print.QPrinter) -> None
        doc.print_(p)

    preview.paintRequested.connect(render_preview)
    preview.setWindowModality(_Core.Qt.ApplicationModal)
    preview.resize(1000, 800)
    preview.exec_()


def print_html_direct(parent, html):
    # type: (Any, str) -> None
    doc = _Gui.QTextDocument()
    doc.setHtml(html)
    printer = _Print.QPrinter(_Print.QPrinter.HighResolution)
    printer.setPaperSize(_Print.QPrinter.A4)
    dlg = _Print.QPrintDialog(printer, parent)
    if dlg.exec_() == _Widgets.QDialog.Accepted:
        doc.print_(printer)


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
