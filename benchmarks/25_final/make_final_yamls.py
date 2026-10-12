#!/usr/bin/env python3
"""Generates the final sweep (user decision 2026-10-08): everything tested before, on the final bench build with the new defaults
(staging 4 queues x 1 MiB, host kernel 2 queues x 4 MiB, SDMA off as the standing base), plus Celerity thread pinning off on every system.
Usage: python3 make_final_yamls.py [--validate | --validate2]

Groups (one YAML per config; paths relative to benchmarks/, results in 25_final/<system>/results/<name>.csv):
  sweep_*      the sweep 4 option set (21_sweep4/make_sweep4_yamls.py) on the new base. The base of each variant is the build's defaults with SDMA
               off (nothing else set), so the sweep checks the compiled-in defaults directly. Every option is swept one at a time on top of it;
               the queues x chunk grid is centered on the new defaults. Placements, including `celerity_pinning_off`, on all three systems.
               Anchors (reduced-grid copies of the base) end every job, as in sweep 4.
  prog_*       every other program at the defaults, staging / host kernel x pinning on / off as one env list (innermost parameter, so the four
               run back to back on the same node): sparse rows (09), both sides strided (08/09), row widths (10), contiguous host / strided
               device (22), plus the native path (CELERITY_COPYLIB=off) for each (smaller N: about 1 MB/s).
  pair_*       paired on/off studies at the defaults: preload (17) and SDMA (20), env innermost.
  --validate   validate_<system>.yaml only: the clean-build check (every program at the defaults, staging and host kernel, both
               implementations, all N), on the clean build and on final-bench, same node.
Overhead (23) and memcpy (24) are rerun with their own make_yamls.py after their programs are rebuilt against the final installs.
NVIDIA (ifi IFIgpu2070): nvidia_*.yaml, the defaults and pinning off only, AdaptiveCpp only (user decision 2026-10-08)."""
import glob
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
STUDY = "25_final"
KiB, MiB, GiB = 1024, 1024 ** 2, 1024 ** 3

# ---- the builds (fill in from the setup agent's reply; the YAMLs are regenerated afterwards) ------------------------------------------
CELERITY = "3dcopylib-final-bench f24e5f0"  # the bench build (clean + env switches + host-kernel mode), written into every CSV
CLEAN = "3dcopylib-final 4f88016"  # the clean release build: no env switches (CELERITY_COPYLIB* aborts), staging only
# build dirs under ~/finalizing-work/build, per program; {impl} is acpp or dpcpp0326
BUILD = {"strided_transfer": "bench-transfer-{impl}-final-bench", "block_transfer": "bench-transfer-{impl}-final-bench",
         "strided_both_transfer": "bench-both_strided-{impl}-final-bench", "strided_rows_transfer": "bench-rows-{impl}-final-bench",
         "device_strided_transfer": "bench-device_strided-{impl}-final-bench"}
BUILD_CLEAN = {k: v.replace("-final-bench", "-final") for k, v in BUILD.items()}
CLEAN2 = "3dcopylib-final d239713"  # the clean build with the minimal configuration (host-kernel switch, CELERITY_COPYLIB, COPYLIB_WORKER_CPUS), preload on, group+local kernel index (81b2cb2 was validated before: results/validate2_81b2cb2/)
BUILD_CLEAN2 = {k: v.replace("-final-bench", "-final2") for k, v in BUILD.items()}
# ifi and gpuc4 validate the published build instead (GitHub master 536d754 = the clean code of d239713 + docs/pin; library 843fafe): same code, no extra build
PUBLISHED = "celerity-runtime master 536d754 (published)"
BUILD_PUBLISHED = {k: v.replace("-final-bench", "-published") for k, v in BUILD.items()}
VALIDATE2_BUILD = {"lumi": (BUILD_CLEAN2, CLEAN2), "ifi": (BUILD_PUBLISHED, PUBLISHED), "gpuc4": (BUILD_PUBLISHED, PUBLISHED)}
BUILD_NVIDIA = "bench-transfer-acpp-cuda-final"
DPCPP_ENV = ". ~/finalizing-work/install/dpcpp-nightly-2026-03-26/env.sh && "
IMPLS = [("Celerity-acpp", "", "acpp"), ("Celerity-dpcpp", DPCPP_ENV, "dpcpp0326")]

JOB_MIN, SAFETY, ANCHOR_RESERVE_MIN = 105, 1.15, 25
SYSTEMS = {  # prefix for every run; worker placements (dedicated cores, both hyper-threads of one core, LUMI: far CCD)
    "gpuc4": dict(prefix="", dedicated="8,10", same_core="6,7"),
    "ifi": dict(prefix="", dedicated="5,6", same_core="5,21"),
    "lumi": dict(prefix="ROCR_VISIBLE_DEVICES=4", dedicated="5,6", same_core="5,69", far="49,50"),
}
SDMA_OFF = {"HSA_ENABLE_SDMA": 0}
PIN_OFF = {"CELERITY_THREAD_PINNING": "false"}
Q, CH, ST, MIN = "CELERITY_COPYLIB_QUEUES", "CELERITY_COPYLIB_CHUNK_BYTES", "CELERITY_COPYLIB_STAGING_BYTES", "CELERITY_COPYLIB_MIN_BYTES"
BASE = {"stg": dict(SDMA_OFF), "hk": {**SDMA_OFF, "COPYLIB_HOST_KERNEL": 1}}  # the build's defaults
# the compiled-in values (for skipping a swept value equal to the default; checked by the validation)
DEFAULT_VALUES = {"stg": {Q: 4, CH: MiB}, "hk": {Q: 2, CH: 4 * MiB, "COPYLIB_MAX_ELEM_SIZE": 16}}
NATIVE = {**SDMA_OFF, "CELERITY_COPYLIB": "off"}

FULL_N = [2 ** i for i in range(29)]
N24 = [2 ** i for i in range(25)]
NATIVE_N = [2 ** i for i in range(24)]
BLOCK_N = [2 ** i for i in range(32)]
STRIDED_M = [1, 2, 4]

# sweep 4's lists without its dropped (slow) values; the grid is centered on the new defaults
MIN_BYTES = (64, 256, KiB, 4 * KiB, 16 * KiB, 64 * KiB, 256 * KiB)
QUEUES = (1, 2, 3, 4, 6, 8, 12, 16, 24, 32)
QUEUES_HK = QUEUES + (64,)
STAGING = (64 * KiB, 256 * KiB, MiB, 4 * MiB, 8 * MiB, 16 * MiB, 64 * MiB, 128 * MiB, 512 * MiB, GiB)
CHUNK = (64 * KiB, 256 * KiB, 512 * KiB, MiB, 2 * MiB, 4 * MiB, 8 * MiB)
CHUNK_BIG = (16 * MiB, 32 * MiB)
ELEMS = (2, 4, 8, 16, 32, 64, 128, 256)
WG = (2, 4, 8, 16, 64, 128, 256, 512, 1024)
MAX_ELEM = (1, 2, 4, 8, 16, 32, 64)
ORDERS = ("block", "dynamic", "interleaved")
GRID = {"stg": ((2, 4, 8), (512 * KiB, MiB, 2 * MiB, 4 * MiB)), "hk": ((1, 2, 4), (MiB, 2 * MiB, 4 * MiB, 8 * MiB, 16 * MiB))}

METRICS = {"machine": "^(\\S+)", "buffer_creation_gbps": "buffer creation:.*?([0-9]+\\.[0-9]+)GB/s", "copy_bandwidth": "first access.*?:.*?([0-9]+\\.[0-9]+)GB/s",
           "read_only_gbps": "read only:.*?([0-9]+\\.[0-9]+)GB/s", "read_write_gbps": "read write:.*?([0-9]+\\.[0-9]+)GB/s",
           "d2h_gbps": "device to host:.*?([0-9]+\\.[0-9]+)GB/s", "check": "Check: (\\w+)", "full_data_size_gib": "Data Size:\\s*([0-9.]+)\\s*GiB",
           "data_size_gib": "Worked on Data Size:\\s*([0-9.]+)\\s*GiB"}
ARGS = {"strided_transfer": "{N} {M}", "block_transfer": "{N}", "strided_both_transfer": "{N} {M}", "strided_rows_transfer": "{N} {M} {W}",
        "device_strided_transfer": "{N} {M}"}


def size_name(b):
    for unit, f in (("GiB", GiB), ("MiB", MiB), ("KiB", KiB)):
        if b >= f and b % f == 0:
            return f"{b // f}{unit}"
    return f"{b}B"


def env_str(d):
    return " ".join(f"{k}={v}" for k, v in d.items())


class Cfg:
    """One YAML: a program, a list of envs (innermost parameter), the other parameters, and the static labels."""

    def __init__(self, name, program, envs, params, option="", value="", variant="", est=10.0, builds=None, impls=None, celerity=None):
        self.name, self.program, self.envs, self.params, self.option, self.value, self.variant = name, program, envs, params, option, value, variant
        self.est, self.builds, self.impls, self.celerity = est, builds or BUILD, impls or IMPLS, celerity or CELERITY


# ---- runtime estimates: the measured minutes of the closest earlier config, scaled by the number of runs ----------------------------------
def measured(system):
    out = {}
    for d in ("21_sweep4", "22_device_strided", "10_rows", "09_sparse", "17_preload", "20_sdma_defaults"):
        for f in glob.glob(os.path.join(HERE, "..", d, system, "results", "*.csv")) + glob.glob(os.path.join(HERE, "..", d, "results", f"{system}*.csv")):
            try:
                t = pd.read_csv(f, usecols=["runtime_sec"]).runtime_sec
            except ValueError:
                continue
            out[f"{d}/{os.path.basename(f)[:-4]}"] = t.sum() / 60
    return out


def est_from(table, key, scale=1.0, fallback=20.0):
    return table.get(key, fallback) * scale * SAFETY


# ---- groups ----------------------------------------------------------------------------------------------------------------------------
def placements(s):
    return {"all": {"COPYLIB_WORKER_CPUS": "all"}, "dedicated": {"COPYLIB_WORKER_CPUS": s["dedicated"]},
            "same_core": {"COPYLIB_WORKER_CPUS": s["same_core"]}, **({"far": {"COPYLIB_WORKER_CPUS": s["far"]}} if "far" in s else {}),
            "celerity_pinning_off": PIN_OFF}


def options(v, block):
    """(option, value, env overrides) swept on top of the variant's defaults."""
    dv = DEFAULT_VALUES[v]
    out = [("min_bytes", size_name(b), {MIN: b}) for b in MIN_BYTES]
    out += [("queues", str(q), {Q: q}) for q in (QUEUES_HK if v == "hk" else QUEUES) if dv.get(Q) != q]
    out += [("staging_bytes", size_name(b), {ST: b}) for b in STAGING if not (block and b < MiB)]
    out += [("chunk", size_name(b), {CH: b}) for b in CHUNK if dv.get(CH) != b]
    if not block:
        if v == "hk":
            out += [("chunk", size_name(b), {CH: b}) for b in CHUNK_BIG]
        else:  # staging chunks are capped at staging / queues
            out += [("chunk", size_name(b), {CH: b, ST: dv[Q] * b}) for b in CHUNK_BIG]
        qs, cs = GRID[v]
        out += [("grid", f"q{gq}_c{size_name(gb)}", {Q: gq, CH: gb}) for gq in qs for gb in cs if (gq, gb) != (dv[Q], dv[CH])]
    out += [("plan_order", p, {"COPYLIB_PLAN_ORDER": p}) for p in ORDERS]
    out.append(("wait_poll", "", {"COPYLIB_WAIT": "poll"}))
    if v == "stg":
        out += [("pageable", "", {"COPYLIB_HOST_STAGING": "pageable"}), ("sdma_on", "", {"HSA_ENABLE_SDMA": 1})]
    else:
        out.append(("preload_off", "", {"COPYLIB_PRELOAD_KERNELS": 0}))
        out += [("max_elem_size", str(m), {"COPYLIB_MAX_ELEM_SIZE": m}) for m in MAX_ELEM if dv.get("COPYLIB_MAX_ELEM_SIZE") != m]
        out += [("elems_per_item", str(e), {"COPYLIB_ELEMS_PER_ITEM": e}) for e in ELEMS]
        out += [("wg_size", str(w), {"COPYLIB_WG_SIZE": w}) for w in WG]
    return out


def sweep_configs(system, s, table):
    c = []
    for prog, short, n, m in (("strided_transfer", "strided", FULL_N, STRIDED_M), ("block_transfer", "block", BLOCK_N, None)):
        route = {"CELERITY_COPYLIB_ROUTE": "all"} if short == "block" else {}
        params = {"N": n, **({"M": m} if m else {})}
        old = lambda name: f"21_sweep4/{short}_{name}"
        if short == "strided":
            c.append(Cfg(f"sweep_strided_native", prog, [env_str(NATIVE)], {"N": NATIVE_N, "M": [2, 4]}, "native", "", "native",
                         est_from(table, "22_device_strided/device_native_2", 1.0, 60)))
        else:
            c.append(Cfg("sweep_block_native", prog, [env_str(SDMA_OFF)], params, "native", "", "native", est_from(table, old("native_base"))))
        for v in ("stg", "hk"):
            base = {**route, **BASE[v]}
            c.append(Cfg(f"sweep_{short}_{v}_base", prog, [env_str(base)], params, "base", "", v, est_from(table, old(f"{v}_base"))))
            for k, over in placements(s).items():
                c.append(Cfg(f"sweep_{short}_{v}_place_{k}", prog, [env_str({**base, **over})], params, "place", k, v, est_from(table, old(f"{v}_base"))))
            for option, value, over in options(v, short == "block"):
                name = f"{v}_{option}" + (f"_{value}" if value else "")
                c.append(Cfg(f"sweep_{short}_{name}", prog, [env_str({**base, **over})], params, option, value, v,
                             est_from(table, old(name), 1.0, table.get(old(f"{v}_base"), 20) * 1.1)))
    return c


def anchor(short, v, tag, table):
    prog = "strided_transfer" if short == "strided" else "block_transfer"
    route = {"CELERITY_COPYLIB_ROUTE": "all"} if short == "block" else {}
    params = {"N": [2 ** i for i in range(16, 29, 2)], "M": STRIDED_M} if short == "strided" else {"N": [2 ** 16, 2 ** 20, 2 ** 24, 2 ** 28]}
    full = len(FULL_N) * 3 if short == "strided" else len(BLOCK_N)
    part = len(params["N"]) * (3 if short == "strided" else 1)
    return Cfg(f"sweep_{short}_{v}_anchor_{tag}", prog, [env_str({**route, **BASE[v]})], params, "anchor", tag, v,
               est_from(table, f"21_sweep4/{short}_{v}_base", part / full))


def four(over_stg=None, over_hk=None):
    """staging / host kernel x pinning on / off at the defaults, as one env list."""
    a, b = {**BASE["stg"], **(over_stg or {})}, {**BASE["hk"], **(over_hk or {})}
    return [env_str(a), env_str(b), env_str({**a, **PIN_OFF}), env_str({**b, **PIN_OFF})]


def program_configs(table):
    c = []
    t = lambda key, scale=1.0: est_from(table, key, scale, 40)
    # sparse rows: 4-byte values with a pitch of 64 / 128 / 256 bytes (09_sparse), host side strided
    c.append(Cfg("prog_sparse", "strided_transfer", four(), {"N": N24, "M": [16, 32, 64]}, "program", "sparse", "", t("21_sweep4/strided_stg_base", 4 * 25 * 3 / (29 * 3))))
    c.append(Cfg("prog_sparse_native", "strided_transfer", [env_str(NATIVE)], {"N": NATIVE_N[:21], "M": [16, 64]}, "native", "sparse", "native", 60))
    # both sides strided (08_both_strided, 09_sparse)
    c.append(Cfg("prog_both", "strided_both_transfer", four(), {"N": N24, "M": [2, 4, 16, 32, 64]}, "program", "both", "", t("21_sweep4/strided_stg_base", 4 * 25 * 5 / (29 * 3))))
    c.append(Cfg("prog_both_native", "strided_both_transfer", [env_str(NATIVE)], {"N": NATIVE_N[:21], "M": [2, 64]}, "native", "both", "native", 60))
    # row widths S = 4 W bytes per 256-byte pitch (10_rows)
    c.append(Cfg("prog_rows", "strided_rows_transfer", four(), {"N": N24, "M": [64], "W": [1, 8, 16, 32, 64]}, "program", "rows", "", t("21_sweep4/strided_stg_base", 4 * 25 * 5 / (29 * 3))))
    c.append(Cfg("prog_rows_native", "strided_rows_transfer", [env_str(NATIVE)], {"N": NATIVE_N[:21], "M": [64], "W": [8, 32]}, "native", "rows", "native", 60))
    # contiguous host, strided device (22_device_strided)
    c.append(Cfg("prog_device", "device_strided_transfer", four(), {"N": FULL_N, "M": STRIDED_M}, "program", "device", "", t("22_device_strided/device_stg_base", 4.4)))
    c.append(Cfg("prog_device_native", "device_strided_transfer", [env_str(NATIVE)], {"N": NATIVE_N, "M": [2, 4]}, "native", "device", "native", t("22_device_strided/device_native_2")))
    return c


def pair_configs(table):
    pre = lambda v, p: env_str({**BASE[v], "COPYLIB_PRELOAD_KERNELS": p})
    sd = lambda v, x: env_str({**BASE[v], "HSA_ENABLE_SDMA": x})
    return [Cfg("pair_preload", "strided_transfer", [pre("stg", 1), pre("stg", 0), pre("hk", 1), pre("hk", 0)],
                {"N": [1, 1024, 65536, 1048576, 16777216], "M": [1, 2]}, "pair", "preload", "", 30),
            Cfg("pair_sdma", "strided_transfer", [sd("stg", 0), sd("stg", 1), sd("hk", 0), sd("hk", 1)], {"N": FULL_N, "M": [1, 2]}, "pair", "sdma", "", 60)]


def validate_configs():
    """The clean build against the final-bench build, every program at the defaults (staging; the clean build has no host kernel and no env
    switches, so only HSA_ENABLE_SDMA=0 is set). One job per program holds the clean and the final-bench YAML, so both run on the same node
    (ifi: within the 2 h limit). The host kernel is covered by the final sweep (final-bench only)."""
    out = []
    for build, cel, tag in ((BUILD_CLEAN, CLEAN, "clean"), (BUILD, CELERITY, "bench")):
        envs = [env_str(BASE["stg"])]
        out += [Cfg(f"validate_strided_{tag}", "strided_transfer", envs, {"N": FULL_N, "M": STRIDED_M}, "validate", tag, "", 60, build, celerity=cel),
                Cfg(f"validate_block_{tag}", "block_transfer", [env_str(SDMA_OFF)], {"N": BLOCK_N[:31]}, "validate", tag, "", 30, build, celerity=cel),
                Cfg(f"validate_both_{tag}", "strided_both_transfer", envs, {"N": N24, "M": [2, 64]}, "validate", tag, "", 20, build, celerity=cel),
                Cfg(f"validate_rows_{tag}", "strided_rows_transfer", envs, {"N": N24, "M": [64], "W": [8, 64]}, "validate", tag, "", 20, build, celerity=cel),
                Cfg(f"validate_device_{tag}", "device_strided_transfer", envs, {"N": FULL_N, "M": [2, 4]}, "validate", tag, "", 30, build, celerity=cel)]
    return out


def validate2_configs(system="lumi"):
    """The clean build final2 (d239713; earlier 81b2cb2) against final-bench at the defaults, staging and host kernel (COPYLIB_HOST_KERNEL=1 exists in both), every
    program; one job per program holds both YAMLs (same node)."""
    out = []
    for build, cel, tag in ((*VALIDATE2_BUILD[system], "clean2"), (BUILD, CELERITY, "bench")):
        envs = [env_str(BASE["stg"]), env_str(BASE["hk"])]
        out += [Cfg(f"validate2_strided_{tag}", "strided_transfer", envs, {"N": FULL_N, "M": STRIDED_M}, "validate2", tag, "", 60, build, celerity=cel),
                Cfg(f"validate2_block_{tag}", "block_transfer", [env_str(SDMA_OFF)], {"N": BLOCK_N[:31]}, "validate2", tag, "", 30, build, celerity=cel),
                Cfg(f"validate2_both_{tag}", "strided_both_transfer", envs, {"N": N24, "M": [2, 64]}, "validate2", tag, "", 20, build, celerity=cel),
                Cfg(f"validate2_rows_{tag}", "strided_rows_transfer", envs, {"N": N24, "M": [64], "W": [8, 64]}, "validate2", tag, "", 20, build, celerity=cel),
                Cfg(f"validate2_device_{tag}", "device_strided_transfer", envs, {"N": FULL_N, "M": [2, 4]}, "validate2", tag, "", 30, build, celerity=cel)]
    return out


def nvidia_configs():
    impl = [("Celerity-acpp", "", "acpp-cuda")]
    b = {"strided_transfer": BUILD_NVIDIA}
    return [Cfg("nvidia_strided", "strided_transfer", four(), {"N": FULL_N, "M": [1, 2]}, "nvidia", "defaults", "", 60, b, impl),
            Cfg("nvidia_strided_native", "strided_transfer", [env_str(NATIVE)], {"N": FULL_N, "M": [1, 2]}, "native", "", "native", 60, b, impl)]


# ---- output ----------------------------------------------------------------------------------------------------------------------------
def q(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def flow(values):
    return "[" + ", ".join(q(v) if isinstance(v, str) else str(v) for v in values) + "]"


def write(system, prefix, cfg, iterations=3):
    lines = ["# generated by make_final_yamls.py", f"iterations: {iterations}", "warmup_iterations: 1",
             f"output_csv: {STUDY}/{system}/results/{cfg.name}.csv", "", "applications:"]
    for app, source, impl in cfg.impls:
        p = prefix + " " if prefix else ""
        build = cfg.builds[cfg.program].format(impl=impl)
        lines += [f"  - name: {app}", f"    command: {q(f'hostname; {source}{p}{{env}} ~/finalizing-work/build/{build}/{cfg.program} {ARGS[cfg.program]}')}",
                  "    parameters:"]
        lines += [f"      {k}: {flow(v)}" for k, v in cfg.params.items()]
        lines.append(f"      env: {flow(cfg.envs)}")  # innermost: the envs of one point run back to back
        lines.append("    metrics:")
        lines += [f"      {k}: {q(v)}" for k, v in METRICS.items()]
        static = {"celerity": cfg.celerity, "program": cfg.program, "variant": cfg.variant, "config": cfg.name, "option": cfg.option, "value": cfg.value}
        lines += ["    static: {" + ", ".join(f"{k}: {q(v)}" for k, v in static.items() if v != "") + "}", ""]
    os.makedirs(os.path.join(HERE, system, "results"), exist_ok=True)
    with open(os.path.join(HERE, system, cfg.name + ".yaml"), "w") as f:
        f.write("\n".join(lines).rstrip() + "\n")


def split(cfgs, limit):
    """Configs estimated above one job: the longest list parameter (M or W) into parts, so every YAML fits the 2 h Slurm limit, while the env
    list (staging / host kernel x pinning on / off) stays together and its runs stay paired on one node. Parts are named <name>_p<k>."""
    out = []
    for c in cfgs:
        parts = [c]
        done = []
        for p in parts:
            key = max((k for k in p.params if k != "N"), key=lambda k: len(p.params[k]), default=None)
            n = 1
            while key and n < len(p.params[key]) and p.est * -(-len(p.params[key]) // n) / len(p.params[key]) > limit:
                n += 1  # the largest part must fit
            if n == 1:
                done.append(p)
                continue
            vals = p.params[key]
            for k in range(n):
                sub = vals[k::n]
                done.append(Cfg(f"{p.name}_p{k + 1}", p.program, p.envs, {**p.params, key: sub}, p.option, p.value, p.variant,
                                p.est * len(sub) / len(vals), p.builds, p.impls, p.celerity))
        out += done
    return out


def pack(cfgs, limit):
    jobs, cur, t = [], [], 0.0
    for c in cfgs:
        if cur and t + c.est > limit:
            jobs.append(cur)
            cur, t = [], 0.0
        cur.append(c)
        t += c.est
    return jobs + ([cur] if cur else [])


def chain_text(system, cfgs, done):
    return ("#!/bin/sh\n# runs every YAML of this system one after another (gpuc4); resumes after a crash by skipping finished CSVs\n"
            "cd ~/finalizing-work/benchmarks\nmd5sum benchmark_wrapper.py\n"
            "for f in " + " ".join(f"{STUDY}/{system}/{c.name}.yaml" for c in cfgs) + "; do\n"
            "\tcsv=$(sed -n 's/^output_csv: //p' $f)\n\t[ -s \"$csv\" ] && continue\n"
            "\techo \"=== $f $(date +%H:%M)\"\n\ttimeout 3h python3 -u benchmark_wrapper.py $f | grep -E \"phase|Done|Error|Traceback\"\ndone\n"
            f"echo {done} $(date +%H:%M)\n")


def main():
    validate2 = "--validate2" in sys.argv
    validate = "--validate" in sys.argv or validate2
    prefix = "validate2_" if validate2 else "validate_"
    for old in glob.glob(os.path.join(HERE, "*", f"{prefix}*.yaml" if validate else "*.yaml")):
        if validate or not os.path.basename(old).startswith(("validate_", "validate2_")):
            os.remove(old)
    for system, s in SYSTEMS.items():
        os.makedirs(os.path.join(HERE, system, "results"), exist_ok=True)
        if validate:
            cfgs = validate2_configs(system) if validate2 else validate_configs()
            for c in cfgs:
                write(system, s["prefix"], c, iterations=2)
            name = f"{prefix}jobs.txt"
            half = len(cfgs) // 2
            jobs = [[cfgs[i], cfgs[i + half]] for i in range(half)]  # per program: clean and final-bench in one job (same node)
        else:
            table = measured(system)
            sweep = sweep_configs(system, s, table)
            limit = JOB_MIN - ANCHOR_RESERVE_MIN
            jobs = pack(sweep, limit)
            for i, cs in enumerate(jobs, 1):
                cs += [anchor(p, v, f"j{i:02d}", table) for p in ("strided", "block") for v in ("stg", "hk")
                       if any(c.name.startswith(f"sweep_{p}_") for c in cs)]
            rest = split(program_configs(table) + pair_configs(table), JOB_MIN)
            jobs += pack(rest, JOB_MIN)
            for c in (c for cs in jobs for c in cs):
                write(system, s["prefix"], c)
            name = "jobs.txt"
            with open(os.path.join(HERE, system, "estimate.txt"), "w") as f:
                tot = sum(c.est for cs in jobs for c in cs)
                f.write(f"{system}: {sum(len(cs) for cs in jobs)} YAMLs in {len(jobs)} jobs, about {tot:.0f} min ({tot / 60:.1f} h) in total\n")
                f.writelines(f"job {i}: {len(cs)} yamls, {sum(c.est for c in cs):.0f} min: {cs[0].name} .. {cs[-1].name}\n" for i, cs in enumerate(jobs, 1))
            print(open(os.path.join(HERE, system, "estimate.txt")).readline().strip())
        with open(os.path.join(HERE, system, name), "w") as f:
            f.write("".join(" ".join(f"{STUDY}/{system}/{c.name}.yaml" for c in cs) + "\n" for cs in jobs))
        if system == "gpuc4":
            with open(os.path.join(HERE, system, f"{prefix}chain.sh" if validate else "chain.sh"), "w") as f:
                f.write(chain_text(system, [c for cs in jobs for c in cs], "VALIDATE-DONE" if validate else "FINAL-DONE"))
    if not validate:
        os.makedirs(os.path.join(HERE, "nvidia", "results"), exist_ok=True)
        for c in nvidia_configs():
            write("nvidia", "", c)
        with open(os.path.join(HERE, "nvidia", "jobs.txt"), "w") as f:
            f.write(" ".join(f"{STUDY}/nvidia/{c.name}.yaml" for c in nvidia_configs()) + "\n")


if __name__ == "__main__":
    main()
