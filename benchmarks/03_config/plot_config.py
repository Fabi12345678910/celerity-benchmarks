import re
import sys
import os
import argparse
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# Plots configuration-sweep CSVs (benchmarks/config): one line per env value, one figure per application and metric, in the style
# of the original transfer plots. Also prints the median per env relative to the reference line ("base" in sweeps, else "default").
# --m <M>: only that M, one line per env, mean +- std band. --m each / --m 1,2: one line per env and M (every M / the listed ones;
# color = env, line style and marker = M, M=1 dotted: the regular path), mean, no bands. --sequential: ordered colors for the values of one variable (in CSV order).
# Usage: python plot_config.py <csv> [<csv> ...] [--m 2|each] [--metric copy_bandwidth d2h_gbps] [--out DIR] [--name NAME] [--sequential]

REFERENCE = ("base", "default")
NO_PINNING = "reference default"  # a sweep's reference without worker pinning, drawn gray next to the black base


def label(env, base=None):
    """Empty env: "base" in a sweep (fixed pinning in the base column), "reference default" for a sweep's reference (no worker
    pinning; empty or without WORKER_CPUS in the base column), "default" outside of sweeps (no base column, base=None)."""
    if not isinstance(env, str) or env == "":
        if base is None:
            return "default"
        return "base" if isinstance(base, str) and "WORKER_CPUS" in base else NO_PINNING
    return env.replace("CELERITY_COPYLIB_", "").replace("COPYLIB_", "")


# Defaults of every tuning variable, shown below sweep plots as the base configuration
BASE_DEFAULTS = [
    ("CELERITY_COPYLIB", "on"), ("CELERITY_COPYLIB_ROUTE", "strided only"), ("CELERITY_COPYLIB_MIN_BYTES", "0"),
    ("CELERITY_COPYLIB_MAX_ROW_BYTES", "no limit"), ("CELERITY_COPYLIB_QUEUES", "2"), ("CELERITY_COPYLIB_STAGING_BYTES", "32 MiB"),
    ("CELERITY_COPYLIB_CHUNK_BYTES", "staging/queues=16 MiB"), ("COPYLIB_WORKER_CPUS", "inherited (executor core 3)"),
    ("COPYLIB_HOST_KERNEL", "0"), ("COPYLIB_MAX_ELEM_SIZE", "64"), ("COPYLIB_ELEMS_PER_ITEM", "1"), ("COPYLIB_WG_SIZE", "32"),
    ("COPYLIB_PLAN_ORDER", "block"), ("COPYLIB_WAIT", "block"), ("COPYLIB_HOST_STAGING", "pinned"), ("COPYLIB_ALLOC_CPU_IDS", "unset"),
    ("COPYLIB_WARMUP", "0"), ("CELERITY_THREAD_PINNING", "auto (cores 1-4)"), ("HSA_ENABLE_SDMA", "1"),
]


def env_vars(s):
    return dict(re.findall(r"(\w+)=(\S+)", s)) if isinstance(s, str) else {}


def caption(fig, df):
    """Writes the base configuration below the plot; variables varied in this plot (in any env, or differing between the bases of
    the plotted lines, e.g. the reference without pinning) are bold."""
    bases = [env_vars(b) for b in df["base"].fillna("").unique()]
    base = max(bases, key=len)  # the system's base (the reference has fewer variables)
    varied = {k for e in df["env"].dropna().unique() for k in env_vars(e)}
    varied |= {k for b in bases for k in set(b) | set(base) if b.get(k) != base.get(k)}
    entries = [(k, base.get(k, v)) for k, v in BASE_DEFAULTS] + [(k, v) for k, v in base.items() if k not in dict(BASE_DEFAULTS)]
    fig.text(0.05, 0.135, "base configuration (bold: varied in this plot)", fontsize=11, fontweight="bold", va="top")
    cols = 4
    rows = -(-len(entries) // cols)
    for i, (k, v) in enumerate(entries):
        fig.text(0.05 + (i // rows) * 0.235, 0.11 - (i % rows) * 0.019, f"{k}={v}", fontsize=9.5, va="top", family="monospace",
                 fontweight="bold" if k in varied else "normal", color="black" if k in varied else "dimgray")


M_STYLE = {1: dict(linestyle=":", marker="o"), 2: dict(linestyle="-", marker="s"), 3: dict(linestyle="--", marker="^"),
           4: dict(linestyle="-.", marker="D")}


def plot(df, app, metric, title, out, each_m=False, sequential=False):
    keys = ["env_label", "M"] if each_m else ["env_label"]
    g = df.groupby(keys + ["data_size_gib"], sort=False)[metric]
    grouped = pd.DataFrame({"y": g.mean(), "std": g.std()}).reset_index()
    grouped["lo"] = np.clip(grouped["y"] - grouped["std"].fillna(0), grouped["y"] * 0.01, None)
    grouped["hi"] = grouped["y"] + grouped["std"].fillna(0)

    envs = list(dict.fromkeys(grouped["env_label"]))
    if sequential:  # references first, then by the last number in the label (the swept value)
        def value(e):
            nums = re.findall(r"\d+", e)
            return (e not in REFERENCE, int(nums[-1]) if nums else -1)
        envs.sort(key=value)
    others = [e for e in envs if e not in REFERENCE and e != NO_PINNING]
    cmap = plt.get_cmap("viridis")
    colors = {e: cmap(i / max(1, len(others) - 1) * 0.9) for i, e in enumerate(others)} if sequential else {}
    if not sequential:
        cycle = plt.rcParams["axes.prop_cycle"].by_key()["color"]
        colors = {e: cycle[i % len(cycle)] for i, e in enumerate(others)}
    colors[NO_PINNING] = "dimgray"

    with_caption = "base" in df.columns
    fig = plt.figure(figsize=(19, 12.5 if with_caption else 10))
    for env in envs:
        ref = env in REFERENCE
        color = "black" if ref else colors[env]
        for m in (sorted(grouped["M"].unique()) if each_m else [None]):
            e_df = grouped[(grouped["env_label"] == env) & ((grouped["M"] == m) if each_m else True)].sort_values("data_size_gib")
            if e_df.empty:
                continue
            x = e_df["data_size_gib"].values
            style = M_STYLE.get(m, dict(linestyle="-", marker="o")) if each_m else dict(linestyle="-", marker="o")
            plt.plot(x, e_df["y"].values, markersize=5 if ref else 4, linewidth=2.5 if ref else 1.5, color=color,
                     label=None if each_m else env, **style)
            if not each_m:
                plt.fill_between(x, e_df["lo"].values, e_df["hi"].values, alpha=0.12, color=color)

    plt.xlabel("data size in GiB")
    plt.ylabel("bandwidth in GB/s")
    plt.title(title)

    ax = plt.gca()
    ax.set_xscale("log", base=2)
    ax.set_yscale("log")
    x_vals = grouped["data_size_gib"]
    min_exp = int(np.floor(np.log2(x_vals.min())))
    max_exp = int(np.ceil(np.log2(x_vals.max())))
    ticks = [2 ** i for i in range(min_exp, max_exp + 1)]
    ax.set_xticks(ticks)
    ax.set_xticklabels([rf"$2^{{{i}}}$" for i in range(min_exp, max_exp + 1)])

    ax.grid(True, which="both")
    if each_m:  # two legends: color = configuration, line style = M
        env_handles = [plt.Line2D([], [], color="black" if e in REFERENCE else colors[e], linewidth=2.5 if e in REFERENCE else 2,
                                  label=e) for e in envs]
        m_handles = [plt.Line2D([], [], color="gray", linewidth=1.5, label=f"M={m}" + (" (regular path)" if m == 1 else ""),
                                **M_STYLE[m]) for m in sorted(grouped["M"].unique())]
        ax.add_artist(ax.legend(handles=env_handles, loc="upper left", fontsize=8, ncol=2 if len(envs) > 12 else 1))
        ax.legend(handles=m_handles, loc="lower right", fontsize=9)
    else:
        plt.legend()
    if with_caption:
        fig.subplots_adjust(left=0.05, right=0.98, top=0.95, bottom=0.21)
        caption(fig, df)
    else:
        plt.tight_layout()
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close()
    print(out)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("csv", nargs="+")
    p.add_argument("--m", default="2", help="M for strided CSVs, 'each' for one line per M, or a list like 1,2 (ignored for block)")
    p.add_argument("--metric", nargs="+", default=["copy_bandwidth", "d2h_gbps"])
    p.add_argument("--out", default=None, help="output directory (default: next to the first CSV)")
    p.add_argument("--name", default=None, help="output name prefix (default: first CSV name without part number)")
    p.add_argument("--sequential", action="store_true", help="ordered colors (values of one variable, in CSV order)")
    args = p.parse_args()
    each_m = args.m == "each" or "," in args.m
    m_list = [int(m) for m in args.m.split(",")] if "," in args.m else None

    df = pd.concat([pd.read_csv(f) for f in args.csv], ignore_index=True)
    df["env_label"] = [label(e, b) for e, b in zip(df["env"], df["base"] if "base" in df.columns else [None] * len(df))]
    strided = "M" in df.columns
    if strided and not each_m:
        df = df[df["M"] == int(args.m)]
    if strided and m_list:
        df = df[df["M"].isin(m_list)]
    failed = df[df["check"] != "ok"]
    if len(failed):
        print(f"WARNING: {len(failed)} rows without 'Check: ok' (crashed or wrong data):")
        print(failed.groupby(["application", "env_label"]).size().to_string())
    df = df[df["data_size_gib"] > 0]

    out_dir = args.out or os.path.dirname(os.path.abspath(args.csv[0]))
    name = args.name or os.path.splitext(os.path.basename(args.csv[0]))[0].rstrip("0123456789").rstrip("_")
    os.makedirs(out_dir, exist_ok=True)
    machines = ",".join(sorted(df["machine"].dropna().astype(str).str.replace(r"^gc\d+$", "ifi", regex=True)
                               .str.replace(r"^nid\d+$", "lumi", regex=True).unique()))
    if "gcds" in df.columns:
        machines += " GCDs " + "/".join(sorted(df["gcds"].dropna().astype(str).unique()))

    for app, a_df in df.groupby("application"):
        for metric in args.metric:
            suffix = f"_M{args.m}" if strided else ""

            what = {"copy_bandwidth": "host to device (first access)", "d2h_gbps": "device to host"}.get(metric, metric)
            title = f"{name}{suffix}, {what}, {app}, {machines}"
            if strided and each_m:
                suffix = ""
                ms = ",".join(str(m) for m in sorted(a_df["M"].unique()))
                title = f"{name}, M={ms}, {what}, {app}, {machines}"
            plot(a_df, app, metric, title, os.path.join(out_dir, f"{name}{suffix}_{app}_{metric}.png"), strided and each_m,
                 args.sequential)

        # median per env at the three largest sizes, relative to the default
        sizes = np.sort(a_df["data_size_gib"].unique())
        big = a_df[a_df["data_size_gib"] >= sizes[-min(3, len(sizes))]]
        med = big.groupby(["env_label", "data_size_gib"], sort=False)[args.metric].median().unstack("data_size_gib")
        ref = next((r for r in REFERENCE if r in med.index), None)
        if ref:
            rel = med / med.loc[ref]
            print(f"\n{app}: median of the three largest sizes, relative to {ref}")
            print(rel.round(2).to_string())


if __name__ == "__main__":
    main()
