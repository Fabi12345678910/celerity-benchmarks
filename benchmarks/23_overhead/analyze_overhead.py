#!/usr/bin/env python3
"""Summary of the task-overhead study. For every system: median over the iterations per (program, config, tasks, elems, buffers) of submit, total,
drain and latency, and the Celerity overhead per task = Celerity total - the plain SYCL total of the same implementation. Needs pandas.
Usage: python3 analyze_overhead.py [system ...]   -> prints tables, writes summary_<system>.csv"""
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
METRICS = ["submit_us_per_task", "total_us_per_task", "drain_us", "latency_us"]


def label(r):
    if r.application.startswith("Celerity"):
        env = r.env
        mode = "native" if "COPYLIB=off" in env else ("hk" if "COPYLIB_HOST_KERNEL=1" in env else "stg")
        return f"{r.application}/{mode}" + ("/strided" if r.strided == 1 else "/kernel")
    return r.application


def load(system):
    frames = []
    for name in ("plain", "celerity", "celerity_strided", "celerity_native", "celerity_strided_acpp", "celerity_strided_dpcpp"):
        p = os.path.join(HERE, system, "results", f"overhead_{name}.csv")
        if os.path.exists(p):
            frames.append(pd.read_csv(p))
    d = pd.concat(frames, ignore_index=True)
    d["env"] = d["env"].fillna("") if "env" in d else ""
    d["strided"] = d["strided"].fillna(0) if "strided" in d else 0
    bad = d[d.check != "ok"]
    if len(bad):
        print(f"{system}: {len(bad)} of {len(d)} runs not ok", file=sys.stderr)
    d = d[d.check == "ok"].copy()
    d["program"] = d.apply(label, axis=1)
    return d


def summarize(system):
    d = load(system)
    g = d.groupby(["program", "tasks", "elems", "buffers"])[METRICS].median().reset_index()
    g.insert(0, "system", system)
    base = g[g.program.isin(["SYCL-acpp", "SYCL-dpcpp"])].copy()
    base["impl"] = base.program.str.split("-").str[1]
    base = base.set_index(["impl", "tasks", "elems", "buffers"]).total_us_per_task.rename("sycl_total")
    c = g[g.program.str.startswith("Celerity")].copy()
    c["impl"] = c.program.str.extract(r"Celerity-(\w+)/")[0]
    c = c.join(base, on=["impl", "tasks", "elems", "buffers"])
    c["overhead_us"] = c.total_us_per_task - c.sycl_total
    out = pd.concat([g[~g.program.str.startswith("Celerity")], c.drop(columns="impl")], ignore_index=True)
    out.to_csv(os.path.join(HERE, f"summary_{system}.csv"), index=False)
    return out


def main():
    pd.set_option("display.width", 250, "display.max_columns", 30, "display.max_rows", 500)
    for system in sys.argv[1:] or ["gpuc4", "ifi", "lumi"]:
        if not os.path.isdir(os.path.join(HERE, system, "results")):
            continue
        s = summarize(system)
        print(f"\n===== {system}: chain (buffers=1), 1000 tasks, medians; overhead = Celerity total - SYCL total (same implementation), us per task")
        v = s[(s.tasks == 1000) & (s.buffers == 1)].copy()
        print(v.pivot_table(index="program", columns="elems", values="total_us_per_task").round(2).to_string())
        print("-- latency (us, one task + wait)")
        print(v.pivot_table(index="program", columns="elems", values="latency_us").round(1).to_string())
        print("-- Celerity overhead per task (us)")
        o = v[v.overhead_us.notna()]
        print(o.pivot_table(index="program", columns="elems", values="overhead_us").round(1).to_string())
        print("-- 64 independent buffers, 1000 tasks, total us per task")
        w = s[(s.tasks == 1000) & (s.buffers == 64)]
        print(w.pivot_table(index="program", columns="elems", values="total_us_per_task").round(2).to_string())


if __name__ == "__main__":
    main()
