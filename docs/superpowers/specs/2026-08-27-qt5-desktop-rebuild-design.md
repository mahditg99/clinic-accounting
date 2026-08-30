# Design: Qt5 Desktop Rebuild of the Azaran Teb Web UI

Date: 2026-08-27 · Status: **implemented** · Author: assistant (brainstorming session with user)

## Goal

Recreate the FastAPI/Jinja web UI (the design the user approved as "the best")
as a native PySide2/PyQt5 desktop application that runs on **Windows 7** with
**Python 3.8** and packages to an `.exe`.

## Why Qt5 (no better option)

* Win7 support ends at Qt 5.15 / Python 3.8 — Qt6 and PySide6 do not run on
  Win7. Toga/Flet/Electron-style wrappers fail the same constraint or lack RTL.
* PyQt5 5.15.10 + Python 3.8 + PyInstaller is the proven Win7 combination.
* QtWebEngine was rejected: heavy (~150 MB), fragile on Win7, and the user
  explicitly wants the native look of the current desktop app.

## Chosen approach

**Option C — full native rebuild** of every page in a new package `app/ui/`,
mirroring `webapp/templates/*.html` 1:1 (cards, tables, tiles, buttons,
messages), while keeping the shared data layer (`app/models.py`,
`app/settings.py`, `app/database.py`, `app/date_utils.py`, `app/money_utils.py`)
untouched except digit-folding search. The old UI (`app/widgets/`,
`app/dialogs/`) was archived to `_legacy/` after the new UI passed smoke tests.

## Architecture

```
main.py                     # QApplication + Fusion + theme + run_desktop()
app/
  auth_core.py              # PBKDF2 login shared with webapp/auth.py
  ui/
    shell.py                # LoginDialog, ChangePasswordDialog, AppWindow
    fields.py               # FaLineEdit/MoneyEdit/QtyEdit/SearchEdit/
                            # JalaliDateEdit(+calendar popup)/table helpers
    dashboard_page.py       # hero + ledger + by-method + low-stock
    invoice_page.py         # new/edit invoice (patient picker, item/payment rows)
    archive_page.py         # filters + live search + view/print/edit/void
    patients_page.py        # inline add/edit + live digit-insensitive search
    products_page.py        # stock batches, re-charge, low-stock tint
    doctors_page.py         # CRUD + search (بدون معرف protected)
    daily_report_page.py
    income_expense_page.py
    expenses_page.py        # CRUD + filters
    financial_reports_page.py  # monthly/yearly receipts/expenses/profit
    doctor_report_page.py   # referral summary or per-doctor detail
    product_sales_page.py
    settings_page.py        # general, methods, categories, backups
    printing.py             # QTextDocument HTML → QPrintPreviewDialog
  theme.py                  # Fusion QSS (cards, sum-cards, sidebar, hero…)
```

`AppWindow` = app bar (brand, today Jalali, user, تغییر رمز, خروج) + sidebar
`QListWidget` in the web nav order (dashboard; عملیات روزانه: فاکتور جدید،
آرشیو، پرونده‌ها، محصولات؛ گزارش‌ها: روزانه، درآمد/هزینه، هزینه‌ها، مالی،
پزشکان، فروش محصولات؛ مدیریت: پزشکان، تنظیمات) + `QStackedWidget`. Each page
implements `refresh()` and is re-read on navigation (mirrors a browser GET).

## Key decisions

1. **Digits**: display Persian (۰-۹, thousands mark ٬) everywhere; store Latin.
   Implemented once in `app/ui/fields.py` (same tables as `app.js`) so every
   line edit converts on the fly, caret-safe.
2. **Search**: word-wise AND, digit-folded, ZWNJ-as-wildcard — desktop reuses
   the same folding as the web (`models._search_word`, `F.match_words`).
3. **Jalali dates**: custom calendar popup (jdatetime not required;
   `date_utils` Borkowski conversion), `YYYY/MM/DD` Persian display.
4. **Auth**: desktop login dialog uses `app/auth_core.py` — identical
   PBKDF2-HMAC-SHA256 credentials as the web session (shared DB).
5. **Printing**: same HTML builders as the web print views rendered through
   `QTextDocument` + `QPrintPreviewDialog` (A4/A5 from settings).
6. **Packaging**: PyInstaller **onedir** (`--windowed --name AzaranTeb`);
   `database._base_dir()` returns the exe folder when frozen so
   `azaran_teb.db` + `backups/` live next to the exe and survive restarts.

## Verification

* `smoke_ui.py` (offscreen Qt): compiles every module, instantiates all 13
  pages, navigates the whole sidebar, exercises live search (Persian digits),
  invoice row add, invoice model round-trip + edit-load, report HTML, backup
  list — 47/47 checks pass on a throwaway DB.
* `verify_web.py`: webapp regression after the auth refactor — login, wrong
  password rejection, all 13 pages 200, Persian digits — 17/17 pass.
* Built exe (`dist/AzaranTeb/AzaranTeb.exe`, ~91 MB onedir) launches offscreen
  and creates the full schema DB next to itself.
