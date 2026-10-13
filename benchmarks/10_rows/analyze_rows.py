import os
import sys

import matplotlib.pyplot as plt
import pandas as pd

# Analyzes the row-width benchmark (10_rows/results/<system>_rows.csv): per system, staging vs. host kernel over the useful bytes per row
# (S = 4 * W, pitch 256 bytes), at the largest N. Host to device is also given with the fixed first-access cost (kernel loading)
# removed: (bytes(N_max) - bytes(N_min)) / (t(N_max) - t(N_min)). Writes 10_rows/results/plots/<system>_rows.png and prints the tables.
# Usage: python 10_rows/analyze_rows.py <system> [<system> ...]

HERE = os.path.dirname(os.path.abspath(__file__))
pd.set_option("display.width", 250)


def table(d):
    d = d[d.check == "ok"].copy()
    d["S"] = d.W * 4
    d["mode"] = d.env.str.contains("HOST_KERNEL").map({True: "host kernel", False: "staging"})
    d["bytes"] = d.N * d.W * 4
    d["t_h2d"] = d.bytes / (d.copy_bandwidth * 1e9)
    nmin, nmax = d.N.min(), d.N.max()
    rows = []
    for (app, S, mode), g in d.groupby(["application", "S", "mode"]):
        t = g.groupby("N")[["t_h2d"]].median()["t_h2d"]
        b = g.groupby("N")["bytes"].first()
        rows.append(dict(app=app.split("-")[1], S=S, mode=mode,
                         h2d=g[g.N == nmax].copy_bandwidth.median(), h2d_corrected=(b[nmax] - b[nmin]) / (t[nmax] - t[nmin]) / 1e9,
                         d2h=g[g.N == nmax].d2h_gbps.median(), useful_mib=b[nmax] >> 20))
    return pd.DataFrame(rows)


def main():
    out = os.path.join(HERE, "results", "plots")
    os.makedirs(out, exist_ok=True)
    for system in sys.argv[1:]:
        raw = pd.read_csv(os.path.join(HERE, "results", f"{system}_rows.csv"))
        print(f"\n=== {system}: {len(raw)} rows, {(raw.check != 'ok').sum()} not ok")
        t = table(raw)
        p = t.pivot_table(index=["app", "S", "useful_mib"], columns="mode", values=["h2d_corrected", "h2d", "d2h"])
        p[("h2d_corrected", "staging/hk")] = p[("h2d_corrected", "staging")] / p[("h2d_corrected", "host kernel")]
        p[("d2h", "staging/hk")] = p[("d2h", "staging")] / p[("d2h", "host kernel")]
        print(p[["h2d_corrected", "d2h"]].round(2).to_string())
        apps = sorted(t.app.unique())
        fig, axes = plt.subplots(2, len(apps), figsize=(15, 10), sharex=True, squeeze=False)
        for row, (col_name, what) in enumerate((("h2d_corrected", "host to device (first-access cost removed)"), ("d2h", "device to host"))):
            for c, app in enumerate(apps):
                ax = axes[row][c]
                for mode, color in (("staging", "tab:blue"), ("host kernel", "tab:orange")):
                    s = t[(t.app == app) & (t["mode"] == mode)].sort_values("S")
                    ax.plot(s.S, s[col_name], marker="o", color=color, label=mode)
                ax.set_xscale("log", base=2)
                ax.set_xticks(sorted(t.S.unique()))
                ax.set_xticklabels([f"{s} B" + (" (contiguous)" if s == 256 else "") for s in sorted(t.S.unique())])
                ax.set_ylabel("GB/s (useful bytes)")
                ax.set_title(f"{what}, {app}")
                ax.grid(True, which="both", alpha=0.5)
                ax.legend(fontsize=9)
                if row == 1:
                    ax.set_xlabel("useful bytes per row (pitch 256 bytes)")
        fig.suptitle(f"{system}: staging vs. host kernel over the row width, N = {raw.N.max()} rows (median of 3 runs)")
        fig.text(0.01, 0.005, "S = 256: whole rows, a contiguous copy on Celerity's regular path (both lines the same configuration); "
                 "staging: dynamic, 4 MiB chunks, recommended worker cores; host kernel: COPYLIB_HOST_KERNEL=1; celerity-bench 014e21a", fontsize=8)
        fig.tight_layout(rect=(0, 0.02, 1, 0.97))
        path = os.path.join(out, f"{system}_rows.png")
        fig.savefig(path, dpi=150)
        plt.close(fig)
        print(path)


if __name__ == "__main__":
    main()
