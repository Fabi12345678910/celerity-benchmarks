import glob
import re
import os
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

# Analyzes the defaults sweep (12_defaults/<system>/results/*.csv): every configuration relative to its variant's base, per system,
# data shape (4-byte rows pitch 8/16 B; 4/32/128-byte rows pitch 256 B) and direction.
#   large   bandwidth of the largest copy (strided_transfer: 1 GiB as measured; rows: host to device with the fixed first-access cost
#           removed, (bytes(Nmax) - bytes(Nmin)) / (t(Nmax) - t(Nmin)), device to host as measured)
#   all     geometric mean over every size of bandwidth / base bandwidth at the same size (small copies count as much as large ones)
# acpp only by default (DPC++'s first-access numbers are not reliable); --app dpcpp for DPC++, as measured.
# Writes 12_defaults/results/ratios_<app>.csv, summary_<app>.csv and defaults_<app>.png (heatmap: geometric mean over shapes per system
# and direction, large copies). Usage: python 12_defaults/analyze_defaults.py [--app acpp|dpcpp]

HERE = os.path.dirname(os.path.abspath(__file__))
SYSTEMS = ["gpuc4", "ifi", "lumi"]
INK, MUTED, SURFACE = "#0b0b0b", "#52514e", "#fcfcfb"
DIVERGING = LinearSegmentedColormap.from_list("worse_better", ["#e34948", "#f0efec", "#2a78d6"])  # red worse <- gray -> blue better


def load(system):
    d = pd.concat([pd.read_csv(f) for f in glob.glob(os.path.join(HERE, system, "results", "*.csv"))], ignore_index=True)
    d["system"] = system
    d["shape"] = np.where(d.program == "strided_transfer", "4 B rows, pitch " + (d.M * 4).astype(str) + " B",
                          (d.W * 4).astype(str) + " B rows, pitch 256 B")
    d["useful"] = d.N * d.W * 4
    return d


def corrected(g, col):
    t = (g.useful / (g[col] * 1e9)).groupby(g.N).median()
    b = g.groupby("N").useful.first()
    lo, hi = b.index.min(), b.index.max()
    return (b[hi] - b[lo]) / (t[hi] - t[lo]) / 1e9


def ratios(d, app):
    d = d[(d.application == f"Celerity-{app}") & (d.check == "ok")]
    rows = []
    for (system, variant, shape), g in d.groupby(["system", "variant", "shape"]):
        base = g[g.config == ("staging_base" if variant == "staging" else "hk_base")]
        bmed = base.groupby("N")[["copy_bandwidth", "d2h_gbps"]].median()
        for config, c in g.groupby("config"):
            cmed = c.groupby("N")[["copy_bandwidth", "d2h_gbps"]].median()
            for col, direction in (("copy_bandwidth", "h2d"), ("d2h_gbps", "d2h")):
                big = c.N.max()
                fix = app == "acpp" and direction == "h2d" and c.program.iloc[0] != "strided_transfer"
                v = corrected(c, col) if fix else cmed.loc[big, col]
                b = corrected(base[base.N.isin(c.N)], col) if fix else bmed.loc[big, col]
                common = cmed.index.intersection(bmed.index)
                rows.append(dict(system=system, variant=variant, config=config, shape=shape, direction=direction, gbps=v, base_gbps=b,
                                 large=v / b, all=float(np.exp(np.log(cmed.loc[common, col] / bmed.loc[common, col]).mean()))))
    return pd.DataFrame(rows)


def heatmap(s, out, app):
    for variant, prefix in (("staging", "staging_"), ("host kernel", "hk_")):
        x = s[s.variant == variant]
        def order(c):  # base first, then by option, values ascending (chunk sizes in bytes, "whole" = 0 first)
            m = re.match(r"(.*?)_(\d+)(KiB|MiB)?$", c)
            if c.endswith("_whole"):
                return (c != prefix + "base", c[:-len("_whole")], 0, c)
            if not m:
                return (c != prefix + "base", c, -1, c)
            return (True, m.group(1), int(m.group(2)) * {None: 1, "KiB": 1024, "MiB": 1024 ** 2}[m.group(3)], c)
        configs = sorted(x.config.unique(), key=order)
        cols = [(sy, di) for sy in SYSTEMS for di in ("h2d", "d2h") if ((x.system == sy) & (x.direction == di)).any()]
        grid = np.array([[x[(x.config == c) & (x.system == sy) & (x.direction == di)].large.squeeze() if
                          ((x.config == c) & (x.system == sy) & (x.direction == di)).any() else np.nan for sy, di in cols] for c in configs],
                        dtype=float)
        fig, ax = plt.subplots(figsize=(10, 0.36 * len(configs) + 2.2), facecolor=SURFACE)
        ax.set_facecolor(SURFACE)
        im = ax.imshow(np.log2(grid), cmap=DIVERGING, vmin=-1, vmax=1, aspect="auto")
        for i in range(len(configs)):
            for j in range(len(cols)):
                if not np.isnan(grid[i, j]):
                    ax.text(j, i, f"{grid[i, j]:.2f}", ha="center", va="center", fontsize=8,
                            color="#ffffff" if abs(np.log2(grid[i, j])) > 0.75 else INK)
        ax.set_xticks(range(len(cols)))
        ax.set_xticklabels([f"{'LUMI' if sy == 'lumi' else sy}\n{'host → device' if di == 'h2d' else 'device → host'}" for sy, di in cols],
                           fontsize=9, color=INK)
        ax.set_yticks(range(len(configs)))
        ax.set_yticklabels([c[len(prefix):] for c in configs], fontsize=9, color=INK, family="monospace")
        for xline in (1.5, 3.5):
            ax.axvline(xline, color=SURFACE, linewidth=5)
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.tick_params(length=0)
        cb = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
        cb.set_ticks([-1, -0.5, 0, 0.5, 1])
        cb.set_ticklabels(["0.5× (worse)", "0.71×", "same as base", "1.41×", "2× (better)"], fontsize=8, color=INK)
        cb.outline.set_visible(False)
        ax.set_title(f"{variant}: bandwidth relative to the base, large copies ({app})", fontsize=11, color=INK, loc="left")
        fig.text(0.01, 0.005, "geometric mean over the data shapes (4 B rows pitch 8/16 B, 4/32/128 B rows pitch 256 B; max_elem: 32/128 B "
                 "rows only); blue = faster than the base", fontsize=7.5, color=MUTED)
        fig.tight_layout(rect=(0, 0.02, 1, 1))
        path = os.path.join(out, f"defaults_{'staging' if variant == 'staging' else 'host_kernel'}_{app}.png")
        fig.savefig(path, dpi=150, facecolor=SURFACE)
        plt.close(fig)
        print(path)


def main():
    app = sys.argv[sys.argv.index("--app") + 1] if "--app" in sys.argv else "acpp"
    out = os.path.join(HERE, "results")
    os.makedirs(out, exist_ok=True)
    d = pd.concat([load(s) for s in SYSTEMS if glob.glob(os.path.join(HERE, s, "results", "*.csv"))], ignore_index=True)
    r = ratios(d, app)
    r.to_csv(os.path.join(out, f"ratios_{app}.csv"), index=False)
    gm = lambda v: float(np.exp(np.log(v).mean()))
    s = r.groupby(["variant", "config", "system", "direction"]).agg(large=("large", gm), worst=("large", "min"), best=("large", "max"),
                                                                    all=("all", gm)).reset_index()
    s.to_csv(os.path.join(out, f"summary_{app}.csv"), index=False)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_rows", 500)
    for variant in ("staging", "host kernel"):
        x = s[s.variant == variant]
        t = x.pivot_table(index="config", columns=["system", "direction"], values=["large", "all"]).round(2)
        print(f"\n=== {variant} ({app}): geometric mean over shapes of bandwidth / base, large copies and all sizes")
        print(t["large"].to_string())
        print(t["all"].to_string())
        o = r[r.variant == variant].groupby("config").agg(large=("large", gm), worst=("large", "min"), all=("all", gm)).round(2)
        print("overall (all systems, shapes, directions):")
        print(o.sort_values("large", ascending=False).to_string())
    heatmap(s, out, app)


if __name__ == "__main__":
    main()
