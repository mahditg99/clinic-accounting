# -*- coding: utf-8 -*-
"""FastAPI web front-end for Azaran Teb clinic accounting.

Run from inside azaran_teb/:
    python -m uvicorn webapp.main:app --reload --port 8000

Reuses the desktop data layer (app.models / app.settings / app.date_utils /
app.money_utils) so both UIs share one SQLite database.
"""
from __future__ import annotations

import datetime as _dt
import mimetypes
import os
import shutil
from typing import Any, Dict, List, Optional

mimetypes.add_type("font/woff2", ".woff2")

from fastapi import FastAPI, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import database, date_utils, models, money_utils, settings as settings_mod
from webapp import auth
from webapp import serializers as ser

_BASE = os.path.dirname(os.path.abspath(__file__))

app = FastAPI(title="Azaran Teb Web", docs_url=None, redoc_url=None)
templates = Jinja2Templates(directory=os.path.join(_BASE, "templates"))
app.mount("/static", StaticFiles(directory=os.path.join(_BASE, "static")), name="static")

database.init_db()
auth.ensure_admin()


# --------------------------------------------------------------------------- #
# Template helpers
# --------------------------------------------------------------------------- #

def _app_title():
    # type: () -> str
    return settings_mod.get_setting("app_title", "آذران طب") or "آذران طب"


templates.env.globals["app_title"] = _app_title()
templates.env.globals["today_jalali"] = lambda: ser.fmt_date_jalali(date_utils.today_iso())
templates.env.globals["fmt_money"] = ser.fmt_money
templates.env.globals["fmt_date"] = ser.fmt_date_jalali
# 'fa' filter: render any number/count in Persian digits (item: all UI numbers
# are shown in Persian; stored as English in the backend).
templates.env.filters["fa"] = date_utils.to_persian_digits


def render(request, template_name, **ctx):
    # type: (Request, str, Any) -> Any
    ctx.setdefault("request", request)
    ctx.setdefault("user", auth.logged_in_username(request))
    ctx.setdefault("nav", "")
    ctx.setdefault("flash", request.query_params.get("msg", ""))
    ctx.setdefault("flash_type", request.query_params.get("ftype", "ok-box"))
    return templates.TemplateResponse(template_name, ctx)


def page(request):
    # type: (Request) -> Optional[RedirectResponse]
    """Return a login redirect when unauthenticated, else None."""
    if not auth.logged_in_username(request):
        return RedirectResponse(url="/login", status_code=303)
    return None


def api_guard(request):
    # type: (Request) -> Optional[JSONResponse]
    if not auth.logged_in_username(request):
        return JSONResponse({"detail": "ابتدا وارد شوید."}, status_code=401)
    return None


def _to_iso(jalali_str):
    # type: (str) -> Optional[str]
    if not jalali_str:
        return None
    try:
        return date_utils.jalali_str_to_iso(jalali_str)
    except ValueError:
        raise ValueError("تاریخ «%s» نامعتبر است." % jalali_str)


def _money(text):
    # type: (str) -> int
    n = money_utils.parse_money(text)
    return n if n is not None else 0


def _int(text):
    # type: (Any) -> int
    return money_utils.parse_int(text, 0)


# --------------------------------------------------------------------------- #
# Auth pages
# --------------------------------------------------------------------------- #

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if auth.logged_in_username(request):
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request,
                                                     "error": ""})


@app.post("/login")
def login_submit(request: Request, username: str = Form(""), password: str = Form("")):
    if auth.verify_user(username.strip(), password):
        resp = RedirectResponse(url="/", status_code=303)
        resp.set_cookie(auth.SESSION_COOKIE, auth.make_session_cookie(username.strip()),
                        max_age=auth.SESSION_TTL_SECONDS, httponly=True)
        return resp
    return templates.TemplateResponse("login.html",
                                      {"request": request,
                                       "error": "نام کاربری یا رمز عبور اشتباه است."},
                                      status_code=401)


@app.get("/logout")
def logout():
    return auth.logout_redirect()


@app.get("/change-password", response_class=HTMLResponse)
def change_password_page(request: Request):
    redir = page(request)
    if redir:
        return redir
    return render(request, "change_password.html", nav="settings")


@app.post("/change-password")
async def change_password_submit(request: Request):
    form = await request.form()
    current = form.get("current_password") or ""
    new = form.get("new_password") or ""
    confirm = form.get("confirm_password") or ""
    if new != confirm:
        return render(request, "change_password.html", nav="settings",
                      error="تکرار رمز جدید با رمز جدید یکسان نیست.")
    try:
        auth.change_password(current, new)
    except ValueError as exc:
        return render(request, "change_password.html", nav="settings",
                      error=str(exc))
    resp = RedirectResponse(url="/login?msg=" +
                            "رمز عبور با موفقیت تغییر کرد.", status_code=303)
    resp.delete_cookie(auth.SESSION_COOKIE)
    return resp


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    redir = page(request)
    if redir:
        return redir
    today = date_utils.today_iso()
    daily = models.daily_report(today)
    for m in daily["by_method"]:
        m["total_f"] = ser.fmt_money(m["total"])
    patients = [p for p in models.list_patients() if p["is_active"]]
    products = models.list_products(active_only=True)
    low_stock = [p for p in products
                 if int(p["stock"]) <= int(p["low_stock_warning"] or 0)]
    archive = models.list_archive_invoices(date_from=today, date_to=today)
    conn = database.get_connection()
    try:
        invoice_count = conn.execute(
            "SELECT COUNT(*) FROM invoices WHERE is_deleted = 0").fetchone()[0]
        receivable = conn.execute(
            "SELECT COALESCE(SUM(i.total_amount),0) - "
            "(SELECT COALESCE(SUM(pm.amount),0) FROM payments pm "
            " JOIN invoices i2 ON i2.id = pm.invoice_id "
            " WHERE i2.is_deleted = 0) "
            "FROM invoices i WHERE i.is_deleted = 0").fetchone()[0]
    finally:
        conn.close()
    return render(
        request, "dashboard.html", nav="dashboard",
        daily_total=daily["total"],
        by_method=daily["by_method"],
        today_invoices=len(archive),
        patient_count=len(patients),
        product_count=len(products),
        invoice_count=invoice_count,
        receivable=int(receivable),
        low_stock=[ser.product_row(p) for p in low_stock],
    )


# --------------------------------------------------------------------------- #
# Patients
# --------------------------------------------------------------------------- #

@app.get("/patients", response_class=HTMLResponse)
def patients_page(request: Request, q: str = ""):
    redir = page(request)
    if redir:
        return redir
    rows = models.list_patients(active_only=False)
    q = q.strip()
    if q:
        # Word-wise + digit-insensitive: every typed word must match
        # file_no / first / last, typed in Persian or English digits, and
        # "مریم حسابداری" works in any word order (نیم‌فاصله ignored).
        def _norm(s):
            s = date_utils.to_english_digits(str(s or ""))
            return s.replace("\u200c", " ").lower()

        words = [w for w in _norm(q).split() if w]

        def _hit(r):
            hay = _norm("%s %s %s" % (r["file_no"], r["first_name"],
                                      r["last_name"]))
            return all(w in hay for w in words)

        rows = [r for r in rows if _hit(r)]
    return render(request, "patients.html", nav="patients",
                  patients=[ser.patient_row(r) for r in rows], q=q)


@app.post("/api/patients")
async def api_patient_save(request: Request):
    guard = api_guard(request)
    if guard:
        return guard
    form = await request.form()
    pid = form.get("patient_id") or None
    first = (form.get("first_name") or "").strip()
    last = (form.get("last_name") or "").strip()
    gender = form.get("gender") or ""
    # Store file_no / phone with English digits (backend convention); the UI
    # accepts Persian typing and shows Persian.
    phone = date_utils.to_english_digits((form.get("phone") or "").strip())
    address = (form.get("address") or "").strip()
    if not first or not last:
        return JSONResponse({"detail": "نام و نام خانوادگی الزامی است."}, status_code=400)
    try:
        if pid:
            models.update_patient(int(pid), first, last, gender, phone, address)
            return {"ok": True, "id": int(pid)}
        file_no = date_utils.to_english_digits((form.get("file_no") or "").strip())
        if not file_no:
            return JSONResponse({"detail": "شماره پرونده الزامی است."}, status_code=400)
        new_id = models.create_patient(file_no, first, last, gender, phone, address)
        return {"ok": True, "id": new_id}
    except ValueError as exc:
        return JSONResponse({"detail": str(exc)}, status_code=400)


@app.post("/api/patients/{patient_id}/deactivate")
def api_patient_deactivate(request: Request, patient_id: int):
    guard = api_guard(request)
    if guard:
        return guard
    models.deactivate_patient(patient_id)
    return {"ok": True}


@app.delete("/api/patients/{patient_id}")
def api_patient_delete(request: Request, patient_id: int):
    guard = api_guard(request)
    if guard:
        return guard
    if models.patient_has_invoices(patient_id):
        return JSONResponse({"detail": "این بیمار فاکتور دارد؛ فقط غیرفعال‌سازی ممکن است."},
                            status_code=400)
    models.delete_patient(patient_id)
    return {"ok": True}


@app.get("/api/patients/search")
def api_patient_search(request: Request, q: str = ""):
    guard = api_guard(request)
    if guard:
        return guard
    q = q.strip()
    # Persian-digit queries should match English-digits stored data and vice versa.
    by_file = date_utils.to_english_digits(q).isdigit()
    rows = models.search_active_patients(date_utils.to_english_digits(q), by_file)
    if not rows:
        rows = models.search_active_patients(date_utils.to_persian_digits(q), by_file)
    out = [{"id": r["id"],
            "text": "%s %s — پرونده %s" % (r["first_name"], r["last_name"],
                                           date_utils.to_persian_digits(r["file_no"])),
            "name": "%s %s" % (r["first_name"], r["last_name"]),
            "file_no": date_utils.to_persian_digits(r["file_no"])}
           for r in rows[:10]]
    return out


# --------------------------------------------------------------------------- #
# Products
# --------------------------------------------------------------------------- #

@app.get("/products", response_class=HTMLResponse)
def products_page(request: Request, show_inactive: int = 0):
    redir = page(request)
    if redir:
        return redir
    rows = models.list_products(active_only=(show_inactive == 0))
    return render(request, "products.html", nav="products",
                  products=[ser.product_row(r) for r in rows],
                  show_inactive=show_inactive)


@app.post("/api/products")
async def api_product_save(request: Request):
    guard = api_guard(request)
    if guard:
        return guard
    form = await request.form()
    pid = form.get("product_id") or None
    title = (form.get("title") or "").strip()
    args = (title, _int(form.get("purchase_price")), _int(form.get("sale_price")),
            _int(form.get("stock")), _int(form.get("low_stock_warning")),
            form.get("description") or "")
    try:
        if pid:
            models.update_product(int(pid), *args)
            return {"ok": True, "id": int(pid)}
        return {"ok": True, "id": models.add_product(*args)}
    except ValueError as exc:
        return JSONResponse({"detail": str(exc)}, status_code=400)


@app.post("/api/products/{product_id}/deactivate")
def api_product_deactivate(request: Request, product_id: int):
    guard = api_guard(request)
    if guard:
        return guard
    models.deactivate_product(product_id)
    return {"ok": True}


@app.delete("/api/products/{product_id}")
def api_product_delete(request: Request, product_id: int):
    guard = api_guard(request)
    if guard:
        return guard
    if models.product_used_in_invoices(product_id):
        return JSONResponse({"detail": "این محصول در فاکتور استفاده شده؛ فقط غیرفعال‌سازی ممکن است."},
                            status_code=400)
    models.hard_delete_product(product_id)
    return {"ok": True}


# --------------------------------------------------------------------------- #
# Invoices: new / edit / save
# --------------------------------------------------------------------------- #

def _saleable_products():
    # type: () -> List[Dict[str, Any]]
    return [p for p in models.list_products(active_only=True) if int(p["stock"]) > 0]


@app.get("/invoice/new", response_class=HTMLResponse)
def invoice_new_page(request: Request):
    redir = page(request)
    if redir:
        return redir
    return render(request, "invoice_new.html", nav="invoice",
                  mode="new", invoice=None, items=[], payments=[],
                  next_no=models.next_invoice_no_stub(),
                  show_doctor_default=(settings_mod.get_setting(
                      "show_doctor_in_print", "0") == "1"),
                  products=_saleable_products(),
                  doctors=models.list_doctors_with_id(),
                  methods=settings_mod.get_payment_methods())


@app.get("/invoice/{invoice_id}/edit", response_class=HTMLResponse)
def invoice_edit_page(request: Request, invoice_id: int):
    redir = page(request)
    if redir:
        return redir
    inv = models.get_invoice(invoice_id)
    if inv is None or inv["is_deleted"]:
        return RedirectResponse(url="/invoices?msg=فاکتور یافت نشد&ftype=error-box",
                                status_code=303)
    items = models.list_invoice_items(invoice_id)
    payments = models.list_payments(invoice_id)
    paid_sum = sum(int(p["amount"]) for p in payments)
    return render(request, "invoice_new.html", nav="archive",
                  mode="edit", invoice=inv, items=items,
                  payments=payments, paid_sum=paid_sum,
                  remaining=int(inv["total_amount"]) - paid_sum,
                  next_no=inv["invoice_no"],
                  products=_saleable_products(),
                  doctors=models.list_doctors_with_id(),
                  methods=settings_mod.get_payment_methods())


@app.post("/api/invoices")
async def api_invoice_save(request: Request):
    guard = api_guard(request)
    if guard:
        return guard
    body = await request.json()
    try:
        patient_id = int(body.get("patient_id") or 0)
        if not patient_id:
            raise ValueError("انتخاب بیمار الزامی است.")
        doctor_raw = body.get("doctor_id")
        doctor_id = int(doctor_raw) if doctor_raw not in (None, "", "none") else None
        issued_iso = body.get("issued_at") or date_utils.today_iso()
        iso = _to_iso(issued_iso) or date_utils.today_iso()

        items = []
        for it in (body.get("items") or []):
            qty = int(it.get("quantity") or 1)
            unit = int(it.get("unit_price") or 0)
            if qty <= 0 or unit < 0:
                raise ValueError("تعداد و قیمت نامعتبر است.")
            items.append({
                "product_id": int(it["product_id"]) if it.get("product_id") else None,
                "title": (it.get("title") or "").strip() or "بدون عنوان",
                "unit_price": unit,
                "quantity": qty,
                "row_total": unit * qty,
            })
        if not items:
            raise ValueError("حداقل یک ردیف کالا لازم است.")

        payments = []
        total = sum(i["row_total"] for i in items)
        paid = 0
        for pm in (body.get("payments") or []):
            amount = int(pm.get("amount") or 0)
            if amount <= 0:
                continue
            paid += amount
            payments.append({"method": pm.get("method") or "نقد",
                             "amount": amount,
                             "paid_at": date_utils.now_iso()})
        if paid > total:
            over = paid - total
            if not body.get("allow_overpay"):
                return JSONResponse(
                    {"detail": "پرداخت بیش از مبلغ فاکتور است (مبلغ اضافه: %s تومان). "
                               "برای تایید دوباره ذخیره کنید." % ser.fmt_money(over),
                     "need_confirm_overpay": True}, status_code=409)

        update_issued = bool(body.get("update_issued"))
        inv_id = models.save_invoice(
            patient_id, doctor_id, iso, items, payments,
            body.get("notes") or "", invoice_id=body.get("invoice_id"),
            update_issued=update_issued)
        return {"ok": True, "id": inv_id}
    except ValueError as exc:
        return JSONResponse({"detail": str(exc)}, status_code=400)


@app.post("/api/invoices/{invoice_id}/void")
def api_invoice_void(request: Request, invoice_id: int):
    guard = api_guard(request)
    if guard:
        return guard
    models.soft_delete_invoice(invoice_id)
    return {"ok": True}


# --------------------------------------------------------------------------- #
# Archive + detail/print view
# --------------------------------------------------------------------------- #

@app.get("/invoices", response_class=HTMLResponse)
def archive_page(request: Request, doctor: str = "all", fdate: str = "",
                 tdate: str = "", q: str = ""):
    redir = page(request)
    if redir:
        return redir
    doc_filter = None
    if doctor == "none":
        doc_filter = "none"
    elif doctor.isdigit():
        doc_filter = int(doctor)
    try:
        df = _to_iso(fdate)
        dt = _to_iso(tdate)
    except ValueError as exc:
        return render(request, "archive.html", nav="archive", error=str(exc),
                      rows=[], doctors=settings_mod.list_doctors(True),
                      doctor=doctor, fdate=fdate, tdate=tdate, q=q)
    # Stored data uses English digits; accept Persian-typed queries too.
    q = date_utils.to_english_digits(q).strip()
    rows = models.list_archive_invoices(doc_filter, df, dt, q)
    shown = [dict(r) for r in rows]
    for r in shown:
        r["issued_at_j"] = ser.fmt_date_jalali(r["issued_at"])
        for k in ("total_amount", "paid_sum", "remaining"):
            r[k] = ser.fmt_money(r[k])
    return render(request, "archive.html", nav="archive", error="",
                  rows=shown, doctors=settings_mod.list_doctors(True),
                  doctor=doctor, fdate=fdate, tdate=tdate, q=q)


@app.get("/invoice/{invoice_id}", response_class=HTMLResponse)
def invoice_detail_page(request: Request, invoice_id: int):
    redir = page(request)
    if redir:
        return redir
    inv = models.get_invoice(invoice_id)
    if inv is None:
        return RedirectResponse(url="/invoices?msg=فاکتور یافت نشد&ftype=error-box",
                                status_code=303)
    items = models.list_invoice_items(invoice_id)
    payments = models.list_payments(invoice_id)
    paid = sum(int(p["amount"]) for p in payments)
    show_doctor = settings_mod.get_setting("show_doctor_in_print", "0") == "1"
    return render(request, "invoice_detail.html", nav="archive",
                  inv=inv, items=items, payments=payments, paid=paid,
                  remaining=int(inv["total_amount"]) - paid,
                  issued_j=ser.fmt_date_jalali(inv["issued_at"]),
                  show_doctor=show_doctor)


# --------------------------------------------------------------------------- #
# Daily report
# --------------------------------------------------------------------------- #

@app.get("/reports/daily", response_class=HTMLResponse)
def daily_report_page(request: Request, date: str = ""):
    redir = page(request)
    if redir:
        return redir
    jdate = date or ser.fmt_date_jalali(date_utils.today_iso())
    try:
        iso = _to_iso(jdate) or date_utils.today_iso()
    except ValueError as exc:
        return render(request, "daily_report.html", nav="daily", error=str(exc),
                      jdate=jdate, report=None)
    rep = models.daily_report(iso)
    for p in rep["payments"]:
        p["paid_at_j"] = ser.fmt_date_jalali(p["paid_at"])
        p["time_hm"] = ser.fmt_time(p["paid_at"])
        p["amount_f"] = ser.fmt_money(p["amount"])
    for m in rep["by_method"]:
        m["total_f"] = ser.fmt_money(m["total"])
    return render(request, "daily_report.html", nav="daily", error="",
                  jdate=jdate, report=rep, total_f=ser.fmt_money(rep["total"]),
                  sales_f=ser.fmt_money(rep["sales"]),
                  remaining_f=ser.fmt_money(rep["remaining"]))


# --------------------------------------------------------------------------- #
# Income / expense report
# --------------------------------------------------------------------------- #

@app.get("/reports/income-expense", response_class=HTMLResponse)
def income_expense_page(request: Request, fdate: str = "", tdate: str = ""):
    redir = page(request)
    if redir:
        return redir
    tdate = tdate or ser.fmt_date_jalali(date_utils.today_iso())
    try:
        df = _to_iso(fdate)
        dt = _to_iso(tdate)
    except ValueError as exc:
        return render(request, "income_expense.html", nav="income_expense",
                      error=str(exc), report=None, fdate=fdate, tdate=tdate)
    rep = models.income_expense_report(df, dt)
    for e in rep["expenses"]:
        e["expense_date_j"] = ser.fmt_date_jalali(e["expense_date"])
        e["amount_f"] = ser.fmt_money(e["amount"])
    for d in rep["doctor_summary"]:
        d["total_f"] = ser.fmt_money(d["total"])
    return render(request, "income_expense.html", nav="income_expense",
                  error="", report=rep, fdate=fdate, tdate=tdate,
                  income_f=ser.fmt_money(rep["income"]),
                  expense_f=ser.fmt_money(rep["expense"]),
                  profit_f=ser.fmt_money(rep["profit"]),
                  sales_f=ser.fmt_money(rep["sales"]),
                  receivable_f=ser.fmt_money(rep["receivable"]))


# --------------------------------------------------------------------------- #
# Expenses CRUD page
# --------------------------------------------------------------------------- #

@app.get("/expenses", response_class=HTMLResponse)
def expenses_page(request: Request, fdate: str = "", tdate: str = "",
                  category: str = "all"):
    redir = page(request)
    if redir:
        return redir
    try:
        df = _to_iso(fdate)
        dt = _to_iso(tdate)
    except ValueError as exc:
        return render(request, "expenses.html", nav="expenses", error=str(exc),
                      rows=[], categories=settings_mod.get_expense_categories(),
                      fdate=fdate, tdate=tdate, category=category, total_f="۰")
    rows = models.list_expenses(df, dt, category)
    total = sum(int(r["amount"]) for r in rows)
    for r in rows:
        r["expense_date_j"] = ser.fmt_date_jalali(r["expense_date"])
        r["amount_f"] = ser.fmt_money(r["amount"])
    return render(request, "expenses.html", nav="expenses", error="",
                  rows=rows, categories=settings_mod.get_expense_categories(),
                  fdate=fdate, tdate=tdate, category=category,
                  total_f=ser.fmt_money(total))


@app.post("/api/expenses")
async def api_expense_add(request: Request):
    guard = api_guard(request)
    if guard:
        return guard
    form = await request.form()
    amount = _money(form.get("amount"))
    if amount <= 0:
        return JSONResponse({"detail": "مبلغ باید بزرگ‌تر از صفر باشد."}, status_code=400)
    try:
        iso = _to_iso(form.get("expense_date") or "") or date_utils.today_iso()
    except ValueError as exc:
        return JSONResponse({"detail": str(exc)}, status_code=400)
    exp_id = models.add_expense(amount, form.get("description") or "", iso,
                                form.get("category") or "متفرقه")
    return {"ok": True, "id": exp_id}


@app.delete("/api/expenses/{expense_id}")
def api_expense_delete(request: Request, expense_id: int):
    guard = api_guard(request)
    if guard:
        return guard
    models.delete_expense(expense_id)
    return {"ok": True}


# --------------------------------------------------------------------------- #
# Financial reports (receipts / expenses / sales-profit)
# --------------------------------------------------------------------------- #

@app.get("/reports/financial", response_class=HTMLResponse)
def financial_reports_page(request: Request, period: str = "monthly",
                           year: str = "0", month: int = 1):
    redir = page(request)
    if redir:
        return redir
    if period not in ("monthly", "yearly"):
        period = "monthly"
    # year may arrive typed in Persian digits (the input shows Persian).
    y = money_utils.parse_int(year, 0) or date_utils.jalali_year_now()
    try:
        if period == "yearly":
            start_iso, end_iso = date_utils.jalali_year_range_iso(y)
        else:
            start_iso, end_iso = date_utils.jalali_month_range_iso(y, month)
    except ValueError as exc:
        return render(request, "financial.html", nav="financial", error=str(exc),
                      period=period, year=y, month=month, months=_JALALI_MONTH_NAMES,
                      receipts=None, expenses_rep=None, profit=None)

    receipts = models.receipts_report(start_iso, end_iso)
    for p in receipts["payment_details"]:
        p["time_hm"] = ser.fmt_time(p["paid_at"])
        p["amount_f"] = ser.fmt_money(p["amount"])
        p["paid_at_j"] = ser.fmt_date_jalali(p["paid_at"])
    for s in receipts["summary_by_method"]:
        s["amount_f"] = ser.fmt_money(s["amount"])
    receipts["total_f"] = ser.fmt_money(receipts["total_received"])

    expenses_rep = models.expenses_report(start_iso, end_iso)
    for e in expenses_rep["expense_details"]:
        e["expense_date_j"] = ser.fmt_date_jalali(e["expense_date"])
        e["amount_f"] = ser.fmt_money(e["amount"])
    for s in expenses_rep["summary_by_category"]:
        s["amount_f"] = ser.fmt_money(s["amount"])
    expenses_rep["total_f"] = ser.fmt_money(expenses_rep["total_expense"])

    profit = models.sales_profit_report(start_iso, end_iso)
    for k in ("gross_sales", "cost_of_goods_sold", "gross_profit",
              "total_expenses", "net_profit"):
        profit[k + "_f"] = ser.fmt_money(profit[k])
    for s in profit["summary_by_doctor"]:
        for k in ("gross_sales", "total_cost", "profit"):
            s[k + "_f"] = ser.fmt_money(s[k])
    for s in profit["summary_by_product"]:
        for k in ("row_total", "row_cost", "profit"):
            s[k + "_f"] = ser.fmt_money(s[k])

    return render(request, "financial.html", nav="financial", error="",
                  period=period, year=y, month=month, months=_JALALI_MONTH_NAMES,
                  receipts=receipts, expenses_rep=expenses_rep, profit=profit)


_JALALI_MONTH_NAMES = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
                       "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]


# --------------------------------------------------------------------------- #
# Product sales report
# --------------------------------------------------------------------------- #

@app.get("/reports/products", response_class=HTMLResponse)
def product_sales_page(request: Request, fdate: str = "", tdate: str = ""):
    redir = page(request)
    if redir:
        return redir
    tdate = tdate or ser.fmt_date_jalali(date_utils.today_iso())
    try:
        df = _to_iso(fdate)
        dt = _to_iso(tdate)
    except ValueError as exc:
        return render(request, "product_sales.html", nav="product_sales",
                      error=str(exc), report=None, fdate=fdate, tdate=tdate)
    rep = models.product_sales_report(df, dt)
    for r in rep["rows"]:
        for k in ("row_total", "row_cost", "profit"):
            r[k + "_f"] = ser.fmt_money(r[k])
    for k in ("total_quantity", "total_revenue", "total_cost", "total_profit"):
        rep[k + "_f"] = ser.fmt_money(rep[k])
    return render(request, "product_sales.html", nav="product_sales",
                  error="", report=rep, fdate=fdate, tdate=tdate)


# --------------------------------------------------------------------------- #
# Doctor report
# --------------------------------------------------------------------------- #

@app.get("/reports/doctor", response_class=HTMLResponse)
def doctor_report_page(request: Request, doctor: str = "all", fdate: str = "",
                       tdate: str = ""):
    redir = page(request)
    if redir:
        return redir
    try:
        df = _to_iso(fdate)
        dt = _to_iso(tdate)
    except ValueError as exc:
        return render(request, "doctor_report.html", nav="doctor_report",
                      error=str(exc), doctors=settings_mod.list_doctors(True),
                      doctor=doctor, fdate=fdate, tdate=tdate, result=None)
    result = None
    referral = None
    if doctor == "all":
        referral = models.doctor_referral_report(None, df, dt)
        for r in referral["rows"]:
            r["last_j"] = ser.fmt_date_jalali(r.get("last_invoice_date"))
            for k in ("total_sum", "paid_sum", "remaining"):
                r[k + "_f"] = ser.fmt_money(r[k])
    elif doctor == "none":
        referral = models.doctor_referral_report("none", df, dt)
        for r in referral["rows"]:
            r["last_j"] = ser.fmt_date_jalali(r.get("last_invoice_date"))
            for k in ("total_sum", "paid_sum", "remaining"):
                r[k + "_f"] = ser.fmt_money(r[k])
    else:
        rep = models.doctor_report(int(doctor), df, dt)
        for row in rep["patients_summary"]:
            for k in ("total_sales", "total_received", "remaining"):
                row[k + "_f"] = ser.fmt_money(row[k])
        for row in rep["invoices_summary"]:
            row["issued_j"] = ser.fmt_date_jalali(row["issued_at"])
            for k in ("total_amount", "total_cost", "total_profit",
                      "total_received", "remaining"):
                row[k + "_f"] = ser.fmt_money(row[k])
        for row in rep["invoice_items_detail"]:
            row["issued_j"] = ser.fmt_date_jalali(row["issued_at"])
            for k in ("unit_price", "cost_price", "row_total", "row_cost",
                      "row_profit"):
                row[k + "_f"] = ser.fmt_money(row[k])
        for k in ("total_sales", "total_cost", "total_profit",
                  "total_received", "total_remaining"):
            rep[k + "_f"] = ser.fmt_money(rep[k])
        result = rep
    return render(request, "doctor_report.html", nav="doctor_report",
                  error="", doctors=settings_mod.list_doctors(True),
                  doctor=doctor, fdate=fdate, tdate=tdate,
                  result=result, referral=referral)


# --------------------------------------------------------------------------- #
# Doctors management
# --------------------------------------------------------------------------- #

@app.get("/doctors", response_class=HTMLResponse)
def doctors_page(request: Request):
    redir = page(request)
    if redir:
        return redir
    return render(request, "doctors.html", nav="doctors",
                  doctors=settings_mod.list_doctors(False),
                  no_doctor=settings_mod.NO_DOCTOR_NAME)


@app.post("/api/doctors")
async def api_doctor_add(request: Request):
    guard = api_guard(request)
    if guard:
        return guard
    form = await request.form()
    first = (form.get("first_name") or "").strip()
    last = (form.get("last_name") or "").strip()
    specialty = (form.get("specialty") or "").strip()
    address = (form.get("address") or "").strip()
    phone = (form.get("phone") or "").strip()
    name = (form.get("name") or "").strip() or ("%s %s" % (first, last)).strip()
    if not name:
        return JSONResponse({"detail": "نام پزشک الزامی است."}, status_code=400)
    if settings_mod.find_doctor_id_by_name(name) is not None:
        return JSONResponse({"detail": "این پزشک قبلا ثبت شده است."}, status_code=400)
    return {"ok": True,
            "id": settings_mod.add_doctor(
                name, specialty, address,
                date_utils.to_english_digits(phone), first, last)}


@app.put("/api/doctors/{doctor_id}")
async def api_doctor_update(request: Request, doctor_id: int):
    guard = api_guard(request)
    if guard:
        return guard
    if doctor_id == settings_mod.get_no_doctor_id():
        return JSONResponse({"detail": "پزشک پیش‌فرض «بدون معرف» قابل ویرایش نیست."},
                            status_code=400)
    form = await request.form()
    first = (form.get("first_name") or "").strip()
    last = (form.get("last_name") or "").strip()
    specialty = (form.get("specialty") or "").strip()
    address = (form.get("address") or "").strip()
    phone = (form.get("phone") or "").strip()
    name = (form.get("name") or "").strip() or ("%s %s" % (first, last)).strip()
    if not name:
        return JSONResponse({"detail": "نام پزشک الزامی است."}, status_code=400)
    settings_mod.update_doctor(doctor_id, name, specialty, address,
                               date_utils.to_english_digits(phone),
                               first, last)
    return {"ok": True, "id": doctor_id}


@app.post("/api/doctors/{doctor_id}/deactivate")
def api_doctor_deactivate(request: Request, doctor_id: int):
    guard = api_guard(request)
    if guard:
        return guard
    if doctor_id == settings_mod.get_no_doctor_id():
        return JSONResponse({"detail": "پزشک پیش‌فرض «بدون معرف» قابل غیرفعال‌سازی نیست."},
                            status_code=400)
    settings_mod.deactivate_doctor(doctor_id)
    return {"ok": True}


@app.delete("/api/doctors/{doctor_id}")
def api_doctor_delete(request: Request, doctor_id: int):
    guard = api_guard(request)
    if guard:
        return guard
    if doctor_id == settings_mod.get_no_doctor_id():
        return JSONResponse({"detail": "پزشک پیش‌فرض «بدون معرف» قابل حذف نیست."},
                            status_code=400)
    if settings_mod.is_doctor_used(doctor_id):
        return JSONResponse({"detail": "این پزشک در فاکتور استفاده شده؛ فقط غیرفعال‌سازی ممکن است."},
                            status_code=400)
    settings_mod.hard_delete_doctor(doctor_id)
    return {"ok": True}


# --------------------------------------------------------------------------- #
# Settings
# --------------------------------------------------------------------------- #

@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    redir = page(request)
    if redir:
        return redir
    return render(request, "settings.html", nav="settings",
                  app_title_value=_app_title(),
                  version=settings_mod.get_setting("version", ""),
                  update_invoice_date_on_edit=settings_mod.get_setting(
                      "update_invoice_date_on_edit", "0") == "1",
                  show_doctor_in_print=settings_mod.get_setting(
                      "show_doctor_in_print", "0") == "1",
                  print_size=settings_mod.get_setting("print_size", "A4"),
                  methods=settings_mod.get_payment_methods(),
                  categories=settings_mod.get_expense_categories(),
                  backups=_list_backups())


@app.post("/settings/general")
async def settings_general_save(request: Request):
    redir = page(request)
    if redir:
        return redir
    form = await request.form()
    title = (form.get("app_title") or "").strip()
    if title:
        settings_mod.set_setting("app_title", title)
    settings_mod.set_setting("update_invoice_date_on_edit",
                             "1" if form.get("update_invoice_date_on_edit") else "0")
    settings_mod.set_setting("show_doctor_in_print",
                             "1" if form.get("show_doctor_in_print") else "0")
    settings_mod.set_setting("print_size", form.get("print_size") or "A4")
    templates.env.globals["app_title"] = _app_title()
    return RedirectResponse(url="/settings?msg=تنظیمات ذخیره شد", status_code=303)


# --------------------------------------------------------------------------- #
# Backup & restore
# --------------------------------------------------------------------------- #

def _list_backups():
    # type: () -> List[Dict[str, Any]]
    """Existing database backups in backups/, newest first."""
    bdir = database._backup_dir()
    items = []
    if os.path.isdir(bdir):
        for name in os.listdir(bdir):
            if not (name.startswith(database.BACKUP_PREFIX) and name.endswith(".db")):
                continue
            path = os.path.join(bdir, name)
            try:
                st = os.stat(path)
            except OSError:
                continue
            when = _dt.datetime.fromtimestamp(st.st_mtime)
            items.append({
                "name": name,
                "size_kb": max(1, int(round(st.st_size / 1024.0))),
                "date": ser.fmt_date_jalali(when.date().isoformat()),
                "time": when.strftime("%H:%M"),
                "mtime": st.st_mtime,
            })
    items.sort(key=lambda b: b["mtime"], reverse=True)
    return items


def _safe_backup_path(name):
    # type: (str) -> Optional[str]
    """Resolve a backup filename inside backups/, refusing traversal/foreign files."""
    if not (name.startswith(database.BACKUP_PREFIX) and name.endswith(".db")):
        return None
    if "/" in name or "\\" in name or ".." in name:
        return None
    return os.path.join(database._backup_dir(), name)


@app.post("/settings/backup")
def backup_create(request: Request):
    redir = page(request)
    if redir:
        return redir
    path = database._backup_db()
    if path is None:
        return RedirectResponse(
            url="/settings?ftype=error-box&msg=پشتیبان‌گیری ناموفق بود؛ پایگاه داده در دسترس نیست",
            status_code=303)
    return RedirectResponse(url="/settings?msg=پشتیبان جدید ساخته شد", status_code=303)


@app.get("/settings/backup/{name}")
def backup_download(request: Request, name: str):
    redir = page(request)
    if redir:
        return redir
    path = _safe_backup_path(name)
    if path is None or not os.path.isfile(path):
        return JSONResponse({"detail": "فایل پشتیبان پیدا نشد."}, status_code=404)
    return FileResponse(path, filename=name, media_type="application/octet-stream")


@app.post("/settings/backup/{name}/delete")
def backup_delete(request: Request, name: str):
    redir = page(request)
    if redir:
        return redir
    path = _safe_backup_path(name)
    if path is None or not os.path.isfile(path):
        return RedirectResponse(url="/settings?ftype=error-box&msg=فایل پشتیبان پیدا نشد",
                                status_code=303)
    try:
        os.remove(path)
    except OSError:
        return RedirectResponse(url="/settings?ftype=error-box&msg=حذف فایل ممکن نشد",
                                status_code=303)
    return RedirectResponse(url="/settings?msg=پشتیبان حذف شد", status_code=303)


@app.post("/settings/backup/{name}/restore")
def backup_restore(request: Request, name: str):
    redir = page(request)
    if redir:
        return redir
    path = _safe_backup_path(name)
    if path is None or not os.path.isfile(path):
        return RedirectResponse(url="/settings?ftype=error-box&msg=فایل پشتیبان پیدا نشد",
                                status_code=303)
    # Safety net: snapshot the current DB before it is overwritten, so the
    # restore itself can be undone from the same list.
    database._backup_db()
    try:
        shutil.copy2(path, database._db_path())
    except OSError:
        return RedirectResponse(url="/settings?ftype=error-box&msg=بازیابی ممکن نشد",
                                status_code=303)
    return RedirectResponse(url="/settings?msg=اطلاعات از پشتیبان بازیابی شد", status_code=303)


def _save_simple_list(items, used_checker, setter, getter):
    # type: (List[str], Any, Any, Any) -> List[str]
    keep = []
    for name in items:
        name = (name or "").strip()
        if name and name not in keep:
            keep.append(name)
    setter(keep)
    return keep


@app.post("/api/settings/methods")
async def api_methods_save(request: Request):
    guard = api_guard(request)
    if guard:
        return guard
    body = await request.json()
    methods = [m.strip() for m in (body.get("methods") or []) if m.strip()]
    for old in settings_mod.get_payment_methods():
        if old not in methods and settings_mod.is_payment_method_used(old):
            return JSONResponse({"detail": "روش پرداخت «%s» در فاکتورها استفاده شده "
                                           "و قابل حذف نیست." % old}, status_code=400)
    settings_mod.set_payment_methods(methods)
    return {"ok": True}


@app.post("/api/settings/categories")
async def api_categories_save(request: Request):
    guard = api_guard(request)
    if guard:
        return guard
    body = await request.json()
    cats = [c.strip() for c in (body.get("categories") or []) if c.strip()]
    for old in settings_mod.get_expense_categories():
        if old not in cats and settings_mod.is_expense_category_used(old):
            return JSONResponse({"detail": "دسته «%s» در هزینه‌ها استفاده شده "
                                           "و قابل حذف نیست." % old}, status_code=400)
    settings_mod.set_expense_categories(cats)
    return {"ok": True}
