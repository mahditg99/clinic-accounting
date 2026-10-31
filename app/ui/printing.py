# -*- coding: utf-8 -*-
"""HTML invoice/report printing helpers using QTextDocument (v2 UI).

Reports print A4 portrait. Invoices print as the clinic's «برگه فاکتور
بیمار» sheet: A5 landscape, fitted to exactly one page, Nastaliq letterhead,
faint hollow lettering behind, doctor name per the settings toggle.
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


def _nastaliq_font():
    # type: () -> str
    """Letterhead face (bundled IranNastaliq), body font as fallback."""
    try:
        from ..utils import nastaliq_font
        return nastaliq_font()
    except Exception:
        return _print_font()


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


# --------------------------------------------------------------------------- #
# Patient invoice sheet («برگه فاکتور بیمار») — landscape form that follows the
# clinic's paper pad. Fixed wording lives here, not in settings.
# --------------------------------------------------------------------------- #
_SHEET_TITLE = "برگه فاکتور بیمار"
_SHEET_CLINIC_LINE = "کلینیک ارتوپدی فنی"
_SHEET_CLINIC_NAME = "آذران طب"
_SHEET_RULES = [
    "وسیله تحویل داده شده به علت بهداشتی بودن پس گرفته نمی‌شود.",
    "قبل از مراجعه جهت اطمینان از آماده بودن وسایل تماس حاصل فرمایید.",
    "در صورت تحویل نگرفتن وسیله سفارش داده شده طی ۶ ماه پس از آماده شدن، "
    "وسیله به کارگاه برگشت خورده و ما هیچ مسئولیتی در قبال آن نداریم.",
    "لطفا هنگام مراجعه بعدی این برگه را همراه داشته باشید.",
    "حضور بیمار در زمان تحویل وسیله ضروری است.",
]
_SHEET_ADDRESS = ("آدرس: تبریز، ۱۷ شهریور جدید، مابین تقاطع طالقانی و "
                  "شریعتی، جنب کوچه شرکت، ساختمان پزشکان نوین، طبقه ۵ واحد A")
_SHEET_CONTACT = ("لطفا برای پیگیری در ساعات کاری شنبه تا چهارشنبه (صبح‌ها "
                  "۱۰:۳۰ تا ۱۳:۳۰ و عصرها ۱۶ تا ۲۱) با شماره ۰۴۱۳۵۵۳۵۶۷۵ "
                  "تماس بگیرید.")

_SHEET_INK = "#161616"
_SHEET_LINE = "#2b2b2b"
_SHEET_BRAND = "#1f3a68"
_SHEET_RED = "#c0392b"
# Lilac (بنفش یاسی) of the pad's letterhead and background emblem.
_LILAC = "#9a6bbf"

def invoice_page_opts(builder=None):
    # type: (Any) -> dict
    """Page setup for the invoice sheet: A5 landscape, watermark on.

    ``builder(zoom, fill_px) -> html`` lets the printer fit the sheet to
    the page it actually prints on (see _fit_doc): the form then fills the
    A5 page exactly, and many item rows shrink it instead of spilling onto
    a second sheet. Pass to show_print_preview / print_html_direct."""
    opts = {"paper": "A5", "landscape": True, "watermark": True}
    if builder is not None:
        opts["builder"] = builder
    return opts


def _invoice_sheet(data, zoom=None, fill=0):
    # type: (dict, Optional[float], int) -> str
    """Invoice print HTML. ``data`` keys: invoice_no, issued_iso, time (str,
    may be empty), file_no, patient_name, doctor_name (empty = blank cell),
    total, paid, remaining, rows (title/quantity/unit_price/row_total), notes.

    Qt5 rich text lays table columns out left-to-right whatever `dir` says,
    so every horizontal structure is emitted in REVERSED source order (see
    the notes above _doc_style). Widths are percentages, so the same markup
    fills any paper the printer reports. ``fill`` adds that many px of
    blank item area so the form reaches the bottom of the page.
    """
    z = float(zoom if zoom is not None else 1.0)
    font = _print_font()

    def fs(n):
        return "font-size:%dpx;" % int(round(n * z))

    def pad(v, h):
        return "padding:%dpx %dpx;" % (int(round(v * z)), int(round(h * z)))

    line = "1px solid %s" % _SHEET_LINE
    fa = date_utils.to_persian_digits

    def money(value):
        return _esc(_money(int(value))) + " تومان"

    # ---- header: [date + number] [clinic mark] [title]  (reversed) -------- #
    stamp = _esc(date_utils.iso_to_jalali_long_persian_str(
        data.get("issued_iso")))
    if data.get("time"):
        stamp += " - ساعت " + _esc(fa(data["time"]))
    head = (
        "<table dir='rtl' width='100%' cellspacing='0' cellpadding='0'><tr>"
        f"<td dir='rtl' width='34%' valign='middle' style='{pad(8, 14)}"
        f"{fs(12.5)}text-align:right;'>{stamp}<br/>"
        f"شماره فاکتور {_esc(fa(str(data.get('invoice_no', ''))))}</td>"
        f"<td dir='rtl' width='32%' valign='middle' style='{pad(8, 4)}"
        f"text-align:center;'>{_letterhead_img(z)}</td>"
        f"<td dir='rtl' width='34%' valign='middle' style='{pad(8, 14)}"
        f"{fs(17)}font-weight:bold;'>{_SHEET_TITLE}</td>"
        "</tr></table>")

    # ---- patient / money grid: label | value | label | value (reversed) --- #
    def grid_row(l1, v1, l2, v2):
        edge = f"border-top:{line};"
        cells = (
            f"<td dir='rtl' width='33%' style='{edge}border-right:{line};"
            f"{pad(5, 12)}{fs(13)}font-weight:bold;'>{v2}</td>"
            f"<td dir='rtl' width='13%' style='{edge}{pad(5, 12)}{fs(13)}"
            f"font-weight:bold;'>{l2}</td>"
            f"<td dir='rtl' width='40%' style='{edge}{pad(5, 12)}{fs(13)}"
            f"font-weight:bold;'>{v1}</td>"
            f"<td dir='rtl' width='14%' style='{edge}{pad(5, 12)}{fs(13)}"
            f"font-weight:bold;'>{l1}</td>")
        return f"<tr>{cells}</tr>"

    grid = (
        "<table dir='rtl' width='100%' cellspacing='0' cellpadding='0'>"
        + grid_row("شماره پرونده", _esc(fa(str(data.get("file_no", "")))),
                   "هزینه", money(data.get("total", 0)))
        + grid_row("نام بیمار", _esc(data.get("patient_name", "")),
                   "بیعانه", money(data.get("paid", 0)))
        + grid_row("نام پزشک", _esc(data.get("doctor_name", "")),
                   "مانده", money(data.get("remaining", 0)))
        + "</table>")

    # ---- items: ردیف | وسیله طبی | تعداد | قیمت واحد | جمع  (reversed) ------ #
    def item_cell(width, text, extra="", head_row=False):
        edge = (f"border-top:{line};" if head_row
                else "border-top:1px solid #8a8a8a;")
        return (f"<td dir='rtl' width='{width}%' style='{edge}{pad(4, 10)}"
                f"{fs(13)}{extra}'>{text}</td>")

    def item_row(idx, title, qty, unit, total, head_row=False):
        b = "font-weight:bold;" if head_row else ""
        return ("<tr>" + item_cell(18, total, b, head_row)
                + item_cell(18, unit, b, head_row)
                + item_cell(11, qty, b, head_row)
                + item_cell(44, title, b, head_row)
                + item_cell(9, idx, b, head_row) + "</tr>")

    items = [item_row("ردیف", "وسیله طبی", "تعداد", "قیمت واحد", "جمع",
                      head_row=True)]
    for i, r in enumerate(data.get("rows") or [], 1):
        items.append(item_row(
            fa(str(i)), _esc(r["title"]), _esc(fa(str(r["quantity"]))),
            _esc(_money(r["unit_price"])), _esc(_money(r["row_total"]))))
    items_html = ("<table dir='rtl' width='100%' cellspacing='0' "
                  "cellpadding='0'>" + "".join(items) + "</table>")

    # ---- free-text notes (only when the operator wrote any) --------------- #
    notes_html = ""
    if data.get("notes"):
        notes_html = (
            "<table dir='rtl' width='100%' cellspacing='0' cellpadding='0'>"
            f"<tr><td dir='rtl' style='border-top:1px solid #8a8a8a;"
            f"{pad(4, 10)}{fs(12.5)}'><b>توضیحات:</b> "
            f"{_esc(data['notes'])}</td></tr></table>")

    # ---- fixed terms, address and phone ----------------------------------- #
    rules = []
    for i, text in enumerate(_SHEET_RULES, 1):
        color = _SHEET_RED if i == len(_SHEET_RULES) else _SHEET_INK
        rules.append(
            f"<div style='{fs(12)}font-weight:bold;color:{color};"
            f"margin:0px;'>{fa(str(i))}. {_esc(text)}</div>")
    foot = (
        "<table dir='rtl' width='100%' cellspacing='0' cellpadding='0'><tr>"
        f"<td dir='rtl' style='border-top:{line};{pad(8, 12)}'>"
        + "".join(rules)
        + f"<div style='{fs(5)}'>&nbsp;</div>"
        f"<div style='{fs(12)}margin:0px;'>{_esc(_SHEET_ADDRESS)}</div>"
        f"<div style='{fs(5)}'>&nbsp;</div>"
        f"<div style='{fs(12)}text-align:center;margin:0px;'>"
        f"{_esc(_SHEET_CONTACT)}</div>"
        "</td></tr></table>")

    return (
        "<html><head><style>"
        f"body{{font-family:'{font}'; color:{_SHEET_INK};}}"
        "table{border-collapse:collapse;} td{padding:0px;}"
        "</style></head>"
        f"<body dir='rtl' style=\"font-family:'{font}'; color:{_SHEET_INK};"
        " text-align:right;\">"
        "<table dir='rtl' width='100%' cellspacing='0' cellpadding='0' "
        f"border='1' style='border-style:solid;border-color:{_SHEET_LINE};'>"
        "<tr><td dir='rtl' style='padding:0px;border-style:none;'>"
        + head + grid + items_html + notes_html + _spacer(fill) + foot
        + "</td></tr></table></body></html>")


# --------------------------------------------------------------------------- #
# Letterhead «کلینیک ارتوپدی فنی / آذران طب» in Nastaliq.
#
# Rendered to an image instead of rich text: Nastaliq's ascent/descent is
# reported very differently by the Windows font engine and by FreeType, so as
# HTML text the second line ran over the header's bottom rule on Windows.
# Painting it here and cropping to the actual ink gives the same size and
# placement on every machine. The image is registered on the QTextDocument
# (attach_resources) under _LH_SCHEME.
# --------------------------------------------------------------------------- #
_LH_SCHEME = "azaran-letterhead"
_LH_SCALE = 4.0          # image px per CSS px (sharp at 300dpi print)
_LH_CACHE = {}           # zoom key -> (QImage, css_w, css_h)


_DARK = None  # compiled lazily: any byte darker than 200


def _ink_rect(img):
    # type: (Any) -> Any
    """Bounding rect of the painted (non-transparent) pixels of ``img``
    (None if blank). Scans alpha rows as bytes (C-speed regex)."""
    global _DARK
    import re
    if _DARK is None:
        _DARK = re.compile(b"[\x38-\xff]")
    g = img.convertToFormat(_Gui.QImage.Format_Alpha8)
    w, h, bpl = g.width(), g.height(), g.bytesPerLine()
    ptr = g.constBits()
    ptr.setsize(bpl * h)
    data = bytes(ptr)
    top, bottom, left, right = None, None, w, -1
    for y in range(h):
        row = data[y * bpl:y * bpl + w]
        m = _DARK.search(row)
        if m is None:
            continue
        if top is None:
            top = y
        bottom = y
        if m.start() < left:
            left = m.start()
        last = w - 1 - _DARK.search(row[::-1]).start()
        if last > right:
            right = last
    if top is None:
        return None
    return _Core.QRect(left, top, right - left + 1, bottom - top + 1)


def _render_line(text, px):
    # type: (str, int) -> Any
    """One Nastaliq line drawn on a white canvas and cropped to its ink."""
    font = _Gui.QFont(_nastaliq_font())
    font.setPixelSize(int(px))
    font.setBold(True)
    w, h = int(px * len(text) * 0.9) + 40, int(px * 3.2)
    img = _Gui.QImage(w, h, _Gui.QImage.Format_ARGB32_Premultiplied)
    img.fill(_Core.Qt.transparent)
    p = _Gui.QPainter(img)
    try:
        p.setRenderHint(_Gui.QPainter.Antialiasing, True)
        p.setRenderHint(_Gui.QPainter.TextAntialiasing, True)
        p.setFont(font)
        p.setPen(_Gui.QColor(_LILAC))
        p.setLayoutDirection(_Core.Qt.RightToLeft)
        p.drawText(_Core.QRectF(0, 0, w, h),
                   _Core.Qt.AlignCenter | _Core.Qt.TextSingleLine, text)
    finally:
        p.end()
    r = _ink_rect(img)
    return img.copy(r) if r is not None else img


def _letterhead(zoom):
    # type: (float) -> tuple
    key = "%.2f" % zoom
    hit = _LH_CACHE.get(key)
    if hit is not None:
        return hit
    k = _LH_SCALE * zoom
    l1 = _render_line(_SHEET_CLINIC_LINE, 27 * k)
    l2 = _render_line(_SHEET_CLINIC_NAME, 38 * k)
    gap = int(2 * k)
    w = max(l1.width(), l2.width())
    h = l1.height() + gap + l2.height()
    img = _Gui.QImage(w, h, _Gui.QImage.Format_ARGB32_Premultiplied)
    img.fill(_Core.Qt.transparent)
    p = _Gui.QPainter(img)
    try:
        p.drawImage((w - l1.width()) // 2, 0, l1)
        p.drawImage((w - l2.width()) // 2, l1.height() + gap, l2)
    finally:
        p.end()
    hit = (img, int(round(w / _LH_SCALE)), int(round(h / _LH_SCALE)))
    _LH_CACHE[key] = hit
    return hit


def _letterhead_img(zoom):
    # type: (float) -> str
    """<img> tag for the letterhead (falls back to plain text off-Qt)."""
    try:
        _img, cw, ch = _letterhead(zoom)
    except Exception:
        return "%s<br/>%s" % (_SHEET_CLINIC_LINE, _SHEET_CLINIC_NAME)
    return ("<img src='%s:%.2f' width='%d' height='%d'/>"
            % (_LH_SCHEME, zoom, cw, ch))


_SPACER_URL = "azaran-spacer:1"
_SPACER = []  # lazily created 1x1 transparent QImage


def _spacer(fill):
    # type: (int) -> str
    """Exact-height blank block (a transparent image: rich-text block heights
    are otherwise only approximately controllable)."""
    fill = int(fill)
    if fill <= 0:
        return ""
    return ("<table dir='rtl' width='100%' cellspacing='0' cellpadding='0'>"
            "<tr><td style='padding:0px;'><img src='" + _SPACER_URL +
            "' width='1' height='%d'/></td></tr></table>" % fill)


def attach_resources(doc):
    # type: (Any) -> None
    """Register the letterhead images (and the spacer) on a QTextDocument —
    print documents and the QTextEdit preview — before its HTML is set."""
    for key, (img, _w, _h) in list(_LH_CACHE.items()):
        doc.addResource(_Gui.QTextDocument.ImageResource,
                        _Core.QUrl("%s:%s" % (_LH_SCHEME, key)), img)
    if not _SPACER:
        img = _Gui.QImage(1, 1, _Gui.QImage.Format_ARGB32_Premultiplied)
        img.fill(_Core.Qt.transparent)
        _SPACER.append(img)
    doc.addResource(_Gui.QTextDocument.ImageResource,
                    _Core.QUrl(_SPACER_URL), _SPACER[0])


def _issue_time(issued_at):
    # type: (Optional[str]) -> str
    """HH:MM for the sheet header. issued_at is normally date-only, so the
    clock time is only known for a sheet issued today (printed now); older
    invoices print without a time rather than with a made-up one."""
    s = str(issued_at or "")
    if len(s) >= 16 and s[10] in " T":
        return s[11:16]
    if s[:10] == date_utils.today_iso():
        return date_utils.now_iso()[11:16]
    return ""


def build_invoice_html(invoice, zoom=None, fill=0):
    # type: (dict, Optional[float], int) -> str
    """invoice dict keys: invoice_no, issued_at (ISO), patient_name, file_no,
    doctor_name, show_doctor (bool), notes (optional), rows (title,
    unit_price, quantity, row_total), total, paid, remaining."""
    return _invoice_sheet({
        "invoice_no": invoice.get("invoice_no", ""),
        "issued_iso": invoice.get("issued_at"),
        "time": _issue_time(invoice.get("issued_at")),
        "file_no": invoice.get("file_no", ""),
        "patient_name": invoice.get("patient_name", ""),
        "doctor_name": invoice.get("doctor_name", "")
        if invoice.get("show_doctor") else "",
        "notes": invoice.get("notes", "") or "",
        "rows": invoice.get("rows", []) or [],
        "total": int(invoice.get("total", 0)),
        "paid": int(invoice.get("paid", 0)),
        "remaining": int(invoice.get("remaining", 0)),
    }, zoom, fill)


def build_proforma_html(data, zoom=None, fill=0):
    # type: (dict, Optional[float], int) -> str
    """Unsaved invoice preview. Keys: invoice_no, issued_iso, patient_name,
    file_no, doctor_name, show_doctor, notes, rows, total, paid."""
    total = int(data.get("total", 0))
    paid = int(data.get("paid", 0))
    return build_invoice_html({
        "invoice_no": data.get("invoice_no", ""),
        "issued_at": data.get("issued_iso"),
        "patient_name": data.get("patient_name", "—"),
        "file_no": data.get("file_no", ""),
        "doctor_name": data.get("doctor_name", ""),
        "show_doctor": data.get("show_doctor"),
        "notes": data.get("notes", ""),
        "rows": data.get("rows", []),
        "total": total, "paid": paid, "remaining": total - paid,
    }, zoom, fill)


def build_saved_invoice_html(invoice_id, zoom=None, fill=0):
    # type: (int, Optional[float], int) -> Optional[str]
    """Print HTML for a persisted invoice — the single builder behind the
    archive's «مشاهده / چاپ» and the post-save print preview. The doctor's
    name appears only when «نمایش نام پزشک در چاپ» is on in the settings."""
    data = _saved_invoice_data(invoice_id)
    return build_invoice_html(data, zoom, fill) if data else None


def _saved_invoice_data(invoice_id):
    # type: (int) -> Optional[dict]
    from .. import models, settings as settings_mod
    from ..database import NO_DOCTOR_NAME
    inv = models.get_invoice(invoice_id)
    if inv is None:
        return None
    items = models.list_invoice_items(invoice_id)
    paid = models.invoice_paid_sum(invoice_id)
    show_doctor = settings_mod.get_setting("show_doctor_in_print",
                                           "0") == "1"
    doctor = (inv.get("doctor_name") or "").strip()
    if doctor == NO_DOCTOR_NAME:
        doctor = ""
    return {
        "invoice_no": inv["invoice_no"],
        "issued_at": inv["issued_at"],
        "patient_name": "%s %s" % (inv["first_name"], inv["last_name"]),
        "file_no": inv["file_no"],
        "doctor_name": doctor,
        "show_doctor": show_doctor,
        "notes": inv.get("notes") or "",
        "rows": [{"title": it["title"], "unit_price": it["unit_price"],
                  "quantity": it["quantity"], "row_total": it["row_total"]}
                 for it in items],
        "total": int(inv["total_amount"]),
        "paid": paid,
        "remaining": int(inv["total_amount"]) - paid,
    }


def show_invoice_preview(parent, invoice_id):
    # type: (Any, int) -> bool
    """Open the print preview for a saved invoice. Whether the doctor's name
    is printed is decided by the settings page — no per-print question."""
    data = _saved_invoice_data(invoice_id)
    if not data:
        return False
    show_print_preview(
        parent, build_invoice_html(data),
        page=invoice_page_opts(lambda z, f: build_invoice_html(data, z, f)))
    return True


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
    attach_resources(doc)
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


def _setup_a4_portrait(printer):
    # type: (_Print.QPrinter) -> None
    try:
        printer.setPaperSize(_Print.QPrinter.A4)
    except Exception:
        pass
    try:
        # QPrinter.setOrientation takes QPrinter.Orientation. The former
        # setPageOrientation(QPrinter.Portrait) call raised TypeError
        # (that one wants QPageLayout.Orientation) and was swallowed.
        printer.setOrientation(_Print.QPrinter.Portrait)
    except Exception:
        pass


def _setup_page(printer, page):
    # type: (_Print.QPrinter, Optional[dict]) -> None
    """Paper/orientation for a print job. ``page`` is None for the A4
    portrait reports, or the dict from invoice_page_opts() (paper size,
    landscape flag, watermark flag)."""
    if not page:
        _setup_a4_portrait(printer)
        return
    qps = _Print.QPrinter
    try:
        printer.setPaperSize(qps.A5 if page.get("paper") == "A5" else qps.A4)
    except Exception:
        pass
    try:
        # QPrinter.Orientation (Qt5). Not setPageOrientation(): that takes
        # QPageLayout.Orientation and rejects QPrinter.Landscape.
        printer.setOrientation(qps.Landscape if page.get("landscape")
                               else qps.Portrait)
    except Exception:
        pass
    try:
        # 5 mm: about the hardware minimum of common printers, so the
        # form covers the sheet. A driver that needs more simply reports a
        # smaller printable area, and _fit_doc sizes the form to that.
        printer.setPageMargins(5, 5, 5, 5, qps.Millimeter)
    except Exception:
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


_WM_COLOR = _LILAC


def _shaped_text_path(text, font):
    # type: (str, Any) -> Any
    """Outline of ``text`` after real RTL shaping (joined letters).

    QPainterPath.addText() does not shape Persian with the Windows font
    engine — it produced separate letters in reverse order. QTextLayout
    shapes the run; the glyph outlines are then taken from its glyph runs.
    simplified() merges overlapping contours of the variable font so the
    stroke shows only each letter's outer edge."""
    layout = _Gui.QTextLayout(text, font)
    opt = _Gui.QTextOption()
    opt.setTextDirection(_Core.Qt.RightToLeft)
    layout.setTextOption(opt)
    layout.beginLayout()
    line = layout.createLine()
    line.setLineWidth(100000.0)
    layout.endLayout()
    path = _Gui.QPainterPath()
    for run in layout.glyphRuns():
        raw = run.rawFont()
        for gi, pos in zip(run.glyphIndexes(), run.positions()):
            gp = raw.pathForGlyph(gi)
            gp.translate(pos)
            path.addPath(gp)
    return path.simplified()


def _outlined_text(painter, text, center, width, pen, brush=None):
    # type: (Any, str, Any, float, Any, Any) -> None
    """Hollow text scaled to ``width``, centred on ``center``."""
    font = _Gui.QFont(_print_font())
    font.setBold(True)
    font.setPixelSize(100)
    path = _shaped_text_path(text, font)
    box = path.boundingRect()
    if box.width() <= 0:
        return
    k = width / box.width()
    painter.save()
    painter.translate(center.x(), center.y())
    painter.scale(k, k)
    painter.translate(-box.center().x(), -box.center().y())
    p = _Gui.QPen(pen)
    p.setWidthF(pen.widthF() / k)
    painter.setPen(p)
    painter.setBrush(brush if brush is not None else _Core.Qt.NoBrush)
    painter.drawPath(path)
    painter.restore()


def _paint_watermark(painter, pw, ph):
    # type: (Any, float, float) -> None
    """The pad's background emblem — a knee — traced from the scanned sheet:

    * a tall rounded frame drawn as a double line with a shaded band,
    * an inner rounded frame, open at the top-left and notched at the
      bottom where the shin passes through,
    * the knee in side view: shaded thigh bone (femur) coming down from the
      top-left and ending in a round condyle, a thin joint gap, the shaded
      shin bone (tibia) with its flat top, the kneecap in front and the
      tendon band curving round the front of the knee, plus the line of the
      back of the leg,
    * hollow lettering «ارتوپدی فنی» over «آذران طب» in the lower part.

    Geometry is in emblem units (u across, v down, 0..1; the emblem is
    1.42x taller than wide). ``ph`` is the form height on this page, so the
    emblem stays inside the frame on any paper. Drawn in the page's 96dpi
    CSS space before the text, so the form always prints on top of it."""
    painter.save()
    try:
        painter.setRenderHint(_Gui.QPainter.Antialiasing, True)
        H = ph * 0.96
        W = H / 1.42
        if W > pw * 0.6:
            W = pw * 0.6
            H = W * 1.42
        x0 = pw * 0.47 - W / 2.0
        y0 = ph * 0.02

        def pt(u, v):
            return _Core.QPointF(x0 + u * W, y0 + v * H)

        def band_of(path, width):
            stroker = _Gui.QPainterPathStroker()
            stroker.setWidth(width)
            stroker.setCapStyle(_Core.Qt.RoundCap)
            stroker.setJoinStyle(_Core.Qt.RoundJoin)
            return stroker.createStroke(path).simplified()

        col = _Gui.QColor(_WM_COLOR)
        stroke = _Gui.QPen(col, max(0.8, W * 0.012))
        stroke.setJoinStyle(_Core.Qt.RoundJoin)
        stroke.setCapStyle(_Core.Qt.RoundCap)
        thin = _Gui.QPen(col, max(0.6, W * 0.006))
        thin.setJoinStyle(_Core.Qt.RoundJoin)
        thin.setCapStyle(_Core.Qt.RoundCap)

        # -- frames --------------------------------------------------------
        outer = _Gui.QPainterPath()
        outer.addRoundedRect(_Core.QRectF(x0, y0, W, H), W * 0.10, W * 0.10)
        ring_w = W * 0.035
        inner_ring = _Gui.QPainterPath()
        inner_ring.addRoundedRect(
            _Core.QRectF(x0 + ring_w, y0 + ring_w,
                         W - 2 * ring_w, H - 2 * ring_w),
            W * 0.075, W * 0.075)
        frame_band = outer.subtracted(inner_ring)

        r = W * 0.063  # inner frame corner radius
        inner = _Gui.QPainterPath(pt(0.575, 0.050))   # top-right part
        inner.lineTo(pt(0.921, 0.050) - _Core.QPointF(r, 0))
        inner.quadTo(pt(0.921, 0.050), pt(0.921, 0.050) + _Core.QPointF(0, r))
        inner.lineTo(pt(0.921, 0.694) - _Core.QPointF(0, r))
        inner.quadTo(pt(0.921, 0.694), pt(0.921, 0.694) - _Core.QPointF(r, 0))
        inner.lineTo(pt(0.795, 0.694))
        inner.lineTo(pt(0.795, 0.561))
        inner.moveTo(pt(0.378, 0.561))                 # bottom-left part
        inner.lineTo(pt(0.378, 0.694))
        inner.lineTo(pt(0.071, 0.694) + _Core.QPointF(r, 0))
        inner.quadTo(pt(0.071, 0.694), pt(0.071, 0.694) - _Core.QPointF(0, r))
        inner.lineTo(pt(0.071, 0.205))

        # -- knee ---------------------------------------------------------
        femur = _Gui.QPainterPath(pt(0.323, 0.069))
        femur.lineTo(pt(0.554, 0.069))
        femur.quadTo(pt(0.620, 0.110), pt(0.658, 0.169))
        femur.cubicTo(pt(0.745, 0.220), pt(0.745, 0.360), pt(0.606, 0.387))
        femur.cubicTo(pt(0.500, 0.400), pt(0.465, 0.320), pt(0.485, 0.250))
        femur.quadTo(pt(0.420, 0.150), pt(0.323, 0.069))

        tibia = _Gui.QPainterPath(pt(0.491, 0.419))
        tibia.quadTo(pt(0.625, 0.400), pt(0.764, 0.419))
        tibia.lineTo(pt(0.764, 0.489))
        tibia.quadTo(pt(0.748, 0.560), pt(0.748, 0.694))
        tibia.lineTo(pt(0.575, 0.694))
        tibia.lineTo(pt(0.575, 0.553))
        tibia.quadTo(pt(0.560, 0.500), pt(0.501, 0.491))
        tibia.closeSubpath()

        tendon_line = _Gui.QPainterPath(pt(0.606, 0.058))
        tendon_line.cubicTo(pt(0.720, 0.140), pt(0.880, 0.250),
                            pt(0.855, 0.380))
        tendon_line.quadTo(pt(0.845, 0.440), pt(0.838, 0.487))
        tendon = band_of(tendon_line, W * 0.040)

        kneecap_line = _Gui.QPainterPath(pt(0.784, 0.272))
        kneecap_line.quadTo(pt(0.845, 0.320), pt(0.814, 0.376))
        kneecap = band_of(kneecap_line, W * 0.030)

        back_line = _Gui.QPainterPath(pt(0.071, 0.267))
        back_line.lineTo(pt(0.449, 0.487))
        back = band_of(back_line, W * 0.032)

        # -- shading (light) ---------------------------------------------
        painter.setPen(_Core.Qt.NoPen)
        painter.setBrush(col)
        painter.setOpacity(0.12)
        painter.drawPath(frame_band)
        painter.drawPath(tendon)
        painter.drawPath(kneecap)
        painter.drawPath(back)
        painter.setOpacity(0.16)
        painter.drawPath(femur)
        painter.drawPath(tibia)

        # -- outlines -----------------------------------------------------
        painter.setBrush(_Core.Qt.NoBrush)
        painter.setOpacity(0.30)
        painter.setPen(thin)
        painter.drawPath(outer)
        painter.drawPath(inner_ring)
        painter.drawPath(tendon)
        painter.drawPath(kneecap)
        painter.drawPath(back)
        painter.drawPath(tibia)
        painter.setPen(stroke)
        painter.drawPath(inner)
        painter.setPen(thin)
        painter.drawPath(femur)

        # -- hollow lettering ---------------------------------------------
        tint = _Gui.QColor(_WM_COLOR)
        tint.setAlpha(22)
        letters = _Gui.QPen(col, max(0.7, W * 0.006))
        letters.setJoinStyle(_Core.Qt.RoundJoin)
        _outlined_text(painter, "ارتوپدی فنی", pt(0.488, 0.786), W * 0.74,
                       letters, _Gui.QBrush(tint))
        _outlined_text(painter, _SHEET_CLINIC_NAME, pt(0.515, 0.911),
                       W * 0.64, letters, _Gui.QBrush(tint))
    finally:
        painter.restore()


def _draw_vector(layout, painter, ctx, pw, ph, scale, total, printer,
                 watermark=False):
    # type: (Any, Any, Any, float, float, float, float, Any, bool) -> None
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
        if watermark:
            _paint_watermark(painter, pw, min(ph, total - y))
        painter.translate(0.0, -y)
        layout.draw(painter, ctx)
        painter.restore()
        y += ph


def _render_pages(layout, ctx, pw, ph, total, watermark=False):
    # type: (Any, Any, float, float, float, bool) -> list
    """The document as a list of full-page 300dpi QImages (CSS space pw x ph)."""
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
            if watermark:
                _paint_watermark(ip, pw, min(ph, total - y))
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
    return pages


def _raster_print(layout, ctx, printer, pw, ph, dev_w, dev_h, total,
                  watermark=False):
    # type: (Any, Any, Any, float, float, float, float, float, bool) -> None
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
    pages = _render_pages(layout, ctx, pw, ph, total, watermark)
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


def _doc_print(doc, printer, watermark=False):
    # type: (Any, Any, bool) -> None
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
                          total, watermark)
            return
        painter = _Gui.QPainter(printer)
        if not painter.isActive():
            painter.begin(printer)
        try:
            _draw_vector(layout, painter, ctx, pw, ph, dpi / 96.0,
                         total, printer, watermark)
        finally:
            painter.end()
    except Exception:
        doc.print_(printer)


def _page_css_size(printer):
    # type: (Any) -> tuple
    dpi = float(printer.logicalDpiX()) or 96.0
    return (float(printer.width()) * 96.0 / dpi,
            float(printer.height()) * 96.0 / dpi)


def _measure(html, pw):
    # type: (str, float) -> tuple
    doc = _make_doc(html)
    doc.setTextWidth(pw)
    return doc, float(doc.documentLayout().documentSize().height())


def _fit_doc(builder, printer):
    # type: (Any, Any) -> Any
    """Exactly one page: the form's frame runs from the top to the bottom
    of the printable area of ``printer``.

    Too tall (many rows / long notes): the whole sheet is scaled down via
    its zoom until it fits. Too short: blank item area is added (an exact
    spacer) until the bottom rule meets the bottom of the page."""
    pw, ph = _page_css_size(printer)
    if pw <= 100 or ph <= 100:
        return _make_doc(builder(1.0, 0))
    limit = ph - 1.0
    z = 1.0
    doc, h = _measure(builder(z, 0), pw)
    tries = 0
    while h > limit and z > 0.45 and tries < 12:
        z = max(0.45, round(z * (limit / h) * 0.99, 2))
        doc, h = _measure(builder(z, 0), pw)
        tries += 1
    fill = int(limit - h)
    for _ in range(4):
        if fill < 2:
            break
        d2, h2 = _measure(builder(z, fill), pw)
        if h2 <= limit:
            doc, h = d2, h2
            gap = int(limit - h2)
            if gap < 2:
                break
            fill += gap
        else:
            fill -= int(h2 - limit) + 1
    return doc


def show_print_preview(parent, html, page=None):
    # type: (Any, Optional[str], Optional[dict]) -> None
    """``page``: None = A4 portrait (reports); invoice_page_opts(builder) =
    the A5-landscape invoice sheet, fitted to the page, with its watermark."""
    builder = page.get("builder") if page else None
    doc = None if builder is not None else _make_doc(html)
    printer = _Print.QPrinter(_printer_mode())
    # Configure paper/orientation BEFORE the dialog is built, so its
    # initial page geometry already reflects the chosen paper.
    _setup_page(printer, page)
    preview = _Print.QPrintPreviewDialog(printer, parent)
    watermark = bool(page and page.get("watermark"))

    def render_preview(p):
        # type: (_Print.QPrinter) -> None
        # Re-fit on every paint: the page setup inside the preview dialog
        # can change paper or margins.
        _doc_print(_fit_doc(builder, p) if builder is not None else doc,
                   p, watermark)

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


def print_html_direct(parent, html, page=None):
    # type: (Any, Optional[str], Optional[dict]) -> None
    builder = page.get("builder") if page else None
    printer = _Print.QPrinter(_printer_mode())
    _setup_page(printer, page)
    dlg = _Print.QPrintDialog(printer, parent)
    if dlg.exec_() == _Widgets.QDialog.Accepted:
        doc = _fit_doc(builder, printer) if builder is not None \
            else _make_doc(html)
        _doc_print(doc, printer, bool(page and page.get("watermark")))


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
