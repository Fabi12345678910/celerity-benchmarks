#!/usr/bin/env python3
"""The overview of sweep 2, the defaults sweep (the "overview", originally the c2 glyph chart): one row per option, one cell per
system x direction, each cell a 2 x 4 glyph (compiler x copy size 64Ki/1Mi/4Mi/16Mi rows). Colour = bandwidth relative to the variant's base,
geometric mean over the shapes at each row count, median of 3 runs. Usage: python3 plot_overview.py ; writes results/overview.png."""
import glob
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

# Per-size ratios of every sweep-2 option against its variant's base: system x compiler x direction x size bucket.

ROOT = os.path.dirname(os.path.abspath(__file__))
MiB = 1 << 20
# concrete row counts, measured for every shape: useful bytes = N x row width (4 B rows: 256 KiB .. 64 MiB, 128 B rows: 8 MiB .. 2 GiB)
ROWS_N = {1 << 16: "64Ki rows", 1 << 20: "1Mi rows", 1 << 22: "4Mi rows", 1 << 24: "16Mi rows"}
SIZES = list(ROWS_N.values())
SHORT = ["64Ki", "1Mi", "4Mi", "16Mi"]
BYTES_NOTE = "rows per copy; useful bytes = rows × row width: 4 B rows 256 KiB / 4 / 16 / 64 MiB, 32 B rows 2 / 32 / 128 / 512 MiB, 128 B rows 8 / 128 / 512 MiB / 2 GiB"
SYSTEMS = ["gpuc4", "ifi", "lumi"]
SYS_LABEL = {"gpuc4": "gpuc4", "ifi": "ifi", "lumi": "LUMI"}
APP_LABEL = {"Celerity-acpp": "acpp", "Celerity-dpcpp": "DPC++"}
METRIC_DIRS = {"copy_bandwidth": "h2d", "d2h_gbps": "d2h"}


def load():
    frames = []
    for system in SYSTEMS:
        for f in glob.glob(f"{ROOT}/{system}/results/*.csv"):
            d = pd.read_csv(f)
            d["M"] = d["M"].fillna(d["M.1"]) if "M.1" in d else d["M"]
            d["W"] = d["W"].fillna(d["W.1"]) if "W.1" in d else d["W"]
            d["system"] = system
            frames.append(d[["system", "application", "variant", "config", "program", "N", "M", "W", "check", *METRIC_DIRS]])
    d = pd.concat(frames)
    d = d[d.check == "ok"]
    d["app"] = d.application.map(APP_LABEL)
    d["useful"] = np.where(d.program == "strided_transfer", d.N * 4, d.N * d.W * 4).astype(np.int64)
    d["shape"] = d.program + " M" + d.M.astype(int).astype(str) + " W" + d.W.astype(int).astype(str)
    d = d[d.N.isin(list(ROWS_N))].copy()
    d["size"] = d.N.map(ROWS_N)
    long = d.melt(id_vars=["system", "app", "variant", "config", "shape", "N", "useful", "size"], value_vars=list(METRIC_DIRS), var_name="metric", value_name="gbps")
    long["direction"] = long.metric.map(METRIC_DIRS)
    med = long.groupby(["system", "app", "variant", "config", "shape", "N", "size", "direction"], observed=True).gbps.median().reset_index()
    base = med[med.config.str.endswith("_base")].drop(columns="config").rename(columns={"gbps": "base"})
    m = med.merge(base, on=["system", "app", "variant", "shape", "N", "size", "direction"])
    m["ratio"] = m.gbps / m.base
    m = m[~m.config.str.endswith("_base")]
    # geometric mean over the shapes at the same row count
    r = m.groupby(["variant", "config", "system", "app", "direction", "size"], observed=True).ratio.apply(lambda x: float(np.exp(np.log(x).mean()))).reset_index()
    r["option"] = r.config.str.replace(r"^(staging|hk)_", "", regex=True)
    return r


SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8984", "#e4e3df"
BLUE, RED, MID = "#2a78d6", "#e34948", "#f0efec"
CMAP = LinearSegmentedColormap.from_list("div", [RED, MID, BLUE])
CMAP.set_bad(SURFACE)
NORM = TwoSlopeNorm(vmin=-1, vcenter=0, vmax=1)  # log2 ratio, 0.5x .. 2x
SYS_COLORS = {"gpuc4": "#2a78d6", "ifi": "#eb6834", "lumi": "#1baf7a"}  # categorical slots 1-3
SIZE_COLORS = ["#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]  # ordinal blue ramp 250/400/550/700
DIRS = [("h2d", "host → device"), ("d2h", "device → host")]
APPS = ["acpp", "DPC++"]

ORDER = {
    "staging": ["chunk_256KiB", "chunk_512KiB", "chunk_1MiB", "chunk_2MiB", "chunk_8MiB", "chunk_16MiB", "chunk_32MiB", "chunk_64MiB",
                "order_block", "order_interleaved", "wait_poll", "pageable", "sdma_off", "alloc_far"],
    "host kernel": ["max_elem_4", "max_elem_8", "max_elem_16", "max_elem_32", "warmup", "chunk_256KiB", "chunk_1MiB", "chunk_4MiB",
                    "chunk_64MiB", "chunk_256MiB", "chunk_whole", "elems_2", "elems_4", "elems_16", "wg_16", "wg_64", "wg_128", "wg_256",
                    "wg_1024", "queues_1", "queues_4", "queues_8", "queues_8_hw_queues_8", "order_dynamic", "order_interleaved",
                    "wait_poll", "coherent"],
}
BASE_NOTE = {"staging": "base: worker-sweep config (4 MiB chunks, dynamic order)", "host kernel": "base: copylib defaults (16 MiB chunks, MAX_ELEM_SIZE 64)"}


def label(option):
    return option.replace("warmup", "preload_kernels").replace("_", " ")


def style():
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "text.color": INK, "axes.labelcolor": INK2,
                         "xtick.color": INK2, "ytick.color": INK2, "axes.edgecolor": GRID, "figure.facecolor": SURFACE,
                         "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE})


def lg(x):
    return np.log2(np.clip(x, 1 / 64, 64))


def add_colorbar(fig, ax_or_rect, orientation="vertical"):
    sm = matplotlib.cm.ScalarMappable(norm=NORM, cmap=CMAP)
    cax = fig.add_axes(ax_or_rect)
    cb = fig.colorbar(sm, cax=cax, orientation=orientation)
    cb.set_ticks([-1, -0.5, 0, 0.5, 1])
    cb.set_ticklabels(["≤ 0.5×", "0.71×", "same", "1.41×", "≥ 2×"])
    cb.outline.set_visible(False)
    cb.ax.tick_params(length=0, labelsize=8)
    return cb


def main():
    style()
    r = load()
    CW, CH, GX, GY = 4, 2, 1.0, 0.7  # glyph cols, rows, gaps
    colgroups = [(s, d) for s in SYSTEMS for d, _ in DIRS]
    rows = [(v, o) for v in ["staging", "host kernel"] for o in ORDER[v]]
    fig, ax = plt.subplots(figsize=(10.5, 17))
    fig.subplots_adjust(left=0.2, right=0.86, top=0.925, bottom=0.01)
    y = 0
    yt, yl, sections = [], [], {}
    for vi, (variant, o) in enumerate(rows):
        if vi and rows[vi - 1][0] != variant:
            y += 2.2
        sections.setdefault(variant, [y, y])[1] = y + CH
        v = r[(r.variant == variant) & (r.option == o)].set_index(["system", "direction", "app", "size"]).ratio
        for ci, (s, d) in enumerate(colgroups):
            x0 = ci * (CW + GX) + (0.6 if ci >= 2 else 0) + (0.6 if ci >= 4 else 0)
            for ai, a in enumerate(APPS):
                for zi, z in enumerate(SIZES):
                    val = v.get((s, d, a, z))
                    if val is None or np.isnan(val):
                        continue
                    ax.add_patch(plt.Rectangle((x0 + zi, y + ai), 0.94, 0.9, color=CMAP(NORM(lg(val)))))
        yt.append(y + CH / 2); yl.append(label(o))
        y += CH + GY
    ax.set_xlim(-0.3, len(colgroups) * (CW + GX) + 1); ax.set_ylim(y, -2.6)
    ax.set_yticks(yt, yl, fontsize=8.5); ax.set_xticks([]); ax.tick_params(length=0)
    for sp in ax.spines.values(): sp.set_visible(False)
    for ci, (s, d) in enumerate(colgroups):
        x0 = ci * (CW + GX) + (0.6 if ci >= 2 else 0) + (0.6 if ci >= 4 else 0)
        ax.text(x0 + CW / 2, -0.6, dict(DIRS)[d].replace("host", "H").replace("device", "D"), ha="center", fontsize=8, color=INK2)
        if d == "h2d":
            ax.text(x0 + CW + GX / 2, -1.9, SYS_LABEL[s], ha="center", fontsize=10.5, color=INK)
    for variant, (y0, y1) in sections.items():
        ax.text(-8.6, (y0 + y1) / 2, variant, rotation=90, ha="center", va="center", fontsize=12, weight="bold", transform=ax.transData, clip_on=False)
    # key glyph
    kx, ky = 0.915, 0.93
    kax = fig.add_axes([0.875, 0.83, 0.12, 0.06]); kax.set_xlim(-3.2, 4.2); kax.set_ylim(3.6, -1.6); kax.axis("off")
    for ai in range(2):
        for zi in range(4):
            kax.add_patch(plt.Rectangle((zi, ai), 0.94, 0.9, color=MID, ec=MUTED, lw=0.4))
    for zi, t in enumerate(SHORT):
        kax.text(zi + 0.47, -0.3, t, ha="center", fontsize=5.5, color=INK2)
    kax.text(-0.2, 0.45, "acpp", fontsize=7, va="center", ha="right", color=INK2); kax.text(-0.2, 1.45, "DPC++", fontsize=7, va="center", ha="right", color=INK2)
    kax.text(2, 3.0, "key: one cell", ha="center", fontsize=7, color=INK2)
    fig.suptitle("Sweep 2 options relative to their base: system × direction × compiler × copy size", x=0.02, ha="left", y=0.99, fontsize=12.5)
    fig.text(0.02, 0.976, "Each cell: top row acpp, bottom row DPC++; left to right copy size 64Ki, 1Mi, 4Mi, 16Mi " + BYTES_NOTE.replace("; useful", ".\nUseful") + ".\n"
             f"Staging {BASE_NOTE['staging']}.\nHost kernel {BASE_NOTE['host kernel']}. Geometric mean over shapes at each row count, median of 3 runs.", ha="left", va="top", fontsize=8, color=INK2)
    add_colorbar(fig, [0.9, 0.45, 0.014, 0.25])
    out = os.path.join(ROOT, "results", "overview.png")
    fig.savefig(out, dpi=110)
    print(out)


if __name__ == "__main__":
    main()
