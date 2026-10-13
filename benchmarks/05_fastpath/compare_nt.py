import sys
import pandas as pd

# Compares the non-temporal pack stores (05_fastpath/results/<system>_nt.csv, celerity-bench 014e21a) with the fixed-width host copy
# before them (05_fastpath/results/<system>.csv, c4ee4f1; the 4-byte rows run the same code in 32920be) and the host kernel of the
# night sweep (03_config/<system>/results/strided_host_kernel.csv): median GB/s per size, M and direction.
# Usage: python 05_fastpath/compare_nt.py <system> [<system> ...]

for system in sys.argv[1:]:
    runs = []
    for f, label in [(f"05_fastpath/results/{system}.csv", "fixed"), (f"05_fastpath/results/{system}_nt.csv", "nt")]:
        d = pd.read_csv(f)
        print(f"=== {system} {label}: {len(d)} rows, check not ok: {(d.check != 'ok').sum()}")
        d["cfg"] = d.env.fillna("").map(lambda e: f"{label}, 4 workers" if "QUEUES=4" in e else f"{label}, base")
        runs.append(d)
    hk = pd.read_csv(f"03_config/{system}/results/strided_host_kernel.csv").assign(cfg="host kernel")
    d = pd.concat(runs + [hk])
    d = d[d.N.isin(runs[0].N.unique()) & d.M.isin(runs[0].M.unique())]
    d["GiB"] = d.N * 4 / 2**30
    for metric, name in [("copy_bandwidth", "host -> device"), ("d2h_gbps", "device -> host")]:
        t = d.groupby(["application", "M", "GiB", "cfg"])[metric].median().unstack("cfg")
        t = t[["fixed, base", "nt, base", "fixed, 4 workers", "nt, 4 workers", "host kernel"]]
        t["nt/fixed base"] = t["nt, base"] / t["fixed, base"]
        t["nt/fixed 4w"] = t["nt, 4 workers"] / t["fixed, 4 workers"]
        print(f"\n{name}, median GB/s")
        print(t.round(2).to_string())
