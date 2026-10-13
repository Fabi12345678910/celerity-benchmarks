import os
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# Celerity + AdaptiveCpp on gpuc4: the original runs (before copylib), the copylib default config, and later the tuned config.
# (label, block csv, application in block csv, strided csv, application in strided csv); a variant whose CSVs don't exist yet is skipped.
HERE = os.path.dirname(os.path.abspath(__file__))
B = os.path.dirname(HERE)  # benchmarks/, the paths below are relative to it
VARIANTS = [
    ("Celerity + acpp (old)", "00_old/results/results_no_barrier.csv", "Celerity", "00_old/results/strided.csv", "Celerity"),
    ("Celerity + acpp (new)", "01_default/results_f8d348b/gpuc4/block_transfer.csv", "Celerity-acpp",
     "01_default/results_f8d348b/gpuc4/strided_transfer.csv", "Celerity-acpp"),
    ("Celerity + acpp (optimized)", "optimized/results/gpuc4/block_transfer.csv", "Celerity-acpp",
     "optimized/results/gpuc4/strided_transfer.csv", "Celerity-acpp"),
]
OUT_DIR = HERE
STRIDED_MS = [1, 2]  # M values shown in the strided plot

# fixed per variant (never by rank), validated categorical slots 1-3; markers are the second channel
STYLE = {
    "Celerity + acpp (old)": dict(color="#2a78d6", marker="o"),
    "Celerity + acpp (new)": dict(color="#eb6834", marker="s"),
    "Celerity + acpp (optimized)": dict(color="#1baf7a", marker="^"),
}
INK, MUTED, GRID = "#1f1f1e", "#6b6a63", "#dcdcd7"


def load(path, app):
    path = os.path.join(B, path)
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path)
    df = df[(df["application"] == app) & (df["data_size_gib"] > 0)]  # also drops failed runs
    return df


def mean_std(df, keys):
    return (df.groupby(keys + ["data_size_gib"], as_index=False)
            .agg(mean=("copy_bandwidth", "mean"), std=("copy_bandwidth", "std"))
            .sort_values("data_size_gib"))


def draw(ax, g, label, log_y):
    x, y, err = g["data_size_gib"].values, g["mean"].values, g["std"].fillna(0).values
    ax.plot(x, y, label=label, linewidth=2, markersize=6, **STYLE[label])
    lower = np.clip(y - err, y * 0.01 if log_y else 0, None)
    ax.fill_between(x, lower, y + err, color=STYLE[label]["color"], alpha=0.15, linewidth=0)


def style_axes(ax, x_vals, every=1):
    ax.set_xscale("log", base=2)
    lo, hi = int(np.floor(np.log2(x_vals.min()))), int(np.ceil(np.log2(x_vals.max())))
    exps = [i for i in range(lo, hi + 1) if (i - lo) % every == 0]
    ax.set_xticks([2.0 ** i for i in exps])
    ax.set_xticklabels([rf"$2^{{{i}}}$" for i in exps])
    ax.grid(True, which="major", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(colors=MUTED, labelcolor=INK)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)


def plot_block(variants):
    fig, ax = plt.subplots(figsize=(19, 10))
    all_x = []
    for label, df in variants:
        g = mean_std(df, [])
        draw(ax, g, label, log_y=False)
        all_x.append(g["data_size_gib"])
    style_axes(ax, pd.concat(all_x))
    ax.set_xlabel("data size in GiB", color=INK)
    ax.set_ylabel("bandwidth in GB/s", color=INK)
    ax.set_title("block data transfer speed, gpuc4, Celerity + AdaptiveCpp", color=INK)
    ax.legend(loc="upper left", frameon=False)
    return fig


# strided: like the original plot, color = M (the original's colors); the variant is the line style and marker
VARIANT_LINE = {
    "Celerity + acpp (old)": dict(linestyle="-", marker="o"),
    "Celerity + acpp (new)": dict(linestyle="--", marker="s"),
    "Celerity + acpp (optimized)": dict(linestyle=":", marker="^"),
}


def plot_strided(variants):
    ms = [m for m in STRIDED_MS if any((df["M"] == m).any() for _, df in variants)]
    m_color = {m: plt.get_cmap("tab10")(i) for i, m in enumerate(ms)}
    fig, ax = plt.subplots(figsize=(19, 10))
    for label, df in variants:
        for m in ms:
            g = mean_std(df[df["M"] == m], ["M"])
            if not len(g):
                continue
            x, y, err = g["data_size_gib"].values, g["mean"].values, g["std"].fillna(0).values
            ax.plot(x, y, color=m_color[m], linewidth=1.8, markersize=5, **VARIANT_LINE[label])
            ax.fill_between(x, np.clip(y - err, y * 0.01, None), y + err, color=m_color[m], alpha=0.1, linewidth=0)
    ax.set_yscale("log")
    style_axes(ax, pd.concat([df["data_size_gib"] for _, df in variants]))
    ax.grid(True, which="minor", axis="y", color=GRID, linewidth=0.5)  # like the original grid(which="both")
    ax.set_xlabel("data size in GiB", color=INK)
    ax.set_ylabel("bandwidth in GB/s", color=INK)
    ax.set_title("strided data transfer speed, gpuc4, Celerity + AdaptiveCpp", color=INK)
    m_handles = [plt.Line2D([], [], color=m_color[m], linewidth=2.5, label=f"M={m}") for m in ms]
    v_handles = [plt.Line2D([], [], color=INK, linewidth=1.8, markersize=6, label=label, **VARIANT_LINE[label])
                 for label, _ in variants]
    ax.add_artist(ax.legend(handles=m_handles, loc="upper left", frameon=False))
    ax.legend(handles=v_handles, loc="upper left", bbox_to_anchor=(0.08, 1.0), frameon=False)
    return fig


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for kind, plot, csv_idx in (("block_transfer", plot_block, 1), ("strided_transfer", plot_strided, 3)):
        variants = []
        for v in VARIANTS:
            df = load(v[csv_idx], v[csv_idx + 1])
            if df is None:
                print(f"skip {v[0]} ({kind}): {v[csv_idx]} not found")
                continue
            variants.append((v[0], df))
        fig = plot(variants)
        out = os.path.join(OUT_DIR, f"{kind}_acpp.png")
        fig.savefig(out, dpi=300, bbox_inches="tight")
        plt.close(fig)
        print(out)


if __name__ == "__main__":
    main()
