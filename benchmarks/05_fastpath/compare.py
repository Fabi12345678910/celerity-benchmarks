import sys
import pandas as pd

# Compares the fixed-width host copy runs (05_fastpath/results/<system>.csv, celerity-bench c4ee4f1) with the night sweep before the
# change (03_config/<system>/results/strided_base.csv and strided_host_kernel.csv, f8d348b): median GB/s per size, M and direction.
# Usage: python 05_fastpath/compare.py <system> [<system> ...]

for system in sys.argv[1:]:
    new = pd.read_csv(f"05_fastpath/results/{system}.csv")
    print(f"=== {system}: {len(new)} rows, check not ok: {(new.check != 'ok').sum()}")
    new["cfg"] = new.env.fillna("").map(lambda e: "new, 4 workers" if "QUEUES=4" in e else "new, base")
    old = pd.read_csv(f"03_config/{system}/results/strided_base.csv").assign(cfg="old, base")
    hk = pd.read_csv(f"03_config/{system}/results/strided_host_kernel.csv").assign(cfg="host kernel")
    d = pd.concat([new, old, hk])
    d = d[d.N.isin(new.N.unique()) & d.M.isin(new.M.unique())]
    d["GiB"] = d.N * 4 / 2**30
    for metric, name in [("copy_bandwidth", "host -> device"), ("d2h_gbps", "device -> host")]:
        t = d.groupby(["application", "M", "GiB", "cfg"])[metric].median().unstack("cfg")
        t = t[["old, base", "new, base", "new, 4 workers", "host kernel"]]
        t["speedup"] = t["new, base"] / t["old, base"]
        print(f"\n{name}, median GB/s")
        print(t.round(2).to_string())
