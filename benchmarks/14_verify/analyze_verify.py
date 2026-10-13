#!/usr/bin/env python3
# Verification of the new defaults: every config relative to the old defaults of its variant (staging_old / hk_old), same system,
# implementation, program, shape, N and direction; median of the 5 runs per point. Usage: analyze_verify.py [system ...]
import glob, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
gm = lambda x: float(np.exp(np.log(x).mean()))


def load(systems):
    frames = []
    for s in systems:
        for f in sorted(glob.glob(os.path.join(HERE, "results", f"{s}_*.csv"))):
            d = pd.read_csv(f)
            d["system"] = s
            frames.append(d)
    d = pd.concat(frames, ignore_index=True)
    for c in ["M", "W"]:
        if c not in d:
            d[c] = np.nan
    d["impl"] = d.application.str.replace("Celerity-", "")
    d["shape"] = np.select([d.program == "strided_transfer", d.program == "strided_rows_transfer"],
                           ["transfer M" + d.M.fillna(0).astype(int).astype(str), "rows W" + d.W.fillna(0).astype(int).astype(str)],
                           "both M" + d.M.fillna(0).astype(int).astype(str))
    width = np.where(d.program == "strided_rows_transfer", d.W.fillna(1) * 4, 4)
    d["bytes"] = (d.N * width).astype(np.int64)
    return d


def ratios(d):
    long = d.melt(id_vars=["system", "impl", "program", "shape", "N", "bytes", "variant", "config"], value_vars=["copy_bandwidth", "d2h_gbps"],
                  var_name="dir", value_name="gbps")
    long["dir"] = long["dir"].map({"copy_bandwidth": "h2d", "d2h_gbps": "d2h"})
    key = ["system", "impl", "program", "shape", "N", "bytes", "variant", "dir"]
    med = long.groupby(key + ["config"]).gbps.median().reset_index()
    old = med[med.config.str.endswith("_old")].drop(columns="config").rename(columns={"gbps": "old"})
    m = med.merge(old, on=key)
    m["ratio"] = m.gbps / m.old
    m["size"] = pd.cut(m.bytes, [0, 4 << 20, 128 << 20, 1 << 40], labels=["≤4M", "≤128M", ">128M"])
    return m


def main():
    systems = sys.argv[1:] or ["gpuc4", "ifi", "lumi"]
    d = load(systems)
    print("runs:", len(d), " not ok:", int((d.check != "ok").sum()), d[d.check != "ok"].groupby(["system", "config"]).size().to_dict())
    m = ratios(d[d.check == "ok"])
    pd.set_option("display.width", 250)
    for variant in ["staging", "host kernel"]:
        v = m[(m.variant == variant) & ~m.config.str.endswith("_old")]
        print(f"\n=== {variant}: bandwidth relative to the old defaults (geomean over shapes and N)")
        t = v.groupby(["config", "system", "impl", "dir"]).ratio.apply(gm).unstack(["dir"]).unstack("impl")
        t.columns = [f"{a}_{b}" for a, b in t.columns]
        print(t.round(2).to_string())
        print("by program and size (all systems, both implementations):")
        print(v.groupby(["config", "program", "dir", "size"], observed=True).ratio.apply(gm).unstack(["dir", "size"]).round(2).to_string())
        print("worst / best point:", v.groupby("config").ratio.agg(["min", "max"]).round(2).to_dict("index"))


if __name__ == "__main__":
    main()
