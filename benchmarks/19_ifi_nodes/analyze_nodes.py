#!/usr/bin/env python3
"""Node-to-node variety on ifi (gc20-gc27, one APU each). Source: the sweep 3 anchor runs (copies of the base of each variant and program, 2 repeats
on each of the 8 nodes, pinned with --nodelist; strided: N 2^16..2^28 step 4, M 2 and 4; block: 4 sizes, ROUTE=all). For every node: bandwidth at
each point (median of the runs of a repeat), relative to the median over the nodes at the same point, geometric mean over the points. Also the
spread between the two repeats on the same node, to tell a node effect from run-to-run noise.
Usage: python3 analyze_nodes.py ; writes node_variety.csv and node_variety.png here and prints the tables."""
import glob
import os
import re

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
S3 = os.path.join(os.path.dirname(HERE), "15_sweep3", "ifi", "results")
INK, MUTED, SURFACE = "#1f1f1e", "#6b6a63", "#fcfcfb"
gm = lambda x: float(np.exp(np.log(x[x > 0]).mean()))


def load():
    frames = []
    for f in sorted(glob.glob(os.path.join(S3, "*_anchor_gc*.csv"))):
        m = re.match(r"(strided|block)_(stg|hk)_anchor_(gc\d+)r(\d)", os.path.basename(f))
        d = pd.read_csv(f, usecols=lambda c: c in ["application", "N", "M", "copy_bandwidth", "d2h_gbps", "check", "machine"])
        d = d[d.check == "ok"]
        d["program"], d["tag"], d["node"], d["rep"] = m.group(1), m.group(2), m.group(3), int(m.group(4))
        if "M" not in d:
            d["M"] = 0
        if m.group(1) == "strided":
            d = d[d.M >= 2]
        frames.append(d)
    d = pd.concat(frames, ignore_index=True)
    assert (d.machine == d.node).all(), "an anchor ran on another node than it was pinned to"
    d["app"] = d.application.str.replace("Celerity-", "")
    long = d.melt(id_vars=["program", "tag", "node", "rep", "app", "N", "M"], value_vars=["copy_bandwidth", "d2h_gbps"], var_name="dir", value_name="gbps")
    long["dir"] = long.dir.map({"copy_bandwidth": "H→D", "d2h_gbps": "D→H"})
    return long[long.gbps > 0]


def main():
    d = load()
    keys = ["program", "tag", "app", "dir", "N", "M"]
    per = d.groupby(keys + ["node", "rep"]).gbps.median().reset_index()
    node = per.groupby(keys + ["node"]).gbps.median().reset_index()
    ref = node.groupby(keys).gbps.median().rename("ref").reset_index()
    node = node.merge(ref, on=keys)
    node["ratio"] = node.gbps / node.ref
    t = node.groupby(["program", "tag", "app", "dir", "node"]).ratio.apply(gm).unstack("node")
    t["spread max/min"] = t.max(axis=1) / t.min(axis=1)
    # the same node twice: the two repeats against each other
    rep = per.pivot_table(index=keys + ["node"], columns="rep", values="gbps").dropna()
    rep["r"] = rep[1] / rep[2]
    noise = rep.groupby(["program", "tag", "app", "dir"]).r.apply(lambda x: gm(np.maximum(x, 1 / x)))
    t["repeat noise (same node)"] = noise
    t.round(3).to_csv(os.path.join(HERE, "node_variety.csv"))
    pd.set_option("display.width", 250)
    print(t.round(2).to_string())
    print("\nmean over rows, per node:", t.drop(columns=["spread max/min", "repeat noise (same node)"]).apply(gm).round(3).to_dict())

    cols = [c for c in t.columns if c.startswith("gc")]
    fig, ax = plt.subplots(figsize=(11, 8.5))
    im = ax.imshow(np.log2(t[cols].values), cmap="RdBu", vmin=-0.6, vmax=0.6, aspect="auto")
    ax.set_xticks(range(len(cols)), cols, color=INK)
    ax.set_yticks(range(len(t)), [" ".join(i) for i in t.index], fontsize=8, color=INK)
    for i in range(len(t)):
        for j, c in enumerate(cols):
            ax.text(j, i, f"{t[c].iloc[i]:.2f}", ha="center", va="center", fontsize=7, color=INK)
    for k in range(4, len(t), 4):
        ax.axhline(k - 0.5, color=SURFACE, linewidth=2)
    ax.set_title("ifi nodes: bandwidth relative to the median over the nodes (anchor runs, geometric mean over the points)", fontsize=10, color=INK, loc="left")
    fig.patch.set_facecolor(SURFACE)
    fig.tight_layout()
    out = os.path.join(HERE, "node_variety.png")
    fig.savefig(out, dpi=130)
    print(out)


if __name__ == "__main__":
    main()
