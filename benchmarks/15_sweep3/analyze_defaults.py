#!/usr/bin/env python3
"""Which sweep 3 settings beat the base consistently, and where do the build's defaults stand? For each config of a variant (stg / hk) and program
(strided M 2 and 4, block ROUTE=all): ratio to the median of the three base reruns at the same point (system, implementation, direction, size, M),
geometric mean over the overview sizes, per cell = system x implementation x direction (12 cells). Prints per config: geomean over the cells, the
worst cell, and the number of cells above 1.05 / below 0.95, so a change can be judged by consistency and not by one cell. Writes candidates_<program>_<tag>.csv.
Usage: python3 analyze_defaults.py"""
import glob
import os

import numpy as np
import pandas as pd

from plot_overview import SIZES, DIRS, SYSTEMS, load, medians

HERE = os.path.dirname(os.path.abspath(__file__))
gm = lambda x: float(np.exp(np.log(x[x > 0]).mean()))


def table(program, tag, ref="rerun"):
    d = load(program)
    own = d.config.str.startswith(f"{program}_{tag}_") | ((tag == "stg") & d.config.str.startswith(f"{program}_native_"))
    med = medians(d[own])
    med_all = med
    reruns = med[med.config.str.contains("_rerun_")]
    med = med[~med.config.str.contains("_anchor_") & ~med.config.str.contains("_rerun_")]
    keys = ["system", "application", "dir", "N", "M"]
    if ref == "rerun":
        r = reruns.groupby(keys).gbps.median().rename("ref").reset_index()
        m = med.merge(r, on=keys)
    else:  # the anchors (copies of the base) of the node the config ran on, else of all nodes of the system
        a = med_all[med_all.config.str.startswith(f"{program}_{tag}_anchor")]
        r_node = a.groupby(keys + ["machine"]).gbps.median().rename("ref_node").reset_index()
        r_sys = a.groupby(keys).gbps.median().rename("ref_sys").reset_index()
        m = med.merge(r_sys, on=keys).merge(r_node, on=keys + ["machine"], how="left")
        m["ref"] = m.ref_node.fillna(m.ref_sys)
    m["ratio"] = m.gbps / m.ref
    cell = m.groupby(["config", "system", "application", "dir"]).ratio.apply(gm).reset_index()
    cell["cell"] = cell.system + " " + cell.application.str.replace("Celerity-", "") + " " + cell["dir"].map({"copy_bandwidth": "H>D", "d2h_gbps": "D>H"})
    g = cell.groupby("config").ratio
    out = pd.DataFrame({"geomean": g.apply(gm), "worst": g.min(), "best": g.max(), "n>1.05": g.apply(lambda x: int((x > 1.05).sum())),
                        "n<0.95": g.apply(lambda x: int((x < 0.95).sum())), "cells": g.size()})
    # per direction geomeans
    for dr, lab in (("copy_bandwidth", "H>D"), ("d2h_gbps", "D>H")):
        out[lab] = cell[cell["dir"] == dr].groupby("config").ratio.apply(gm)
    return out.sort_values("geomean", ascending=False), cell


def main():
    pd.set_option("display.width", 220)
    for program in ("strided", "block"):
        for tag in ("stg", "hk"):
            for ref in ("rerun", "anchor"):
                t, cell = table(program, tag, ref)
                t.round(3).to_csv(os.path.join(HERE, f"candidates_{program}_{tag}_{ref}.csv"))
                print(f"\n=== {program} {tag}, reference: {'median of the base reruns' if ref == 'rerun' else 'anchors of the same node'} (cells: {int(t.cells.max())})")
                print(t.round(2).head(10).to_string())
                print("  ... defaults/old:", t.loc[[c for c in t.index if c.endswith(("_defaults", "_old"))]].round(2)[["geomean", "worst", "H>D", "D>H"]].to_dict("index"))


if __name__ == "__main__":
    main()
