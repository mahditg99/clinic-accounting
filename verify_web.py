# -*- coding: utf-8 -*-
"""Verify the webapp after the auth refactor (login + key pages)."""
import sys
import urllib.request
import urllib.parse
import http.cookiejar

BASE = "http://127.0.0.1:8011"
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

fails = 0


def check(name, cond):
    global fails
    print(("OK   " if cond else "FAIL ") + name)
    if not cond:
        fails += 1


def get(path):
    r = op.open(BASE + path, timeout=15)
    return r.getcode(), r.read().decode("utf-8", "replace")


def login(user, password):
    import urllib.error
    data = urllib.parse.urlencode({"username": user, "password": password})
    req = urllib.request.Request(BASE + "/login", data=data.encode())
    try:
        r = op.open(req, timeout=15)
        return r.getcode(), r.geturl(), r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, BASE + "/login", exc.read().decode("utf-8", "replace")


# 1. unauthenticated dashboard redirects to login
code, body = get("/")
check("unauth /dashboard -> login page", "name=\"password\"" in body or "ورود" in body)

# 2. wrong password rejected
code, url, body = login("admin", "wrongpass")
check("wrong password rejected", "ورود" in body or code != 200)

# 3. correct login succeeds
code, url, body = login("admin", "admin")
check("login admin/admin ok", "/" in url or "داشبورد" in body)

for path in ("/", "/patients", "/invoice/new", "/invoices",
             "/products", "/reports/daily", "/reports/income-expense",
             "/expenses", "/reports/financial", "/reports/doctor",
             "/reports/products", "/doctors", "/settings"):
    try:
        code, body = get(path)
        check("GET %s -> 200" % path, code == 200)
    except Exception as exc:
        check("GET %s (%s)" % (path, exc), False)

# 4. Persian digits present on dashboard (numbers rendered fa)
code, body = get("/")
check("dashboard renders Persian digits", any(ch in body for ch in "۰۱۲۳۴۵۶۷۸۹"))

print("=" * 40)
print("FAILURES: %d" % fails)
sys.exit(1 if fails else 0)
