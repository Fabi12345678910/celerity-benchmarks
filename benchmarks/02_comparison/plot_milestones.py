#!/usr/bin/env python3
"""The original transfer charts (bandwidth over data size, host to device "first access" as in benchmarks/00_old) redrawn with one line per
code state, using each state's default configuration:
  before copylib          Celerity before the copylib integration (00_old; gpuc4 and AdaptiveCpp only)
  first copylib af82e39   the first 3dcopylib implementation (01_default/results; gpuc4, ifi)
  copylib f8d348b         the same with two compile fixes, the "new" line of the old chart (01_default/results_f8d348b; gpuc4, ifi)
  after fastpath c4ee4f1  right after the fixed-width host copies (05_fastpath, N 2^22..2^28, plus results/fastpath_small_*.csv, N 1..2^24, M 2; strided only, two pinned workers)
  tuned 2dda28f           after the tuning: the build's new defaults (15_sweep3 strided_stg_defaults; block: block_native_base, as the default
                          build routes only strided copies to copylib)
One figure per program and system, panels = SYCL implementation. Strided: solid M = 2 (strided, copylib), dotted M = 1 (contiguous, the
regular copy path). Mean of the runs, band = +- one standard deviation. Usage: python3 plot_milestones.py ; writes milestones_<program>_<system>.png."""
import os

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, LogLocator, NullLocator

HERE = os.path.dirname(os.path.abspath(__file__))
B = os.path.dirname(HERE)
SYSTEMS = [("gpuc4", "gpuc4 · RX 9060 XT (PCIe)"), ("ifi", "ifi · APU"), ("lumi", "LUMI · MI250X")]
APPS = [("Celerity-acpp", "AdaptiveCpp"), ("Celerity-dpcpp", "DPC++")]
# (label, colour, {program: path pattern}, application override, filter); categorical slots in a fixed order, never by rank
STATES = [
    ("before copylib", "#8a8984", {"block": "00_old/results/results_no_barrier.csv", "strided": "00_old/results/strided.csv"}, "Celerity", None),
    ("first copylib (af82e39)", "#2a78d6", {"block": "01_default/results/{s}/block_transfer.csv", "strided": "01_default/results/{s}/strided_transfer.csv"}, None, None),
    ("copylib fixes (f8d348b)", "#9b5de5", {"block": "01_default/results_f8d348b/{s}/block_transfer.csv",
                                            "strided": "01_default/results_f8d348b/{s}/strided_transfer.csv"}, None, None),
    ("after fastpath (c4ee4f1)", "#eb6834", {"strided": ("05_fastpath/results/{s}.csv", "02_comparison/results/fastpath_small_{s}.csv")}, None, "base"),
    ("tuned (2dda28f)", "#1baf7a", {"block": "15_sweep3/{s}/results/block_native_base.csv", "strided": "15_sweep3/{s}/results/strided_stg_defaults.csv"}, None, None),
]
INK, MUTED, GRID, SURFACE = "#1f1f1e", "#6b6a63", "#dcdcd7", "#fcfcfb"


def load(path, system, app, app_override, filt):
    """path: one CSV pattern or a tuple of them (concatenated; the runs of a point are pooled)."""
    paths = [os.path.join(B, q.format(s=system)) for q in ([path] if isinstance(path, str) else path)]
    paths = [q for q in paths if os.path.exists(q)]
    if not paths or (app_override and system != "gpuc4"):
        return None
    d = pd.concat([pd.read_csv(q) for q in paths], ignore_index=True)
    if app_override:
        if app != "Celerity-acpp":
            return None
        d = d[d.application == app_override]
    else:
        d = d[d.application == app]
    if filt == "base" and "env" in d:
        d = d[d.env.isna()]  # the run without extra settings: two workers pinned (the sweep base of that time), else defaults
    if filt == "sdma_off":  # 20_sdma_defaults: the runs with HSA_ENABLE_SDMA=0 (the other runs of the file are the same config with SDMA on)
        d = d[d.env.fillna("").str.contains("HSA_ENABLE_SDMA=0")]
    if "check" in d:
        d = d[d.check == "ok"]
    d = d[(d.data_size_gib > 0) & (d.copy_bandwidth > 0)]
    return d if len(d) else None


def human(v, base, suffix=""):
    """1..999 with up to three significant digits and a unit: 64 KB, 1.5 MB, 250 MB/s (base 1024 for sizes, 1000 for rates)."""
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while i < 4 and round(abs(v), 3) >= base * 0.9995:
        v /= base
        i += 1
    return f"{v:.3g} {units[i]}{suffix}"


def to_plot(g, column):
    """Plot units: x in bytes (data_size_gib is GiB), y in bytes per second (the programs print GB/s = bytes per ns)."""
    g = g.copy()
    g["x"] = g.data_size_gib * 2 ** 30
    g["mean"], g["std"] = g["mean"] * 1e9, g["std"] * 1e9
    return g


def series(d):
    return to_plot(d.groupby("data_size_gib").copy_bandwidth.agg(["mean", "std"]).reset_index().sort_values("data_size_gib"), "copy_bandwidth")


def style(ax, log_y):
    ax.set_xscale("log", base=2)
    ax.xaxis.set_major_locator(LogLocator(base=16, numticks=30))
    ax.xaxis.set_minor_locator(NullLocator())
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: human(v, 1024)))
    if log_y:
        ax.set_yscale("log")
        ax.yaxis.set_major_locator(LogLocator(base=10, numticks=30))
        ax.yaxis.set_minor_locator(NullLocator())
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: human(v, 1000, "/s")))
    ax.grid(True, which="major", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelcolor=INK, labelsize=8)
    ax.set_xlabel("data size (1 KB = 1024 B)", color=INK, fontsize=9)


def main():
    plt.rcParams.update({"font.family": "DejaVu Sans", "figure.facecolor": SURFACE, "axes.facecolor": SURFACE})
    for program in ("block", "strided"):
        for system, sname in SYSTEMS:
            fig, axes = plt.subplots(1, 2, figsize=(15, 6.2), sharey=True)
            shown = []
            for ax, (app, aname) in zip(axes, APPS):
                for label, colour, paths, override, filt in STATES:
                    if program not in paths:
                        continue
                    d = load(paths[program], system, app, override, filt)
                    if d is None:
                        continue
                    ms = [(None, "-")] if program == "block" else [(2, "-"), (1, ":")]
                    for m, ls in ms:
                        x = d if m is None else d[d.M == m]
                        if not len(x):
                            continue
                        g = series(x)
                        ax.plot(g.x, g["mean"], color=colour, linestyle=ls, linewidth=2 if ls == "-" else 1.4,
                                marker="o" if ls == "-" else None, markersize=3.5)
                        y, e = g["mean"].values, g["std"].fillna(0).values
                        ax.fill_between(g.x, np.clip(y - e, y * 0.05, None), y + e, color=colour, alpha=0.12, linewidth=0)
                    if label not in shown:
                        shown.append(label)
                style(ax, log_y=program == "strided")
                ax.set_title(aname, fontsize=10, color=INK)
            axes[0].set_ylabel("host → device bandwidth (first access)", color=INK, fontsize=9)
            handles = [plt.Line2D([], [], color=c, linewidth=2.5, label=l) for l, c, *_ in STATES if l in shown]
            if program == "strided":
                handles += [plt.Line2D([], [], color=INK, linestyle="-", label="M = 2 (strided, copylib)"),
                            plt.Line2D([], [], color=INK, linestyle=":", label="M = 1 (contiguous, regular path)")]
            fig.legend(handles=handles, loc="upper left", ncol=len(handles), frameon=False, fontsize=8.5, bbox_to_anchor=(0.005, 0.945))
            what = "block data transfer" if program == "block" else "strided data transfer (4-byte rows)"
            fig.suptitle(f"{what}, {sname}: code states, each in its default configuration", x=0.01, ha="left", y=0.995, fontsize=12, color=INK)
            fig.tight_layout(rect=(0, 0, 1, 0.88))
            out = os.path.join(HERE, f"milestones_{program}_{system}.png")
            fig.savefig(out, dpi=140)
            plt.close(fig)
            print(out, shown)


if __name__ == "__main__":
    main()
