#!/usr/bin/env python3
"""Appendix figures for the thesis (vector PDF, 15 cm wide, no title line; PROVISIONAL, sweep 4 era data), same colours as plot_thesis.py:
  fig_sdma.pdf   SDMA off / SDMA on per point (20_sdma_defaults: build 2dda28f defaults, same node back to back), AdaptiveCpp, M = 2 (copylib) and
                 M = 1 (contiguous, Celerity's native path), staging and host kernel, per system and direction
  fig_rows.pdf   row width S = 4..256 B per 256-byte pitch (10_rows: build 014e21a, SDMA on, staging tuned per system vs host kernel), AdaptiveCpp,
                 2^24 rows, per system and direction
Usage: python3 plot_appendix.py [--final]
--final: fig_sdma from 25_final pair_sdma (final defaults, SDMA on/off back to back), fig_rows from 25_final prog_rows (SDMA off, final defaults,
pinning on), both AdaptiveCpp."""
import sys
import glob
import os

import matplotlib

matplotlib.use("pdf")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.ticker import FixedLocator, FuncFormatter  # noqa: E402

from plot_thesis import CM, DIRS, GRID, INK, STYLE, SYS, W, axes_fmt, gbps  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FINAL = "--final" in sys.argv
B = os.path.join(HERE, "..", "..")


def clean(ax):
    ax.grid(True, which="major", color=GRID, lw=0.5)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def sdma():
    fig, axs = plt.subplots(2, 3, figsize=(W, 9.0 * CM), sharex=True, sharey=True)
    for c, (s, title) in enumerate(SYS):
        frames = []
        if FINAL:
            d = pd.read_csv(os.path.join(B, "25_final", s, "results", "pair_sdma.csv"))
            d["var"] = np.where(d.env.str.contains("HOST_KERNEL=1"), "hostkernel", "staging")
            frames.append(d)
        for f in [] if FINAL else glob.glob(os.path.join(B, "20_sdma_defaults", s, "results", "strided_*_sdma.csv")):
            d = pd.read_csv(f)
            d["var"] = "hostkernel" if "_hk_" in f else "staging"
            frames.append(d)
        d = pd.concat(frames)
        d = d[(d.check == "ok") & (d.application == "Celerity-acpp")]
        d["sdma"] = np.where(d.env.fillna("").str.contains("SDMA=0"), "off", "on")
        for r, (dr, dname) in enumerate(DIRS):
            ax = axs[r, c]
            m = d.groupby(["var", "M", "N", "sdma"])[dr].median().unstack("sdma")
            ratio = (m["off"] / m["on"]).dropna()
            for var in ("staging", "hostkernel"):
                t = ratio.loc[(var, 2)]
                t = t[t.index >= 2 ** 6]
                st = STYLE[var]
                ax.plot(t.index * 4, t.values, color=st["color"], marker=st["marker"], markevery=3, label=f"{st['label']} (M = 2)")
            t = ratio.loc[("staging", 1)]
            t = t[t.index >= 2 ** 6]
            ax.plot(t.index * 4, t.values, color=STYLE["block"]["color"], ls="--", lw=1.0, label="contiguous column, native path (M = 1)")
            axes_fmt(ax, 0.2)
            ax.set_ylim(0.1, 20)
            ax.yaxis.set_major_locator(FixedLocator([0.1, 0.25, 0.5, 1, 2, 4, 10, 20]))
            ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}x"))
            ax.yaxis.set_minor_locator(matplotlib.ticker.NullLocator())
            ax.axhline(1, color=INK, lw=0.6)
            if r == 0:
                ax.set_title(title, fontsize=7, color=INK)
            if c == 0:
                ax.set_ylabel(f"{dname}\nSDMA off / SDMA on")
            if r == 1:
                ax.set_xlabel("useful data per copy")
    h, l = axs[0, 0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=3, fontsize=6.3, bbox_to_anchor=(0.5, -0.01))
    fig.tight_layout(rect=(0, 0.06, 1, 1), h_pad=0.6, w_pad=0.4)
    fig.savefig(os.path.join(HERE, "fig_sdma.pdf"))
    plt.close(fig)


def rows():
    fig, axs = plt.subplots(2, 3, figsize=(W, 8.5 * CM), sharex=True, sharey=True)
    for c, (s, title) in enumerate(SYS):
        if FINAL:
            d = pd.concat([pd.read_csv(f) for f in glob.glob(os.path.join(B, "25_final", s, "results", "prog_rows*.csv")) if "native" not in f])
            d = d[~d.env.str.contains("PINNING")]
        else:
            d = pd.read_csv(os.path.join(B, "10_rows", "results", f"{s}_rows.csv"))
        d = d[(d.check == "ok") & (d.application == "Celerity-acpp") & (d.N == 2 ** 24)]
        d["var"] = np.where(d.env.str.contains("HOST_KERNEL=1"), "hostkernel", "staging")
        for r, (dr, dname) in enumerate(DIRS):
            ax = axs[r, c]
            m = d.groupby(["var", "W"])[dr].median()
            for var in ("staging", "hostkernel"):
                t = m.loc[var]
                st = STYLE[var]
                ax.plot(t.index * 4, t.values, color=st["color"], marker=st["marker"], label=st["label"])
            ax.set_xscale("log", base=2)
            ax.xaxis.set_major_locator(FixedLocator([4, 32, 256]))
            ax.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
            ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f} B"))
            ax.set_yscale("log")
            ax.yaxis.set_minor_locator(matplotlib.ticker.NullLocator())
            ax.yaxis.set_major_locator(FixedLocator([0.1, 1, 10, 100]))
            ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: gbps(v)))
            ax.set_ylim(0.05, 150)
            clean(ax)
            if r == 0:
                ax.set_title(title, fontsize=7, color=INK)
            if c == 0:
                ax.set_ylabel(f"{dname}\n(useful data rate)")
            if r == 1 and c == 1:
                ax.set_xlabel("useful bytes per row (pitch 256 B; 256 B = contiguous rows)")
    h, l = axs[0, 0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=2, fontsize=6.5, bbox_to_anchor=(0.5, -0.01))
    fig.tight_layout(rect=(0, 0.05, 1, 1), h_pad=0.6, w_pad=0.4)
    fig.savefig(os.path.join(HERE, "fig_rows.pdf"))
    plt.close(fig)


if __name__ == "__main__":
    sdma()
    rows()
