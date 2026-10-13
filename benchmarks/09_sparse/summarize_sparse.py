import os
import sys

import pandas as pd

# Summarizes the sparse and both-strided runs (09_sparse/results/<system>_{sparse,both}.csv): median GB/s per M at the largest N for
# staging and the host kernel, and staging / host kernel. Usage: python 09_sparse/summarize_sparse.py <system> [<system> ...]
HERE = os.path.dirname(os.path.abspath(__file__))
pd.set_option("display.width", 250)

for system in sys.argv[1:]:
    for kind in ("sparse", "both"):
        f = os.path.join(HERE, "results", f"{system}_{kind}.csv")
        if not os.path.exists(f):
            continue
        d = pd.read_csv(f)
        fix = os.path.join(HERE, "results", f"{system}_{kind}_dpcpp64.csv")  # rerun of the crashed DPC++ M = 64 runs
        if os.path.exists(fix):
            d = pd.concat([d[~((d.application == "Celerity-dpcpp") & (d.M == 64) & (d.N >= 2 ** 22))], pd.read_csv(fix)], ignore_index=True)
        bad = (d.check != "ok").sum()
        d = d[d.check == "ok"]
        d["mode"] = d.env.str.contains("HOST_KERNEL").map({True: "host kernel", False: "staging"})
        big = d[d.N == d.N.max()]
        t = big.groupby(["application", "M", "mode"])[["copy_bandwidth", "d2h_gbps"]].median().unstack("mode")
        out = pd.DataFrame({
            ("h2d", "staging"): t[("copy_bandwidth", "staging")], ("h2d", "host kernel"): t[("copy_bandwidth", "host kernel")],
            ("h2d", "staging/hk"): t[("copy_bandwidth", "staging")] / t[("copy_bandwidth", "host kernel")],
            ("d2h", "staging"): t[("d2h_gbps", "staging")], ("d2h", "host kernel"): t[("d2h_gbps", "host kernel")],
            ("d2h", "staging/hk"): t[("d2h_gbps", "staging")] / t[("d2h_gbps", "host kernel")],
        })
        print(f"\n=== {system} {kind}: {len(d)} rows ok, {bad} not ok; median GB/s at N = {d.N.max()} ({d.N.max() * 4 >> 20} MiB useful)")
        print(out.round(3).to_string())
