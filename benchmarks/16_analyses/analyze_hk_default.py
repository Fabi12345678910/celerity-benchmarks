#!/usr/bin/env python3
"""Could the host kernel (COPYLIB_HOST_KERNEL=1) be the default instead of staging? Both variants at the build's defaults (2dda28f):
  15_sweep3  strided_transfer (4-byte rows, pitch 8 / 16 B, M = 2, 4), <program>_hk_defaults vs <program>_stg_defaults, 3 runs;
             block_transfer with ROUTE=all (contiguous; note the default build does not route contiguous copies to copylib at all)
  14_verify  strided_transfer, strided_rows_transfer (4 / 32 / 128-byte rows, pitch 256 B), strided_both_transfer (host and device
             strided): hk_new vs staging_new, 5 runs
Ratio = host kernel / staging bandwidth (> 1: the host kernel is faster), per system, implementation, direction, program and size class
(useful bytes per copy). Also counts correctness checks of every host-kernel run. Writes hk_default.csv; prints the tables.
Usage: python3 analyze_hk_default.py"""
import glob
import os
import sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
B = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(B, "14_verify"))
from analyze_verify import load as load_verify  # noqa: E402

DIRS = {"copy_bandwidth": "h2d", "d2h_gbps": "d2h"}
gm = lambda x: float(np.exp(np.log(x[x > 0]).mean()))


def sweep3(program):
    out = []
    for s in ("gpuc4", "ifi", "lumi"):
        for v in ("hk", "stg"):
            d = pd.read_csv(os.path.join(B, "15_sweep3", s, "results", f"{program}_{v}_defaults.csv"))
            d = d[d.check == "ok"]
            if program == "strided":
                d = d[d.M >= 2]
                d["shape"] = "transfer M" + d.M.astype(str)
            else:
                d["shape"], d["M"] = "block (ROUTE=all)", 0
            d["system"], d["variant"], d["source"] = s, v, "sweep3"
            d["bytes"] = d.N * 4
            out.append(d)
    return pd.concat(out)


def verify():
    d = load_verify(["gpuc4", "ifi", "lumi"])
    d = d[d.config.isin(["hk_new", "staging_new"])].copy()
    d["variant"] = np.where(d.config == "hk_new", "hk", "stg")
    d["source"] = "verify"
    return d


def ratios(d):
    d = d.copy()
    d["app"] = d.application.str.replace("Celerity-", "")
    long = d.melt(id_vars=["source", "system", "app", "shape", "N", "bytes", "variant"], value_vars=list(DIRS), var_name="dir", value_name="gbps")
    long["dir"] = long["dir"].map(DIRS)
    med = long[long.gbps > 0].groupby(["source", "system", "app", "shape", "N", "bytes", "dir", "variant"]).gbps.median().unstack("variant").dropna()
    med["ratio"] = med.hk / med.stg
    r = med.reset_index()
    r["size"] = pd.cut(r.bytes, [0, 4 << 20, 128 << 20, 1 << 40], labels=["<=4MiB", "<=128MiB", ">128MiB"])
    return r


def main():
    raw = pd.concat([sweep3("strided"), sweep3("block"), verify()], ignore_index=True)
    hk = raw[raw.variant == "hk"]
    print(f"host-kernel runs: {len(hk)}, correctness check not ok: {int((hk.check != 'ok').sum())}")
    r = ratios(raw)
    r.to_csv(os.path.join(HERE, "hk_default.csv"), index=False)
    pd.set_option("display.width", 220)
    r["prog"] = r["shape"].str.extract(r"^(\w+)")[0].replace({"transfer": "strided 4B", "rows": "rows", "both": "both strided", "block": "block"})
    r.loc[r["shape"].str.startswith("rows"), "prog"] = "rows " + r["shape"].str.extract(r"W(\d+)")[0].map({"1": "4B", "8": "32B", "32": "128B"})
    t = r.groupby(["system", "dir", "app", "prog"]).ratio.agg(gm=gm, worst="min", best="max", n="size",
                                                             below_09=lambda x: float((x < 0.9).mean()))
    print("\nhost kernel / staging at the defaults (geomean over sizes and shapes; below_09 = share of points where hk is >10% slower)")
    print(t.round(2).to_string())
    print("\nby size class (all programs):")
    print(r.groupby(["system", "dir", "size"], observed=True).ratio.apply(gm).unstack("size").round(2).to_string())
    print("\nwhere the host kernel loses most (median over implementations):")
    w = r.groupby(["system", "dir", "prog", "size"], observed=True).ratio.median().reset_index()
    print(w.nsmallest(12, "ratio").round(2).to_string(index=False))


if __name__ == "__main__":
    main()
