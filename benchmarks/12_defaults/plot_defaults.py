import os
import re
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter, NullFormatter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyze_defaults import SYSTEMS, load  # noqa: E402

# Charts of the defaults sweep (run analyze_defaults.py first; it writes results/ratios_<app>.csv):
#   curves_<app>.png      every numeric option over its values: bandwidth / base (geometric mean over the data shapes, large copies),
#                         one line per system, host to device and device to host; the copylib default is marked
#   max_elem_<app>.png    host kernel, 32 / 128-byte rows: GB/s over COPYLIB_MAX_ELEM_SIZE per system and direction
#   small_copies_<app>.png  bandwidth over the copy size for the base vs. WARMUP=1 (host kernel) and vs. HSA_ENABLE_SDMA=0 (staging),
#                         4-byte rows with an 8-byte pitch: the options that only act on small copies
# Usage: python 12_defaults/plot_defaults.py [--app acpp|dpcpp]

HERE = os.path.dirname(os.path.abspath(__file__))
INK, MUTED, SURFACE, GRID = "#0b0b0b", "#52514e", "#fcfcfb", "#e4e3df"
SYSTEM_STYLE = {"gpuc4": dict(color="#2a78d6", marker="o"), "ifi": dict(color="#eb6834", marker="s"),
                "lumi": dict(color="#1baf7a", marker="^")}  # categorical slots 1-3 (validated); marker = secondary encoding
NAMES = {"gpuc4": "gpuc4", "ifi": "ifi", "lumi": "LUMI"}
KiB, MiB = 1024, 1024 ** 2

# family: (variant, title, config prefix, value of the base, value parser, x label)
def size(v):
    return 0 if v == "whole" else int(v[:-3]) * (KiB if v.endswith("KiB") else MiB)


FAMILIES = [
    ("staging", "staging: chunk size (staging = workers × chunk)", "staging_chunk_", 4 * MiB, size, "chunk"),
    ("host kernel", "host kernel: chunk size (0 = one kernel per copy)", "hk_chunk_", 16 * MiB, size, "chunk"),
    ("host kernel", "host kernel: queues (kernels in flight)", "hk_queues_", 2, int, "queues"),
    ("host kernel", "host kernel: work-group size", "hk_wg_", 32, int, "work-group size"),
    ("host kernel", "host kernel: elements per work item", "hk_elems_", 1, int, "elements per item"),
    ("host kernel", "host kernel: widest access (32 / 128 B rows only)", "hk_max_elem_", 64, int, "bytes"),
]


def style(ax):
    ax.set_facecolor(SURFACE)
    ax.grid(True, color=GRID, linewidth=1)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.tick_params(colors=INK, labelsize=8)


def label_size(b):
    return "whole" if b == 0 else f"{b // MiB} MiB" if b >= MiB else f"{b // KiB} KiB"


def curves(r, out, app):
    gm = lambda v: float(np.exp(np.log(v).mean()))
    fig, axes = plt.subplots(len(FAMILIES), 2, figsize=(12, 3.0 * len(FAMILIES)), facecolor=SURFACE, sharey=True)
    for row, (variant, title, prefix, base_value, parse, xlabel) in enumerate(FAMILIES):
        base = "staging_base" if variant == "staging" else "hk_base"
        x = r[(r.config.str.startswith(prefix) & ~r.config.str.contains("hw_queues")) | (r.config == base)].copy()
        if prefix == "hk_max_elem_":
            x = x[x["shape"].str.contains("32 B|128 B")]
        x["value"] = [base_value if c == base else parse(c[len(prefix):]) for c in x.config]
        values = sorted(x.value.unique())
        pos = {v: i for i, v in enumerate(values)}
        for col, (direction, what) in enumerate((("h2d", "host → device"), ("d2h", "device → host"))):
            ax = axes[row][col]
            style(ax)
            for system in SYSTEMS:
                g = x[(x.system == system) & (x.direction == direction)].groupby("value").large.agg(gm)
                if len(g) < 2:
                    continue
                ax.plot([pos[v] for v in g.index], g.values, linewidth=2, markersize=8, markeredgecolor=SURFACE, markeredgewidth=1.5,
                        label=NAMES[system], **SYSTEM_STYLE[system])
            ax.axvline(pos[base_value], color=MUTED, linewidth=1, linestyle=":")
            ax.axhline(1, color=MUTED, linewidth=1)
            ax.set_xticks(range(len(values)))
            ax.set_xticklabels([label_size(v) if xlabel == "chunk" else str(v) for v in values], fontsize=8)
            ax.set_xlim(-0.4, len(values) - 0.2)
            ax.set_yscale("log", base=2)
            ax.set_ylim(0.45, 4)
            ax.set_yticks([0.5, 0.71, 1, 1.41, 2, 4])
            ax.set_yticklabels(["0.5×", "0.71×", "1×", "1.41×", "2×", "4×"])
            ax.set_title(f"{title}, {what}", fontsize=9.5, color=INK, loc="left")
            if col == 0:
                ax.set_ylabel("bandwidth / base", fontsize=8, color=INK)
    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper right", bbox_to_anchor=(0.99, 0.995), fontsize=9, frameon=False, ncol=3)
    fig.suptitle(f"Defaults sweep: bandwidth relative to the variant's base over each option's values, large copies ({app})",
                 fontsize=12, color=INK, x=0.01, ha="left")
    fig.text(0.01, 0.004, "geometric mean over the data shapes (4 B rows pitch 8 / 16 B, 4 / 32 / 128 B rows pitch 256 B); dotted line = "
             "the base's value (staging: worker sweep's recommendation, host kernel: copylib's default); log scale", fontsize=7.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.01, 1, 0.98))
    path = os.path.join(out, f"curves_{app}.png")
    fig.savefig(path, dpi=140, facecolor=SURFACE)
    plt.close(fig)
    return path


def max_elem(r, out, app):
    x = r[(r.config.str.startswith("hk_max_elem_") | (r.config == "hk_base")) & r["shape"].str.contains("32 B|128 B")].copy()
    x["value"] = [64 if c == "hk_base" else int(c.rsplit("_", 1)[1]) for c in x.config]
    systems = [s for s in SYSTEMS if (x[x.system == s].value.nunique() > 1)]
    shapes = ["32 B rows, pitch 256 B", "128 B rows, pitch 256 B"]
    fig, axes = plt.subplots(len(systems), 2, figsize=(11, 3.1 * len(systems)), facecolor=SURFACE, squeeze=False)
    values = [4, 8, 16, 32, 64]
    for i, system in enumerate(systems):
        for j, shape in enumerate(shapes):
            ax = axes[i][j]
            style(ax)
            g = x[(x.system == system) & (x["shape"] == shape)]
            for k, (direction, color, what) in enumerate((("h2d", "#2a78d6", "host → device"), ("d2h", "#eb6834", "device → host"))):
                v = g[g.direction == direction].set_index("value").gbps.reindex(values)
                bars = ax.bar(np.arange(len(values)) + (k - 0.5) * 0.38, v.values, width=0.36, color=color, label=what,
                              edgecolor=SURFACE, linewidth=2)
                for b, val in zip(bars, v.values):
                    if not np.isnan(val):
                        ax.text(b.get_x() + b.get_width() / 2, val, f"{val:.0f}" if val >= 10 else f"{val:.1f}", ha="center",
                                va="bottom", fontsize=7, color=INK)
            ax.set_xticks(range(len(values)))
            ax.set_xticklabels([f"{v}" + (" (default)" if v == 64 else "") for v in values], fontsize=8)
            ax.set_title(f"{NAMES[system]}, {shape}", fontsize=9.5, color=INK, loc="left")
            ax.set_ylabel("GB/s (useful bytes)", fontsize=8, color=INK)
            ax.margins(y=0.15)
            if i == len(systems) - 1:
                ax.set_xlabel("COPYLIB_MAX_ELEM_SIZE (bytes per access)", fontsize=8, color=INK)
    axes[0][1].legend(loc="upper left", fontsize=8, frameon=False)
    fig.suptitle(f"Host kernel: widest access per work item, large copies ({app})", fontsize=12, color=INK, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    path = os.path.join(out, f"max_elem_{app}.png")
    fig.savefig(path, dpi=140, facecolor=SURFACE)
    plt.close(fig)
    return path


def small_copies(d, out, app):
    d = d[(d.application == f"Celerity-{app}") & (d.program == "strided_transfer") & (d.M == 2)]
    pairs = [("hk_base", "hk_warmup", "host kernel: COPYLIB_WARMUP"), ("staging_base", "staging_sdma_off", "staging: HSA_ENABLE_SDMA")]
    fig, axes = plt.subplots(2, 2 * len(SYSTEMS), figsize=(18, 7), facecolor=SURFACE, sharex=True)
    for row, (base, other, title) in enumerate(pairs):
        for si, system in enumerate(SYSTEMS):
            for k, (col, what) in enumerate((("copy_bandwidth", "host → device"), ("d2h_gbps", "device → host"))):
                ax = axes[row][si * 2 + k]
                style(ax)
                for cfg, color, name in ((base, "#52514e", "base"), (other, "#2a78d6", other.split("_", 1)[1])):
                    g = d[(d.system == system) & (d.config == cfg)].groupby("N")[col].median()
                    if len(g):
                        ax.plot(g.index * 4, g.values, color=color, marker="o", markersize=5, linewidth=2, label=name)
                ax.set_xscale("log", base=2)
                ax.set_yscale("log")
                ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
                lo, hi = ax.get_ylim()
                ax.yaxis.set_minor_formatter(FuncFormatter(lambda v, _: f"{v:.3g}") if hi / lo < 10 else NullFormatter())
                ax.set_title(f"{NAMES[system]}, {what}", fontsize=9, color=INK, loc="left")
                if si == 0 and k == 0:
                    ax.set_ylabel(f"{title}\nGB/s (log)", fontsize=8.5, color=INK, labelpad=2)
                if row == 1:
                    ax.set_xlabel("useful bytes per copy", fontsize=8, color=INK)
                ticks = [2 ** 18, 2 ** 22, 2 ** 26, 2 ** 30]
                ax.set_xticks(ticks)
                ax.set_xticklabels(["256 KiB", "4 MiB", "64 MiB", "1 GiB"], fontsize=7.5)
                if si == 1 and k == 0:  # ifi: both configurations are complete on every system but gpuc4 (sweep still running)
                    ax.legend(fontsize=8, frameon=False, loc="lower right")
    fig.suptitle(f"Options that act on small copies: bandwidth over the copy size, 4-byte rows with an 8-byte pitch ({app}; "
                 "host → device is the first access, incl. one-off costs)", fontsize=11, color=INK, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    path = os.path.join(out, f"small_copies_{app}.png")
    fig.savefig(path, dpi=140, facecolor=SURFACE)
    plt.close(fig)
    return path


def main():
    app = sys.argv[sys.argv.index("--app") + 1] if "--app" in sys.argv else "acpp"
    out = os.path.join(HERE, "results")
    r = pd.read_csv(os.path.join(out, f"ratios_{app}.csv"))
    print(curves(r, out, app))
    print(max_elem(r, out, app))
    print(small_copies(pd.concat([load(s) for s in SYSTEMS], ignore_index=True), out, app))


if __name__ == "__main__":
    main()
