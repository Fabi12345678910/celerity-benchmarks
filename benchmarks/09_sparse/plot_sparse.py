import os
import sys

import matplotlib.pyplot as plt
import pandas as pd

# Plots staging vs. host kernel over the row pitch (4 useful bytes per row of M * 4 bytes) at N = 2^24 rows (64 MiB useful), for the
# column strided on the host only (strided_transfer: M = 2, 4 from the worker sweep 06_cores/, same staging configuration; M = 16, 32,
# 64 from 09_sparse/) and on both sides (strided_both_transfer). One figure per system: rows = direction, columns = SYCL implementation.
# Usage: python 09_sparse/plot_sparse.py <system> [<system> ...]

HERE = os.path.dirname(os.path.abspath(__file__))
CORES = os.path.join(HERE, "..", "06_cores")
BEST = {"gpuc4": "workers_04_dynamic", "ifi": "workers_08_dynamic", "lumi": "workers_04_dynamic"}  # = the staging env of 09_sparse/
N = 2 ** 24


def results(system):
    def load(f):
        return pd.read_csv(f) if os.path.exists(f) else None

    frames = []
    for kind, layout in (("sparse", "host strided"), ("both", "host and device strided")):
        d = load(os.path.join(HERE, "results", f"{system}_{kind}.csv"))
        if d is None:
            continue
        fix = load(os.path.join(HERE, "results", f"{system}_{kind}_dpcpp64.csv"))
        if fix is not None:
            d = pd.concat([d[~((d.application == "Celerity-dpcpp") & (d.M == 64) & (d.N >= 2 ** 22))], fix], ignore_index=True)
        d["mode"] = d.env.str.contains("HOST_KERNEL").map({True: "host kernel", False: "staging"})
        d["layout"] = layout
        frames.append(d)
    for cfg, mode in ((BEST[system], "staging"), ("reference_host_kernel", "host kernel")):
        d = load(os.path.join(CORES, system, "results", f"{cfg}.csv"))
        if d is not None:
            frames.append(d.assign(mode=mode, layout="host strided"))
    d = pd.concat(frames, ignore_index=True)
    d = d[(d.check == "ok") & (d.N == N)]
    d["pitch"] = d.M * 4
    return d


def main():
    out = os.path.join(HERE, "results", "plots")
    os.makedirs(out, exist_ok=True)
    for system in sys.argv[1:]:
        d = results(system)
        apps = sorted(d.application.unique())
        fig, axes = plt.subplots(2, len(apps), figsize=(16, 11), sharex=True, squeeze=False)
        for row, (metric, what) in enumerate((("copy_bandwidth", "host to device"), ("d2h_gbps", "device to host"))):
            for col, app in enumerate(apps):
                ax = axes[row][col]
                for (mode, layout), g in d[d.application == app].groupby(["mode", "layout"]):
                    s = g.groupby("pitch")[metric].agg(["median", "min", "max"])
                    color = "tab:blue" if mode == "staging" else "tab:orange"
                    style = "-" if layout == "host strided" else "--"
                    ax.plot(s.index, s["median"], marker="o", color=color, linestyle=style, label=f"{mode}, {layout}")
                    ax.fill_between(s.index, s["min"], s["max"], alpha=0.12, color=color)
                ax.set_xscale("log", base=2)
                ax.set_yscale("log")
                pitches = sorted(d.pitch.unique())
                ax.set_xticks(pitches)
                ax.set_xticklabels([f"{p} B\n(M={p // 4})" for p in pitches])
                ax.set_title(f"{what}, {app}")
                ax.set_ylabel("GB/s (useful bytes)")
                ax.grid(True, which="both", alpha=0.5)
                if row == 1:
                    ax.set_xlabel("row pitch (4 useful bytes per row)")
                ax.legend(fontsize=8)
        fig.suptitle(f"{system}: staging vs. host kernel over the row pitch, 64 MiB useful per copy (median, band = min-max of 3 runs)")
        fig.text(0.01, 0.005, "staging: COPYLIB_PLAN_ORDER=dynamic, 4 MiB chunks, the worker cores of the worker sweep's recommendation; "
                 "host kernel: COPYLIB_HOST_KERNEL=1; host strided M = 2, 4 from 06_cores/ (same configuration); celerity-bench 014e21a",
                 fontsize=8)
        fig.tight_layout(rect=(0, 0.02, 1, 0.97))
        path = os.path.join(out, f"{system}_pitch.png")
        fig.savefig(path, dpi=150)
        plt.close(fig)
        print(path)


if __name__ == "__main__":
    main()
