#!/usr/bin/env python3
"""The "lines" charts: the original transfer chart (bandwidth over data size, host to device "first access", strided_transfer, 4-byte rows)
with very few lines, AdaptiveCpp only, each line one code state in its default configuration, one figure per variant and system.
  lines_staging_<system>.png      M = 1 (contiguous: the regular copy path, current defaults), M = 2 before copylib (00_old, gpuc4 only),
                                  M = 2 right after the first copylib build (af82e39), M = 2 after the fast path (c4ee4f1; 05_fastpath N >= 2^22 and results/fastpath_small_*.csv N <= 2^24),
                                  M = 2 with the current defaults (2dda28f, staging)
  lines_defaults_<system>.png     M = 1 (contiguous) against M = 2 with the current defaults, staging and host kernel
  (the host kernel is unaffected by SDMA off, so its charts and lines have no SDMA-off line for M = 2)
  lines_hostkernel_<system>.png   M = 1 (current defaults), M = 2 with the first host-kernel build (f8d348b, sweep 1: COPYLIB_HOST_KERNEL=1 on
                                  its defaults), M = 2 with the current defaults (2dda28f, host kernel)
Mean of the runs, band = +- one standard deviation. Usage: python3 plot_lines.py [d2h <system> [<name>]] ; writes the PNGs here (device-to-host: lines_<name>_d2h_<system>.png)."""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import sys

from plot_milestones import HERE, SYSTEMS, INK, MUTED, SURFACE, load, style, to_plot

APP = "Celerity-acpp"
# (label, colour, linestyle, M, path pattern, application override, filter)
STAGING = [
    ("M = 1, contiguous: regular copy path (current)", INK, ":", 1, "15_sweep3/{s}/results/strided_stg_defaults.csv", None, None),
    ("M = 2 before copylib", "#8a8984", "-", 2, "00_old/results/strided.csv", "Celerity", None),
    ("M = 2 first copylib (af82e39)", "#2a78d6", "-", 2, "01_default/results/{s}/strided_transfer.csv", None, None),
    ("M = 2 after fastpath (c4ee4f1)", "#eb6834", "-", 2, ("05_fastpath/results/{s}.csv", "02_comparison/results/fastpath_small_{s}.csv"), None, "base"),
    ("M = 2 current defaults (2dda28f)", "#1baf7a", "-", 2, "15_sweep3/{s}/results/strided_stg_defaults.csv", None, None),
    ("M = 1, SDMA off (HSA_ENABLE_SDMA=0)", INK, "-.", 1, "20_sdma_defaults/{s}/results/strided_stg_sdma.csv", None, "sdma_off"),
    ("M = 2 current defaults, SDMA off", "#1baf7a", "--", 2, "20_sdma_defaults/{s}/results/strided_stg_sdma.csv", None, "sdma_off"),
]
HOSTKERNEL = [
    ("M = 1, contiguous: regular copy path (current)", INK, ":", 1, "15_sweep3/{s}/results/strided_hk_defaults.csv", None, None),
    ("M = 2 first host kernel (f8d348b)", "#9b5de5", "-", 2, "03_config/{s}/results/strided_host_kernel.csv", None, None),
    ("M = 2 current defaults (2dda28f)", "#1baf7a", "-", 2, "15_sweep3/{s}/results/strided_hk_defaults.csv", None, None),
    ("M = 1, SDMA off (HSA_ENABLE_SDMA=0)", INK, "-.", 1, "20_sdma_defaults/{s}/results/strided_hk_sdma.csv", None, "sdma_off"),
]
DEFAULTS = [
    ("M = 1, contiguous: regular copy path", INK, ":", 1, "15_sweep3/{s}/results/strided_stg_defaults.csv", None, None),
    ("M = 2 staging, current defaults", "#1baf7a", "-", 2, "15_sweep3/{s}/results/strided_stg_defaults.csv", None, None),
    ("M = 2 host kernel, current defaults", "#9b5de5", "-", 2, "15_sweep3/{s}/results/strided_hk_defaults.csv", None, None),
    ("M = 1, SDMA off (HSA_ENABLE_SDMA=0)", INK, "-.", 1, "20_sdma_defaults/{s}/results/strided_stg_sdma.csv", None, "sdma_off"),
    ("M = 2 staging, SDMA off", "#1baf7a", "--", 2, "20_sdma_defaults/{s}/results/strided_stg_sdma.csv", None, "sdma_off"),
]
# the NVIDIA node of ifi (RTX 2070, partition IFIgpu2070; 18_ifi_nvidia): only the current defaults exist there, and there is no SDMA setting
NVIDIA = ("nvidia", "ifi · RTX 2070 (PCIe, CUDA)")
NVIDIA_DEFAULTS = [
    ("M = 1, contiguous: regular copy path", INK, ":", 1, "18_ifi_nvidia/results/strided_stg_defaults.csv", None, None),
    ("M = 2 staging, current defaults", "#1baf7a", "-", 2, "18_ifi_nvidia/results/strided_stg_defaults.csv", None, None),
    ("M = 2 host kernel, current defaults", "#9b5de5", "-", 2, "18_ifi_nvidia/results/strided_hk_defaults.csv", None, None),
    ("M = 2 without copylib (CELERITY_COPYLIB=off)", "#8a8984", "-", 2, ("18_ifi_nvidia/results/strided_native_copylib_off.csv", "18_ifi_nvidia/results/strided_native_copylib_off_large.csv"), None, None),
]


def series(d, metric):
    d = d[d[metric] > 0]
    return to_plot(d.groupby("data_size_gib")[metric].agg(["mean", "std"]).reset_index().sort_values("data_size_gib"), metric)


def main(metric="copy_bandwidth", only_systems=None, only_names=None):
    plt.rcParams.update({"font.family": "DejaVu Sans", "figure.facecolor": SURFACE, "axes.facecolor": SURFACE})
    for name, lines, title in (("staging", STAGING, "staging"), ("hostkernel", HOSTKERNEL, "host kernel"),
                                ("defaults", DEFAULTS, "current defaults")):
        if only_names and name not in only_names:
            continue
        for system, sname in SYSTEMS + ([NVIDIA] if name == "defaults" else []):
            if system == "nvidia":
                lines = NVIDIA_DEFAULTS
            if only_systems and system not in only_systems:
                continue
            fig, ax = plt.subplots(figsize=(9, 6))
            shown = []
            for label, colour, ls, m, path, override, filt in lines:
                d = load(path, system, APP, override, filt) if not override else load_old(path, system)
                if d is None:
                    continue
                if metric not in d.columns:
                    continue  # the early runs (00_old, 01_default) did not record device-to-host
                d = d[d.M == m]
                if not len(d):
                    continue
                g = series(d, metric)
                if not len(g):
                    continue
                ax.plot(g.x, g["mean"], color=colour, linestyle=ls, linewidth=2.2 if ls == "-" else 1.8, marker="o" if ls == "-" else None, markersize=3.5, label=label)
                y, e = g["mean"].values, g["std"].fillna(0).values
                ax.fill_between(g.x, np.clip(y - e, y * 0.05, None), y + e, color=colour, alpha=0.12, linewidth=0)
                shown.append(label)
            if not shown:
                plt.close(fig)
                continue
            style(ax, log_y=True)
            ax.set_ylabel("host → device bandwidth (first access)" if metric == "copy_bandwidth" else "device → host bandwidth", color=INK, fontsize=9)
            ax.legend(loc="upper left", frameon=False, fontsize=8.5)
            ax.set_title(f"strided data transfer (4-byte rows), {sname}, AdaptiveCpp, {title}", fontsize=11, color=INK, loc="left")
            fig.tight_layout()
            out = os.path.join(HERE, f"lines_{name}_{'d2h_' if metric == 'd2h_gbps' else ''}{system}.png")
            fig.savefig(out, dpi=140)
            plt.close(fig)
            print(out, len(shown), "lines")


def load_old(path, system):
    """The pre-copylib run (00_old) has one application, 'Celerity', and exists for gpuc4 only."""
    import pandas as pd
    p = os.path.join(os.path.dirname(HERE), path)
    if system != "gpuc4" or not os.path.exists(p):
        return None
    d = pd.read_csv(p)
    d = d[(d.application == "Celerity") & (d.data_size_gib > 0) & (d.copy_bandwidth > 0)]
    return d if len(d) else None


if __name__ == "__main__":
    # python3 plot_lines.py                          all host-to-device charts
    # python3 plot_lines.py d2h <system> [<name>]    device-to-host charts of one system (name: staging, hostkernel, defaults)
    if sys.argv[1:2] == ["d2h"]:
        main("d2h_gbps", sys.argv[2:3] or None, sys.argv[3:4] or None)
    else:
        main()
