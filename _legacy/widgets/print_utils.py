# -*- coding: utf-8 -*-
"""HTML invoice/report printing helpers using QTextDocument.

Uses QPrintPreviewDialog so the user can preview and choose printer.
"""
from __future__ import annotations

from typing import Any, List, Optional, Sequence

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


def build_invoice_html(invoice):
    # type: (dict) -> str
    """invoice dict keys: app_title, invoice_no, issued_at (ISO),
    patient_name, file_no, doctor_name(optional), rows (list of dicts with
    index, title, unit_price, quantity, row_total), total, paid, remaining,
    show_doctor (bool)."""
    app_title = _esc(invoice.get("app_title", "آذران طب"))
    inv_no = _esc(invoice.get("invoice_no", ""))
    issued = _jalali(invoice.get("issued_at"))
    patient = _esc(invoice.get("patient_name", ""))
    file_no = _esc(invoice.get("file_no", ""))
    rows = invoice.get("rows", []) or []
    total = _esc(_money(invoice.get("total", 0)))
    paid = _esc(_money(invoice.get("paid", 0)))
    remaining = _esc(_money(invoice.get("remaining", 0)))
    show_doctor = invoice.get("show_doctor", False)
    doctor_name = _esc(invoice.get("doctor_name", "")) if show_doctor else ""

    rows_html = []
    for r in rows:
        rows_html.append(
            "<tr><td style='text-align:center'>%s</td>"
            "<td>%s</td>"
            "<td style='text-align:left'>%s</td>"
            "<td style='text-align:center'>%s</td>"
            "<td style='text-align:left'>%s</td></tr>" % (
                date_utils.to_persian_digits(str(r["index"])),
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
        "<div>شماره فاکتور: <b>%s</b></div>"
        "<div>تاریخ: <b>%s</b></div>"
        "<div>شماره پرونده: <b>%s</b></div>"
        "<div>نام بیمار: <b>%s</b></div>" % (
            _doc_style(), app_title, inv_no, issued, file_no, patient)
    )
    if show_doctor and doctor_name:
        doc += "<div>پزشک معالج: <b>%s</b></div>" % doctor_name
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
        "</body></html>" % (rows_body, total, paid, remaining))
    return doc


def show_print_preview(parent, html):
    # type: (Any, str) -> None
    doc = _Gui.QTextDocument()
    doc.setHtml(html)
    printer = _Print.QPrinter(_Print.QPrinter.HighResolution)
    preview = _Print.QPrintPreviewDialog(printer, parent)
    # Default to A4 portrait; user can change in dialog.
    printer.setPaperSize(_Print.QPrinter.A4)
    printer.setPageOrientation(_Core.Qt.Portrait)

    def render_preview(p):
        # type: (_Print.QPrinter) -> None
        p.setPageSize(_Print.QPrinter.A4)
        doc.print_(p)

    preview.paintRequested.connect(render_preview)
    preview.setWindowModality(_Core.Qt.ApplicationModal)
    preview.exec_()


def print_html_direct(parent, html):
    # type: (Any, str) -> None
    """Print without preview (no user confirmation dialog)."""
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

    title: report heading.
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
