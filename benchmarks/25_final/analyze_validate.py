#!/usr/bin/env python3
"""Validation of the clean build (3dcopylib-final 4f88016) against the final-bench build (f24e5f0), both at their defaults (staging, SDMA off), every
program, same node (one job per program). Prints per system and program: runs, non-ok checks, and the ratio clean / bench of the medians per point
(geometric mean over N >= 2^16, per implementation and direction), plus the worst point. Expectation: equal within noise.
Usage: python3 analyze_validate.py [--v2]   (--v2: final2 81b2cb2 vs final-bench, staging and host kernel pooled per point key incl. variant)"""
import glob
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
gm = lambda x: float(np.exp(np.log(x[x > 0]).mean())) if (x > 0).any() else float("nan")
KEYS = ["application", "N", "M", "W", "variant"]
V2 = "--v2" in sys.argv  # validate2: the clean build final2 (d239713, with host-kernel switch; 81b2cb2 results in validate2_81b2cb2/) vs final-bench
PREFIX, CLEAN = ("validate2", "clean2") if V2 else ("validate", "clean")


def load(system, program, tag):
    f = os.path.join(HERE, system, "results", f"{PREFIX}_{program}_{tag}.csv")
    if not os.path.exists(f):
        return None
    d = pd.read_csv(f)
    for k in ("M", "W"):
        if k not in d:
            d[k] = 0
    d["variant"] = d.env.fillna("").str.contains("HOST_KERNEL=1").map({True: "hk", False: "stg"})
    return d


def main():
    pd.set_option("display.width", 200)
    rows = []
    for system in ("gpuc4", "ifi", "lumi"):
        for program in ("strided", "block", "both", "rows", "device"):
            c, b = load(system, program, CLEAN), load(system, program, "bench")
            if c is None or b is None:
                rows.append((system, program, "missing", "", "", "", "", ""))
                continue
            bad = int((c.check != "ok").sum() + (b.check != "ok").sum())
            out = [system, program, f"{len(c)}+{len(b)}", bad]
            for dr in ("copy_bandwidth", "d2h_gbps"):
                mc = c[c.check == "ok"].groupby(KEYS)[dr].median()
                mb = b[b.check == "ok"].groupby(KEYS)[dr].median()
                r = (mc / mb).dropna()
                r = r[r.index.get_level_values("N") >= 2 ** 16]
                out += [round(gm(r), 3), f"{r.min():.2f}-{r.max():.2f}" if len(r) else ""]
            rows.append(tuple(out))
    t = pd.DataFrame(rows, columns=["system", "program", "runs", "non_ok", "H>D clean/bench", "H>D range", "D>H clean/bench", "D>H range"])
    print(t.to_string(index=False))
    t.to_csv(os.path.join(HERE, f"{PREFIX}_summary.csv"), index=False)


if __name__ == "__main__":
    main()
