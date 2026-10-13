import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plot_cores import load  # noqa: E402

# Summarizes the worker/core sweep per system: completeness, median GB/s over the worker count at 1 GiB (fixed and dynamic), the best
# configuration per direction and M against the host kernel and the base so far, dynamic / fixed, and the 4-worker placements.
# Usage: python 06_cores/summarize_cores.py <system> [<system> ...]
pd.set_option("display.width", 250)
DIRS = {"copy_bandwidth": "h2d", "d2h_gbps": "d2h"}

for system in sys.argv[1:]:
    d = load(system)
    print(f"\n######## {system}: {d.cfg.nunique()} configurations, {len(d)} rows with Check: ok")
    expected = d.groupby("cfg").size()
    if expected.nunique() > 1:
        print("rows per configuration differ:", expected[expected != expected.max()].to_dict())
    big = d[d.N == d.N.max()]
    med = big.groupby(["cfg", "application", "M"])[list(DIRS)].median()

    w = big[big.workers.notna()]
    t = w.groupby(["application", "M", "order", "workers"])[list(DIRS)].median().unstack("workers").round(2)
    print("\nmedian GB/s at 1 GiB over the worker count (columns), fixed = block")
    print(t.rename(columns=DIRS).to_string())

    print("\nbest per direction and M at 1 GiB, against the host kernel and the base so far")
    for app in sorted(d.application.unique()):
        for m in (2, 4):
            for metric, short in DIRS.items():
                x = med.xs((app, m), level=("application", "M"))[metric]
                cands = x[[c for c in x.index if not c.startswith("reference")]]
                best = cands.idxmax()
                hk, base = x.get("reference_host_kernel"), x.get("reference_base")
                print(f"  {app:15s} M={m} {short}: best {best:20s} {cands.max():6.2f} GB/s | host kernel {hk:6.2f} "
                      f"({cands.max() / hk:4.2f}x) | base so far {base:6.2f} ({cands.max() / base:4.2f}x)")

    dyn = w.groupby(["application", "M", "order", "workers"])[list(DIRS)].median()
    ratio = (dyn.xs("dynamic", level="order") / dyn.xs("block", level="order")).unstack("workers").round(2)
    print("\ndynamic / fixed at 1 GiB over the worker count")
    print(ratio.rename(columns=DIRS).to_string())

    near = med.loc[["workers_04_block", "workers_04_dynamic"]]
    place = med.loc[[c for c in med.index.get_level_values(0).unique() if c.startswith("place_")]]
    print("\n4-worker placements at 1 GiB, GB/s (near = workers_04)")
    print(pd.concat([near, place]).unstack(["application", "M"]).round(2).rename(columns=DIRS).to_string())
