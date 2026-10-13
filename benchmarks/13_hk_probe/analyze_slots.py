import glob
import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

# Analyzes the check of the proposed copylib change (13_hk_probe/results/<system>_slots.csv, see make_slots_yamls.py): device -> host
# bandwidth of the proposed launch pattern (filter) and the compact variant (phase) relative to copylib today (natural), per system,
# shape and size. A ratio counts as a loss if it is below 1 by more than the run-to-run noise: ratio < 1 - max(3%, 2 x the larger
# coefficient of variation of the two configurations' 5 runs). Writes 13_hk_probe/results/slots_summary.csv and slots.png (heatmap).
# Usage: python 13_hk_probe/analyze_slots.py

HERE = os.path.dirname(os.path.abspath(__file__))
SYSTEMS = ["gpuc4", "ifi", "lumi"]
INK, MUTED, SURFACE = "#0b0b0b", "#52514e", "#fcfcfb"
DIVERGING = LinearSegmentedColormap.from_list("worse_better", ["#e34948", "#f0efec", "#2a78d6"])  # red worse <- gray -> blue better


def load():
    frames = []
    for f in sorted(glob.glob(os.path.join(HERE, "results", "*_slots.csv"))):
        d = pd.read_csv(f)
        d = d.loc[:, ~d.columns.str.contains(r"\.\d+$")]
        d["system"] = os.path.basename(f).split("_")[0]
        frames.append(d)
    d = pd.concat(frames, ignore_index=True)
    bad = d[d.check != "ok"]
    if len(bad):
        print(f"WARNING: {len(bad)} runs failed their check")
    return d[d.check == "ok"]


def summarize(d):
    g = d.groupby(["system", "S", "P", "rows", "order"]).gbps
    s = pd.DataFrame({"median": g.median(), "cv": g.std() / g.mean(), "n": g.size()}).reset_index()
    w = s.pivot_table(index=["system", "S", "P", "rows"], columns="order", values=["median", "cv"]).reset_index()
    w.columns = ["_".join(c).strip("_") for c in w.columns]
    for o in ("filter", "phase"):
        w[f"{o}_ratio"] = w[f"median_{o}"] / w["median_natural"]
        noise = np.maximum(0.03, 2 * np.maximum(w[f"cv_{o}"], w["cv_natural"]))
        w[f"{o}_verdict"] = np.where(w[f"{o}_ratio"] < 1 - noise, "loss", np.where(w[f"{o}_ratio"] > 1 + noise, "gain", "same"))
    return w


def heatmap(w, out):
    shapes = w[["S", "P"]].drop_duplicates().sort_values(["P", "S"]).itertuples(index=False)
    shapes = [tuple(x) for x in shapes]
    sizes = sorted(w.rows.unique())
    cols = [(sy, r) for sy in SYSTEMS for r in sizes if ((w.system == sy) & (w.rows == r)).any()]
    grid = np.full((len(shapes), len(cols)), np.nan)
    for i, (s, p) in enumerate(shapes):
        for j, (sy, r) in enumerate(cols):
            x = w[(w.system == sy) & (w.rows == r) & (w.S == s) & (w.P == p)]
            if len(x):
                grid[i, j] = x.filter_ratio.iloc[0]
    fig, ax = plt.subplots(figsize=(12, 0.42 * len(shapes) + 2.4), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    im = ax.imshow(np.log2(grid), cmap=DIVERGING, vmin=-2, vmax=2, aspect="auto")
    for i in range(len(shapes)):
        for j in range(len(cols)):
            v = grid[i, j]
            if not np.isnan(v):
                ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=8.5, color="#ffffff" if abs(np.log2(v)) > 1.2 else INK)
    ax.set_xticks(range(len(cols)))
    ax.set_xticklabels([f"{'LUMI' if sy == 'lumi' else sy}\n{r // 1024}k rows" for sy, r in cols], fontsize=9, color=INK)
    ax.set_yticks(range(len(shapes)))
    ax.set_yticklabels([f"{s} B rows, pitch {p} B" + ("  (unchanged)" if p >= 64 else "") for s, p in shapes], fontsize=9, color=INK)
    for x in np.arange(len(sizes), len(cols), len(sizes)) - 0.5:
        ax.axvline(x, color=SURFACE, linewidth=5)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(length=0)
    cb = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cb.set_ticks([-2, -1, 0, 1, 2])
    cb.set_ticklabels(["0.25× (worse)", "0.5×", "same", "2×", "4× (better)"], fontsize=8, color=INK)
    cb.outline.set_visible(False)
    ax.set_title("Proposed change (one launch per row slot of a 64-byte line): device → host bandwidth relative to copylib today",
                 fontsize=11, color=INK, loc="left")
    fig.text(0.01, 0.005, "hk_probe, pinned host memory; median of 5 runs each; blue = faster with the change. Rows with a pitch of 64 B or "
             "more keep one launch (controls).", fontsize=7.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    path = os.path.join(out, "slots.png")
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    return path


def main():
    w = summarize(load())
    out = os.path.join(HERE, "results")
    w.to_csv(os.path.join(out, "slots_summary.csv"), index=False)
    pd.set_option("display.width", 220)
    pd.set_option("display.max_rows", 300)
    cols = ["system", "S", "P", "rows", "median_natural", "median_filter", "filter_ratio", "filter_verdict", "median_phase", "phase_ratio",
            "phase_verdict", "cv_natural", "cv_filter"]
    print(w[cols].round(3).to_string(index=False))
    print("\nverdicts of the proposed change (filter) per system:")
    print(w.groupby("system").filter_verdict.value_counts().unstack(fill_value=0).to_string())
    print(heatmap(w, out))


if __name__ == "__main__":
    main()
