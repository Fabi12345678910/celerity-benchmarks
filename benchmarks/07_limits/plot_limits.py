import glob
import os
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Plots and summarizes the hardware-limit benchmarks (07_limits/results/<system>_{membw,linkbw,concurrent}.csv) into 07_limits/results/plots:
#   <system>_membw_<useful|memory>.png   GB/s over the thread count, one line per access pattern (median, band = min-max of 3 runs)
#   <system>_linkbw_<sdma>.png           GB/s over the copy size, one line per transfer test, SDMA on (default) and off
#   <system>_concurrent.png              DMA copy alone vs. next to 2/4/8 threads packing or unpacking, and their combined memory traffic
# and prints the summary tables. Usage: python 07_limits/plot_limits.py <system> [<system> ...]

HERE = os.path.dirname(os.path.abspath(__file__))
pd.set_option("display.width", 250)
TRAFFIC = {"pack2": 3, "pack4": 5, "unpack2": 5, "unpack4": 9}  # memory bytes per useful byte (membw.cpp)


def read(system, kind):
    f = os.path.join(HERE, "results", f"{system}_{kind}.csv")
    return pd.read_csv(f) if os.path.exists(f) else None


def membw(system, out):
    d = read(system, "membw")
    if d is None:
        return
    d["threads"] = d.cpus.astype(str).str.count(",") + 1
    for app, a in d.groupby("application"):
        place = "data on one NUMA node (first-touch by the first thread)" if app == "membw" and system == "lumi" else \
            "each thread's data on its own NUMA node" if app == "membw-local" else "one NUMA node"
        for metric in ("useful_gbps", "memory_gbps"):
            fig, ax = plt.subplots(figsize=(14, 8))
            cmap = plt.get_cmap("tab10")
            for i, (test, t) in enumerate(a.groupby("test", sort=False)):
                # extra CPU lists (e.g. ifi 5,6,8,9) share a thread count with the ordered list; plot the ordered ones only
                ordered = t[~t.cpus.astype(str).isin(["8,9,10,11", "5,6,8,9"])]
                g = ordered.groupby("threads")[metric].agg(["median", "min", "max"])
                ax.plot(g.index, g["median"], marker="o", label=test, color=cmap(i), linestyle="--" if "nt" in test or "pack" in test else "-")
                ax.fill_between(g.index, g["min"], g["max"], alpha=0.12, color=cmap(i))
            ax.set_xscale("log", base=2)
            counts = sorted(a.threads.unique())
            ax.set_xticks(counts)
            ax.set_xticklabels([str(c) for c in counts])
            ax.set_xlabel("threads, each on its own core (order as in the worker sweep)")
            ax.set_ylabel(("useful" if metric == "useful_gbps" else "modeled memory traffic") + " GB/s")
            ax.set_title(f"{system} {app}: host memory, {place}")
            ax.grid(True, which="both", alpha=0.5)
            ax.legend(fontsize=9)
            fig.text(0.01, 0.01, "memory traffic per useful byte: read 1, write 2 (write-allocate), write_nt 1, copy 3, copy_nt 2, packM M+1, "
                     "unpackM 2M+1; 64 MiB useful per thread, median of 5 passes per run", fontsize=8)
            fig.tight_layout(rect=(0, 0.03, 1, 1))
            path = os.path.join(out, f"{system}_{app}_{metric.split('_')[0]}.png")
            fig.savefig(path, dpi=150)
            plt.close(fig)
        t = a.groupby(["test", "threads"])[["useful_gbps", "memory_gbps"]].median().unstack("threads")
        print(f"\n=== {system} {app}: median GB/s over the thread count (useful | modeled memory traffic)")
        print(t["useful_gbps"].round(1).to_string())
        print(t["memory_gbps"].round(1).to_string())
        extra = a[a.cpus.astype(str).isin(["8,9,10,11", "5,6,8,9"])]
        if len(extra):
            print(extra.groupby(["test", "cpus"])[["useful_gbps", "memory_gbps"]].median().unstack("cpus").round(1).to_string())


def linkbw(system, out):
    # <system>_linkbw.csv plus the rerun of its SDMA-off half (<system>_linkbw_sdma_off.csv) where the first run had no value
    parts = [p for p in (read(system, "linkbw"), read(system, "linkbw_sdma_off")) if p is not None]
    if not parts:
        return
    d = pd.concat(parts, ignore_index=True)
    d = d[d.gbps.notna()].copy()
    d["sdma"] = np.where(d.env.fillna("").str.contains("SDMA=0"), "SDMA off", "SDMA on")
    for sdma, s in d.groupby("sdma"):
        fig, ax = plt.subplots(figsize=(14, 8))
        cmap = plt.get_cmap("tab10")
        for i, (test, t) in enumerate(s.groupby("test", sort=False)):
            g = t.groupby("mib")["gbps"].agg(["median", "min", "max"])
            ax.plot(g.index, g["median"], marker="o", label=test, color=cmap(i), linestyle="-" if test.startswith("dma") else "--")
            ax.fill_between(g.index, g["min"], g["max"], alpha=0.12, color=cmap(i))
        ax.set_xscale("log", base=2)
        ax.set_yscale("log")
        sizes = sorted(s.mib.unique())
        ax.set_xticks(sizes)
        ax.set_xticklabels([f"{m} MiB" if m < 1024 else f"{m // 1024} GiB" for m in sizes])
        ax.set_xlabel("useful bytes per copy")
        ax.set_ylabel("GB/s (dma_bidir: both directions together)")
        ax.set_title(f"{system}: CPU <-> GPU transfers without Celerity, {sdma}")
        ax.grid(True, which="both", alpha=0.5)
        ax.legend(fontsize=9)
        fig.tight_layout()
        path = os.path.join(out, f"{system}_linkbw_{sdma.replace(' ', '_')}.png")
        fig.savefig(path, dpi=150)
        plt.close(fig)
    t = d[d.mib == d.mib.max()].groupby(["test", "sdma"])["gbps"].median().unstack("sdma")
    print(f"\n=== {system} linkbw: median GB/s at {d.mib.max()} MiB")
    print(t.round(2).to_string())


def concurrent(system, out):
    d = read(system, "concurrent")
    l = read(system, "linkbw")
    if d is None:
        return
    d["kind"] = d.load.str.split(":").str[0]
    d["threads"] = d.load.str.split(":").str[1].str.count(",") + 1
    # memory traffic: the DMA copy reads (h2d) or writes (d2h) host memory once per byte, the load threads as modeled per pattern
    d["memory_gbps"] = d.gbps + d.load_gbps * d.kind.map(TRAFFIC)
    t = d.groupby(["test", "kind", "threads"])[["gbps", "load_gbps", "memory_gbps"]].median().round(2)
    alone = l[(l.mib == 1024) & l.env.isna()].groupby("test")["gbps"].median() if l is not None else pd.Series(dtype=float)
    print(f"\n=== {system} concurrent: DMA of 1 GiB next to CPU threads running the staging loop (GB/s)")
    print(f"DMA alone: {alone.reindex(['dma_h2d', 'dma_d2h']).round(2).to_dict()}")
    print(t.rename(columns={"gbps": "DMA", "load_gbps": "CPU loop (useful)", "memory_gbps": "memory traffic"}).to_string())
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    for ax, test in zip(axes, ("dma_h2d", "dma_d2h")):
        x = t.xs(test, level="test")
        labels = [f"{k}\n{n} thr" for k, n in x.index]
        pos = np.arange(len(x))
        ax.bar(pos - 0.2, x.gbps, 0.4, label="DMA copy GB/s", color="tab:blue")
        ax.bar(pos + 0.2, x.load_gbps, 0.4, label="CPU staging loop GB/s (useful)", color="tab:orange")
        ax.plot(pos, x.memory_gbps, "kD", label="combined memory traffic GB/s")
        if test in alone:
            ax.axhline(alone[test], color="tab:blue", linestyle=":", label="DMA copy alone")
        ax.set_xticks(pos)
        ax.set_xticklabels(labels, fontsize=8)
        ax.set_title(test)
        ax.grid(True, axis="y", alpha=0.5)
        ax.legend(fontsize=8)
    fig.suptitle(f"{system}: DMA copy (1 GiB) while CPU threads pack/unpack (memory shared by both)")
    fig.tight_layout()
    path = os.path.join(out, f"{system}_concurrent.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main():
    out = os.path.join(HERE, "results", "plots")
    os.makedirs(out, exist_ok=True)
    for system in sys.argv[1:]:
        membw(system, out)
        linkbw(system, out)
        concurrent(system, out)


if __name__ == "__main__":
    main()
