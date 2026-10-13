#!/usr/bin/env python3
"""The overview of sweep 1, the first configuration sweep (layout: ../overview.py), on build f8d348b before any tuning: one row per setting,
strided_transfer only (4-byte rows, copy sizes 64Ki / 1Mi / 4Mi / 16Mi rows, geometric mean over M = 2, 3, 4; M = 1 is contiguous and
never reaches copylib). Reference: the sweep's base (Celerity's and copylib's defaults of the time with two workers pinned to dedicated
cores); the host-kernel kernel options (elements per item, work-group size) are relative to the plain host kernel. Shows what an untuned
configuration looks like: many settings are clearly better than the base. Usage: python3 plot_overview.py ; writes overview.png here."""
import glob
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from overview import draw, gm, SYSTEMS, DIRS  # noqa: E402

SIZES = [1 << 16, 1 << 20, 1 << 22, 1 << 24]
UNIT = {"B": 1, "KiB": 1024, "MiB": 1 << 20, "GiB": 1 << 30}
STAGING = [("ref", ["reference_default", "host_kernel", "best_combination", "copylib_off"]), ("min_bytes", None), ("queues", None),
           ("staging", None), ("chunk", None), ("misc", ["wait_poll", "host_staging_pageable", "warmup", "sdma_off"])]
HOST_KERNEL = [("elems_per_item", None), ("wg_size", None)]
LABEL = {"reference_default": "defaults without pinning", "host_kernel": "host kernel", "best_combination": "best combination (earlier tuning)",
         "copylib_off": "native (CELERITY_COPYLIB=off)", "host_staging_pageable": "pageable staging", "warmup": "warmup (no kernel in staging)"}


def load():
    frames = []
    for system, _ in SYSTEMS:
        for f in glob.glob(os.path.join(HERE, system, "results", "strided_*.csv")):
            d = pd.read_csv(f, usecols=["application", "N", "M", "copy_bandwidth", "d2h_gbps", "check"])
            d["system"], d["config"] = system, os.path.basename(f)[len("strided_"):-4].rstrip("_12") if "copylib_off" in f else os.path.basename(f)[len("strided_"):-4]
            frames.append(d[(d.check == "ok") & (d.M >= 2) & d.N.isin(SIZES)])
    d = pd.concat(frames, ignore_index=True)
    long = d.melt(id_vars=["system", "application", "config", "N", "M"], value_vars=[k for k, _ in DIRS], var_name="dir", value_name="gbps")
    return long[long.gbps > 0].groupby(["system", "application", "config", "dir", "N", "M"]).gbps.median().reset_index()


def ratios(med, ref_config, configs):
    keys = ["system", "application", "dir", "N", "M"]
    r = med[med.config == ref_config].drop(columns="config").rename(columns={"gbps": "ref"})
    m = med[med.config.isin(configs)].merge(r, on=keys)
    m["ratio"] = m.gbps / m.ref
    return m.groupby(["config", "system", "dir", "application", "N"]).ratio.apply(gm).to_dict()


def rows_for(med, spec):
    present = set(med.config)
    out = []
    for group, names in spec:
        if names is None:
            names = sorted((c for c in present if c.startswith(group + "_")), key=lambda c: num(c[len(group) + 1:]))
        out += [(LABEL.get(c, c.replace("_", " ")), group, c) for c in names if c in present]
    return out


def num(v):
    digits = v.rstrip("BKiMG")
    return int(digits) * UNIT.get(v[len(digits):], 1) if digits.isdigit() else 0


def main():
    med = load()
    stg, hk = rows_for(med, STAGING), rows_for(med, HOST_KERNEL)
    g = {**ratios(med, "base", [k for _, _, k in stg]), **ratios(med, "host_kernel", [k for _, _, k in hk])}
    sub = ("Each cell: top row acpp, bottom row DPC++; left to right 64Ki, 1Mi, 4Mi, 16Mi rows per copy (4-byte rows). Geometric mean over "
           "M = 2, 3, 4, median of 3 runs.\nReference, staging: the sweep's base (Celerity and copylib defaults of the time, 2 workers pinned to "
           "dedicated cores); host kernel: COPYLIB_HOST_KERNEL=1 on top of it.\nBlue faster, red slower, 0.5x to 2x. Empty outlined cell = not "
           "run on that system (the native path only up to 8Mi rows).")
    out = draw(os.path.join(HERE, "overview.png"), "Sweep 1 (first configuration sweep, build f8d348b): bandwidth relative to the base, strided_transfer",
               sub, [("staging", stg), ("host kernel", hk)], lambda k, s, dk, app, zi: g.get((k, s, dk, app, SIZES[zi])), ["64Ki", "1Mi", "4Mi", "16Mi"])
    print(out, len(stg) + len(hk), "rows")


if __name__ == "__main__":
    main()
