# Generates all benchmark YAMLs below this directory. Run: python3 make_yamls.py (rewrites every generated YAML).
#
#   workers/            initial worker/thread pinning benchmarks (gpuc4, ifi, LUMI with 1/2/4/8 GCDs)
#   gpuc4/ ifi/ lumi/   the configuration sweep, one directory per target system. Every configuration runs on top of the system's fixed
#                       pinning (SYSTEM_BASE, CSV column "base"); the swept flag is in the column "env". A system is generated only once
#                       its base is set.
#
# Each YAML writes <its directory>/results/<name>.csv (paths relative to benchmarks/, where the wrapper and job_bench.sbatch run).
# Strided: one file per configuration (about 35 min on ifi, the slowest, 1 KiB chunks, about 1 h; ifi jobs are limited to 2 h).
# Block: one file per flag group, split so that a file stays under about 60 min on ifi.
import os
import glob

HERE = os.path.dirname(os.path.abspath(__file__))
KiB, MiB, GiB = 1024, 1024 ** 2, 1024 ** 3

# Fixed pinning per target system, prepended to every sweep configuration: the best variant of the worker benchmarks.
# None: not decided yet, the system's directory is not generated.
# Decided 2026-10-04 from the worker benchmarks (workers/results, results_v1): dedicated workers on two free physical cores next to
# Celerity's threads were best or equal-best everywhere; on LUMI one GCD (more GCDs share the same 2 workers and only add startup cost),
# GCD 4, whose CCD holds Celerity's default cores 1-4.
SYSTEM_BASE = {
    "gpuc4": "COPYLIB_WORKER_CPUS=8,10",
    "ifi": "COPYLIB_WORKER_CPUS=5,6",
    "lumi": "ROCR_VISIBLE_DEVICES=4 COPYLIB_WORKER_CPUS=5,6",
}
# The references run Celerity's and copylib's own defaults; on LUMI still on one GCD, so they stay single-device runs
SYSTEM_REFERENCE = {"lumi": "ROCR_VISIBLE_DEVICES=4"}

# strided: the original N (1 .. 8 Mi) plus 16 .. 256 Mi rows, so copies span many chunks (256 Mi rows = 1 GiB per direction, 64 default
# chunks); M > 4 dropped (the host buffer grows with M, the copied column does not)
STRIDED_N = [2 ** i for i in range(29)]  # 1 .. 268435456
STRIDED_N_ORIGINAL = [2 ** i for i in range(24)]  # 1 .. 8388608
STRIDED_M = [1, 2, 3, 4]
BLOCK_N = [2 ** i for i in range(32)]  # 1 .. 2147483648, as in the original block_transfer.yaml

BLOCK_MIN, BLOCK_JOB_MIN = 9, 60  # estimated ifi minutes per block configuration / per block file

HK = "COPYLIB_HOST_KERNEL=1"
ROUTE = "CELERITY_COPYLIB_ROUTE=all"
# best combination of the earlier strided_copy tuning, without its COPYLIB_WORKER_CPUS=all: pinning is the base's job
BEST = ("CELERITY_COPYLIB_QUEUES=4 CELERITY_COPYLIB_CHUNK_BYTES=1048576 COPYLIB_HOST_KERNEL=1 COPYLIB_MAX_ELEM_SIZE=4 "
        "COPYLIB_ELEMS_PER_ITEM=4 COPYLIB_WG_SIZE=256")


def size_name(b):
    for unit, f in (("GiB", GiB), ("MiB", MiB), ("KiB", KiB)):
        if b >= f and b % f == 0:
            return f"{b // f}{unit}"
    return f"{b}B"


# ---- sweep (per target system) -------------------------------------------------------------------------------------------------------
# strided: file name -> env (on top of the base)
STRIDED = {"strided_base": ""}
STRIDED.update({f"strided_min_bytes_{size_name(b)}": f"CELERITY_COPYLIB_MIN_BYTES={b}"
                for b in (64, 256, KiB, 4 * KiB, 16 * KiB, 64 * KiB, 256 * KiB, MiB, 4 * MiB, 16 * MiB)})
STRIDED.update({f"strided_queues_{q}": f"CELERITY_COPYLIB_QUEUES={q}" for q in (1, 3, 4, 6, 8, 12, 16, 24, 32, 64)})
STRIDED.update({f"strided_staging_{size_name(b)}": f"CELERITY_COPYLIB_STAGING_BYTES={b}"
                for b in (4 * KiB, 64 * KiB, 256 * KiB, MiB, 4 * MiB, 8 * MiB, 16 * MiB, 64 * MiB, 128 * MiB, 512 * MiB, GiB)})
STRIDED.update({f"strided_chunk_{size_name(b)}": f"CELERITY_COPYLIB_CHUNK_BYTES={b}"
                for b in (KiB, 4 * KiB, 16 * KiB, 64 * KiB, 256 * KiB, 512 * KiB, MiB, 2 * MiB, 4 * MiB, 8 * MiB)})
STRIDED["strided_host_kernel"] = HK  # = elems_per_item 1 = wg_size 32
STRIDED.update({f"strided_elems_per_item_{e}": f"{HK} COPYLIB_ELEMS_PER_ITEM={e}" for e in (2, 4, 8, 16, 32, 64, 128, 256, 1024)})
STRIDED.update({f"strided_wg_size_{w}": f"{HK} COPYLIB_WG_SIZE={w}" for w in (1, 2, 4, 8, 16, 64, 128, 256, 512, 1024)})
STRIDED.update({
    "strided_wait_poll": "COPYLIB_WAIT=poll",
    "strided_host_staging_pageable": "COPYLIB_HOST_STAGING=pageable",
    "strided_warmup": "COPYLIB_WARMUP=1",
    "strided_sdma_off": "HSA_ENABLE_SDMA=0",
    "strided_best_combination": BEST,
})
# CELERITY_COPYLIB=off: the regular path needs about 7 s per Mi rows and direction, so only the original N (up to 8 Mi; 256 Mi rows
# would take about 30 min per copy), split by M (about 25 min per M >= 2 on ifi)
STRIDED_OFF_M = {"strided_copylib_off_1": [2, 3], "strided_copylib_off_2": [4, 1]}

# block: group -> list of (env, estimated ifi minutes or None for BLOCK_MIN)
BLOCK = {
    "flags": [("", None), (ROUTE, None), ("HSA_ENABLE_SDMA=0", None), (f"{ROUTE} HSA_ENABLE_SDMA=0", None), (f"{ROUTE} {HK}", None),
              (f"{ROUTE} COPYLIB_WAIT=poll", None), (f"{ROUTE} COPYLIB_HOST_STAGING=pageable", None)],
    "queues": [("", None)] + [(f"{ROUTE} CELERITY_COPYLIB_QUEUES={q}", None) for q in (1, 2, 3, 4, 6, 8, 12, 16, 24, 32, 64)],
    "staging": [("", None)] + [(f"{ROUTE} CELERITY_COPYLIB_STAGING_BYTES={b}", 15 if b <= 64 * KiB else None)
                               for b in (64 * KiB, 256 * KiB, MiB, 4 * MiB, 8 * MiB, 16 * MiB, 32 * MiB, 64 * MiB, 128 * MiB,
                                         512 * MiB, GiB)],
    "chunk": [("", None)] + [(f"{ROUTE} CELERITY_COPYLIB_CHUNK_BYTES={b}", 20 if b <= 16 * KiB else None)
                             for b in (16 * KiB, 64 * KiB, 256 * KiB, 512 * KiB, MiB, 2 * MiB, 4 * MiB, 8 * MiB, 16 * MiB)],
}
# Every chunk costs a fixed 40-90 us (strided measurements with 1 KiB chunks), and block copies are up to 8 GiB, i.e. millions of tiny
# chunks: 1 KiB chunks would take about 6 h for the full block sizes. These run alone and only up to 2^28 values (1 GiB per copy).
BLOCK_SLOW = {"block_chunk_1KiB": f"{ROUTE} CELERITY_COPYLIB_CHUNK_BYTES={KiB}",
              "block_chunk_4KiB": f"{ROUTE} CELERITY_COPYLIB_CHUNK_BYTES={4 * KiB}",
              "block_staging_4KiB": f"{ROUTE} CELERITY_COPYLIB_STAGING_BYTES={4 * KiB}"}
BLOCK_N_SLOW = [2 ** i for i in range(29)]  # 1 .. 268435456

# ---- worker benchmarks (workers/) ----------------------------------------------------------------------------------------------------
# gpuc4: CPUs 2k and 2k+1 share a P-core; ifi: CPUs n and n+16 share a core. Celerity pins its threads to CPUs 1-4 on both.
WORKERS = {
    "strided_default": "",
    "strided_worker_cpus_all": "COPYLIB_WORKER_CPUS=all",
    "strided_dedicated_gpuc4": "COPYLIB_WORKER_CPUS=8,10",  # one physical core per worker, away from Celerity's threads
    "strided_dedicated_ifi": "COPYLIB_WORKER_CPUS=5,6",  # run only the files of the machine
    "strided_same_core_gpuc4": "COPYLIB_WORKER_CPUS=6,7",  # one fixed CPU per worker, both hyper-threads of one physical core
    "strided_same_core_ifi": "COPYLIB_WORKER_CPUS=5,21",
}

# LUMI: worker CPU pinning with 1, 2, 4 and 8 visible GCDs.
# GCD order as LUMI recommends (map:4,5,2,3,6,7,0,1), so device 0 is always GCD 4, next to Celerity's default cores 1-4. Celerity pins
# 3 + (GCDs) threads from core 1 on (core 8 is not available): 1-4, 1-5, 1-7, 1-7 and 9-12. Hyper-threading siblings are +64.
LUMI_GCDS = {1: "4", 2: "4,5", 4: "4,5,2,3", 8: "4,5,2,3,6,7,0,1"}
LUMI_NEAR = {1: "5,6", 2: "6,7", 4: "9,10", 8: "13,14"}  # the next free cores after Celerity's threads
LUMI_SAME_CORE = {1: "5,69", 2: "6,70", 4: "9,73", 8: "13,77"}  # one fixed CPU per worker, both on one physical core
LUMI_FAR = "49,50"  # GCD 0's CCD on NUMA node 3, away from Celerity's threads (NUMA node 0)


def lumi_envs(g):
    return ["", "COPYLIB_WORKER_CPUS=all", f"COPYLIB_WORKER_CPUS={LUMI_NEAR[g]}", f"COPYLIB_WORKER_CPUS={LUMI_SAME_CORE[g]}",
            f"COPYLIB_WORKER_CPUS={LUMI_FAR}", "CELERITY_THREAD_PINNING=false"]


# Split into many short jobs (about LUMI_JOB_MIN each) that run in parallel on separate nodes. Split by size, never by variant, so all
# variants of a size are compared on the same node; a size too long for one job is split by SYCL implementation, then by M.
LUMI_STARTUP_S = {1: 0.7, 2: 1.0, 4: 1.6, 8: 2.9}  # measured process startup per run (smoke test, 2026-10-04)
LUMI_JOB_MIN = 10


def lumi_split(g):
    def minutes(n, ms, impls):  # runs * (startup + about 8 s per 256 Mi rows for the copies and the buffer creation)
        return len(lumi_envs(g)) * len(ms) * impls * 4 * (LUMI_STARTUP_S[g] + 8 * n / 2 ** 28) / 60
    apps = [a for a, _ in IMPLS]
    jobs, cur, t = [], [], 0
    for n in STRIDED_N:
        m = minutes(n, STRIDED_M, 2)
        if m > LUMI_JOB_MIN:
            if cur:
                jobs.append((cur, STRIDED_M, None))
                cur, t = [], 0
            halves = [STRIDED_M] if minutes(n, STRIDED_M, 1) <= LUMI_JOB_MIN else [STRIDED_M[:2], STRIDED_M[2:]]
            jobs += [([n], ms, [app]) for app in apps for ms in halves]
            continue
        if cur and t + m > LUMI_JOB_MIN:
            jobs.append((cur, STRIDED_M, None))
            cur, t = [], 0
        cur.append(n)
        t += m
    return jobs + ([(cur, STRIDED_M, None)] if cur else [])


# ---- YAML output ---------------------------------------------------------------------------------------------------------------------
METRICS = {
    "machine": "^(\\S+)",
    "buffer_creation_gbps": "buffer creation:.*?([0-9]+\\.[0-9]+)GB/s",
    "copy_bandwidth": "first access.*?:.*?([0-9]+\\.[0-9]+)GB/s",
    "read_only_gbps": "read only:.*?([0-9]+\\.[0-9]+)GB/s",
    "read_write_gbps": "read write:.*?([0-9]+\\.[0-9]+)GB/s",
    "d2h_gbps": "device to host:.*?([0-9]+\\.[0-9]+)GB/s",
    "check": "Check: (\\w+)",
}
STRIDED_METRICS = {**METRICS, "full_data_size_gib": "Data Size:\\s*([0-9.]+)\\s*GiB",
                   "data_size_gib": "Worked on Data Size:\\s*([0-9.]+)\\s*GiB"}
BLOCK_METRICS = {**METRICS, "data_size_gib": "Data Size:\\s*([0-9.]+)\\s*GiB"}

IMPLS = [("Celerity-acpp", ""), ("Celerity-dpcpp", ". ~/finalizing-work/install/dpcpp-nightly-2026-03-26/env.sh && ")]
BIN = {"Celerity-acpp": "~/finalizing-work/build/bench-transfer-acpp-bench",
       "Celerity-dpcpp": "~/finalizing-work/build/bench-transfer-dpcpp0326-bench"}


def q(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def flow(values):
    return "[" + ", ".join(q(v) if isinstance(v, str) else str(v) for v in values) + "]"


def write(directory, name, program, envs, sizes, metrics, base=None, gcds=None, impls=None):
    """base: fixed env prepended to every env (CSV column "base"); gcds: ROCR_VISIBLE_DEVICES (CSV column "gcds")."""
    lines = ["# generated by make_yamls.py", "iterations: 3", "warmup_iterations: 1",
             f"output_csv: 03_config/{directory}/results/{name}.csv", "", "applications:"]
    for app, prefix in [i for i in IMPLS if impls is None or i[0] in impls]:
        args = "{N} {M}" if program == "strided_transfer" else "{N}"
        visible = "ROCR_VISIBLE_DEVICES={gcds} " if gcds else ""
        fixed = "{base} " if base is not None else ""
        lines += [f"  - name: {app}",
                  f"    command: {q('hostname; ' + prefix + visible + fixed + '{env} ' + BIN[app] + '/' + program + ' ' + args)}",
                  "    parameters:"]
        if base is not None:
            lines.append(f"      base: {flow([base])}")
        if gcds:
            lines.append(f"      gcds: {flow([gcds])}")
        lines.append(f"      env: {flow(envs)}")
        lines += [f"      {k}: {flow(v)}" for k, v in sizes.items()]
        lines.append("    metrics:")
        lines += [f"      {k}: {q(v)}" for k, v in metrics.items()]
        lines += ["    static: {celerity: \"3dcopylib-bench f8d348b\"}", ""]
    os.makedirs(os.path.join(HERE, directory, "results"), exist_ok=True)
    with open(os.path.join(HERE, directory, name + ".yaml"), "w") as f:
        f.write("\n".join(lines).rstrip() + "\n")
    return f"{directory}/{name}"


def pack(configs):
    """Greedily packs (env, minutes) into files of at most BLOCK_JOB_MIN estimated ifi minutes; slow configurations go last."""
    parts, cur, t = [], [], 0
    for env, m in sorted(configs, key=lambda c: c[1] or BLOCK_MIN):
        m = m or BLOCK_MIN
        if cur and t + m > BLOCK_JOB_MIN:
            parts.append(cur)
            cur, t = [], 0
        cur.append(env)
        t += m
    return parts + [cur]


def main():
    for old in glob.glob(os.path.join(HERE, "**", "*.yaml"), recursive=True):
        os.remove(old)
    written = []
    all_sizes = {"N": STRIDED_N, "M": STRIDED_M}

    for name, env in WORKERS.items():
        written.append(write("workers", name, "strided_transfer", [env], all_sizes, STRIDED_METRICS))
    for g, gcds in LUMI_GCDS.items():
        for i, (ns, ms, impls) in enumerate(lumi_split(g), 1):
            written.append(write("workers", f"lumi_workers_{g}gcd_{i:02d}", "strided_transfer", lumi_envs(g), {"N": ns, "M": ms},
                                 STRIDED_METRICS, gcds=gcds, impls=impls))

    for system, base in SYSTEM_BASE.items():
        if base is None:
            print(f"skipped {system}: SYSTEM_BASE not decided yet")
            continue
        # reference: Celerity's and copylib's own defaults, without the base
        ref = SYSTEM_REFERENCE.get(system, "")
        written.append(write(system, "strided_reference_default", "strided_transfer", [""], all_sizes, STRIDED_METRICS, base=ref))
        written.append(write(system, "block_reference_default", "block_transfer", [""], {"N": BLOCK_N}, BLOCK_METRICS, base=ref))
        for name, env in STRIDED.items():
            written.append(write(system, name, "strided_transfer", [env], all_sizes, STRIDED_METRICS, base=base))
        for name, ms in STRIDED_OFF_M.items():
            written.append(write(system, name, "strided_transfer", ["CELERITY_COPYLIB=off"], {"N": STRIDED_N_ORIGINAL, "M": ms},
                                 STRIDED_METRICS, base=base))
        for group, configs in BLOCK.items():
            parts = pack(configs)
            for i, envs in enumerate(parts, 1):
                name = f"block_{group}" + (f"_{i}" if len(parts) > 1 else "")
                written.append(write(system, name, "block_transfer", envs, {"N": BLOCK_N}, BLOCK_METRICS, base=base))
        for name, env in BLOCK_SLOW.items():
            written.append(write(system, name, "block_transfer", [env], {"N": BLOCK_N_SLOW}, BLOCK_METRICS, base=base))
    print("\n".join(written))


if __name__ == "__main__":
    main()
