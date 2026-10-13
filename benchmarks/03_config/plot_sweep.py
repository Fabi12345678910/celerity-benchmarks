import glob
import os
import subprocess
import sys

# Plots the configuration sweep of one or more systems (benchmarks/03_config/<system>/results): one chart per tuning variable, copy
# direction and SYCL implementation, with every value of the variable as a line (strided: one line per value for M=1, the regular path, and M=2).
# Charts land in 03_config/<system>/results/plots/. Usage: python plot_sweep.py <system> [<system> ...]

HERE = os.path.dirname(os.path.abspath(__file__))

# group -> (file name patterns, sequential colors); "base"/"reference" are included where they are the comparison point
STRIDED = {
    "strided_queues": (["base", "queues_*"], True),
    "strided_chunk": (["base", "chunk_*"], True),
    "strided_staging": (["base", "staging_*"], True),
    "strided_min_bytes": (["base", "min_bytes_*"], True),
    "strided_elems_per_item": (["base", "host_kernel", "elems_per_item_*"], True),
    "strided_wg_size": (["base", "host_kernel", "wg_size_*"], True),
    "strided_flags": (["reference_default", "base", "host_kernel", "best_combination", "wait_poll", "host_staging_pageable",
                       "warmup", "sdma_off", "copylib_off_*"], False),
}
BLOCK = {
    "block_queues": (["queues_*"], True),
    "block_chunk": (["chunk_*"], True),
    "block_staging": (["staging_*"], True),
    "block_flags": (["reference_default", "flags_*"], False),
}


def main():
    for system in sys.argv[1:]:
        results = os.path.join(HERE, system, "results")
        out = os.path.join(results, "plots")
        for prefix, groups, m in (("strided", STRIDED, ["--m", "1,2"]), ("block", BLOCK, [])):
            for group, (patterns, sequential) in groups.items():
                files = sorted({f for p in patterns for f in glob.glob(os.path.join(results, f"{prefix}_{p}.csv"))})
                if not files:
                    print(f"{system} {group}: no results yet")
                    continue
                cmd = [sys.executable, os.path.join(HERE, "plot_config.py"), *files, *m, "--out", out, "--name", f"{system}_{group}"]
                if sequential:
                    cmd.append("--sequential")
                r = subprocess.run(cmd, capture_output=True, text=True)
                pngs = [l for l in r.stdout.splitlines() if l.endswith(".png")]
                print(f"{system} {group}: {len(files)} CSVs -> {len(pngs)} charts" + (f"  ERROR: {r.stderr[-300:]}" if r.returncode else ""))


if __name__ == "__main__":
    main()
