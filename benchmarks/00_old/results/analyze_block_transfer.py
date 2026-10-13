import sys
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

def main():
    if len(sys.argv) < 2:
        print("Usage: python plot_benchmark.py <input.csv>")
        sys.exit(1)

    csv_file = sys.argv[1]

    # Load CSV
    df = pd.read_csv(csv_file)

    required_cols = {
        "application",
        "command",
        "iteration",
        "data_size_gib",
        "copy_bandwidth",
    }

    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # remove invalid log values
    df = df[df["data_size_gib"] > 0]

    # Group: mean + std over iterations
    grouped = (
        df.groupby(["application", "command", "data_size_gib"], as_index=False)
        .agg(
            copy_bandwidth_mean=("copy_bandwidth", "mean"),
            copy_bandwidth_std=("copy_bandwidth", "std"),
        )
    )

    plt.figure()

    # Plot per application
    for app, app_df in grouped.groupby("application"):
        app_df = app_df.sort_values("data_size_gib")

        x = app_df["data_size_gib"].values
        y = app_df["copy_bandwidth_mean"].values
        yerr = app_df["copy_bandwidth_std"].fillna(0).values

        plt.plot(
            x,
            y,
            marker="o",
            label=app,
        )

        # shaded ±1 std deviation
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
    plt.title("block data transfer speed")

    # --- log2 axis ---
    ax = plt.gca()
    ax.set_xscale("log", base=2)

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
        "block_data_transfer.png",
        dpi=300,              # increase to 600 for publication quality
        bbox_inches="tight"
    )

    plt.close()


if __name__ == "__main__":
    main()