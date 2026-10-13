#!/usr/bin/env python3
# Generates sweep 3: the option set and value lists of the very first configuration sweep (03_config/make_yamls.py, "night sweep"), rerun on
# the new defaults (Celerity 3dcopylib-bench 2dda28f) and for both copylib variants. Run: python3 make_sweep3_yamls.py
#
# What is the same as in the first sweep: the swept options and their values (MIN_BYTES, QUEUES, STAGING_BYTES, CHUNK_BYTES, ELEMS_PER_ITEM,
# WG_SIZE, WAIT=poll, HOST_STAGING=pageable, SDMA off, the best combination of the earlier tuning, the worker placements of workers/,
# CELERITY_COPYLIB=off), the programs (strided_transfer M 1, 2, 4 with N 1..2^28, block_transfer N 1..2^31 with ROUTE=all), 3 iterations +
# 1 warmup, both SYCL implementations, one YAML per strided configuration.
# What is different (updated: the base is the best combination of the earlier tuning, see BASE):
#   * the base is the best combination of the earlier tuning (the first sweep's BEST: 4 queues, 1 MiB chunks, and for the host kernel
#     MAX_ELEM_SIZE 4, 4 elements per item, work-group 256), split by variant; every option is swept on top of it, one at a time, and values
#     equal to the base are left out. Two more references per variant: `defaults` (the build's defaults, nothing set: 8/2 queues, workers on
#     all CPUs, preload on, 16-byte elements) and `old` (the defaults before 2dda28f, emulated by env)
#   * two more options: COPYLIB_MAX_ELEM_SIZE 1..64 (hk) and COPYLIB_PLAN_ORDER block / dynamic / interleaved (both)
#   * M = 1, 2, 4 (M = 3 dropped)
#   * every option runs on the variant it acts on (03_config/ swept the queue, chunk and staging options on staging only):
#       stg  staging, COPYLIB_HOST_KERNEL unset: 8 queues, 4 MiB chunks, 32 MiB staging
#       hk   host kernel, COPYLIB_HOST_KERNEL=1: 2 queues, 16 MiB chunks. ELEMS_PER_ITEM and WG_SIZE act only here; WAIT, MIN_BYTES, QUEUES,
#            STAGING_BYTES (only through the default chunk size) and CHUNK_BYTES on both; SDMA off and pageable staging only on stg
#   * COPYLIB_WARMUP is now COPYLIB_PRELOAD_KERNELS and on by default: the sweep value is 0
#   * the references are the old defaults emulated by env (as in 14_verify/) and, for strided, CELERITY_COPYLIB=off as before
# Not swept: worker count lists (06_cores/), HIP_HOST_COHERENT, GPU_MAX_HW_QUEUES, ALLOC_CPU_IDS, multi-GCD runs.
#
# Output per system: 15_sweep3/<system>/<name>.yaml writing 15_sweep3/<system>/results/<name>.csv (paths relative to benchmarks/), plus
#   jobs.txt   one job per line: the YAMLs one sbatch job runs (at most JOB_MIN estimated minutes; ifi and LUMI allow 2 h)
#   chain.sh   gpuc4: all YAMLs one after another        estimate.txt   per-job and total estimated minutes
# Anchors are on by default (see ANCHOR_*); --no-anchors reproduces the sweep that ran, --post-anchors adds them to a finished sweep.
# Estimates come from the first sweep's measured runtimes (03_config/<system>/results) for the same env, x SAFETY.
import glob
import os
import statistics
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
KiB, MiB, GiB = 1024, 1024 ** 2, 1024 ** 3
CELERITY = "3dcopylib-bench 2dda28f"
JOB_MIN, SAFETY = 105, 1.15
# Anchors: a reduced-grid copy of each variant's base inside every job (default), so any config can be compared to a base that ran on the same node
# in the same job. ANCHOR_RESERVE_MIN of every job is kept free for them. --no-anchors reproduces the sweep that ran on 2026-10-05 (without anchors).
ANCHOR_RESERVE_MIN = 25
IFI_NODES = [f"gc{n}" for n in range(20, 28)]
POST_REPEATS = 2  # --post-anchors: anchor repeats per ifi node / LUMI job

SYSTEMS = {
    # prefix for every run; worker placements of the first sweep's workers/ (dedicated, both hyper-threads of one core), LUMI extras
    "gpuc4": dict(prefix="", dedicated="8,10", same_core="6,7"),
    "ifi": dict(prefix="", dedicated="5,6", same_core="5,21"),
    "lumi": dict(prefix="ROCR_VISIBLE_DEVICES=4", dedicated="5,6", same_core="5,69", far="49,50", pinning_off=True),
}
STRIDED_N, STRIDED_N_ORIGINAL, STRIDED_M = [2 ** i for i in range(29)], [2 ** i for i in range(24)], [1, 2, 4]
BLOCK_N, BLOCK_N_SLOW = [2 ** i for i in range(32)], [2 ** i for i in range(29)]
MIN_BYTES = (64, 256, KiB, 4 * KiB, 16 * KiB, 64 * KiB, 256 * KiB, MiB, 4 * MiB, 16 * MiB)
QUEUES = (1, 3, 4, 6, 8, 12, 16, 24, 32, 64)
STAGING = (4 * KiB, 64 * KiB, 256 * KiB, MiB, 4 * MiB, 8 * MiB, 16 * MiB, 64 * MiB, 128 * MiB, 512 * MiB, GiB)
CHUNK = (KiB, 4 * KiB, 16 * KiB, 64 * KiB, 256 * KiB, 512 * KiB, MiB, 2 * MiB, 4 * MiB, 8 * MiB)
CHUNK_HK_STRIDED = (16 * MiB, 32 * MiB)  # host kernel uses the chunk size as is, so it can go beyond the staging cap (staging / queues)
CHUNK_STG_STRIDED = (16 * MiB, 32 * MiB)  # staging chunks are capped at staging / queues, so STAGING_BYTES grows with them (queues x chunk)
ELEMS = (2, 4, 8, 16, 32, 64, 128, 256, 1024)
WG = (1, 2, 4, 8, 16, 64, 128, 256, 512, 1024)
# block: the first sweep's lists (queues also 2; staging from 64 KiB, chunk from 16 KiB); 1 KiB / 4 KiB chunks and 4 KiB staging are slow
BLOCK_QUEUES, BLOCK_STAGING = (1, 2, 3, 4, 6, 8, 12, 16, 24, 32, 64), STAGING[1:]
BLOCK_CHUNK, BLOCK_CHUNK_SLOW = CHUNK[2:], (KiB, 4 * KiB)


def size_name(b):
    for unit, f in (("GiB", GiB), ("MiB", MiB), ("KiB", KiB)):
        if b >= f and b % f == 0:
            return f"{b // f}{unit}"
    return f"{b}B"


class Cfg:
    def __init__(self, name, program, variant, option, value, env, family, n=None, m=None, est_env=None):
        self.name, self.program, self.variant, self.option, self.value, self.env, self.family = name, program, variant, option, value, env, family
        self.n, self.m, self.est_env = n, m, env if est_env is None else est_env


# env dicts: a later key overrides the base, so an option is swept on top of the base by updating the dict
BASE = {  # the best combination of the earlier tuning (the first sweep's BEST), split by variant
    "stg": {"CELERITY_COPYLIB_QUEUES": 4, "CELERITY_COPYLIB_CHUNK_BYTES": MiB},
    "hk": {"COPYLIB_HOST_KERNEL": 1, "CELERITY_COPYLIB_QUEUES": 4, "CELERITY_COPYLIB_CHUNK_BYTES": MiB, "COPYLIB_MAX_ELEM_SIZE": 4,
           "COPYLIB_ELEMS_PER_ITEM": 4, "COPYLIB_WG_SIZE": 256},
}
DEFAULTS = {"stg": {}, "hk": {"COPYLIB_HOST_KERNEL": 1}}  # the build's defaults, nothing else set
OLD_ENV = {"COPYLIB_WORKER_CPUS": "inherit", "COPYLIB_PLAN_ORDER": "block", "COPYLIB_PRELOAD_KERNELS": 0, "COPYLIB_MAX_ELEM_SIZE": 64}
OLD = {"stg": {**OLD_ENV, "CELERITY_COPYLIB_QUEUES": 2}, "hk": {"COPYLIB_HOST_KERNEL": 1, **OLD_ENV}}
Q, CH, ST, MIN = "CELERITY_COPYLIB_QUEUES", "CELERITY_COPYLIB_CHUNK_BYTES", "CELERITY_COPYLIB_STAGING_BYTES", "CELERITY_COPYLIB_MIN_BYTES"
MAX_ELEM = (1, 2, 4, 8, 16, 32, 64)
ORDERS = ("block", "dynamic", "interleaved")


def env_str(d):
    return " ".join(f"{k}={v}" for k, v in d.items())


def placements(s):
    return {"all": "all", "inherit": "inherit", "dedicated": s["dedicated"], "same_core": s["same_core"], **({"far": s["far"]} if "far" in s else {})}


def options(s, route=False, block=False):
    """(variant, option, value, env overrides, family) of every swept setting; the first sweep's lists, plus MAX_ELEM_SIZE and PLAN_ORDER."""
    out = []
    for v in ("stg", "hk"):
        base = BASE[v]
        skip = lambda var, val: base.get(var) == val  # a value equal to the base is the base
        o = lambda option, value, over, fam: out.append((v, option, value, over, f"{v}-{fam}"))
        queues, staging, chunk = (BLOCK_QUEUES, BLOCK_STAGING, BLOCK_CHUNK) if block else (QUEUES, STAGING, CHUNK)
        for b in MIN_BYTES:
            o("min_bytes", size_name(b), {MIN: b}, "min_bytes")
        for q in queues:
            if not skip(Q, q):
                o("queues", q, {Q: q}, "queues")
        for b in staging:
            o("staging_bytes", size_name(b), {ST: b}, "staging")
        for b in chunk + (CHUNK_HK_STRIDED if v == "hk" and not block else ()):
            if not skip(CH, b):
                o("chunk", size_name(b), {CH: b}, "chunk")
        if v == "stg" and not block:
            for b in CHUNK_STG_STRIDED:
                o("chunk", size_name(b), {CH: b, ST: base[Q] * b}, "chunk")
        for p in ORDERS:
            o("plan_order", p, {"COPYLIB_PLAN_ORDER": p}, "misc")
        o("wait_poll", "", {"COPYLIB_WAIT": "poll"}, "misc")
        if v == "stg":
            o("pageable", "", {"COPYLIB_HOST_STAGING": "pageable"}, "misc")
            o("sdma_off", "", {"HSA_ENABLE_SDMA": 0}, "misc")
        else:
            o("preload_off", "", {"COPYLIB_PRELOAD_KERNELS": 0}, "misc")
            for m in MAX_ELEM:
                if not skip("COPYLIB_MAX_ELEM_SIZE", m):
                    o("max_elem_size", m, {"COPYLIB_MAX_ELEM_SIZE": m}, "kernel")
            for e in ELEMS:
                if not skip("COPYLIB_ELEMS_PER_ITEM", e):
                    o("elems_per_item", e, {"COPYLIB_ELEMS_PER_ITEM": e}, "kernel")
            for w in WG:
                if not skip("COPYLIB_WG_SIZE", w):
                    o("wg_size", w, {"COPYLIB_WG_SIZE": w}, "kernel")
    return out


def strided_configs(s):
    c = []

    def add(variant, option, value, env, family, **kw):
        c.append(Cfg(f"strided_{variant}_{option}" + (f"_{value}" if value != "" else ""), "strided_transfer", variant, option, value, env_str(env), family,
                     n=STRIDED_N, m=STRIDED_M, **kw))

    for v in ("stg", "hk"):
        add(v, "base", "", BASE[v], f"{v}-ref", est_env="")  # the best combination of the earlier tuning
        add(v, "defaults", "", DEFAULTS[v], f"{v}-ref", est_env="")  # the build's new defaults
        add(v, "old", "", OLD[v], f"{v}-ref", est_env="")  # the defaults before 2dda28f
        # worker placement (first sweep's workers/): inherit, two dedicated cores, both hyper-threads of one core (+ LUMI: far CCD, Celerity
        # thread pinning off); "all" is the build's default and a config of its own
        for k, cpus in placements(s).items():
            add(v, "place", k, {**BASE[v], "COPYLIB_WORKER_CPUS": cpus}, f"{v}-place", est_env="")
        if s.get("pinning_off"):
            add(v, "place", "celerity_pinning_off", {**BASE[v], "CELERITY_THREAD_PINNING": "false"}, f"{v}-place", est_env="")
    for v, option, value, over, fam in options(s):
        est = env_str(over) if option in ("min_bytes", "queues", "staging_bytes", "chunk", "wait_poll", "pageable", "sdma_off") else ""
        if v == "hk" and option in ("elems_per_item", "wg_size"):
            est = f"COPYLIB_HOST_KERNEL=1 {est}"
        add(v, option, value, {**BASE[v], **over}, fam, est_env=est)
    # the native path (CELERITY_COPYLIB=off) is slow: original N only, split by M
    for i, ms in enumerate(([2, 1], [4]), 1):
        add("native", "copylib_off", i, {"CELERITY_COPYLIB": "off"}, "native", est_env="CELERITY_COPYLIB=off")
        c[-1].n, c[-1].m = STRIDED_N_ORIGINAL, ms
    return c


def block_configs(s):
    c = []
    R = {"CELERITY_COPYLIB_ROUTE": "all"}

    def add(variant, option, value, env, family, n=BLOCK_N, est_env=None):
        c.append(Cfg(f"block_{variant}_{option}" + (f"_{value}" if value != "" else ""), "block_transfer", variant, option, value, env_str(env), family,
                     n=n, est_env=est_env))

    add("native", "base", "", {}, "block-ref", est_env="")  # Celerity's regular copy path, copylib not routed
    add("native", "sdma_off", "", {"HSA_ENABLE_SDMA": 0}, "block-ref", est_env="HSA_ENABLE_SDMA=0")
    for v in ("stg", "hk"):
        add(v, "base", "", {**R, **BASE[v]}, "block-ref", est_env=env_str(R))
        add(v, "defaults", "", {**R, **DEFAULTS[v]}, "block-ref", est_env=env_str(R))
        add(v, "old", "", {**R, **OLD[v]}, "block-ref", est_env=env_str(R))
        for k, cpus in placements(s).items():
            add(v, "place", k, {**R, **BASE[v], "COPYLIB_WORKER_CPUS": cpus}, f"{v}-place", est_env=env_str(R))
        if s.get("pinning_off"):
            add(v, "place", "celerity_pinning_off", {**R, **BASE[v], "CELERITY_THREAD_PINNING": "false"}, f"{v}-place", est_env=env_str(R))
    for v, option, value, over, fam in options(s, block=True):
        add(v, option, value, {**R, **BASE[v], **over}, fam, est_env=env_str({**R, **over}) if option in ("queues", "staging_bytes", "chunk", "wait_poll", "pageable", "sdma_off") else env_str(R))
    for v in ("stg", "hk"):
        for b in BLOCK_CHUNK_SLOW:
            add(v, "chunk", size_name(b), {**R, **BASE[v], CH: b}, f"{v}-slow", n=BLOCK_N_SLOW, est_env=env_str({**R, CH: b}))
        add(v, "staging_bytes", "4KiB", {**R, **BASE[v], ST: 4 * KiB}, f"{v}-slow", n=BLOCK_N_SLOW, est_env=env_str({**R, ST: 4 * KiB}))
    return c


ROUTE_ENV = {"CELERITY_COPYLIB_ROUTE": "all"}
ANCHOR_N = {"strided": [2 ** i for i in range(16, 29, 2)], "block": [2 ** 16, 2 ** 20, 2 ** 24, 2 ** 28]}  # contains every size the overview plots
ANCHOR_M = [1, 2, 4]


def anchor_cfg(program, variant, tag):
    env = BASE[variant] if program == "strided" else {**ROUTE_ENV, **BASE[variant]}
    prog = "strided_transfer" if program == "strided" else "block_transfer"
    return Cfg(f"{program}_{variant}_anchor_{tag}", prog, variant, "anchor", tag, env_str(env), "anchor", n=ANCHOR_N[program],
               m=ANCHOR_M if program == "strided" else None, est_env="")


def anchor_minutes(program, variant, est):
    full = (len(STRIDED_N) * len(STRIDED_M)) if program == "strided" else len(BLOCK_N)
    part = len(ANCHOR_N[program]) * (len(ANCHOR_M) if program == "strided" else 1)
    return est[f"{program}_{variant}_base"] * part / full


# ---- runtime estimates from the first sweep ----------------------------------------------------------------------------------------
def first_sweep_minutes(system):
    """(kind, env) -> estimated minutes of one configuration of the first sweep (3 measured + 1 warmup iteration, all N and M)."""
    seen = {}
    for f in glob.glob(os.path.join(HERE, "..", "03_config", system, "results", "*.csv")):
        kind = "strided" if os.path.basename(f).startswith("strided") else "block"
        d = pd.read_csv(f)
        if "runtime_sec" not in d:
            continue
        d["env"] = d["env"].fillna("")
        for env, g in d.groupby("env"):
            seen.setdefault((kind, env), []).append(g.runtime_sec.sum() * 4 / 3 / 60)  # one value per file: the same env can recur (anchors)
    return {k: statistics.mean(v) for k, v in seen.items()}


def estimate(cfg, table, fallback):
    kind = "strided" if cfg.program == "strided_transfer" else "block"
    m = table.get((kind, cfg.est_env))
    if m is None:
        m = fallback[kind]
    if kind == "strided":
        m *= 0.75  # M 1, 2, 4 instead of 1..4
    if CH not in cfg.env and "CELERITY_COPYLIB=off" not in cfg.env:  # the base's 1 MiB chunks cost more than the build's chunks
        ratio = table.get((kind, f"{CH}={MiB}"), 0) / table.get((kind, ""), 1) if table.get((kind, "")) else 1
        m *= min(max(ratio, 1.0), 3.0)
    return m * SAFETY * (1.0 if cfg.variant != "hk" else 1.05)


# ---- output ------------------------------------------------------------------------------------------------------------------------
METRICS = {"machine": "^(\\S+)", "buffer_creation_gbps": "buffer creation:.*?([0-9]+\\.[0-9]+)GB/s", "copy_bandwidth": "first access.*?:.*?([0-9]+\\.[0-9]+)GB/s",
           "read_only_gbps": "read only:.*?([0-9]+\\.[0-9]+)GB/s", "read_write_gbps": "read write:.*?([0-9]+\\.[0-9]+)GB/s",
           "d2h_gbps": "device to host:.*?([0-9]+\\.[0-9]+)GB/s", "check": "Check: (\\w+)"}
STRIDED_METRICS = {**METRICS, "full_data_size_gib": "Data Size:\\s*([0-9.]+)\\s*GiB", "data_size_gib": "Worked on Data Size:\\s*([0-9.]+)\\s*GiB"}
BLOCK_METRICS = {**METRICS, "data_size_gib": "Data Size:\\s*([0-9.]+)\\s*GiB"}
IMPLS = [("Celerity-acpp", "", "bench-transfer-acpp-bench"),
         ("Celerity-dpcpp", ". ~/finalizing-work/install/dpcpp-nightly-2026-03-26/env.sh && ", "bench-transfer-dpcpp0326-bench")]


def q(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def flow(values):
    return "[" + ", ".join(q(v) if isinstance(v, str) else str(v) for v in values) + "]"


def write(system, s, cfg):
    lines = ["# generated by make_sweep3_yamls.py", "iterations: 3", "warmup_iterations: 1", f"output_csv: 15_sweep3/{system}/results/{cfg.name}.csv", "",
             "applications:"]
    for app, source, build in IMPLS:
        args = "{N} {M}" if cfg.program == "strided_transfer" else "{N}"
        prefix = s["prefix"] + " " if s["prefix"] else ""
        lines += [f"  - name: {app}", f"    command: {q(f'hostname; {source}{prefix}{{env}} ~/finalizing-work/build/{build}/{cfg.program} {args}')}",
                  "    parameters:", f"      env: {flow([cfg.env])}", f"      N: {flow(cfg.n)}"]
        if cfg.m:
            lines.append(f"      M: {flow(cfg.m)}")
        lines.append("    metrics:")
        lines += [f"      {k}: {q(v)}" for k, v in (STRIDED_METRICS if cfg.program == "strided_transfer" else BLOCK_METRICS).items()]
        static = {"celerity": CELERITY, "program": cfg.program, "variant": {"stg": "staging", "hk": "host kernel", "native": "native"}[cfg.variant],
                  "config": cfg.name, "option": cfg.option, "value": str(cfg.value), "prefix": s["prefix"]}
        lines += ["    static: {" + ", ".join(f"{k}: {q(v)}" for k, v in static.items() if v != "") + "}", ""]
    os.makedirs(os.path.join(HERE, system, "results"), exist_ok=True)
    with open(os.path.join(HERE, system, cfg.name + ".yaml"), "w") as f:
        f.write("\n".join(lines).rstrip() + "\n")


def pack(configs, est):
    """Consecutive configurations (families stay together) into jobs of at most JOB_MIN estimated minutes."""
    jobs, cur, t = [], [], 0.0
    for cfg in configs:
        m = est[cfg.name]
        if cur and t + m > JOB_MIN:
            jobs.append((cur, t))
            cur, t = [], 0.0
        cur.append(cfg)
        t += m
    return jobs + ([(cur, t)] if cur else [])


def write_cfgs(system, s, cfgs):
    for c in cfgs:
        write(system, s, c)


def chain_text(system, groups, done):
    body = ("#!/bin/sh\n# runs every YAML of this system one after another (gpuc4); resumes after a crash by skipping finished CSVs\n"
            "cd ~/finalizing-work/benchmarks\nmd5sum benchmark_wrapper.py\n")
    body += "for f in " + " ".join(f"15_sweep3/{system}/{c.name}.yaml" for g in groups for c in g) + "; do\n"
    body += ("\tcsv=$(sed -n 's/^output_csv: //p' $f)\n\t[ -s \"$csv\" ] && continue\n"
             "\techo \"=== $f $(date +%H:%M)\"\n\ttimeout 3h python3 -u benchmark_wrapper.py $f | grep -E \"phase|Done|Error|Traceback\"\ndone\n")
    return body + f"echo {done} $(date +%H:%M)\n"


def post_anchors(system, s, est):
    """Anchors for a sweep that already ran without them: gpuc4 a chain, ifi one job per node (--nodelist), LUMI a few jobs."""
    def block_of(tag, reps):
        return [anchor_cfg(p, v, f"{tag}r{r}") for r in range(1, reps + 1) for p in ("strided", "block") for v in ("stg", "hk")]
    if system == "gpuc4":
        groups = [block_of("p", POST_REPEATS * 2)]
        nodes = ["-"]
    elif system == "ifi":
        groups = [block_of(n, POST_REPEATS) for n in IFI_NODES]
        nodes = IFI_NODES
    else:
        groups = [block_of(f"j{j}", POST_REPEATS) for j in range(1, 5)]
        nodes = ["-"] * 4
    write_cfgs(system, s, [c for g in groups for c in g])
    with open(os.path.join(HERE, system, "anchors_post_jobs.txt"), "w") as f:
        f.write("".join(f"{n} " + " ".join(f"15_sweep3/{system}/{c.name}.yaml" for c in g) + "\n" for n, g in zip(nodes, groups)))
    if system == "gpuc4":
        with open(os.path.join(HERE, system, "anchors_post_chain.sh"), "w") as f:
            f.write(chain_text(system, groups, "ANCHORS-DONE"))
    mins = [sum(anchor_minutes(c.name.split("_")[0], c.variant, est) for c in g) for g in groups]
    print(f"{system}: post anchors, {len(groups)} jobs, about {max(mins):.0f} min each")


def main():
    flags = [a for a in sys.argv[1:] if a.startswith("--")]
    only = [a for a in sys.argv[1:] if not a.startswith("--")] or list(SYSTEMS)
    anchors, post = "--no-anchors" not in flags, "--post-anchors" in flags
    if not post:
        for old in glob.glob(os.path.join(HERE, "*", "*.yaml")):
            os.remove(old)
    for system, s in SYSTEMS.items():
        if system not in only:
            continue
        os.makedirs(os.path.join(HERE, system, "results"), exist_ok=True)
        configs = strided_configs(s) + block_configs(s)
        table = first_sweep_minutes(system)
        fallback = {k: statistics.median(v for (kk, _), v in table.items() if kk == k) for k in ("strided", "block")}
        est = {c.name: estimate(c, table, fallback) for c in configs}
        if post:
            post_anchors(system, s, est)
            continue
        write_cfgs(system, s, configs)
        # order: strided before block, base and old first inside a family, then the option families as listed
        global JOB_MIN
        full_min = JOB_MIN
        JOB_MIN = full_min - (ANCHOR_RESERVE_MIN if anchors else 0)
        jobs = pack(configs, est)
        JOB_MIN = full_min
        if anchors:  # every job ends with a reduced-grid base of each variant (and program) it contains, named after the job
            jobs = [(cs + [anchor_cfg(p, v, f"j{i:02d}") for p in ("strided", "block") for v in ("stg", "hk")
                           if any(c.variant == v and c.name.startswith(p) for c in cs)], t) for i, (cs, t) in enumerate(jobs, 1)]
            write_cfgs(system, s, [c for cs, _ in jobs for c in cs if c.option == "anchor"])
            for cs, _ in jobs:
                for c in cs:
                    if c.option == "anchor":
                        est[c.name] = anchor_minutes(c.name.split("_")[0], c.variant, est)
            jobs = [(cs, sum(est[c.name] for c in cs)) for cs, _ in jobs]
        with open(os.path.join(HERE, system, "jobs.txt"), "w") as f:
            f.write("".join(" ".join(f"15_sweep3/{system}/{c.name}.yaml" for c in cs) + "\n" for cs, _ in jobs))
        with open(os.path.join(HERE, system, "estimate.txt"), "w") as f:
            f.write(f"{system}: {len(configs)} configurations{' + anchors' if anchors else ''}, {len(jobs)} jobs of at most {JOB_MIN} min, {sum(est.values()):.0f} min in total "
                    f"(strided {sum(m for n, m in est.items() if n.startswith('strided')):.0f}, block {sum(m for n, m in est.items() if n.startswith('block')):.0f})\n")
            f.writelines(f"job {i}: {len(cs)} configs, {t:.0f} min: {cs[0].name} .. {cs[-1].name}\n" for i, (cs, t) in enumerate(jobs, 1))
            f.writelines(f"{n:55s} {m:6.1f} min\n" for n, m in sorted(est.items(), key=lambda x: -x[1])[:15])
        with open(os.path.join(HERE, system, "chain.sh"), "w") as f:
            f.write(chain_text(system, [cs for cs, _ in jobs], "SWEEP3-DONE"))
        print(open(os.path.join(HERE, system, "estimate.txt")).readline().strip())


if __name__ == "__main__":
    main()
