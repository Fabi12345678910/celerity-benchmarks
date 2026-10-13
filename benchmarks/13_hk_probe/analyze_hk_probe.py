import os
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Analyzes the gpuc4 host-kernel slowdown study (13_hk_probe/results/gpuc4_hk_probe.csv, see make_hk_probe_yamls.py).
# Per configuration: median, 95% confidence interval of the mean (t, 10 runs) and coefficient of variation over the runs; every run's
# check must be ok. Writes 13_hk_probe/results/summary.csv and hk_probe.png:
#   (a) device -> host bandwidth of 4-byte rows over the pitch: copylib's host-kernel order, the two safe kernel fixes, the unsafe
#       read-modify-write, Celerity's host kernel and Celerity's staging (both through the real stack)
#   (b) device -> host rows per second over the row width at a 256-byte pitch (the cost is per row, not per byte)
#   (c) device -> host rows per second over the distance between two writes to the same 64-byte line (the slow window)
# Usage: python 13_hk_probe/analyze_hk_probe.py

HERE = os.path.dirname(os.path.abspath(__file__))
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
STAGING, HOSTK, PHASE, RMW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"  # categorical slots 1-4 (staging/host kernel as in 11_consistency/)
T95 = {n: t for n, t in zip(range(2, 13), (12.71, 4.30, 3.18, 2.78, 2.57, 2.45, 2.36, 2.31, 2.26, 2.23, 2.20))}


def load():
    d = pd.read_csv(os.path.join(HERE, "results", "gpuc4_hk_probe.csv"))
    d = d.loc[:, ~d.columns.str.contains(r"\.\d+$")]
    bad = d[d.check != "ok"]
    if len(bad):
        print(f"WARNING: {len(bad)} runs failed their check:\n{bad[['application', 'command']].to_string()}")
    return d[d.check == "ok"].copy()


def stats(v):
    v = np.asarray(v, dtype=float)
    n = len(v)
    half = T95.get(n, 1.96) * v.std(ddof=1) / np.sqrt(n) if n > 1 else np.nan
    return pd.Series(dict(n=n, median=np.median(v), mean=v.mean(), ci95=half, cv=v.std(ddof=1) / v.mean() if n > 1 else np.nan,
                          min=v.min(), max=v.max()))


def summarize(d):
    probe = d[d.tool == "hk_probe"]
    keys = ["application", "dir", "S", "P", "E", "rows", "order"]
    p = probe.groupby(keys).gbps.apply(stats).unstack().reset_index()
    p["mrows_per_s"] = p["median"] * 1e3 / p.S
    cel = d[d.tool == "Celerity-acpp"].copy()
    cel["P"] = cel.M * 4
    rows = []
    for (app, n, m), g in cel.groupby(["application", "N", "M"]):
        for col, direction in (("copy_bandwidth", "r"), ("d2h_gbps", "w")):
            s = stats(g[col])
            rows.append(dict(application=app, dir=direction, S=4, P=m * 4, E=4, rows=n, order="celerity", **s.to_dict()))
    c = pd.DataFrame(rows)
    c["mrows_per_s"] = c["median"] * 1e3 / 4
    return pd.concat([p, c], ignore_index=True)


def style(ax, title):
    ax.set_facecolor(SURFACE)
    ax.grid(True, color=GRID, linewidth=1)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(MUTED)
    ax.tick_params(colors=INK, labelsize=8.5)
    ax.set_title(title, fontsize=10.5, color=INK, loc="left")


def line(ax, x, y, err, color, marker, label, label_at=None, dy=1.0):
    ax.errorbar(x, y, yerr=err, color=color, linewidth=2, marker=marker, markersize=7, markeredgecolor=SURFACE, markeredgewidth=1.5,
                capsize=0, elinewidth=1.5, zorder=3, label=label)
    if label_at is not None:
        i = list(x).index(label_at)
        ax.annotate(label, (x[i], y[i] * dy), textcoords="offset points", xytext=(6, 0), fontsize=8.5, color=INK, va="center")


def plot(s, out):
    fig, axes = plt.subplots(1, 3, figsize=(17, 5.6), facecolor=SURFACE, gridspec_kw=dict(width_ratios=[1.6, 1, 1]))
    w = s[s.dir == "w"]

    # (a) 4-byte rows, device -> host, over the pitch
    ax = axes[0]
    nat = w[(w.application.isin(["w_pitch", "w_pitch_far"])) & (w.S == 4)].sort_values("P")
    series = [
        (w[(w.application == "celerity_staging") & (w.rows == 16777216)].sort_values("P"), STAGING, "s", "Celerity staging"),
        (w[(w.application == "w_fix") & (w.order == "rmw")].sort_values("P"), RMW, "D", "read-modify-write lines (unsafe)"),
        (pd.concat([w[(w.application == "w_fix") & (w.order == "phase")], nat[nat.P >= 64]]).sort_values("P"), PHASE, "^",
         "one launch per line slot"),
        (nat, HOSTK, "o", "host kernel as in copylib"),
        (w[(w.application == "celerity_hk") & (w.rows == 16777216)].sort_values("P"), INK, "x", "Celerity host kernel"),
    ]
    for g, color, marker, label in series:
        if len(g):
            line(ax, g.P.values, g["median"].values, g.ci95.values, color, marker, label)
    ax.set_xscale("log", base=2)
    ax.set_yscale("log")
    ax.set_xticks([8, 16, 32, 64, 128, 256, 1024])
    ax.set_xticklabels(["8", "16", "32", "64", "128", "256", "1024"])
    ax.axvspan(6, 64, color=GRID, alpha=0.45, zorder=0)
    ax.text(22, 0.13, "several rows share a 64-byte line", fontsize=8, color=MUTED, ha="center")
    ax.set_yticks([0.15, 0.25, 0.5, 1, 2, 4])
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:g}"))
    ax.yaxis.set_minor_formatter(plt.NullFormatter())
    ax.set_xlabel("row pitch in bytes (4 useful bytes per row)", color=INK, fontsize=9)
    ax.set_ylabel("device → host, useful GB/s (log)", color=INK, fontsize=9)
    ax.legend(loc="upper right", fontsize=8.5, frameon=False)
    style(ax, "(a) 4-byte rows, device → host on gpuc4 (PCIe)")

    # (b) rows per second over the row width, pitch 256 B
    ax = axes[1]
    g = w[w.application == "w_width"].sort_values("S")
    line(ax, g.S.values, g.mrows_per_s.values, g.ci95.values * 1e3 / g.S.values, HOSTK, "o", "host kernel")
    ax.set_xscale("log", base=2)
    ax.set_xticks(g.S.values)
    ax.set_xticklabels([str(int(v)) for v in g.S.values])
    ax.set_ylim(0, max(200, g.mrows_per_s.max() * 1.15))
    for x, y, gb in zip(g.S.values, g.mrows_per_s.values, g["median"].values):
        ax.annotate(f"{gb:.2g} GB/s", (x, y), textcoords="offset points", xytext=(0, 9), fontsize=8, color=MUTED, ha="center")
    ax.set_xlabel("row width in bytes (pitch 256 B)", color=INK, fontsize=9)
    ax.set_ylabel("million rows per second", color=INK, fontsize=9)
    style(ax, "(b) the cost is per row, not per byte")

    # (c) the slow window: distance between two writes to one 64-byte line
    ax = axes[2]
    g = w[(w.application == "w_distance")].copy()
    g["D"] = g.order.str[1:].astype(int)
    base = w[(w.application == "w_pitch") & (w.P == 8)]
    xs = np.r_[1, g.sort_values("D").D.values]
    ys = np.r_[base.mrows_per_s.values[:1], g.sort_values("D").mrows_per_s.values]
    es = np.r_[base.ci95.values[:1] * 250, g.sort_values("D").ci95.values * 250]
    line(ax, xs, ys, es, HOSTK, "o", "4-byte rows, pitch 8 B")
    ax.set_xscale("log", base=2)
    ax.set_xticks([1, 16, 256, 4096, 16384, 65536])
    ax.set_xticklabels(["1", "16", "256", "4k", "16k", "64k"])
    ax.set_ylim(0, 200)
    ax.axvline(4096 * 1024 / 64, color=MUTED, linewidth=1, linestyle="--")
    ax.text(4096 * 1024 / 64 / 1.3, 20, "65,536 lines × 64 B\n= 4 MiB = the GPU's L2", fontsize=8, color=MUTED, ha="right")
    ax.set_xlabel("other lines written between two writes to one line", color=INK, fontsize=9)
    ax.set_ylabel("million rows per second", color=INK, fontsize=9)
    style(ax, "(c) a repeated partial write to a line still in L2 is slow")

    fig.text(0.01, 0.01, "Median of 10 runs (each the median of 5 in-process repetitions), error bars 95% confidence interval of the mean. "
             "hk_probe: plain HIP, pinned host memory (hipHostMallocDefault), no Celerity. Celerity: strided_transfer, acpp, 014e21a, 2^24 rows.",
             fontsize=7.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    path = os.path.join(out, "hk_probe.png")
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    return path


def main():
    d = load()
    s = summarize(d)
    out = os.path.join(HERE, "results")
    s.to_csv(os.path.join(out, "summary.csv"), index=False)
    pd.set_option("display.width", 220)
    pd.set_option("display.max_rows", 200)
    cols = ["application", "dir", "S", "P", "E", "rows", "order", "n", "median", "ci95", "cv", "min", "max", "mrows_per_s"]
    print(s[cols].round(4).to_string(index=False))
    print(plot(s, out))


if __name__ == "__main__":
    sys.exit(main())
