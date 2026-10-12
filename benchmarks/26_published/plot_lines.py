#!/usr/bin/env python3
"""Lines charts of the published Celerity (GitHub master 536d754, gpu3dcopylib 843fafe): strided_transfer, 4-byte rows, bandwidth over the size of
the copy, one column per system that has results (RX 9060 XT, Radeon 8060S, MI250X, RTX 2070), host to device and device to host. Lines: M = 2 with the
defaults (staging), M = 2 with COPYLIB_HOST_KERNEL=1, M = 2 with CELERITY_COPYLIB=off (Celerity's own path), and M = 1 (contiguous) as the reference.
Median of the 3 runs per point; SDMA off on AMD. Style and colours as 25_final/thesis/plot_thesis.py.
Usage: python3 plot_lines.py [acpp|dpcpp]   writes lines_<impl>.pdf and .png here (DPC++: AMD systems only)."""
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.ticker import FixedLocator  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "25_final", "thesis"))
from plot_thesis import CM, DIRS, INK, STYLE, W, axes_fmt  # noqa: E402

SYSTEMS = [("gpuc4", "RX 9060 XT (PCIe)"), ("ifi", "Radeon 8060S (APU)"), ("lumi", "MI250X (GCD)"), ("nvidia", "RTX 2070 (PCIe)")]


def load(system):
    f1, f2 = (os.path.join(HERE, system, "results", f"{n}_{system}.csv") for n in ("lines", "lines_native"))
    if not (os.path.exists(f1) and os.path.exists(f2)):
        return None
    a, b = pd.read_csv(f1), pd.read_csv(f2)
    a["cfg"] = a.env.map(lambda e: "hostkernel" if "HOST_KERNEL" in e else "staging")
    b["cfg"] = "native"
    d = pd.concat([a, b])
    return d[d.check == "ok"]


def main():
    impl = (sys.argv[1:] or ["acpp"])[0]
    app = f"Celerity-{impl}"
    systems = [(s, t) for s, t in SYSTEMS if load(s) is not None and (impl == "acpp" or s != "nvidia")]
    fig, axs = plt.subplots(2, len(systems), figsize=(W, 9.5 * CM), sharex=True, sharey=True, squeeze=False)
    for c, (s, title) in enumerate(systems):
        d = load(s)
        d = d[d.application == app]
        for r, (dr, dname) in enumerate(DIRS):
            ax = axs[r, c]
            for key in ("native", "staging", "hostkernel"):
                t = d[(d.cfg == key) & (d.M == 2)].groupby("N")[dr].median()
                t = t[(t.index >= 2 ** 6) & (t > 0)]
                st = STYLE[key]
                label = st["label"] if key != "native" else "copylib off (Celerity's own path)"
                ax.plot(t.index * 4, t.values, color=st["color"], marker=st["marker"], markevery=3, label=label)
            t = d[(d.cfg == "staging") & (d.M == 1)].groupby("N")[dr].median()
            t = t[(t.index >= 2 ** 6) & (t > 0)]
            ax.plot(t.index * 4, t.values, color=STYLE["block"]["color"], ls="--", lw=1.0, label="contiguous column (M = 1)")
            axes_fmt(ax, 2e-4)
            if len(systems) > 3:  # four columns: fewer size ticks so the labels do not overlap
                ax.xaxis.set_major_locator(FixedLocator([2 ** 10, 2 ** 22, 2 ** 30]))
            if r == 0:
                ax.set_title(title, fontsize=7, color=INK)
            if c == 0:
                ax.set_ylabel(f"{dname}\n(useful data rate)")
            if r == 1:
                ax.set_xlabel("useful data per copy")
    h, l = axs[0, 0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=4, fontsize=6.3, bbox_to_anchor=(0.5, -0.01))
    fig.tight_layout(rect=(0, 0.06, 1, 1), h_pad=0.6, w_pad=0.4)
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(HERE, f"lines_{impl}.{ext}"), dpi=150)
    print("systems:", [s for s, _ in systems])


if __name__ == "__main__":
    main()
