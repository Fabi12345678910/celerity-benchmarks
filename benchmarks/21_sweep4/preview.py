#!/usr/bin/env python3
"""Prints the preview of sweep 4: the swept values per option and variant (base in bold, values in []), and per system the number of configs,
jobs, node-hours and the estimated finish time if the jobs are submitted at START (default: now). gpuc4 runs one chain; ifi and LUMI jobs run in
parallel on PAR nodes (list scheduling, longest job first). Usage: python3 preview.py [HH:MM] [--no-block]"""
import re
import sys
import datetime as dt

import make_sweep4_yamls as m

PAR = {"ifi": 8, "lumi": 8}
NAMES = {"min_bytes": "MIN_BYTES", "queues": "QUEUES", "staging_bytes": "STAGING_BYTES", "chunk": "CHUNK_BYTES", "grid": "QUEUES x CHUNK_BYTES (grid)",
         "plan_order": "PLAN_ORDER", "wait_poll": "WAIT=poll", "pageable": "HOST_STAGING=pageable", "sdma_on": "SDMA on (HSA_ENABLE_SDMA=1)", "preload_off": "preload off",
         "max_elem_size": "MAX_ELEM_SIZE", "elems_per_item": "ELEMS_PER_ITEM", "wg_size": "WG_SIZE", "place": "worker placement"}
BASE_VALUE = {("stg", "queues"): "4", ("hk", "queues"): "4", ("stg", "chunk"): "1MiB", ("hk", "chunk"): "1MiB", ("hk", "max_elem_size"): "4",
              ("hk", "elems_per_item"): "4", ("hk", "wg_size"): "256", ("stg", "place"): "all", ("hk", "place"): "all"}


def values(configs, program, variant, option):
    vs = [str(c.value) for c in configs if c.name.startswith(program) and c.variant == variant and c.option == option and c.value != ""]
    base = BASE_VALUE.get((variant, option))
    if base and base not in vs and option in ("queues", "chunk", "max_elem_size", "elems_per_item", "wg_size"):
        vs.append(base)
    if option == "place" and "all" not in vs:
        vs.append("all")
    key = lambda v: (m.__dict__.get("UNIT_ORDER", 0), len(v), v)
    return vs, base


def fmt(vs, base):
    if not vs:
        return "–"
    def num(v):
        d = re.match(r"(\d+)(B|KiB|MiB|GiB)?", v)
        return int(d.group(1)) * {"B": 1, "KiB": 1024, "MiB": 1 << 20, "GiB": 1 << 30, None: 1}[d.group(2)] if d else 0
    if all(re.match(r"\d", v) and "_" not in v for v in vs):
        vs = sorted(vs, key=num)
    return "[" + ", ".join(f"**{v}**" if v == base else v for v in vs) + "]"


def main():
    flags = [a for a in sys.argv[1:] if a.startswith("--")]
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=2)))
    start = now if not args else now.replace(hour=int(args[0][:2]), minute=int(args[0][3:]), second=0)
    s = m.SYSTEMS["gpuc4"]
    cfgs = m.strided_configs(s) + m.block_configs(s)
    print("| Option | staging, strided | host kernel, strided | staging, block | host kernel, block |\n|---|---|---|---|---|")
    for option, label in NAMES.items():
        cells = [fmt(*values(cfgs, p, v, option)) for p in ("strided", "block") for v in ("stg", "hk")]
        if any(c != "–" for c in cells):
            print(f"| {label} | " + " | ".join(cells) + " |")
    print("\nReferences: `base` (4 queues, 1 MiB chunks; host kernel also MAX_ELEM_SIZE 4, 4 elements per item, work-group 256; SDMA off in all configs), "
          "`defaults` (the build's defaults, SDMA off); block also the native copy path (`native base`, `native sdma_on`).")
    print(f"\n| System | configs (+ anchors) | strided / block min | jobs | node-hours | parallel | finish if started {start:%a %H:%M} CEST |\n|---|---|---|---|---|---|---|")
    for system in ("gpuc4", "ifi", "lumi"):
        lines = open(f"{system}/estimate.txt").read().splitlines()
        head = lines[0]
        total = float(re.search(r"(\d+) min in total", head).group(1))
        sb = re.search(r"strided (\d+), block (\d+)", head).groups()
        jobs = [float(re.search(r": (\d+) configs, (\d+) min", l).group(2)) for l in lines if l.startswith("job ")]
        par = PAR.get(system, 1)
        free = [0.0] * par
        for j in sorted(jobs, reverse=True):
            i = free.index(min(free))
            free[i] += j
        span = max(free) if system != "gpuc4" else total
        fin = start + dt.timedelta(minutes=span)
        n = int(re.search(r"(\d+) configurations", head).group(1))
        print(f"| {system} | {n} | {sb[0]} / {sb[1]} | {len(jobs) if system != 'gpuc4' else '1 chain'} | {total / 60:.1f} | {par if system != 'gpuc4' else 1} | {span / 60:.1f} h → {fin:%a %H:%M} |")
    print("\nLUMI costs 4 GPU-h per node-hour, i.e. about %.0f GPU-h for the sweep (each job at most 8 GPU-h, inside the pre-approval)." % (float(re.search(r"(\d+) min in total", open("lumi/estimate.txt").readline()).group(1)) / 60 * 4))


if __name__ == "__main__":
    main()
