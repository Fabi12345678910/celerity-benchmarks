#!/usr/bin/env python3
"""Preload study (make_preload_yamls.py): COPYLIB_PRELOAD_KERNELS 1 vs 0, same node, back to back. Per system/node, SYCL implementation, variant
(staging / host kernel), M and N: median over the runs of the process wall time (runtime_sec), the measured first-access copy bandwidth and the
buffer-creation bandwidth, with the preload on and off. Writes preload.csv and prints the tables.
  d_ms   = median wall time on - off (ms; negative: the whole program is faster with the preload)
  sd_off_ms = standard deviation of the wall time with the preload off (noise scale for d_ms)
  d_pct  = the same relative to off
  copy_x = copy_bandwidth on / off (> 1: the measured copy is faster with the preload)
Usage: python3 analyze_preload.py"""
import glob
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
COLS = ["application", "N", "M", "env", "runtime_sec", "copy_bandwidth", "buffer_creation_gbps", "check", "machine", "config"]


def load():
    frames = []
    for f in sorted(glob.glob(os.path.join(HERE, "*", "results", "preload*.csv"))):
        d = pd.read_csv(f, usecols=lambda c: c in COLS)
        d["system"] = f.split(os.sep)[-3]
        frames.append(d[d.check == "ok"])
    d = pd.concat(frames, ignore_index=True)
    d["variant"] = np.where(d.env.str.contains("COPYLIB_HOST_KERNEL=1"), "hk", "stg")
    d["preload"] = np.where(d.env.str.contains("PRELOAD_KERNELS=1"), "on", "off")
    d["app"] = d.application.str.replace("Celerity-", "")
    return d


def main():
    d = load()
    keys = ["system", "machine", "app", "variant", "M", "N"]
    g = d.groupby(keys + ["preload"])[["runtime_sec", "copy_bandwidth", "buffer_creation_gbps"]].median().unstack("preload")
    g.columns = [f"{a}_{b}" for a, b in g.columns]
    g = g.reset_index()
    sd = d[d.preload == "off"].groupby(keys).runtime_sec.std().rename("sd_off_ms").reset_index()
    sd["sd_off_ms"] *= 1000
    g = g.merge(sd, on=keys)
    g["d_ms"] = (g.runtime_sec_on - g.runtime_sec_off) * 1000
    g["d_pct"] = (g.runtime_sec_on / g.runtime_sec_off - 1) * 100
    g["copy_x"] = g.copy_bandwidth_on / g.copy_bandwidth_off
    g["bc_x"] = g.buffer_creation_gbps_on / g.buffer_creation_gbps_off
    g.to_csv(os.path.join(HERE, "preload.csv"), index=False)
    gm = lambda x: float(np.exp(np.log(x[x > 0]).mean()))
    pd.set_option("display.width", 200)
    print("Whole process wall time, on minus off (ms, median over the sizes; negative = faster with preload)")
    print(g.groupby(["system", "machine", "variant", "M", "app"]).d_ms.median().unstack("app").round(1).to_string())
    print("\nWall time off, for scale (s, median over the sizes)")
    print(g.groupby(["system", "machine", "variant", "M", "app"]).runtime_sec_off.median().unstack("app").round(3).to_string())
    print("\nRun-to-run noise: standard deviation of the wall time with preload off (ms, median over the sizes)")
    print(g.groupby(["system", "machine", "variant", "M", "app"]).sd_off_ms.median().unstack("app").round(1).to_string())
    print("\nMeasured first-access copy, bandwidth on/off (geomean over the sizes; M = 2 only)")
    print(g[g.M == 2].groupby(["system", "machine", "variant", "app"]).copy_x.apply(gm).unstack("app").round(2).to_string())
    print("\nBuffer-creation phase, bandwidth on/off (geomean; < 1: the preload cost shows up here)")
    print(g.groupby(["system", "machine", "variant", "M", "app"]).bc_x.apply(gm).unstack("app").round(2).to_string())
    print("\nWall time on minus off by size (ms, DPC++ and acpp, M = 2)")
    print(g[g.M == 2].pivot_table(index=["system", "machine", "variant", "app"], columns="N", values="d_ms").round(1).to_string())


if __name__ == "__main__":
    main()
