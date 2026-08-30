# نبض کلینیک — Azaran Teb Clinic Accounting

**Read this in Persian: [README.fa.md](README.fa.md)**

A Persian (Farsi), right-to-left desktop accounting application for a small
clinic — invoicing, patient files, stock, expenses and reports — plus a
browser version of the same product. Built to run on **Windows 7** with
**Python 3.8**, package into a portable `.exe`, and ship with a
**hardware-bound license**.

* UI language: Persian, RTL, Persian digits, Jalali (Shamsi) calendar.
* Desktop: Python 3.8 + Qt 5.15 (PyQt5 or PySide2, auto-detected) + SQLite.
* Web: FastAPI + Jinja2 over the *same* database file.
* No QtWebEngine, no ORM, no binary crypto wheels.

---

## Table of contents

- [What it does](#what-it-does)
- [Requirements](#requirements)
- [Quick start](#quick-start)
- [Project layout](#project-layout)
- [How it is put together](#how-it-is-put-together)
- [Hardware licensing](#hardware-licensing)
- [Demo data](#demo-data)
- [Tests and probes](#tests-and-probes)
- [Building the exe](#building-the-exe)
- [Design docs](#design-docs)

---

## What it does

Thirteen screens in the desktop shell, mirrored one-for-one by the web UI:

| Section | Screens |
|---|---|
| Daily work | داشبورد · فاکتور جدید · آرشیو فاکتورها · پرونده‌ها · فهرست محصولات |
| Reports | گزارش روزانه · درآمد / هزینه · هزینه‌ها · گزارش‌های مالی · گزارش پزشکان · فروش محصولات |
| Admin | فهرست پزشکان · تنظیمات |

Highlights:

- **Invoicing** — multi-item invoices with cost/sale price, discount, several
  payment methods per invoice, partial payments, automatic stock decrease,
  void-with-restock, printable A4 invoice.
- **Patient files** — search-as-you-type, invoice history per patient, safe
  delete (a patient with invoices is deactivated instead of erased).
- **Stock** — products with purchase/sale price, quantity, low-stock threshold
  highlighting, restock flow, per-product sales report with profit margin.
- **Money in / money out** — expense categories, doctor referral report,
  monthly and yearly financial summary (received / expenses / net profit).
- **Printing** — the same HTML the web print views use, through
  `QPrintPreviewDialog`.
- **Everything in Persian** — Jalali date pickers on every date field, Persian
  digits in every number, RTL tables with click-to-sort headers, and a
  Vazirmatn font bundled with the app so it looks identical on a bare Win7 box.

## Requirements

- Windows 7 SP1 or newer (32/64-bit). Linux/macOS also run it; the license
  check is Windows-only and simply does not fire from source.
- **Python 3.8.x** — exactly. 3.9+ drops Windows 7 support.
- Qt 5.15 bindings: `PySide2==5.15.2.1` (preferred) or `PyQt5==5.15.x`.
- `jdatetime` for the Jalali calendar.
- Optional, for the browser version: `fastapi`, `uvicorn`, `jinja2`,
  `python-multipart`.

## Quick start

```bat
cd azaran_teb
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Log in with **admin / admin** (change it from the top bar).

The SQLite database is created on first run as `azaran_teb.db` **next to the
exe** (or next to `main.py` when run from source), which keeps the whole
folder portable.

Browser version, sharing the same database:

```bat
python -m uvicorn webapp.main:app --reload --port 8000
```

then open <http://127.0.0.1:8000>.

## Project layout

```
azaran_teb/
├── main.py                  entry point: scaling → DB → theme → license gate → shell
├── app/
│   ├── utils.py             Qt binding auto-detect, fonts, high-DPI scaling recipe
│   ├── database.py          schema, migrations, portable path, backups
│   ├── models.py            all data access (invoices, patients, stock, reports)
│   ├── settings.py          settings + doctors + payment methods + expense categories
│   ├── date_utils.py        Jalali ⇄ Gregorian, Persian digit folding
│   ├── money_utils.py       rial formatting
│   ├── auth_core.py         login users, password hashing
│   ├── theme.py             the global QSS (the "Clinic Pulse" design)
│   ├── rsa_lite.py          pure-Python RSA-2048 (PKCS#1 v1.5 + SHA-256)
│   ├── license.py           hardware code, license format, verification
│   └── ui/
│       ├── shell.py         sidebar + top bar + page stack + login dialog
│       ├── fields.py        the shared table/field factory (RTL, sorting, lazy rows)
│       ├── *_page.py        the 13 screens
│       ├── license_dialog.py activation + details dialogs
│       └── printing.py      print previews
├── webapp/                  FastAPI version over the same data layer
│   ├── main.py  auth.py  serializers.py
│   ├── templates/           Jinja2 pages (the design source of truth)
│   └── static/              style.css + Vazirmatn webfont
├── tools/license_issuer.py  VENDOR-ONLY license generator (GUI + CLI)
├── docs/superpowers/specs/  design documents
├── _seed_demo.py            fills the DB with realistic demo data
├── smoke_ui.py              opens every page and fails on any exception
├── _*.py                    pixel probes and regression harnesses (see below)
└── AzaranTeb.spec           PyInstaller build recipe
```

`_legacy/` holds the first-generation Qt UI. It is not imported by anything and
is kept only for reference.

## How it is put together

**One data layer, two front ends.** `app/models.py` owns every query. The
desktop pages and the FastAPI templates both call it, so a feature is
implemented once and the two UIs cannot drift apart in behaviour.

**The web UI is the design spec.** Every desktop screen was rebuilt to match
`webapp/templates/*.html` + `static/style.css` pixel for pixel — same palette,
same card shapes, same ECG ribbon.

**RTL is explicit, not inherited.** Qt resolves `AlignLeft`/`AlignRight`
*against the widget's layout direction*, so in an RTL table `AlignRight`
paints on the visual **left**. `app/ui/fields.py` therefore asks for
`AlignLeft` to get right-aligned headers and cells. A wrapped `QLabel` behaves
differently again: a digits-only string (a Jalali date) resolves its paragraph
as LTR and drifts left, so those values get a leading U+200F mark. Both
behaviours are pinned by pixel probes (`_rtlprobe.py`, `_liclayout.py`).

**High-DPI on Win7.** Qt 5.15 rounds its auto scale factor to an integer, so
`setup_scaling()` pins `QT_FONT_DPI=96` and applies `QT_SCALE_FACTOR = dpi/96`
uniformly — before `QApplication` exists. This is what makes 125%/150% laptop
screens render like the web UI instead of clipping text.

**Big tables stay fast.** Tables with per-row action buttons build those
widgets only for the visible rows (`set_row_widget_factory`) and recycle them
on scroll; layout passes are coalesced through a single `schedule_fit()`.
Measured on a 588-invoice archive: **54.7 s → 1.1 s** to open. Sorting is safe
because Qt moves persistent index widgets with their rows.

## Hardware licensing

The packaged exe only runs on a machine the vendor has licensed.

- **Hardware code** — `SHA-256` of the Windows `MachineGuid`, rendered as
  20 Base32 characters in four groups: `ABCDE-FGHIJ-KLMNP-QRSTU`. Changing
  disks/RAM/NIC keeps it; reinstalling Windows or copying the folder to another
  PC changes it.
- **License file** — `license.key` next to the exe:
  `AZARAN1.<payload>.<signature>`, where the payload is JSON
  (`v, hw, name, issued, expires|null`) and the signature is
  **RSA-2048 / PKCS#1 v1.5 / SHA-256** over those exact payload bytes.
- **Keys** — the *public* key is embedded in `app/license.py`; the *private*
  key lives in `keys/issuer_private.json`, which is git-ignored and must never
  be shipped or committed. `rsa_lite.py` is hand-written on top of Python's
  `int`/`pow` so the build needs no binary crypto wheel.
- **Behaviour** — checked once at startup, only in the frozen build
  (`sys.frozen`). Valid → straight to login. Missing / wrong machine / bad
  signature / expired → a blocking activation dialog that shows the reason in
  Persian, the hardware code with a copy button, and a file picker that
  installs the license and continues. A «مجوز نرم‌افزار» item in the sidebar
  footer shows full details at any time, and a one-shot reminder appears in
  the last 15 days.
- **Clock guard** — the highest date ever seen is stored in `settings`; if the
  system clock is more than two days behind it, the license is refused, so an
  expired license cannot be revived by changing the date. The two-day slack
  avoids locking out a clinic after a dead CMOS battery.
- **Issuing a license**

  ```bat
  python tools\license_issuer.py                 :: GUI (issue / keys / help tabs)
  python tools\license_issuer.py --print-hwid
  python tools\license_issuer.py --hw <CODE> --name "کلینیک آذر" --expires 1407-06-31 --out license.key
  python tools\license_issuer.py --verify license.key
  ```

  Full workflow in [LICENSE-HOWTO.md](LICENSE-HOWTO.md) (Persian).

> **Honest limits.** Losing `keys/issuer_private.json` means no new licenses
> can be issued without regenerating the pair, updating the embedded public
> key and rebuilding — which invalidates every license issued before. And no
> client-side check resists someone who can edit a PyInstaller bundle: this
> stops folder-copying to another machine, which is the actual problem in this
> market; it is not DRM.

## Demo data

```bat
python _seed_demo.py
```

Idempotent (guarded by a `settings.demo_seeded` flag). Adds 8 doctors, 250
patients, 66 products, ~585 invoices and 250 expenses spread over the last 13
months with realistic Persian names and weighted-recent dates — enough to judge
scrolling, sorting and report performance.

## Tests and probes

No test framework; each script exits non-zero on failure and prints a tally.

| Script | What it proves |
|---|---|
| `smoke_ui.py` | every page opens, refreshes and resizes without an exception |
| `_verifyfixes.py` | 80 assertions covering all reported bugs (fonts, RTL, widths, license, patient picker) |
| `_licenseprobe.py` | 107 assertions: RSA, token format, tamper/wrong-machine/expiry/clock rejection, issuer CLI |
| `_liclayout.py` | license dialogs: RTL edges, no clipped widget, code centred |
| `_issuelayout.py` | the vendor tool's window: validation, quick presets, issuing path |
| `_rtlprobe.py` | pixel-measures every header and cell in the app → must be 0 left-hugging |
| `_colprobe.py` / `_btnprobe.py` | every column wide enough for real data / action buttons |
| `_lazyprobe.py` | lazy row widgets stay bounded and follow their row across sort and scroll |
| `_pickprobe.py` | patient-picker flows (create, search, exact match, resolve on save) |
| `_perfprobe.py` | page-switch, resize and scroll timings against the seeded database |
| `_launchtest.ps1` | runs the built exe in a temp copy: no license, foreign license, valid license |

```bat
python smoke_ui.py
python _verifyfixes.py
python _licenseprobe.py
powershell -File _launchtest.ps1
```

## Building the exe

```bat
pip install pyinstaller
pyinstaller --noconfirm AzaranTeb.spec
```

Produces `dist\AzaranTeb\AzaranTeb.exe` as a **folder** build (onedir): faster
start, friendlier to Windows 7 antivirus scanning, and the database, backups
and `license.key` all live next to the exe, so the folder is portable. Ship the
whole `AzaranTeb` folder — and **not** `keys\`, `tools\` or any `license.key`.

Win7 notes: Qt 5.15 is the last series supporting Windows 7, so stay on
Python 3.8 + PyQt5/PySide2 5.15.x, add no QtWebEngine, and expect the VC++
2015-2019 runtime to be required on a clean machine.

## Design docs

- [docs/superpowers/specs/2026-08-27-qt5-desktop-rebuild-design.md](docs/superpowers/specs/2026-08-27-qt5-desktop-rebuild-design.md) — rebuilding the web UI as a Win7-compatible Qt desktop app
- [docs/superpowers/specs/2026-08-30-hardware-license-design.md](docs/superpowers/specs/2026-08-30-hardware-license-design.md) — the licensing subsystem

---

© آذران طب (Azaran Teb). All rights reserved. This repository is public for
review; it is not licensed for reuse or redistribution.
