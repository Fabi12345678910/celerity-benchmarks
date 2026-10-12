#!/usr/bin/env python3
"""Numeric analysis of the final sweep (the method of 21_sweep4/analyze_sweep4.py on 25_final): per config of a variant (stg / hk) and program
(strided: M = 2 and 4; block: ROUTE=all), the ratio of its median to the reference at the same point (geometric mean over M), geometric mean over
the overview sizes, per cell = system x implementation x direction. References: job (the anchor of the same job: same node, minutes apart; the
base where the job has no anchor of that variant) and base (the variant's base config = the build's defaults, SDMA off).
Writes final_candidates_<program>_<tag>_<ref>.csv and final_cells_<program>_<tag>_job.csv; prints the tables.
Usage: python3 analyze_final.py [systems...] [--keep-ifi-acpp-h2d]   (default: every system with results)
By default the ifi AdaptiveCpp host-to-device cell is left out: it drifts with time (0.1-1.0 GB/s between job waves, 21_sweep4/README.md), so a config
and its same-job anchor can differ by 0.3-11x with nothing changed (base vs its own anchor: 11x in the final sweep). --keep-ifi-acpp-h2d keeps it."""
import glob
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
SIZES = {"strided": [1 << 16, 1 << 20, 1 << 22, 1 << 24], "block": [1 << 16, 1 << 20, 1 << 24, 1 << 28]}
DIRS = {"copy_bandwidth": "H>D", "d2h_gbps": "D>H"}
gm = lambda x: float(np.exp(np.log(x[x > 0]).mean())) if (x > 0).any() else float("nan")


def systems():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    return args or [s for s in ("gpuc4", "ifi", "lumi") if glob.glob(os.path.join(HERE, s, "results", "sweep_*.csv"))]


def job_map(system):
    out = {}
    for i, line in enumerate(open(os.path.join(HERE, system, "jobs.txt")), 1):
        for y in line.split():
            out[os.path.basename(y)[:-5]] = i
    return out


def load(program, system):
    frames = []
    for f in sorted(glob.glob(os.path.join(HERE, system, "results", f"sweep_{program}_*.csv"))):
        d = pd.read_csv(f, usecols=lambda c: c in ("application", "N", "M", "check", "copy_bandwidth", "d2h_gbps", "machine"))
        d["config"] = os.path.basename(f)[len(f"sweep_{program}_"):-4]
        frames.append(d[d.check == "ok"])
    d = pd.concat(frames, ignore_index=True)
    if "M" not in d:
        d["M"] = 0
    d["M"] = d.M.fillna(0)
    if program == "strided":
        d = d[d.M >= 2]
    d = d[d.N.isin(SIZES[program])]
    d["system"] = system
    d["job"] = d.config.map({k[len(f"sweep_{program}_"):]: v for k, v in job_map(system).items()})
    long = d.melt(id_vars=["system", "application", "config", "job", "N", "M"], value_vars=list(DIRS), var_name="dir", value_name="gbps")
    return long[long.gbps > 0].groupby(["system", "application", "config", "job", "dir", "N", "M"]).gbps.median().reset_index()


def table(med, tag, ref):
    own = med[med.config.str.startswith(f"{tag}_")]
    anchors = own[own.config.str.startswith(f"{tag}_anchor_")]
    cfgs = own[~own.config.str.startswith(f"{tag}_anchor_")]
    keys = ["system", "application", "dir", "N", "M"]
    base = cfgs[cfgs.config == f"{tag}_base"].groupby(keys).gbps.median().rename("ref_base").reset_index()
    m = cfgs.merge(base, on=keys)
    if ref == "job":
        a = anchors.groupby(keys + ["job"]).gbps.median().rename("ref_job").reset_index()
        m = m.merge(a, on=keys + ["job"], how="left")
        m["ref"] = m.ref_job.fillna(m.ref_base)
    else:
        m["ref"] = m.ref_base
    m["ratio"] = m.gbps / m.ref
    if "--keep-ifi-acpp-h2d" not in sys.argv:
        m = m[~((m.system == "ifi") & (m.application == "Celerity-acpp") & (m["dir"] == "copy_bandwidth"))]
    pt = m.groupby(["config", "system", "application", "dir", "N"]).ratio.apply(gm).reset_index()
    cell = pt.groupby(["config", "system", "application", "dir"]).ratio.apply(gm).reset_index()
    cell["cell"] = cell.system + " " + cell.application.str.replace("Celerity-", "") + " " + cell["dir"].map(DIRS)
    g = cell.groupby("config").ratio
    out = pd.DataFrame({"geomean": g.apply(gm), "worst": g.min(), "best": g.max(), "n>1.05": g.apply(lambda x: int((x > 1.05).sum())),
                        "n<0.95": g.apply(lambda x: int((x < 0.95).sum())), "cells": g.size()})
    for dr, lab in DIRS.items():
        out[lab] = cell[cell["dir"] == dr].groupby("config").ratio.apply(gm)
    for s in cell.system.unique():
        out[s] = cell[cell.system == s].groupby("config").ratio.apply(gm)
    return out.sort_values("geomean", ascending=False), cell


def main():
    pd.set_option("display.width", 250)
    pd.set_option("display.max_rows", 300)
    ss = systems()
    for program in ("strided", "block"):
        med = pd.concat([load(program, s) for s in ss if glob.glob(os.path.join(HERE, s, "results", f"sweep_{program}_*.csv"))], ignore_index=True)
        for tag in ("stg", "hk"):
            for ref in ("job", "base"):
                t, cell = table(med, tag, ref)
                t.round(3).to_csv(os.path.join(HERE, f"final_candidates_{program}_{tag}_{ref}.csv"))
                if ref == "job":
                    cell.round(3).to_csv(os.path.join(HERE, f"final_cells_{program}_{tag}_job.csv"), index=False)
                print(f"\n=== {program} {tag}, reference: {'anchor of the same job' if ref == 'job' else 'base config'}, systems {ss} (cells: {int(t.cells.max())})")
                print(t.round(2).to_string())


if __name__ == "__main__":
    main()
