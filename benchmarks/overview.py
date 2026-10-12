"""The overview layout shared by the sweeps (the user's name for the c2 glyph chart): one row per setting, one cell per system x direction,
each cell a 2 x 4 glyph (top row acpp, bottom row DPC++; left to right four copy sizes). Colour = bandwidth relative to a reference on a
diverging scale 0.5x .. 2x: blue faster, red slower, grey equal. An empty outlined cell has no data (not run or not finished).
Portrait A4. Used by 03_config/plot_overview.py and 15_sweep3/plot_overview.py (12_defaults keeps the original c2 code)."""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

SURFACE, INK, INK2, MUTED, GRID, MID = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8984", "#e4e3df", "#f0efec"
CMAP = LinearSegmentedColormap.from_list("div", ["#e34948", MID, "#2a78d6"])
NORM = TwoSlopeNorm(vmin=-1, vcenter=0, vmax=1)  # log2 ratio, 0.5x .. 2x
SYSTEMS = [("gpuc4", "gpuc4"), ("ifi", "ifi"), ("lumi", "LUMI")]
DIRS = [("copy_bandwidth", "H → D"), ("d2h_gbps", "D → H")]
APPS = [("Celerity-acpp", "acpp"), ("Celerity-dpcpp", "DPC++")]


def gm(x):
    x = np.asarray(x, dtype=float)
    x = x[(x > 0) & np.isfinite(x)]
    return float(np.exp(np.log(x).mean())) if len(x) else np.nan


def draw(out, title, subtitle, sections, cell, size_labels, systems=SYSTEMS, dirs=DIRS, apps=APPS):
    """sections: [(section label or None, [(row label, group, key), ...]), ...]; a new group starts after a small gap, a new section
    after a larger one with its label written vertically on the left. cell(key, system, dir, app, size index) -> ratio or None."""
    plt.rcParams.update({"font.family": "DejaVu Sans", "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "text.color": INK,
                         "ytick.color": INK2})
    n_rows = sum(len(r) for _, r in sections)
    fs = float(np.clip(420 / max(n_rows, 1), 5.2, 8.5))
    fig = plt.figure(figsize=(8.27, 11.69))
    ax = fig.add_axes([0.24, 0.02, 0.74, 0.86])
    cw, gx = len(size_labels), 1.0
    ncol = len(systems) * len(dirs)

    def x0(ci):
        return ci * (cw + gx) + 0.6 * (ci // len(dirs))

    y, yt, yl, spans = 0.0, [], [], []
    for si, (slabel, rows) in enumerate(sections):
        if si:
            y += 1.8
        y_start, prev = y, None
        for label, group, key in rows:
            if prev is not None and group != prev:
                y += 0.9
            prev = group
            ci = 0
            for system, _ in systems:
                for dk, _ in dirs:
                    for ai, (app, _) in enumerate(apps):
                        for zi in range(cw):
                            val = cell(key, system, dk, app, zi)
                            rect = (x0(ci) + zi, y + ai * 0.5)
                            if val is None or not np.isfinite(val):
                                ax.add_patch(plt.Rectangle(rect, 0.94, 0.46, fill=False, ec=GRID, lw=0.25))
                            else:
                                ax.add_patch(plt.Rectangle(rect, 0.94, 0.46, color=CMAP(NORM(np.log2(np.clip(val, 1 / 64, 64))))))
                    ci += 1
            yt.append(y + 0.5)
            yl.append(label)
            y += 1.15
        spans.append((slabel, y_start, y))
    ax.set_xlim(-0.3, x0(ncol - 1) + cw + 0.4)
    ax.set_ylim(y, -2.2)
    ax.set_yticks(yt, yl, fontsize=fs)
    ax.set_xticks([])
    ax.tick_params(length=0, pad=2)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ci = 0
    for system, sname in systems:
        for dk, dname in dirs:
            ax.text(x0(ci) + cw / 2, -0.7, dname, ha="center", fontsize=6.5, color=INK2)
            if dk == dirs[0][0]:
                ax.text(x0(ci) + cw + gx / 2, -1.7, sname, ha="center", fontsize=8.5, color=INK)
            ci += 1
    for slabel, a, b in spans:
        if slabel:
            fig.text(0.012, 0.02 + 0.86 * (1 - ((a + b) / 2 + 2.2) / (y + 2.2)), slabel, rotation=90, ha="left", va="center", fontsize=10.5,
                     weight="bold", color=INK)
    fig.text(0.02, 0.985, title, fontsize=10.5, va="top", color=INK)
    fig.text(0.02, 0.962, subtitle, fontsize=6.3, va="top", color=INK2, linespacing=1.4)
    cax = fig.add_axes([0.80, 0.918, 0.17, 0.008])
    cb = fig.colorbar(matplotlib.cm.ScalarMappable(norm=NORM, cmap=CMAP), cax=cax, orientation="horizontal")
    cb.set_ticks([-1, 0, 1])
    cb.set_ticklabels(["≤ 0.5×", "same", "≥ 2×"])
    cb.outline.set_visible(False)
    cb.ax.tick_params(length=0, labelsize=5.5)
    # key: one glyph
    kax = fig.add_axes([0.80, 0.885, 0.17, 0.022])
    kax.set_xlim(-2.6, cw + 0.2)
    kax.set_ylim(1.1, -0.9)
    kax.axis("off")
    for ai, (_, aname) in enumerate(apps):
        kax.text(-0.15, ai * 0.5 + 0.23, aname, fontsize=5, ha="right", va="center", color=INK2)
        for zi in range(cw):
            kax.add_patch(plt.Rectangle((zi, ai * 0.5), 0.94, 0.46, color=MID, ec=MUTED, lw=0.3))
    for zi, t in enumerate(size_labels):
        kax.text(zi + 0.47, -0.25, t, fontsize=4.8, ha="center", color=INK2)
    fig.savefig(out, dpi=200, facecolor=SURFACE)
    plt.close(fig)
    return out
