"""Chart of the verification of the new copylib defaults: new / old bandwidth per copy size, one panel per system x variant x direction."""
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator, NullLocator

import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyze_verify import load, ratios, gm

SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8984", "#e4e3df"
DIRS = [("h2d", "host → device"), ("d2h", "device → host")]


def style():
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "text.color": INK, "axes.labelcolor": INK2,
                         "xtick.color": INK2, "ytick.color": INK2, "axes.edgecolor": GRID, "figure.facecolor": SURFACE,
                         "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE})

IMPL = {"acpp": ("AdaptiveCpp", "#2a78d6"), "dpcpp": ("DPC++", "#eb6834")}
SYSTEMS = [("gpuc4", "gpuc4 · RX 9060 XT (PCIe)"), ("ifi", "ifi · APU"), ("lumi", "LUMI · MI250X")]
COLS = [("staging", "h2d"), ("staging", "d2h"), ("host kernel", "h2d"), ("host kernel", "d2h")]
LO, HI = 0.25, 8


def main(out=os.path.join(os.path.dirname(os.path.abspath(__file__)), "verify.png")):
    style()
    m = ratios(load([s for s, _ in SYSTEMS]))
    m = m[m.config.isin(["staging_new", "hk_new"])]
    fig, axes = plt.subplots(3, 4, figsize=(15, 9.6), sharex=True, sharey=True)
    for r, (sysname, syslabel) in enumerate(SYSTEMS):
        for c, (variant, dirn) in enumerate(COLS):
            ax = axes[r, c]
            v = m[(m.system == sysname) & (m.variant == variant) & (m.dir == dirn)]
            ax.axhspan(LO, 1, color="#fbeceb", zorder=0)
            ax.axhline(1, color=MUTED, lw=1, zorder=1)
            for impl, (lab, col) in IMPL.items():
                x = v[v.impl == impl]
                ax.scatter(x.bytes, x.ratio.clip(LO, HI), s=9, color=col, alpha=0.22, lw=0, zorder=2)
                # pair up powers of two: the shapes sit on different byte counts (rows W8/W32 shift by 2^3/2^5),
                # so per exact byte count the line would zigzag between shape mixes
                b = 2.0 ** (2 * np.floor(np.log2(x.bytes) / 2) + 0.5)
                g = x.ratio.groupby(b.values).apply(gm)
                ax.plot(g.index, g.clip(LO, HI), color=col, lw=2, marker="o", ms=4, mec=SURFACE, mew=1, zorder=3, label=lab)
                tot = gm(x.ratio)
                ax.text(0.03, 0.95 - 0.09 * list(IMPL).index(impl), f"{lab}  {tot:.2f}×", transform=ax.transAxes,
                        ha="left", va="top", fontsize=8.5, color=INK, bbox=dict(fc=SURFACE, ec="none", pad=1), zorder=5)
            ax.set_xscale("log", base=2)
            ax.set_yscale("log", base=2)
            ax.set_ylim(LO, HI)
            ax.yaxis.set_major_locator(FixedLocator([0.25, 0.5, 1, 2, 4, 8]))
            ax.yaxis.set_minor_locator(NullLocator())
            ax.set_yticklabels(["0.25×", "0.5×", "1×", "2×", "4×", "≥8×"])
            ax.xaxis.set_major_locator(FixedLocator([2**16, 2**20, 2**24, 2**28, 2**31]))
            ax.xaxis.set_minor_locator(NullLocator())
            ax.set_xticklabels(["64 KiB", "1 MiB", "16 MiB", "256 MiB", "2 GiB"])
            ax.grid(axis="y", color=GRID, lw=0.8)
            for s in ["top", "right"]:
                ax.spines[s].set_visible(False)
            if r == 0:
                ax.set_title(f"{'Staging' if variant == 'staging' else 'Host kernel'}\n{dict(DIRS)[dirn]}", fontsize=10, color=INK)
            if c == 0:
                ax.set_ylabel(f"{syslabel}\nnew / old bandwidth", fontsize=9)
            if r == 2:
                ax.set_xlabel("bytes copied")
    h, l = axes[0, 0].get_legend_handles_labels()
    fig.legend(h, l, loc="upper right", ncol=2, frameon=False, bbox_to_anchor=(0.985, 0.985))
    fig.suptitle("New copylib defaults vs old: bandwidth ratio per copy size", x=0.012, ha="left", y=0.985, fontsize=13, color=INK)
    fig.text(0.012, 0.945, "line = geomean over shapes in factor-4 size bins (transfer M2/M4, rows W1/8/32, both M2/4/16) · dots = single shapes, median of 5 runs · "
             "panel number = geomean over all points · red band = slower than old", fontsize=8.5, color=INK2)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(out, dpi=130)


if __name__ == "__main__":
    main()
