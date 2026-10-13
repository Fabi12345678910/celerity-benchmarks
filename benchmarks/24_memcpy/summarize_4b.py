#!/usr/bin/env python3
"""Medians of the 4 B memcpy runs (memcpy_4b.csv) per program and copylib setting. Usage: python3 summarize_4b.py <system>..."""
import csv
import statistics as st
import sys
from collections import defaultdict

for system in sys.argv[1:]:
    rows = list(csv.DictReader(open(f"{system}/results/memcpy_4b.csv")))
    print(f"== {system}: {len(rows)} runs, checks {sorted(set(r['check'] for r in rows))}, nodes {sorted(set(r['machine'] for r in rows))}")
    groups = defaultdict(list)
    for r in rows:
        groups[(r["application"], "off" if "COPYLIB=off" in r["env"] else "on")].append(r)
    for (app, copylib), v in groups.items():
        med = lambda c: st.median(float(r[c]) for r in v)
        line = f"{app:15} copylib {copylib:3} H2D {med('h2d_us'):6.1f} us  D2H {med('d2h_us'):6.1f} us"
        if v[0].get("h2d_tasks_us"):
            line += f"  | task pair with copy {med('h2d_tasks_us'):5.1f} / {med('d2h_tasks_us'):5.1f}, without {med('h2d_base_us'):5.1f} / {med('d2h_base_us'):5.1f}"
        print(line)
