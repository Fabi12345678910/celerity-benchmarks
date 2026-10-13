import sys
import os
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

def plot(df, title, out):
    # --- GROUPING: by M ---
    grouped = (
        df.groupby(["M", "command", "data_size_gib"], as_index=False)
        .agg(
            copy_bandwidth_mean=("copy_bandwidth", "mean"),
            copy_bandwidth_std=("copy_bandwidth", "std"),
        )
    )

    plt.figure()

    # --- PLOT PER M ---
    for m_value, m_df in grouped.groupby("M"):
        m_df = m_df.sort_values("data_size_gib")

        x = m_df["data_size_gib"].values
        y = m_df["copy_bandwidth_mean"].values
        yerr = m_df["copy_bandwidth_std"].fillna(0).values

        plt.plot(
            x,
            y,
            marker="o",
            label=f"M={m_value}",
        )

        # std deviation shading
        y_lower = np.clip(y - yerr, 0, None)
        y_upper = y + yerr

        plt.fill_between(
            x,
            y_lower,
            y_upper,
            alpha=0.2
        )

    plt.xlabel("data size in GiB")
    plt.ylabel("bandwidth in GB/s")
    plt.title(title)

    # --- log2 axis ---
    ax = plt.gca()
    ax.set_xscale("log", base=2)
    ax.set_yscale("log")

    # --- force ALL 2^n ticks ---
    x_vals = grouped["data_size_gib"]
    min_exp = int(np.floor(np.log2(x_vals.min())))
    max_exp = int(np.ceil(np.log2(x_vals.max())))

    ticks = [2 ** i for i in range(min_exp, max_exp + 1)]
    ax.set_xticks(ticks)
    ax.set_xticklabels([rf"$2^{{{i}}}$" for i in range(min_exp, max_exp + 1)])

    plt.legend()
    plt.grid(True, which="both")

    plt.tight_layout()

    plt.gcf().set_size_inches(19, 10)  # widescreen aspect ratio

    plt.savefig(
        out,
        dpi=300,              # increase to 600 for publication quality
        bbox_inches="tight"
    )
    print(out)
    plt.close()


def main():
    if len(sys.argv) < 2:
        print("Usage: python plot_strided_transfer.py <input.csv>")
        sys.exit(1)

    csv_file = sys.argv[1]

    df = pd.read_csv(csv_file)

    required_cols = {
        "application",
        "M",
        "command",
        "iteration",
        "data_size_gib",
        "copy_bandwidth",
    }

    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # remove invalid values for log scale (and failed runs, which have no values)
    df = df[df["data_size_gib"] > 0]

    # one figure per application (SYCL implementation)
    base = os.path.splitext(csv_file)[0]
    for app, app_df in df.groupby("application"):
        plot(app_df, f"strided data transfer speed ({app})", f"{base}_{app}.png")


if __name__ == "__main__":
    main()
