# -*- coding: utf-8 -*-
"""End-to-end checks for the hardware-license subsystem.

Runs against a throwaway DB + a throwaway license dir so the real dev data is
never touched.  Uses the REAL vendor private key (keys/issuer_private.json) so
the tokens exercised here are exactly the ones the shipped exe must accept.
"""
import json
import os
import sys
import tempfile
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.utils import Qt, setup_scaling            # noqa: E402
setup_scaling()
App = Qt.QtWidgets.QApplication.instance() or Qt.QtWidgets.QApplication(sys.argv)

from app import license as lic                      # noqa: E402
from app import rsa_lite as R                       # noqa: E402
from app import database                            # noqa: E402
from app import settings as S                       # noqa: E402

TMP = tempfile.mkdtemp(prefix="licprobe-")
DB = os.path.join(TMP, "probe.db")
database._db_path = lambda: DB
database.init_db()
# license.key now lives in the temp dir, not next to the exe/source.
database._base_dir = lambda: TMP

PRIV = R.key_from_json(open(os.path.join(os.path.dirname(
    os.path.abspath(__file__)), "keys", "issuer_private.json"),
    encoding="utf-8").read())

PASS = [0]
FAIL = []


def check(name, cond, extra=""):
    if cond:
        PASS[0] += 1
    else:
        FAIL.append("%s %s" % (name, extra))
        print("FAIL  %s %s" % (name, extra))


def token_for(hw, expires, name="کلینیک تست", issued=None):
    payload = lic.make_payload(hw, name, (issued or date.today()).isoformat(), expires)
    return lic.build_token(payload, PRIV)


def write_license(text):
    with open(lic.license_path(), "w", encoding="utf-8") as fh:
        fh.write(text + "\n")


def clear_license():
    try:
        os.remove(lic.license_path())
    except OSError:
        pass


# ------------------------------------------------------------------ #
# 1. hardware code
# ------------------------------------------------------------------ #
hw = lic.hardware_code()
check("hw code stable", hw == lic.hardware_code())
raw = hw.replace("-", "")
check("hw code 20 chars", len(raw) == 20, repr(hw))
check("hw code grouped", hw.count("-") == 3 and all(len(g) == 5 for g in hw.split("-")))
check("hw code base32 alphabet", all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567" for c in raw))
check("hw code no ambiguous 0/1", "0" not in raw and "1" not in raw)
check("hw code valid()", lic.code_is_valid(hw))
check("normalize lowercase", lic.normalize_code(hw.lower()) == hw)
check("normalize no dashes", lic.normalize_code(raw) == hw)
check("normalize spaces", lic.normalize_code(" ".join(hw.split("-"))) == hw)
check("normalize rejects short", lic.normalize_code("ABC") == "")
check("normalize rejects long", lic.normalize_code(raw + "A") == "")
check("normalize rejects wrong alphabet", lic.normalize_code("ABCD$-FGHIJ-KLMNP-QR") == "")
check("normalize tolerates separators", lic.normalize_code(hw.replace("-", ".")) == hw)
check("source is machine guid", lic.machine_source().startswith("MG:"),
      lic.machine_source())

# ------------------------------------------------------------------ #
# 2. key custody
# ------------------------------------------------------------------ #
check("public key embedded", len(lic.PUB_N_HEX) == 512, str(len(lic.PUB_N_HEX)))
check("fingerprint matches", lic.public_fingerprint() == lic.KEY_FINGERPRINT)
check("private key matches app", R.fingerprint(PRIV["n"]) == lic.public_fingerprint())
check("modulus is 2048 bit", int(lic.PUB_N_HEX, 16).bit_length() == 2048)

# ------------------------------------------------------------------ #
# 3. happy path (dated)
# ------------------------------------------------------------------ #
exp = (date.today() + timedelta(days=365)).isoformat()
write_license(token_for(hw, exp))
st = lic.verify()
check("dated license OK", st.ok, st.code)
check("days_left ~365", st.days_left == 365, str(st.days_left))
check("customer name", st.customer == "کلینیک تست", st.customer)
check("warns_of_expiry false", lic.warns_of_expiry(st) is False)

# ------------------------------------------------------------------ #
# 4. perpetual
# ------------------------------------------------------------------ #
write_license(token_for(hw, None))
st = lic.verify()
check("perpetual OK", st.ok, st.code)
check("perpetual days None", st.days_left is None)
check("perpetual shows دائمی", "expires" not in st.payload or st.payload["expires"] is None)

# ------------------------------------------------------------------ #
# 5. near-expiry warning window
# ------------------------------------------------------------------ #
write_license(token_for(hw, (date.today() + timedelta(days=10)).isoformat()))
st = lic.verify()
check("10 days still OK", st.ok)
check("warns at 10 days", lic.warns_of_expiry(st) is True)
write_license(token_for(hw, (date.today() + timedelta(days=40)).isoformat()))
check("no warn at 40 days", lic.warns_of_expiry(lic.verify()) is False)
write_license(token_for(hw, date.today().isoformat()))
st = lic.verify()
check("expiry day itself is valid", st.ok and st.days_left == 0)

# ------------------------------------------------------------------ #
# 6. failure modes
# ------------------------------------------------------------------ #
clear_license()
check("missing -> MISSING", lic.verify().code == lic.MISSING)
check("missing message fa", "لایسنس" in lic.verify().message)

write_license("hello world")
check("garbage -> BAD_FORMAT", lic.verify().code == lic.BAD_FORMAT)

tok = token_for(hw, exp)
write_license(tok)
check("valid token OK", lic.verify().ok)

# flip one character inside the signature block
head, p1, p2 = tok.split(".")
bad_sig = p2[:-4] + ("AAAA" if not p2.endswith("AAAA") else "BBBB")
write_license(".".join([head, p1, bad_sig]))
check("tampered signature -> BAD_SIGN", lic.verify().code == lic.BAD_SIGN,
      lic.verify().code)

# flip one character inside the payload (name) -> signature no longer matches
bad_pay = p1[:-4] + ("AAAA" if not p1.endswith("AAAA") else "BBBB")
write_license(".".join([head, bad_pay, p2]))
check("tampered payload rejected", lic.verify().code in (lic.BAD_SIGN, lic.BAD_FORMAT),
      lic.verify().code)

# wrong product prefix
write_license("OTHERPROD.%s.%s" % (p1, p2))
check("foreign product -> BAD_FORMAT", lic.verify().code == lic.BAD_FORMAT)

# license for another machine
write_license(token_for("ABCDE-FGHIJ-KLMNP-QRSTU", exp))
st = lic.verify()
check("other machine -> HW_MISMATCH", st.code == lic.HW_MISMATCH, st.code)
check("hw mismatch not ok", st.ok is False)
check("mismatch still shows my code", st.hw == hw)

# expired
write_license(token_for(hw, (date.today() - timedelta(days=1)).isoformat()))
st = lic.verify()
check("expired -> EXPIRED", st.code == lic.EXPIRED, st.code)
check("expired message has date", "منقضی" in st.message, st.message)

# signed with a different (rogue) key of the same size
rogue = R.generate_keypair(1024)
rogue_tok = lic.build_token(lic.make_payload(hw, "متقلب", date.today().isoformat(), exp),
                            rogue)
write_license(rogue_tok)
check("rogue key -> BAD_SIGN", lic.verify().code == lic.BAD_SIGN, lic.verify().code)

# ------------------------------------------------------------------ #
# 7. install_license safety
# ------------------------------------------------------------------ #
good = token_for(hw, exp)
write_license(good)
before = open(lic.license_path(), encoding="utf-8").read().strip()
bad_path = os.path.join(TMP, "bad.key")
with open(bad_path, "w", encoding="utf-8") as fh:
    fh.write("not-a-license")
res = lic.install_license(bad_path)
check("install bad -> not ok", res.ok is False)
check("install bad keeps old file",
      open(lic.license_path(), encoding="utf-8").read().strip() == before)
other_path = os.path.join(TMP, "other.key")
with open(other_path, "w", encoding="utf-8") as fh:
    fh.write(token_for("ABCDE-FGHIJ-KLMNP-QRSTU", exp))
res = lic.install_license(other_path)
check("install other-machine -> HW_MISMATCH", res.code == lic.HW_MISMATCH, res.code)
check("install other-machine keeps old file",
      open(lic.license_path(), encoding="utf-8").read().strip() == before)
new_path = os.path.join(TMP, "new.key")
with open(new_path, "w", encoding="utf-8") as fh:
    fh.write(token_for(hw, None, "کلینیک جدید"))
res = lic.install_license(new_path)
check("install good -> OK", res.ok, res.code)
check("install good replaced file", res.customer == "کلینیک جدید")
check("install missing file -> BAD_FORMAT",
      lic.install_license(os.path.join(TMP, "nope.key")).code == lic.BAD_FORMAT)

# ------------------------------------------------------------------ #
# 8. clock rollback guard
# ------------------------------------------------------------------ #
write_license(token_for(hw, exp))
check("baseline OK before clock test", lic.verify().ok)
S.set_setting(lic._SEEN_KEY, (date.today() + timedelta(days=30)).isoformat())
st = lic.verify()
check("clock back 30d -> CLOCK_TAMPER", st.code == lic.CLOCK_TAMPER, st.code)
check("clock tamper message fa", "ساعت" in st.message, st.message)
S.set_setting(lic._SEEN_KEY, (date.today() + timedelta(days=1)).isoformat())
check("1 day drift tolerated", lic.verify().ok, lic.verify().code)
S.set_setting(lic._SEEN_KEY, date.today().isoformat())
check("same day fine", lic.verify().ok)
# a valid run must push the watermark forward
S.set_setting(lic._SEEN_KEY, (date.today() - timedelta(days=5)).isoformat())
lic.verify()
check("watermark advances", S.get_setting(lic._SEEN_KEY) == date.today().isoformat(),
      S.get_setting(lic._SEEN_KEY))

# ------------------------------------------------------------------ #
# 9. token shape / robustness
# ------------------------------------------------------------------ #
tok = token_for(hw, exp)
check("token prefix", tok.startswith("AZARAN1."))
check("token 3 parts", len(tok.split(".")) == 3)
check("token ascii only", all(ord(c) < 128 for c in tok))
check("parses with newlines", lic.verify_token("  \n" + tok + "\r\n").ok)
check("parses with wrapped line", lic.verify_token(tok[:60] + "\n" + tok[60:]).ok)
check("empty rejected", lic.verify_token("").code == lic.BAD_FORMAT)
check("two dots only", lic.verify_token(tok + ".").code == lic.BAD_FORMAT)
sig = tok.split(".")[2]
check("signature is 256 bytes", len(lic._b64d(sig)) == 256, str(len(lic._b64d(sig))))
check("persian name survives", "آذر" in lic.verify_token(
    token_for(hw, exp, "کلینیک آذر")).payload["name"])

# ------------------------------------------------------------------ #
# 10. rsa_lite primitives
# ------------------------------------------------------------------ #
k = R.generate_keypair(1024)
msg = b"the quick brown fox"
s = R.sign(msg, k["d"], k["n"])
check("rsa roundtrip", R.verify(msg, s, k["e"], k["n"]))
check("rsa wrong msg", not R.verify(b"other", s, k["e"], k["n"]))
check("rsa wrong key", not R.verify(msg, s, k["e"] + 2, k["n"]))
check("rsa short sig", not R.verify(msg, s[:-1], k["e"], k["n"]))
check("rsa long sig", not R.verify(msg, s + b"\x00", k["e"], k["n"]))
check("rsa zero sig", not R.verify(msg, b"\x00" * len(s), k["e"], k["n"]))
check("key json roundtrip", R.key_from_json(R.key_to_json(k))["n"] == k["n"])
check("pub json has no d", "d" not in json.loads(R.key_to_json(k, private=False)))
check("prime test", R._is_prime(9973) and not R._is_prime(9974))
check("modinv", (R._modinv(17, 3120) * 17) % 3120 == 1)

# ------------------------------------------------------------------ #
# 11. issuer tool (module level, no GUI)
# ------------------------------------------------------------------ #
TOOLS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools")
sys.path.insert(0, TOOLS)
import license_issuer as LI  # noqa: E402

check("issuer loads private key", "d" in LI.load_private())
check("issuer key matches app", LI.private_matches_app(LI.load_private()))
t = LI.issue(hw, "کلینیک CLI", (date.today() + timedelta(days=30)).isoformat())
check("issuer token verifies", lic.verify_token(t).ok)
check("parse_expiry jalali", LI.parse_expiry("1406-06-08").startswith("2027-"),
      LI.parse_expiry("1406-06-08"))
check("parse_expiry iso", LI.parse_expiry("2027-08-30") == "2027-08-30")
check("parse_expiry persian digits", LI.parse_expiry("۱۴۰۶/۰۶/۰۸") ==
      LI.parse_expiry("1406-06-08"))
check("parse_expiry empty", LI.parse_expiry("") == "")
try:
    LI.parse_expiry("not-a-date")
    check("parse_expiry rejects junk", False)
except ValueError:
    check("parse_expiry rejects junk", True)
try:
    LI.issue("BAD", "x", "", PRIV)
    check("issue rejects bad hw", False)
except ValueError:
    check("issue rejects bad hw", True)

# CLI end-to-end (in-process: no child stdio pipes needed)
import io  # noqa: E402
import contextlib  # noqa: E402

SRC = os.path.dirname(os.path.abspath(__file__))


def run_cli(argv):
    buf = io.StringIO()
    code = 0
    with contextlib.redirect_stdout(buf):
        try:
            code = LI.main(argv)
        except SystemExit as exc:  # argparse errors
            code = exc.code or 2
        except Exception as exc:
            buf.write("EXC %r" % (exc,))
            code = 99
    return code, buf.getvalue()


code, out_txt = run_cli(["--print-hwid"])
check("CLI --print-hwid", code == 0 and out_txt.strip() == hw, repr(out_txt))
outfile = os.path.join(TMP, "cli.key")
code, out_txt = run_cli(["--hw", hw, "--name", "CLI تست",
                         "--expires", "1407-01-01", "--out", outfile])
check("CLI issue exit 0", code == 0, out_txt)
check("CLI file written", os.path.exists(outfile))
check("CLI file verifies", lic.verify_token(
    open(outfile, encoding="utf-8").read().strip()).ok)
code, out_txt = run_cli(["--verify", outfile])
check("CLI --verify exit 0", code == 0, out_txt)
check("CLI verify says معتبر", "معتبر" in out_txt, out_txt)
code, out_txt = run_cli(["--hw", "ABCDE-FGHIJ-KLMNP-QRSTU", "--name", "دیگری",
                         "--perpetual"])
check("CLI perpetual token ok", code == 0 and lic.verify_token(out_txt.strip()).ok,
      out_txt[:120])
check("CLI perpetual has no expiry",
      lic.verify_token(out_txt.strip()).payload["expires"] is None)
code, out_txt = run_cli(["--hw", "nope", "--name", "x", "--perpetual"])
check("CLI rejects bad hw", code != 0, "%s %s" % (code, out_txt))

# ------------------------------------------------------------------ #
# 12. dialogs construct + render (offscreen-safe)
# ------------------------------------------------------------------ #
from app.ui import license_dialog as LD  # noqa: E402
from app.theme import apply_theme  # noqa: E402
apply_theme(App)

clear_license()
d = LD.ActivationDialog(lic.verify())
labels = [w.text() for w in d.findChildren(Qt.QtWidgets.QLabel)]
edits = [w.text() for w in d.findChildren(Qt.QtWidgets.QLineEdit)]
check("activation shows hw code", hw in edits, str(edits))
check("activation shows reason", any("لایسنس" in t for t in labels))
check("activation has copy button", any(t == "کپی" for t in
                                        [b.text() for b in d.findChildren(
                                            Qt.QtWidgets.QPushButton)]))
check("activation has pick button", any("انتخاب فایل" in b.text()
                                        for b in d.findChildren(
                                            Qt.QtWidgets.QPushButton)))
check("activation RTL", d.layoutDirection() == Qt.QtCore.Qt.RightToLeft)
check("activation not accepted", d.result() == 0)

write_license(token_for(hw, (date.today() + timedelta(days=7)).isoformat()))
d2 = LD.LicenseDetailsDialog(status=lic.verify())
l2 = " | ".join([w.text() for w in d2.findChildren(Qt.QtWidgets.QLabel)] +
                [w.text() for w in d2.findChildren(Qt.QtWidgets.QLineEdit)])
check("details shows customer", "کلینیک تست" in l2, l2[:200])
check("details shows days left", "۷" in l2 and "روز" in l2, l2[:200])
check("details shows code", hw in l2, l2[:200])
check("details badge معتبر", "معتبر" in l2)
check("details jalali date", "۱۴" in l2, l2[:200])
d3 = LD.LicenseDetailsDialog(status=lic.Status(lic.HW_MISMATCH,
                                               lic.make_payload("X", "y",
                                                                date.today().isoformat(),
                                                                None)))
l3 = " | ".join(w.text() for w in d3.findChildren(Qt.QtWidgets.QLabel))
check("details invalid badge", "نامعتبر" in l3, l3[:200])

# ------------------------------------------------------------------ #
# 13. enforcement switch
# ------------------------------------------------------------------ #
os.environ.pop("AZARAN_LICENSE_ENFORCE", None)
check("source build not gated", lic.enforcement_required() is False)
os.environ["AZARAN_LICENSE_ENFORCE"] = "1"
check("env forces gate", lic.enforcement_required() is True)
os.environ.pop("AZARAN_LICENSE_ENFORCE", None)
check("enforce_startup passes when not gated", lic.enforce_startup() is True)

# ------------------------------------------------------------------ #
print("\nlicense probe: %d checks, %d failures" % (PASS[0], len(FAIL)))
for f in FAIL:
    print("  -", f)
sys.stdout.flush()
try:
    import shutil
    shutil.rmtree(TMP, ignore_errors=True)
except Exception:
    pass
sys.exit(1 if FAIL else 0)
