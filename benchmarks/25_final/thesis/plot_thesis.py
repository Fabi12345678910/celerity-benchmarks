#!/usr/bin/env python3
"""Figures for thesis chapter 6 (vector PDF, 15 cm text width), PROVISIONAL data as in thesis_numbers.py (sweep 4 / 22 / 18, SDMA off);
rerun on the final sweep by pointing SOURCES at 25_final. Colours per strategy, fixed in every figure: native = gray, staging = blue,
host kernel = orange, contiguous (block) reference = dark gray dashed; markers repeat the identity for print.
  fig_strided_acpp.pdf / fig_strided_dpcpp.pdf   strided column copies (M = 2) vs size, H>D and D>H x 3 systems
  fig_device_strided.pdf                         host-strided vs device-strided (M = 4, 2^28 rows, AdaptiveCpp), per strategy
  fig_nvidia_d2h.pdf                             NVIDIA RTX 2070: copylib vs Celerity's CUDA backend (cudaMemcpy2D/3D), D>H
Usage: python3 plot_thesis.py [--final]   (--final: the final sweep 25_final, see thesis_numbers.py; NVIDIA from the published build, 26_published)"""
import sys
import glob
import os

import matplotlib

matplotlib.use("pdf")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator  # noqa: E402

TITLES = False  # the thesis captions carry the titles (thesis agent, 2026-10-08)
HERE = os.path.dirname(os.path.abspath(__file__))
FINAL = "--final" in sys.argv
B = os.path.join(HERE, "..", "..")
CM = 1 / 2.54
W = 15 * CM
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
STYLE = {"native": dict(color="#8a8984", marker="s", label="native (Celerity, copylib off)"),
         "staging": dict(color="#2a78d6", marker="o", label="copylib staging"),
         "hostkernel": dict(color="#eb6834", marker="^", label="copylib host kernel"),
         "block": dict(color="#52514e", ls="--", marker=None, label="contiguous copy (block, native)")}
SYS = [("gpuc4", "RX 9060 XT (PCIe)"), ("ifi", "Radeon 8060S (APU)"), ("lumi", "MI250X (GCD)")]  # thesis names (user, 2026-10-08)
DIRS = [("copy_bandwidth", "host to device"), ("d2h_gbps", "device to host")]
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 7, "axes.edgecolor": INK2, "axes.labelcolor": INK, "xtick.color": INK2,
                     "ytick.color": INK2, "axes.linewidth": 0.6, "xtick.major.width": 0.6, "ytick.major.width": 0.6, "lines.linewidth": 1.4,
                     "lines.markersize": 3.2, "legend.frameon": False, "pdf.fonttype": 42})


def nbytes(b):
    for u, f in (("GiB", 2 ** 30), ("MiB", 2 ** 20), ("KiB", 2 ** 10)):
        if b >= f:
            return f"{b / f:.0f} {u}"
    return f"{b:.0f} B"


def gbps(v):
    return f"{v:g} GB/s" if v >= 1 else (f"{v * 1000:g} MB/s")


def med(pattern, keys=("application", "M", "N")):
    fs = glob.glob(os.path.join(B, pattern))
    d = pd.concat([pd.read_csv(f).assign(system=f.split(os.sep)[-3]) for f in fs], ignore_index=True)
    if "M" not in d:
        d["M"] = 0
    d = d[d.check == "ok"]
    return d.groupby(["system", *keys])[[k for k, _ in DIRS]].median()


def axes_fmt(ax, ymin):
    ax.set_xscale("log", base=2)
    ax.set_yscale("log")
    ax.xaxis.set_major_locator(FixedLocator([4 * 2 ** e for e in (8, 14, 20, 26)]))
    ax.xaxis.set_minor_locator(NullLocator())
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: nbytes(v)))
    ax.yaxis.set_major_locator(FixedLocator([10.0 ** e for e in range(-4, 3)]))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: gbps(v)))
    ax.set_ylim(ymin, 150)
    ax.grid(True, which="major", color=GRID, lw=0.5)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def strided(app, out):
    if FINAL:
        nat = med("25_final/*/results/sweep_strided_native.csv")
        stg = med("25_final/*/results/sweep_strided_stg_base.csv")
        hk = med("25_final/*/results/sweep_strided_hk_base.csv")
        blk = med("25_final/*/results/sweep_block_native.csv", ("application", "N"))
    else:
        nat = med("15_sweep3/*/results/strided_native_copylib_off_*.csv")
        stg = med("21_sweep4/*/results/strided_stg_base.csv")
        hk = med("21_sweep4/*/results/strided_hk_grid_q2_c4MiB.csv")
        blk = med("21_sweep4/*/results/block_native_base.csv", ("application", "N"))
    fig, axs = plt.subplots(2, 3, figsize=(W, 9.5 * CM), sharex=True, sharey=True)
    for c, (s, title) in enumerate(SYS):
        for r, (dr, dname) in enumerate(DIRS):
            ax = axs[r, c]
            for key, src in (("native", nat), ("staging", stg), ("hostkernel", hk)):
                try:
                    t = src.loc[(s, app, 2)][dr]
                except KeyError:
                    continue
                t = t[(t.index >= 2 ** 6) & (t > 0)]
                st = STYLE[key]
                ax.plot(t.index * 4, t.values, color=st["color"], marker=st["marker"], markevery=3, label=st["label"])
            t = blk.loc[(s, app)][dr]
            t = t[(t.index >= 2 ** 6) & (t.index <= 2 ** 28) & (t > 0)]
            ax.plot(t.index * 4, t.values, color=STYLE["block"]["color"], ls="--", lw=1.0, label=STYLE["block"]["label"])
            axes_fmt(ax, 2e-4)
            if r == 0:
                ax.set_title(title, fontsize=7, color=INK)
            if c == 0:
                ax.set_ylabel(f"{dname}\n(useful data rate)")
            if r == 1:
                ax.set_xlabel("useful data per copy")
    h, l = axs[0, 0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=4, fontsize=6.5, bbox_to_anchor=(0.5, -0.01))
    impl = "AdaptiveCpp" if "acpp" in app else "DPC++"
    if TITLES:
        fig.suptitle(f"Strided column copies (4-byte rows, pitch 8 B, M = 2), {impl}, SDMA off", fontsize=7.5, color=INK, y=0.995)
    fig.tight_layout(rect=(0, 0.06, 1, 0.97), h_pad=0.6, w_pad=0.4)
    fig.savefig(os.path.join(HERE, out))
    plt.close(fig)


def device_strided():
    # 22_device_strided/README.md table: AdaptiveCpp, M = 4, N = 2^28 rows, sweep 4 base configs, SDMA off
    vals = {"host to device": {"host-strided": {"staging": (4.6, 7.5, 6.7), "hostkernel": (2.8, 17.5, 9.6)},
                               "device-strided": {"staging": (9.2, 13.2, 18.1), "hostkernel": (11.1, 13.3, 29.5)}},
            "device to host": {"host-strided": {"staging": (2.9, 8.9, 3.7), "hostkernel": (0.17, 22.1, 4.4)},
                               "device-strided": {"staging": (10.4, 30.6, 10.1), "hostkernel": (14.5, 39.1, 24.6)}}}
    if FINAL:  # the same table from the final sweep: host-strided = sweep_strided_<v>_base, device-strided = prog_device (pinning on)
        def one(system, side, key, dr):
            if side == "host-strided":
                d = pd.read_csv(os.path.join(B, "25_final", system, "results", f"sweep_strided_{'stg' if key == 'staging' else 'hk'}_base.csv"))
            else:
                d = pd.read_csv(os.path.join(B, "25_final", system, "results", "prog_device.csv"))
                d = d[d.env == ("HSA_ENABLE_SDMA=0" + ("" if key == "staging" else " COPYLIB_HOST_KERNEL=1"))]
            d = d[(d.check == "ok") & (d.application == "Celerity-acpp") & (d.M == 4) & (d.N == 2 ** 28)]
            return round(float(d[dr].median()), 2)
        vals = {dname: {side: {key: tuple(one(s, side, key, dr) for s, _ in SYS) for key in ("staging", "hostkernel")}
                        for side in ("host-strided", "device-strided")} for dr, dname in DIRS}
    fig, axs = plt.subplots(1, 2, figsize=(W, 6.2 * CM), sharey=True)
    x = np.arange(3)
    for ax, (dname, v) in zip(axs, vals.items()):
        w = 0.19
        for i, (side, key) in enumerate((("host-strided", "staging"), ("host-strided", "hostkernel"), ("device-strided", "staging"), ("device-strided", "hostkernel"))):
            st = STYLE[key]
            ys = v[side][key]
            bars = ax.bar(x + (i - 1.5) * (w + 0.02), ys, w, color=st["color"], alpha=1.0 if side == "device-strided" else 0.45,
                          hatch=None if side == "device-strided" else "////", edgecolor="white", lw=0.5,
                          label=f"{side}, {'staging' if key == 'staging' else 'host kernel'}")
            for b, y in zip(bars, ys):
                ax.text(b.get_x() + b.get_width() / 2, y * 1.03, f"{y:.2g}" if y < 1 else f"{y:.1f}", ha="center", va="bottom", fontsize=5.5, color=INK2)
        ax.set_xticks(x, [t.replace(" (", "\n(") for _, t in SYS], fontsize=5.8)
        ax.set_title(dname, fontsize=7, color=INK)
        ax.set_yscale("log")
        ax.yaxis.set_major_locator(FixedLocator([0.1, 1, 10, 100]))
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: gbps(v)))
        ax.set_ylim(0.1, 80)
        ax.grid(True, axis="y", color=GRID, lw=0.5)
        ax.set_axisbelow(True)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    h, l = axs[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=4, fontsize=6, bbox_to_anchor=(0.5, -0.01))
    if TITLES:
        fig.suptitle("Which side is strided: 1 GiB column (M = 4, 2^28 rows), AdaptiveCpp, SDMA off", fontsize=7.5, color=INK, y=0.99)
    fig.tight_layout(rect=(0, 0.1, 1, 0.95))
    fig.savefig(os.path.join(HERE, "fig_device_strided.pdf"))
    plt.close(fig)


def nvidia():
    if FINAL:  # the published release build (26_published, GitHub master 536d754 + gpu3dcopylib 843fafe), mapped to the 18_ifi_nvidia config names
        a = pd.read_csv(os.path.join(B, "26_published", "nvidia", "results", "lines_nvidia.csv"))
        a["cfg"] = a.env.map(lambda e: "strided_hk_defaults" if "HOST_KERNEL" in e else "strided_stg_defaults")
        b = pd.read_csv(os.path.join(B, "26_published", "nvidia", "results", "lines_native_nvidia.csv")).assign(cfg="strided_native_copylib_off")
        d = pd.concat([a, b])
    else:
        fs = glob.glob(os.path.join(B, "18_ifi_nvidia", "results", "*.csv"))
        d = pd.concat([pd.read_csv(f).assign(cfg=os.path.basename(f)[:-4].replace("_large", "")) for f in fs])
    d = d[d.check == "ok"]
    m = d.groupby(["cfg", "M", "N"]).d2h_gbps.median()
    fig, ax = plt.subplots(figsize=(W * 0.62, 6.5 * CM))
    for cfg, key, lab in (("strided_native_copylib_off", "native", "native: Celerity CUDA backend (cudaMemcpy2D/3D)"),
                          ("strided_stg_defaults", "staging", None), ("strided_hk_defaults", "hostkernel", None)):
        t = m.loc[(cfg, 2)]
        t = t[(t.index >= 2 ** 6) & (t > 0)]
        st = STYLE[key]
        ax.plot(t.index * 4, t.values, color=st["color"], marker=st["marker"], markevery=3, label=lab or st["label"])
    t = m.loc[("strided_native_copylib_off", 1)]
    t = t[(t.index >= 2 ** 6) & (t > 0)]
    ax.plot(t.index * 4, t.values, color=STYLE["block"]["color"], ls="--", lw=1.0, label="contiguous column (M = 1, native)")
    axes_fmt(ax, 1e-3)
    ax.set_ylim(1e-2, 50)
    ax.set_xlabel("useful data per copy")
    ax.set_ylabel("device to host (useful data rate)")
    if TITLES:
        ax.set_title("RTX 2070 (PCIe 3.0 x16), AdaptiveCpp, M = 2", fontsize=7, color=INK)
    ax.legend(fontsize=5.8, loc="upper left")
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, "fig_nvidia_d2h.pdf"))
    plt.close(fig)


if __name__ == "__main__":
    strided("Celerity-acpp", "fig_strided_acpp.pdf")
    strided("Celerity-dpcpp", "fig_strided_dpcpp.pdf")
    device_strided()
    nvidia()
    print("written:", sorted(f for f in os.listdir(HERE) if f.endswith(".pdf")))
