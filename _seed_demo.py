# -*- coding: utf-8 -*-
"""Seed a large realistic demo dataset into the dev DB (real %APPDATA% DB).

Adds ~8 doctors, 250 patients, 60 products, 600 invoices (items + payments)
and 250 expenses spread over the last 13 Jalali months so scrolling,
filtering, sorting and the reports can be exercised with real volume.

Idempotent: a `demo_seeded` settings marker prevents double-seeding.
Run:  & "C:\\Program Files\\Python38\\python.exe" -u _seed_demo.py
"""
import os
import random
import sys
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from app.database import init_db, get_connection as _conn  # noqa: E402
from app import models, settings as settings_mod, date_utils  # noqa: E402

init_db()

conn = _conn()
row = conn.execute("SELECT value FROM settings WHERE key = 'demo_seeded'").fetchone()
conn.close()
if row is not None:
    print("SKIP: demo data already seeded (settings.demo_seeded=%s)" % row[0])
    sys.exit(0)

random.seed(1405)

MALE = ["علی", "محمد", "حسین", "رضا", "امیر", "مهدی", "احمد", "سعید",
        "مجتبی", "ابوالفضل", "عرفان", "پویا", "کیان", "آرمان", "بهرام",
        "فرهاد", "مهران", "نوید", "سامان", "یاسر", "حسام", "دانیال"]
FEMALE = ["فاطمه", "زهرا", "مریم", "سارا", "الهه", "نرگس", "المیرا", "رها",
          "آیدا", "مهسا", "سمیرا", "یلدا", "بهار", "ترانه", "دنیا", "آتوسا",
          "پریناز", "نگار", "شیدا", "لیلا", "المیرا", "پریسا", "روشا"]
LAST = ["محمدی", "حسینی", "احمدی", "کریمی", "موسوی", "جعفری", "صادقی",
        "رضایی", "طاهری", "امینی", "رحیمی", "نوری", "قاسمی", "شریفی",
        "بهرامی", "فرهادی", "حق‌دوست", "اسدی", "کاظمی", "یوسفی", "هاشمی",
        "اکبری", "رستمی", "زارع", "عابدی", "ملایی", "دهقان", "مکودی",
        "آذرمهر", "فرهمند", "صبری", "چمن‌آرا", "گیلانی", "مازندرانی"]
CITY = ["تهران، خیابان ولیعصر", "تهران، میدان ونک", "اصفهان، خیابان آمادگاه",
        "اصفهان، جوباره", "شیراز، خیابان زند", "تبریز، خیابان آذر",
        "کرج، مهرشهر", "قم، خیابان ارم", "رشت، خیابان گلسان",
        "مشهد، وکیل‌آباد"]

DOCTORS = [
    ("نگار", "صبری", "داخلی و قلب", "تهران، خیابان ولیعصر، مجتمع آرش، طبقه ۳"),
    ("کامران", "دهقان", "عمومی", "تهران، میدان ونک، برج نگین، واحد ۲۱"),
    ("شیرین", "آذرمهر", "زنان و زایمان", "اصفهان، خیابان آمادگاه، کلینیک مهر، طبقه ۲"),
    ("بابک", "شریفی", "ارتوپدی", "شیراز، خیابان زند، مجتمع پزشکان، واحد ۵"),
    ("مینا", "فرهمند", "اطفال", "تبریز، خیابان آذر، کلینیک سلامت، طبقه همکف"),
    ("هوشنگ", "زارع", "چشم‌پزشکی", "کرج، مهرشهر، بلک ۱۴، پلاک ۳۲"),
    ("رویا", "مکودی", "پوست و مو", "قم، خیابان ارم، مجتمع کوثر، واحد ۹"),
    ("فریدون", "عابدی", "غدد و متابولیسم", "مشهد، وکیل‌آباد، کلینیک رضوی، طبقه ۴"),
]

# title, purchase, sale, stock, low_warning, description
PRODUCTS = [
    ("ست سرم نمکی ۱۰۰۰ سی‌سی", 42000, 65000, 1200, 100, "سرم رینگر نرمال"),
    ("ست سرم ۵۰۰ سی‌سی", 28000, 45000, 900, 80, ""),
    ("آنژیوکت ۲۲", 9000, 16000, 2500, 200, "نارگان"),
    ("آنژیوکت ۲۰", 9000, 16000, 1800, 200, ""),
    ("سرنگ ۵ سی‌سی", 4500, 9000, 3000, 300, ""),
    ("سرنگ ۱۰ سی‌سی", 7000, 13000, 2200, 250, ""),
    ("سوزن انسولین ۳۱G", 12000, 22000, 1500, 150, "بسته ۱۰۰ عددی"),
    ("الکل طبی ۲۵۰ سی‌سی", 18000, 32000, 800, 100, ""),
    ("بتادین ۱۲۰ سی‌سی", 22000, 38000, 650, 80, ""),
    ("چسب زخم نواری", 8000, 15000, 1400, 150, ""),
    ("گاز استریل ۱۰×۱۰", 15000, 27000, 1100, 120, "بسته ۵۰ برگی"),
    ("دستکش لاتکس جفت", 6000, 11000, 4000, 400, "بدون پودر"),
    ("ماسک جراحی بسته ۵۰ عددی", 65000, 98000, 400, 50, ""),
    ("ژل ضدعفونی دست ۲۵۰ سی‌سی", 48000, 75000, 350, 40, ""),
    ("دماسنج دیجیتال", 180000, 290000, 120, 15, ""),
    ("فشارسنج زنبوری", 620000, 950000, 60, 10, ""),
    ("قندسنج خانگی", 1450000, 2100000, 35, 5, ""),
    ("نوار قند ۵۰ عددی", 320000, 490000, 220, 25, ""),
    ("ولتارن ۷۵ آمپول", 14000, 25000, 900, 100, "دیکلوفناک"),
    ("دگزامتازون ۸ آمپول", 9000, 17000, 750, 90, ""),
    ("آمپول پروژسترون", 26000, 42000, 400, 50, ""),
    ("استامینوفن ۳۲۵ قرص", 11000, 19000, 1600, 200, "بسته ۲۰ عددی"),
    ("ایبوپروفن ۴۰۰", 16000, 27000, 1200, 150, ""),
    ("آموکسی‌سیلین ۵۰۰", 24000, 39000, 1000, 120, ""),
    ("آزیترومایسین ۵۰۰", 46000, 72000, 600, 70, ""),
    ("امپرازول ۴۰", 21000, 35000, 900, 100, ""),
    ("متفورمین ۵۰۰", 18000, 30000, 1100, 120, ""),
    ("لوزارتان ۵۰", 27000, 44000, 800, 90, ""),
    ("آتورواستاتین ۲۰", 33000, 54000, 700, 80, ""),
    ("لووتیروکسین ۵۰", 29000, 47000, 650, 70, ""),
    ("فروکسیتین ۲۰", 52000, 82000, 400, 50, ""),
    ("سرآسیب ۲۱G", 3500, 7000, 3500, 400, ""),
    ("پنبه و الکل پد", 12000, 21000, 1300, 150, ""),
    ("سرم قند ۵٪", 38000, 58000, 700, 80, ""),
    ("مانیتول ۲۰٪", 95000, 145000, 260, 30, ""),
    ("آمپول متیل‌پردنیزولون", 31000, 49000, 480, 60, ""),
    ("ویال رانیتیدین", 17000, 28000, 520, 60, ""),
    ("سوزن بخیه ۲/۰", 24000, 40000, 340, 40, ""),
    ("نخ جراحی سیلک", 42000, 68000, 280, 30, ""),
    ("اسپری سرد (اسپری ضربه)", 88000, 135000, 190, 25, ""),
    ("باند کشی ۱۰ سانتی", 26000, 43000, 430, 50, ""),
    ("واترپیک ۲ لیتری", 130000, 205000, 90, 10, ""),
    ("ساعت شنی ۵ دقیقه", 45000, 75000, 60, 8, ""),
    ("پد الکلی بسته ۱۰۰ عددی", 21000, 34000, 560, 60, ""),
    ("دستبند شناسایی بیمار", 6500, 12000, 1500, 200, ""),
    ("مقنعه یکبار مصرف", 9000, 16000, 1250, 150, ""),
    ("روشنی مطب یکبار مصرف", 14000, 24000, 950, 100, ""),
    ("ژل سونوگرافی ۵ لیتری", 210000, 320000, 70, 8, ""),
    ("الکتروکاردیوگراف کاغذ", 95000, 150000, 140, 15, ""),
    ("نوار قلب حرارتی", 78000, 122000, 160, 20, ""),
    ("ویزیت متخصص", 0, 350000, 9999, 0, "خدمات درمانی"),
    ("ویزیت عمومی", 0, 180000, 9999, 0, "خدمات درمانی"),
    ("تزریقات عضلانی", 0, 90000, 9999, 0, "خدمات درمانی"),
    ("سرم‌درمانی", 0, 220000, 9999, 0, "خدمات درمانی"),
    ("پانسمان ساده", 0, 160000, 9999, 0, "خدمات درمانی"),
    ("بخیه زخم", 0, 420000, 9999, 0, "خدمات درمانی"),
    ("نوار قلب (ECG)", 0, 280000, 9999, 0, "خدمات تشخیصی"),
    ("اسپیرومتری", 0, 380000, 9999, 0, "خدمات تشخیصی"),
    ("تست بارداری", 0, 140000, 9999, 0, ""),
    ("مشاوره تغذیه", 0, 250000, 9999, 0, ""),
]

# a few deliberately low-stock items for the dashboard warnings
LOW_STOCK = [
    ("آمپول آگمرا ۱۰ عددی", 240000, 360000, 4, 10, "موجودی رو به اتمام"),
    ("کیت آنفولانزا", 180000, 280000, 3, 8, ""),
    ("فیلر ۱ سی‌سی", 2400000, 3600000, 2, 5, ""),
    ("بوتاکس ۵۰ واحدی", 1900000, 2800000, 6, 10, ""),
    ("نوار تست هپاتیت", 95000, 150000, 1, 6, ""),
    ("سرم دگسته", 52000, 79000, 7, 15, ""),
]

EXPENSE_TPL = [
    ("حقوق", (70000000, 130000000), ["حقوق کادر درمان", "حقوق منشی و پذیرش",
                                     "پاداش عملکرد پرسنل"]),
    ("اجاره", (28000000, 55000000), ["اجاره شعبه مرکزی", "اجاره مطب فرعی"]),
    ("خرید تجهیزات", (12000000, 240000000),
     ["خرید دستگاه اکسیژن‌سنج", "تجهیزات مطب", "خرید تخت معاینه",
      "سیستم کامپیوتر پذیرش"]),
    ("قبوض", (1800000, 9500000), ["قبض برق", "قبض گاز", "قبض تلفن و اینترنت",
                                  "حق آب"]),
    ("متفرقه", (400000, 6500000), ["خرید ملزومات", "تعمید آسانسور",
                                    "پذیرایی بیماران", "شارژ دستگاه کارتخوان",
                                    "هزینه تبلیغات و چاپ بنر"]),
]

METHODS = ["پوز", "نقد", "انتقال", "چک"]
NOTES = ["", "", "", "", "بسته به پیگیری", "نسخه ارسال شد",
         "بیمار سرپایی", "نوبت فوق‌العاده", "تخفیف پزشک اعمال شد"]


def jdate_range(n_days):
    """Random ISO datetime string within the last n_days (weighted recent)."""
    today = datetime.strptime(date_utils.today_iso(), "%Y-%m-%d")
    # bias toward recent months: square the fraction
    frac = random.random() ** 1.6
    d = today - timedelta(days=int(frac * n_days))
    d = d.replace(hour=random.randint(8, 20), minute=random.choice(
        [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55]),
        second=random.randint(0, 59))
    return d.strftime("%Y-%m-%d %H:%M:%S")


print("Seeding demo data (this takes a few seconds)...")

# ---- doctors ------------------------------------------------------------- #
doc_ids = []
for first, last, spec, addr in DOCTORS:
    name = "%s %s" % (first, last)
    phone = "0%d" % random.randint(3100000000, 3999999999)
    did = settings_mod.add_doctor(name, spec, addr, phone, first, last)
    doc_ids.append(int(did))
print("doctors: +%d" % len(doc_ids))

# ---- patients ------------------------------------------------------------ #
conn = _conn()
mx = conn.execute("SELECT MAX(CAST(file_no AS INTEGER)) FROM patients").fetchone()[0]
conn.close()
file_no = int(mx or 1000) + 1
patient_ids = []
for i in range(250):
    female = random.random() < 0.55
    first = random.choice(FEMALE if female else MALE)
    last = random.choice(LAST)
    gender = "female" if female else "male"
    phone = "09%d" % random.randint(100000000, 999999999)
    addr = "%s، پلاک %d، واحد %d" % (random.choice(CITY),
                                     random.randint(1, 90),
                                     random.randint(1, 20))
    pid = models.create_patient(str(file_no), first, last, gender, phone, addr)
    patient_ids.append(int(pid))
    file_no += 1
# a handful of archived (inactive) patients
for pid in random.sample(patient_ids, 12):
    models.deactivate_patient(pid)
print("patients: +250 (12 inactive)")

# ---- products ------------------------------------------------------------ #
prod_ids = []
for title, pp, sp, stock, low, desc in PRODUCTS + LOW_STOCK:
    pid = models.add_product(title, pp, sp, stock, low, desc)
    prod_ids.append(int(pid))
sellable = [p for p in prod_ids if p not in prod_ids[-6:]]  # skip low-stock
print("products: +%d (%d sellable)" % (len(prod_ids), len(sellable)))

# ---- invoices ------------------------------------------------------------ #
conn = _conn()
prod_rows = conn.execute(
    "SELECT id, title, sale_price, purchase_price FROM products "
    "WHERE id IN (%s)" % ",".join("?" * len(sellable)), sellable).fetchall()
conn.close()

n_inv = 0
for i in range(600):
    pid = random.choice(patient_ids)
    did = random.choice(doc_ids) if random.random() < 0.72 else None
    issued = jdate_range(400)
    k = random.choices([1, 2, 3, 4], weights=[38, 32, 20, 10])[0]
    items = []
    for row in random.sample(prod_rows, k):
        qty = random.randint(1, 6) if row[3] > 0 else random.randint(1, 2)
        items.append({"product_id": row[0], "title": row[1],
                      "unit_price": int(row[2]), "quantity": qty,
                      "row_total": int(row[2]) * qty})
    total = sum(it["row_total"] for it in items)
    payments = []
    roll = random.random()
    if roll < 0.62:
        payments = [{"method": random.choice(METHODS), "amount": total,
                     "paid_at": issued}]
    elif roll < 0.86:
        a = int(total * random.uniform(0.35, 0.85))
        b = total - a
        payments = [{"method": random.choice(METHODS), "amount": a,
                     "paid_at": issued},
                    {"method": random.choice(METHODS), "amount": b,
                     "paid_at": issued}]
    try:
        models.save_invoice(pid, did, issued, items, payments,
                            random.choice(NOTES))
        n_inv += 1
    except ValueError as exc:
        print("  invoice skipped:", exc)
print("invoices: +%d" % n_inv)

# ---- expenses ------------------------------------------------------------ #
n_exp = 0
for i in range(250):
    cat, (lo, hi), descs = random.choice(EXPENSE_TPL)
    amount = int(random.uniform(lo, hi) / 100000) * 100000
    iso = jdate_range(400).split(" ")[0]
    models.add_expense(amount, random.choice(descs), iso, cat)
    n_exp += 1
print("expenses: +%d" % n_exp)

conn = _conn()
conn.execute("INSERT OR REPLACE INTO settings(key, value) VALUES "
             "('demo_seeded', ?)", (date_utils.now_iso(),))
conn.commit()
conn.close()
print("DONE")
