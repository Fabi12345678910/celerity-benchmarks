import os
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

# Staging vs. host kernel over all measured data shapes and systems (build 014e21a, acpp, largest size of each benchmark):
#   4-byte rows, host strided, pitch 8/16 B   06_cores/ (1 GiB, staging = the recommended workers, dynamic; host kernel = reference)
#   4-byte rows, host strided, pitch 64-256 B 09_sparse/<system>_sparse (64 MiB)
#   4-byte rows, host and device strided      09_sparse/<system>_both (+ _both_dpcpp64, 64 MiB)
#   32/64/128-byte rows, pitch 256 B          10_rows/ (512 MiB - 2 GiB)
# Host to device of the 64 MiB-and-larger runs has the fixed first-access cost removed ((bytes(Nmax) - bytes(Nmin)) / (t(Nmax) - t(Nmin)));
# the 1 GiB runs are used as measured. Writes 11_consistency/results/scenarios.csv and two charts:
#   winner_map.png     staging / host kernel per system, direction and data shape (diverging: blue = staging faster, red = host kernel)
#   consistency.png    each method's bandwidth as a share of the faster method, per scenario (the spread and worst case per method)
# Usage: python 11_consistency/consistency.py

HERE = os.path.dirname(os.path.abspath(__file__))
B = os.path.join(HERE, "..")
SYSTEMS = ["gpuc4", "ifi", "lumi"]
BEST = {"gpuc4": "workers_04_dynamic", "ifi": "workers_08_dynamic", "lumi": "workers_04_dynamic"}
APP = "Celerity-acpp"
INK, MUTED, SURFACE = "#0b0b0b", "#52514e", "#fcfcfb"
STAGING, HOSTK = "#2a78d6", "#eb6834"  # categorical slots 1, 2 (validated)
DIVERGING = LinearSegmentedColormap.from_list("hk_staging", ["#e34948", "#f0efec", "#2a78d6"])  # red <- gray -> blue


def corrected(g, col):
    """bandwidth with the time of the smallest run subtracted; g: rows of one configuration over N"""
    t = (g.useful / (g[col] * 1e9)).groupby(g.N).median()
    b = g.groupby("N").useful.first()
    lo, hi = b.index.min(), b.index.max()
    return (b[hi] - b[lo]) / (t[hi] - t[lo]) / 1e9


def scenarios():
    rows = []

    def add(system, shape, order, mode, g, h2d_corr):
        g = g[(g.check == "ok") & (g.application == APP)]
        big = g[g.N == g.N.max()]
        h2d = corrected(g, "copy_bandwidth") if h2d_corr else big.copy_bandwidth.median()
        cv = lambda c: (big[c].std() / big[c].mean()) if len(big) > 1 else np.nan
        rows.append(dict(system=system, shape=shape, order=order, mode=mode, h2d=h2d, d2h=big.d2h_gbps.median(),
                         cv_h2d=cv("copy_bandwidth"), cv_d2h=cv("d2h_gbps")))

    for s in SYSTEMS:
        for cfg, mode in ((BEST[s], "staging"), ("reference_host_kernel", "host kernel")):
            d = pd.read_csv(os.path.join(B, "06_cores", s, "results", f"{cfg}.csv"))
            d = d[d.N == d.N.max()]
            for m in (2, 4):
                add(s, f"pitch {m * 4} B", m, mode, d[d.M == m].assign(useful=lambda x: x.N * 4), False)
        for kind, label, ms in (("sparse", "pitch {} B", (16, 32, 64)), ("both", "pitch {} B ", (2, 4, 16, 32, 64))):
            d = pd.read_csv(os.path.join(B, "09_sparse", "results", f"{s}_{kind}.csv"))
            fix = os.path.join(B, "09_sparse", "results", f"{s}_{kind}_dpcpp64.csv")
            if os.path.exists(fix):
                d = pd.concat([d[~((d.application == "Celerity-dpcpp") & (d.M == 64) & (d.N >= 2 ** 22))], pd.read_csv(fix)])
            d["mode"] = d.env.str.contains("HOST_KERNEL").map({True: "host kernel", False: "staging"})
            d["useful"] = d.N * 4
            for m in ms:
                for mode in ("staging", "host kernel"):
                    add(s, label.format(m * 4), (100 if kind == "both" else 0) + m, mode, d[(d.M == m) & (d["mode"] == mode)], True)
        d = pd.read_csv(os.path.join(B, "10_rows", "results", f"{s}_rows.csv"))
        d["mode"] = d.env.str.contains("HOST_KERNEL").map({True: "host kernel", False: "staging"})
        d["useful"] = d.N * d.W * 4
        for w in (8, 16, 32):
            for mode in ("staging", "host kernel"):
                add(s, f"{w * 4} B rows", 200 + w, mode, d[(d.W == w) & (d["mode"] == mode)], True)
    t = pd.DataFrame(rows)
    long = t.melt(id_vars=["system", "shape", "order", "mode"], value_vars=["h2d", "d2h"], var_name="direction", value_name="gbps")
    w = long.pivot_table(index=["system", "direction", "shape", "order"], columns="mode", values="gbps").reset_index()
    w["ratio"] = w["staging"] / w["host kernel"]
    best = w[["staging", "host kernel"]].max(axis=1)
    w["staging_share"] = w["staging"] / best
    w["hk_share"] = w["host kernel"] / best
    cvs = t.melt(id_vars=["system", "mode"], value_vars=["cv_h2d", "cv_d2h"], value_name="cv")
    return w.sort_values(["system", "direction", "order"]), cvs


def winner_map(w, out):
    shapes = w.drop_duplicates("order").sort_values("order")
    cols = list(shapes["shape"])
    rows = [(s, d) for s in SYSTEMS for d in ("h2d", "d2h")]
    grid = np.full((len(rows), len(cols)), np.nan)
    for i, (s, d) in enumerate(rows):
        for j, c in enumerate(cols):
            x = w[(w.system == s) & (w.direction == d) & (w["shape"] == c)]
            if len(x):
                grid[i, j] = x.ratio.iloc[0]
    fig, ax = plt.subplots(figsize=(19, 6.8), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    im = ax.imshow(np.log2(grid), cmap=DIVERGING, vmin=-5, vmax=5, aspect="auto")
    for i in range(len(rows)):
        for j in range(len(cols)):
            r = grid[i, j]
            if np.isnan(r):
                continue
            txt = f"S {r:.1f}×" if r >= 1 else f"H {1 / r:.1f}×"
            strong = abs(np.log2(r)) > 2.5
            ax.text(j, i, txt, ha="center", va="center", fontsize=9, color="#ffffff" if strong else INK)
    ax.set_xticks(range(len(cols)))
    ax.set_xticklabels(cols, fontsize=8, color=INK)
    ax.set_yticks(range(len(rows)))
    names = {"h2d": "host → device", "d2h": "device → host"}
    ax.set_yticklabels([f"{'LUMI' if s == 'lumi' else s} {names[d]}" for s, d in rows], fontsize=10, color=INK)
    for x, label in ((2, "4-byte rows, host side strided"), (7, "4-byte rows, host and device strided"), (11, "wider rows, 256-byte pitch")):
        ax.text(x, -0.75, label, ha="center", va="bottom", fontsize=10, color=INK, fontweight="bold")
    for x in (4.5, 9.5):  # separators between the three data-shape groups
        ax.axvline(x, color=SURFACE, linewidth=6)
    for y in (1.5, 3.5):
        ax.axhline(y, color=SURFACE, linewidth=6)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(length=0)
    cb = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.01)
    cb.set_ticks([-5, -3, -1, 0, 1, 3, 5])
    cb.set_ticklabels(["host kernel 32× faster", "8×", "2×", "tie", "2×", "8×", "staging 32× faster"], fontsize=8, color=INK)
    cb.outline.set_visible(False)
    ax.set_title("Which method is faster, and by how much (acpp): S = staging, H = host kernel, × = its lead", fontsize=12, color=INK,
                 loc="left", pad=40)
    fig.text(0.01, 0.01, "blue: staging faster, red: host kernel faster. 1 GiB per copy (pitch 8/16 B, host side strided) or 64 MiB - 2 GiB; "
             "host→device of the runs below 1 GiB with the fixed first-access cost removed.", fontsize=8, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    path = os.path.join(out, "winner_map.png")
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    return path


def consistency(w, out):
    groups = SYSTEMS + ["all systems"]
    fig, ax = plt.subplots(figsize=(14, 7.5), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    rng = np.random.default_rng(1)
    for gi, g in enumerate(groups):
        x = w if g == "all systems" else w[w.system == g]
        for k, (col, color, name) in enumerate((("staging_share", STAGING, "staging"), ("hk_share", HOSTK, "host kernel"))):
            pos = gi * 3 + k
            v = x[col].values * 100
            ax.scatter(pos + rng.uniform(-0.25, 0.25, len(v)), v, s=36, color=color, edgecolor=SURFACE, linewidth=1.5, zorder=3,
                       label=name if gi == 0 else None)
            med = np.median(v)
            ax.plot([pos - 0.35, pos + 0.35], [med, med], color=INK, linewidth=2, zorder=4)
            ax.text(pos, -6, f"median {med:.0f}%", fontsize=8, color=INK, ha="center")
            ax.text(pos, -11, f"worst {v.min():.0f}%", fontsize=8, color=MUTED, ha="center")
    ax.set_xticks([gi * 3 + 0.5 for gi in range(len(groups))])
    ax.set_xticklabels(["LUMI" if g == "lumi" else g for g in groups], fontsize=11, color=INK)
    ax.set_ylim(-14, 105)
    ax.set_yticks(range(0, 101, 20))
    ax.set_ylabel("bandwidth as % of the faster method in that scenario", color=INK)
    ax.grid(True, axis="y", color="#e4e3df", linewidth=1)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.legend(loc="lower right", bbox_to_anchor=(1, 1.0), ncol=2, fontsize=10, frameon=False)
    ax.set_title("How close each method stays to the better one, over all data shapes and both directions (acpp)", fontsize=12,
                 color=INK, loc="left")
    fig.text(0.01, 0.01, "one dot per scenario (system × direction × data shape, 26 per system); 100% = that method was the faster one; "
             "black bar = median", fontsize=8, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    path = os.path.join(out, "consistency.png")
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    return path


def main():
    out = os.path.join(HERE, "results")
    os.makedirs(out, exist_ok=True)
    w, cvs = scenarios()
    w.to_csv(os.path.join(out, "scenarios.csv"), index=False)
    pd.set_option("display.width", 200)
    summary = []
    for g, x in [(s, w[w.system == s]) for s in SYSTEMS] + [("all", w)]:
        for col, name in (("staging_share", "staging"), ("hk_share", "host kernel")):
            v = x[col]
            summary.append(dict(group=g, method=name, scenarios=len(v), wins=int((v >= 0.999).sum()), within_20pct=int((v >= 0.8).sum()),
                                median=v.median(), geomean=float(np.exp(np.log(v).mean())), worst=v.min()))
    print(pd.DataFrame(summary).round(2).to_string(index=False))
    print("\nrun-to-run spread (coefficient of variation of the 3 runs at the largest size), median over scenarios:")
    print(cvs.groupby(["system", "mode"]).cv.median().unstack().round(3).to_string())
    print(winner_map(w, out))
    print(consistency(w, out))


if __name__ == "__main__":
    main()
