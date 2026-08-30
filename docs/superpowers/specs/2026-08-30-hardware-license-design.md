# Hardware License for AzaranTeb (نبض کلینیک) — Design

Date: 2026-08-30 · Status: **implemented** · Scope: desktop PyQt5 app + standalone issuer tool

## Goal

The packaged `AzaranTeb.exe` must only run on a machine that holds a valid,
vendor-signed license bound to that machine's hardware. On an unlicensed or
wrongly-licensed machine the app shows the machine's hardware code so the
vendor can issue a license for it. The vendor uses a separate Python program
(not shipped to customers) to create license files.

## Decisions (client-approved)

| Topic | Decision |
|---|---|
| Crypto model | RSA-2048, PKCS#1 v1.5 + SHA-256, **pure Python** (no `cryptography` dependency) |
| Key custody | Public key embedded in the app; private key only in the vendor's issuer tool |
| Expiry | Both perpetual and dated licenses supported (`expires: null` = perpetual) |
| Invalid license | Hard block — activation dialog, no pages until activated |
| Hardware source | Windows `MachineGuid` (registry), fallback to MAC + computer name |
| Details on start | Silent when valid; warning only when ≤ 15 days remain; full details from a menu |
| Issuer tool | PyQt5 GUI (plus a CLI mode used by automated tests) |
| Enforcement scope | Only when frozen (`sys.frozen`); source runs stay open, `AZARAN_LICENSE_ENFORCE=1` forces the check for testing |
| Trial period | None |

## Components

### 1. `app/rsa_lite.py` — minimal RSA

Pure stdlib (`hashlib`, `os`, `random`, `binascii`). Public surface:

- `generate_keypair(bits=2048, e=65537)` → dict of ints `{n, e, d, p, q}`
- `sign(msg: bytes, d: int, n: int) -> bytes` — EMSA-PKCS1-v1_5(SHA-256)
- `verify(msg: bytes, sig: bytes, e: int, n: int) -> bool`
- `key_to_json(keys) / key_from_json(text)` — hex-encoded ints, human-readable
- `fingerprint(n, e) -> str` — first 8 hex of SHA-256(modulus), to identify a key pair

Prime generation: random odd candidates with the top two bits set, filtered by
trial division against a table of small primes, then Miller-Rabin with 24
rounds from `random.SystemRandom`. Modular inverse is an extended-Euclid
implementation (not `pow(x, -1, m)`) to stay safe on Python 3.8.

### 2. `app/license.py` — fingerprint, format, verification

- `hardware_code()` → `ABCDE-FGHIJ-KLMNP-QRSTU`
  = first 20 chars of `base32(SHA256("AZARAN1|" + machine_source))`, grouped in 5s.
  `machine_source` is `"MG:" + MachineGuid` (read with `KEY_WOW64_64KEY`), or
  `"FB:" + hex(uuid.getnode()) + ":" + COMPUTERNAME` when the registry is unreadable.
  Base32 (RFC 4648) has no `0`/`1`, so the code survives being read aloud.
- License file `license.key`, stored next to the exe (same dir as `azaran_teb.db`).
  One token: `AZARAN1.<b64url(payload)>.<b64url(signature)>`.
  The signature covers the **exact payload bytes as stored**, so no
  canonicalisation mismatch is possible between issuer and verifier.
  Payload keys: `v` (int, =1), `hw` (str), `name` (str), `issued` (ISO date),
  `expires` (ISO date or `null`).
- `verify()` → `Status(ok, code, message, payload, days_left)` with codes
  `OK / MISSING / BAD_FORMAT / BAD_SIGN / HW_MISMATCH / EXPIRED / CLOCK_TAMPER`.
- `install_license(src_path)` copies a chosen file into place atomically
  (temp + `os.replace`) and re-verifies.
- Clock guard: the highest date ever seen is persisted in `settings` under
  `license.last_seen`. If today is more than 2 days *earlier* than that, the
  license is refused with `CLOCK_TAMPER`. The 2-day slack avoids locking a
  clinic out after a dead CMOS battery.
- `enforce_startup()` is the single entry point used by `main.py`.

### 3. `app/ui/license_dialog.py` — the two dialogs

Both are RTL, Vazirmatn, and reuse the app's `fields`/theme helpers.

- `ActivationDialog(status)`: red banner with the Persian reason, the hardware
  code in a large read-only field with a «کپی» button, «انتخاب فایل لایسنس…»
  (copies the file, re-verifies, accepts on success, otherwise shows the new
  reason inline), and «خروج».
- `LicenseDetailsDialog`: licensee, issue/expiry in Jalali with Persian digits,
  days remaining, hardware code + copy, «بارگذاری لایسنس جدید».

### 4. `tools/license_issuer.py` — vendor-only generator

PyQt5 window with three tabs:

- **صدور لایسنس**: paste hardware code (live format validation), licensee name,
  «بدون انقضا» or a Jalali expiry date, «ساخت و ذخیرهٔ فایل» + «کپی متن».
- **کلیدها**: «ساخت جفت‌کلید جدید» (with an explicit warning that every license
  issued earlier becomes invalid), shows the `PUBLIC_KEY_N` block to paste into
  `app/license.py`, shows the current key fingerprint.
- **راهنما**: the Persian step-by-step for dealing with a customer.

Private key lives in `keys/issuer_private.json` and is **never** copied into
`dist/`. CLI mode: `python tools/license_issuer.py --hw ... --name ... --expires ... --out license.key`.

### 5. Wiring

- `main.py`: after `apply_theme()`, before `run_desktop()` →
  `if not license.enforce_startup(): return 0`.
- `app/ui/shell.py`: «مجوز نرم‌افزار» button in the sidebar footer next to the
  version label; after a successful login, a one-shot warning when
  `0 <= days_left <= 15`.

## Error handling

Every failure path produces a distinct Persian message; unknown exceptions
inside the license check degrade to `BAD_FORMAT` rather than crashing the app.
A corrupt `license.key` never blocks re-activation — the dialog always offers
file selection, and the hardware code is always shown so a new license can be
requested even when the DB is empty.

## Testing

- `_licenseprobe.py`: key generation, sign/verify round trip, single-byte
  tampering → `BAD_SIGN`, foreign hardware code → `HW_MISMATCH`, past expiry →
  `EXPIRED`, perpetual → `OK`, hardware-code stability and format, clock
  rollback → `CLOCK_TAMPER`, CLI ↔ GUI token compatibility.
- New assertions inside `_verifyfixes.py`; the existing 62 checks must stay green.
- `smoke_ui.py` must stay at 0 failures.
- Frozen build: launch with no `license.key` (activation dialog, screenshot)
  and with a license for the dev machine (normal login).

## Implementation notes discovered while building

- **`QLabel` does not mirror like `QTableView` does.** In an RTL widget,
  `Qt::AlignLeft` paints on the visual right — which is why the table fix in
  the previous round works. But a *word-wrapped* `QLabel` whose text has no
  strong RTL character (a Jalali date such as `۱۴۰۵/۰۶/۱۵`, or a day count)
  resolves its paragraph as LTR and drifts to the visual **left**. Measured
  variants: `AlignRight` fixes digits but breaks Persian text; forcing the
  label LTR breaks Persian text. The only flag that is correct for every text
  class is a leading **RLM (U+200F)** with the default alignment, so
  `license_dialog._row()` prefixes values with it.
- `date.fromisoformat("1406-06-08")` succeeds (year 1406 CE), so a Jalali
  expiry typed on the CLI would silently be stored as a medieval date.
  `parse_expiry()` only accepts the ISO reading when the year is in
  1900–2200 and otherwise falls through to the Jalali parser.
- `license.key` is deliberately **not** shipped inside `dist/`: the first run
  on a new machine must show the hardware code, which is the whole point.
- The frozen build resolves the same `MachineGuid` as the source build, so a
  license minted by `tools/license_issuer.py` on the vendor machine is
  accepted by the customer's exe (verified by `_launchtest.ps1` scenario C).

## Known limits (stated to the client)

- Losing `keys/issuer_private.json` means no new licenses can be issued; a new
  key pair requires replacing the embedded public key and rebuilding the exe.
- A pure-Python check inside a PyInstaller build can be patched out by someone
  who can decompile Python. This design stops folder-copying to another
  machine, which is the actual threat in this market — it is not DRM.
