# -*- coding: utf-8 -*-
import io, re, glob, sys
sys.stdout.reconfigure(encoding="utf-8")
pat = re.compile(r'"(info|success|danger|warning|warn|accent|positive|negative)"')
for f in sorted(glob.glob("app/ui/*_page.py")):
    s = io.open(f, encoding="utf-8").read()
    for m in re.finditer(r"tile_row\(\[(.*?)\]\s*\)", s, re.S):
        print(f, "->", pat.findall(m.group(1)))
    for m in re.finditer(r"sum_card\([^)]*\)", s):
        print(f, "sum:", m.group(0))
    for m in re.finditer(r"badge\(([^)]*)\)", s):
        print(f, "badge:", m.group(1))
