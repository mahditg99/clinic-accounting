# -*- coding: utf-8 -*-
"""Print row counts of the dev database (read-only)."""
import sqlite3, os, sys
sys.stdout.reconfigure(encoding="utf-8")
p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "azaran_teb.db")
if not os.path.exists(p):
    print("NO DB at", p); sys.exit(0)
c = sqlite3.connect("file:" + p.replace("\\", "/") + "?mode=ro", uri=True)
for (t,) in c.execute("select name from sqlite_master where type='table' order by name").fetchall():
    try:
        n = c.execute("select count(*) from " + t).fetchone()[0]
    except Exception as e:
        n = "ERR " + str(e)
    print("%-22s %s" % (t, n))
