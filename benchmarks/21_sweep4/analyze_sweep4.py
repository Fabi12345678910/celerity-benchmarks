#!/usr/bin/env python3
"""Numeric analysis of sweep 4 (the analogue of 15_sweep3/analyze_defaults.py): which settings beat the base consistently, and where do the
build's defaults stand? For each config of a variant (stg / hk) and program (strided M 2 and 4, block ROUTE=all): ratio of its median to the
reference at the same point (plot_overview.ratios: geometric mean over M), geometric mean over the four overview sizes, per cell = system x
implementation x direction (12 cells). Prints per config: geomean over the cells, the worst and best cell, the number of cells above 1.05 /
below 0.95, and the geomean per direction, so a change can be judged by consistency and not by one cell.
References: job (the anchor of the same job: same node, minutes apart; the best one on ifi) and anchor (anchors of the same node, else the system).
Writes candidates_<program>_<tag>_<ref>.csv and cells_<program>_<tag>_job.csv (every cell, for drill-down).
Usage: python3 analyze_sweep4.py"""
import os

import pandas as pd

from plot_overview import HERE, gm, load, ratios


def table(d, program, tag, ref):
    r = ratios(d, program, tag, ref)
    m = pd.DataFrame([(*k, v) for k, v in r.items()], columns=["config", "system", "dir", "application", "N", "ratio"])
    cell = m.groupby(["config", "system", "application", "dir"]).ratio.apply(gm).reset_index()
    cell["cell"] = cell.system + " " + cell.application.str.replace("Celerity-", "") + " " + cell["dir"].map({"copy_bandwidth": "H>D", "d2h_gbps": "D>H"})
    g = cell.groupby("config").ratio
    out = pd.DataFrame({"geomean": g.apply(gm), "worst": g.min(), "best": g.max(), "n>1.05": g.apply(lambda x: int((x > 1.05).sum())),
                        "n<0.95": g.apply(lambda x: int((x < 0.95).sum())), "cells": g.size()})
    for dr, lab in (("copy_bandwidth", "H>D"), ("d2h_gbps", "D>H")):
        out[lab] = cell[cell["dir"] == dr].groupby("config").ratio.apply(gm)
    for s in ("gpuc4", "ifi", "lumi"):
        out[s] = cell[cell.system == s].groupby("config").ratio.apply(gm)
    out.index = out.index.str.replace(f"{program}_", "", n=1)
    return out.sort_values("geomean", ascending=False), cell


def main():
    pd.set_option("display.width", 250)
    pd.set_option("display.max_rows", 200)
    for program in ("strided", "block"):
        d = load(program)
        for tag in ("stg", "hk"):
            for ref in ("job", "anchor"):
                t, cell = table(d, program, tag, ref)
                t.round(3).to_csv(os.path.join(HERE, f"candidates_{program}_{tag}_{ref}.csv"))
                if ref == "job":
                    cell.round(3).to_csv(os.path.join(HERE, f"cells_{program}_{tag}_job.csv"), index=False)
                print(f"\n=== {program} {tag}, reference: {'anchor of the same job' if ref == 'job' else 'anchors of the same node'} (cells: {int(t.cells.max())})")
                print(t.round(2).to_string())


if __name__ == "__main__":
    main()
