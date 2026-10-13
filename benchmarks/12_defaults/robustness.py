import glob
import os
import sys

import numpy as np
import pandas as pd

# How far the defaults sweep (sweep 2) can be trusted, and which method wins once the proposed defaults are in place.
#   noise        run-to-run coefficient of variation at the largest size, per system, implementation and direction (median, 90th pct)
#   collapses    share of single runs below half the median of their configuration (same system, implementation, config, shape, N)
#   ifi_base     ifi host kernel, device -> host at the largest size: the base vs. the options that should be neutral, per shape
#                (the base ran on gc24 and came out 3-20% above them, so most options look worse there than they are)
#   winners      staging (the worker-sweep config) vs. the host kernel with the proposed COPYLIB_MAX_ELEM_SIZE=8 (32/128 B rows; 4 B rows
#                are unaffected), large copies, the same metric as analyze_defaults.py (ratios_<app>.csv must exist)
# Writes 12_defaults/results/winners_<app>.csv. Usage: python 12_defaults/robustness.py [--app acpp|dpcpp]

HERE = os.path.dirname(os.path.abspath(__file__))
SYSTEMS = ["gpuc4", "ifi", "lumi"]
NEUTRAL_EXCLUDE = "max_elem|256KiB|1MiB|elems"  # options with a real effect; the rest are within noise elsewhere


def load():
    frames = []
    for s in SYSTEMS:
        for f in glob.glob(os.path.join(HERE, s, "results", "*.csv")):
            d = pd.read_csv(f)
            d["system"] = s
            frames.append(d)
    d = pd.concat(frames, ignore_index=True)
    d = d.loc[:, ~d.columns.str.contains(r"\.\d+$")]
    d["app"] = d.application.str.replace("Celerity-", "")
    d["shape"] = np.where(d.program == "strided_transfer", "4 B rows, pitch " + (d.M * 4).astype(str) + " B",
                          (d.W * 4).astype(str) + " B rows, pitch 256 B")
    return d[d.check == "ok"]


def main():
    app = sys.argv[sys.argv.index("--app") + 1] if "--app" in sys.argv else "acpp"
    pd.set_option("display.width", 220)
    d = load()

    big = d[d.N == d.groupby("program").N.transform("max")]
    g = big.groupby(["system", "app", "config", "shape"])
    cv = pd.DataFrame({"h2d": g.copy_bandwidth.std() / g.copy_bandwidth.mean(), "d2h": g.d2h_gbps.std() / g.d2h_gbps.mean()}).reset_index()
    print("=== noise: run-to-run CV at the largest size (median / 90th percentile over configs and shapes)")
    print(cv.groupby(["system", "app"])[["h2d", "d2h"]].quantile([0.5, 0.9]).unstack().round(3).to_string())

    keys = ["system", "app", "config", "shape", "N"]
    for col, name in (("copy_bandwidth", "h2d"), ("d2h_gbps", "d2h")):
        d[f"collapse_{name}"] = d[col] < 0.5 * d.groupby(keys)[col].transform("median")
    print("\n=== collapses: % of single runs below half their configuration's median")
    print(d.groupby(["system", "app"])[["collapse_h2d", "collapse_d2h"]].mean().mul(100).round(2).to_string())

    x = big[(big.system == "ifi") & (big.app == "acpp") & (big.variant == "host kernel")]
    base = x[x.config == "hk_base"].groupby("shape").d2h_gbps.median()
    neutral = x[(x.config != "hk_base") & ~x.config.str.contains(NEUTRAL_EXCLUDE)].groupby("shape").d2h_gbps.median()
    print("\n=== ifi_base: host kernel device -> host GB/s at the largest size (acpp)")
    print(pd.DataFrame({"hk_base (gc24)": base, "neutral options (median)": neutral, "base / neutral": base / neutral}).round(2).to_string())

    r = pd.read_csv(os.path.join(HERE, "results", f"ratios_{app}.csv"))
    pick = lambda c: r[r.config == c].set_index(["system", "direction", "shape"]).gbps
    t = pd.DataFrame({"staging": pick("staging_base"), "hk_today": pick("hk_base"), "hk_max_elem_8": pick("hk_max_elem_8").combine_first(
        pick("hk_base"))}).dropna(subset=["staging"])
    t["staging_over_hk"] = t.staging / t.hk_max_elem_8
    t["winner"] = np.where(t.staging_over_hk > 1.05, "staging", np.where(t.staging_over_hk < 1 / 1.05, "host kernel", "tie"))
    t.reset_index().to_csv(os.path.join(HERE, "results", f"winners_{app}.csv"), index=False)
    print(f"\n=== winners ({app}): GB/s, large copies; staging vs. host kernel with MAX_ELEM_SIZE=8")
    print(t.round(2).to_string())
    print(t.groupby(level="system").winner.value_counts().unstack(fill_value=0).to_string())


if __name__ == "__main__":
    main()
