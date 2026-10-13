#!/usr/bin/env python3
"""Does COPYLIB_PRELOAD_KERNELS make the whole program faster, or only the measured copy? Sweep 3 pairs: <program>_hk_preload_off vs
<program>_hk_base (identical except the preload; host kernel, the only variant whose copies run copylib kernels in these programs).
Per system, implementation and size: median over runs of runtime_sec (wall time of the whole process, measured by the wrapper), of the
measured first-access host-to-device bandwidth (copy_bandwidth) and of buffer_creation_gbps. Writes preload.csv and prints the tables.
Usage: python3 analyze_preload.py"""
import os
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
S3 = os.path.join(os.path.dirname(HERE), "15_sweep3")
COLS = ["application", "N", "runtime_sec", "copy_bandwidth", "d2h_gbps", "buffer_creation_gbps", "check", "machine"]


def load(system, name):
    d = pd.read_csv(os.path.join(S3, system, "results", f"{name}.csv"), usecols=lambda c: c in COLS + ["M"])
    d = d[d.check == "ok"]
    if "M" in d:
        d = d[d.M >= 2]
    return d


def main():
    rows = []
    for program in ("strided", "block"):
        for system in ("gpuc4", "ifi", "lumi"):
            on, off = load(system, f"{program}_hk_base"), load(system, f"{program}_hk_preload_off")
            keys = ["application", "N"] + (["M"] if program == "strided" else [])
            a = on.groupby(keys)[["runtime_sec", "copy_bandwidth", "buffer_creation_gbps"]].median()
            b = off.groupby(keys)[["runtime_sec", "copy_bandwidth", "buffer_creation_gbps"]].median()
            j = a.join(b, lsuffix="_on", rsuffix="_off").reset_index()
            j["program"], j["system"] = program, system
            j["node_on"], j["node_off"] = on.machine.iloc[0], off.machine.iloc[0]
            rows.append(j)
    d = pd.concat(rows, ignore_index=True)
    d["app"] = d.application.str.replace("Celerity-", "")
    d["d_runtime_ms"] = (d.runtime_sec_on - d.runtime_sec_off) * 1000  # < 0: the whole program is faster with preload
    d["bw_ratio"] = d.copy_bandwidth_on / d.copy_bandwidth_off  # > 1: the measured copy is faster with preload
    d["bc_ratio"] = d.buffer_creation_gbps_on / d.buffer_creation_gbps_off
    d.to_csv(os.path.join(HERE, "preload.csv"), index=False)
    gm = lambda x: float(np.exp(np.log(x[x > 0]).mean()))
    small = d[d.N <= (1 << 20)]
    print("Whole program: median change of the process wall time with preload on (ms; negative = faster), all sizes and only <= 1Mi elements")
    print(d.groupby(["program", "system", "app"]).d_runtime_ms.median().unstack("app").round(1).join(
        small.groupby(["program", "system", "app"]).d_runtime_ms.median().unstack("app").round(1), rsuffix=" <=1Mi").to_string())
    print("\nMeasured copy (first access H->D): geomean bandwidth ratio on/off, all sizes and <= 1Mi")
    print(d.groupby(["program", "system", "app"]).bw_ratio.apply(gm).unstack("app").round(2).join(
        small.groupby(["program", "system", "app"]).bw_ratio.apply(gm).unstack("app").round(2), rsuffix=" <=1Mi").to_string())
    print("\nBuffer creation phase: geomean bandwidth ratio on/off (< 1: the preload cost shows up here)")
    print(d.groupby(["program", "system", "app"]).bc_ratio.apply(gm).unstack("app").round(2).to_string())
    print("\nmedian process wall time (s) with preload off, for scale:")
    print(d.groupby(["program", "system", "app"]).runtime_sec_off.median().unstack("app").round(3).to_string())
    print("\nnodes (on/off):", d.groupby("system")[["node_on", "node_off"]].first().to_dict("index"))


if __name__ == "__main__":
    main()
