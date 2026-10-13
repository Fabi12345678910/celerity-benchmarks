# Generates the defaults sweep (sweep 2, celerity-bench 014e21a): which default value of each copylib option is best, separately for the
# two variants. Run: python3 make_defaults_yamls.py
#
# One option is changed at a time on top of the variant's base. Only options that act on the variant are swept:
#   staging      (COPYLIB_HOST_KERNEL=0: CPU pack/unpack into pinned staging + DMA; the device side is contiguous, so no copylib kernel runs)
#     base         the worker sweep's recommendation (06_cores/): n workers on dedicated cores, dynamic order, 4 MiB chunks, staging n * 4 MiB
#     chunk_<x>    chunk size x, staging n * x                      CELERITY_COPYLIB_CHUNK_BYTES (+ STAGING_BYTES, which only caps the chunk)
#     order_<o>    block (copylib's default), interleaved           COPYLIB_PLAN_ORDER
#     wait_poll    spin on the DMA event instead of blocking         COPYLIB_WAIT
#     pageable     host staging from aligned_alloc                   COPYLIB_HOST_STAGING
#     sdma_off     DMA by blit kernels instead of the copy engines   HSA_ENABLE_SDMA
#     alloc_far    host staging first-touched on NUMA node 3 (LUMI only; gpuc4 and ifi have one NUMA node)   COPYLIB_ALLOC_CPU_IDS
#     not swept: worker count and placement (06_cores/), WG_SIZE / ELEMS_PER_ITEM / MAX_ELEM_SIZE / WARMUP (no copylib kernel),
#     HIP_HOST_COHERENT and GPU_MAX_HW_QUEUES (only GPU caching and compute queues; the DMA engines use neither)
#   host kernel  (COPYLIB_HOST_KERNEL=1: one GPU kernel per chunk reads/writes the pinned host buffer directly)
#     base         copylib's defaults: 2 queues, 16 MiB chunks (32 MiB staging / 2), block order, work-group 32, 1 element per item,
#                  up to 64-byte elements; workers on the sweep base's cores (they only submit kernels and wait)
#     chunk_<x>    chunk size x, whole = 0 (one kernel per copy)    CELERITY_COPYLIB_CHUNK_BYTES
#     queues_<q>   q queues = q kernels in flight (16 MiB chunks, workers on the q nearest dedicated cores)   CELERITY_COPYLIB_QUEUES
#     queues_8_hw_queues_8   8 queues on 8 instead of HIP's default 4 hardware queues                    GPU_MAX_HW_QUEUES
#     order_<o>    dynamic, interleaved                              COPYLIB_PLAN_ORDER
#     wait_poll                                                      COPYLIB_WAIT
#     wg_<w>       work-group size                                   COPYLIB_WG_SIZE
#     elems_<e>    elements per work item                            COPYLIB_ELEMS_PER_ITEM
#     max_elem_<b> widest access per element; only the wide rows (4-byte rows always use 4-byte elements)    COPYLIB_MAX_ELEM_SIZE
#     warmup       loads the copy kernels at startup                 COPYLIB_WARMUP
#     coherent     pinned host memory fine-grained (uncached on the GPU); acpp and DPC++ both allocate it with default flags
#                                                                    HIP_HOST_COHERENT
#     not swept: HOST_STAGING, ALLOC_CPU_IDS, HSA_ENABLE_SDMA (no staging, no DMA)
#
# Data shapes, both SYCL implementations, 3 runs + 1 warmup each:
#   strided_transfer       4-byte rows, pitch 8 / 16 B (M = 2, 4), N 2^16 .. 2^28 (up to 1 GiB per copy)
#   strided_rows_transfer  4 / 32 / 128-byte rows with a 256-byte pitch (M = 64, W = 1, 8, 32), N 2^14 .. 2^24 (up to 2 GiB per copy)
# Output: 12_defaults/<system>/<variant>_<option>.yaml writing 12_defaults/<system>/results/<same name>.csv (paths relative to benchmarks/);
# run_order.txt per system (bases first).
import os
import glob

HERE = os.path.dirname(os.path.abspath(__file__))
KiB, MiB = 1024, 1024 ** 2

SYSTEMS = {
    # dedicated free cores, nearest first (as in 06_cores/); staging workers (the worker sweep's choice); host-kernel workers (sweep base)
    "gpuc4": dict(cores=[8, 10, 12, 14, 6, 16, 17, 18], workers=4, hk_cpus="8,10", prefix=""),
    "ifi": dict(cores=[5, 6, 7, 0, 8, 9, 10, 11], workers=8, hk_cpus="5,6", prefix=""),
    "lumi": dict(cores=[5, 6, 7, 9, 10, 11, 12, 13], workers=4, hk_cpus="5,6", prefix="ROCR_VISIBLE_DEVICES=4", alloc_far=49),
}

STRIDED = dict(program="strided_transfer", args="{N} {M}", N=[2 ** i for i in range(16, 29, 2)], M=[2, 4], static={"W": 1})
ROWS = dict(program="strided_rows_transfer", args="{N} 64 {W}", N=[2 ** i for i in range(14, 25, 2)], W=[1, 8, 32], static={"M": 64})
WIDE_ROWS = {**ROWS, "W": [8, 32]}

IMPLS = [("Celerity-acpp", "", "acpp"), ("Celerity-dpcpp", ". ~/finalizing-work/install/dpcpp-nightly-2026-03-26/env.sh && ", "dpcpp0326")]
BINARY = {"strided_transfer": "bench-transfer-{}-bench", "strided_rows_transfer": "bench-rows-{}-bench"}
METRICS = {
    "machine": "^(\\S+)",
    "buffer_creation_gbps": "buffer creation:.*?([0-9]+\\.[0-9]+)GB/s",
    "copy_bandwidth": "first access.*?:.*?([0-9]+\\.[0-9]+)GB/s",
    "read_only_gbps": "read only:.*?([0-9]+\\.[0-9]+)GB/s",
    "read_write_gbps": "read write:.*?([0-9]+\\.[0-9]+)GB/s",
    "d2h_gbps": "device to host:.*?([0-9]+\\.[0-9]+)GB/s",
    "check": "Check: (\\w+)",
    "full_data_size_gib": "Data Size:\\s*([0-9.]+)\\s*GiB",
    "data_size_gib": "Worked on Data Size:\\s*([0-9.]+)\\s*GiB",
}


def size_name(b):
    for unit, f in (("MiB", MiB), ("KiB", KiB)):
        if b >= f and b % f == 0:
            return f"{b // f}{unit}"
    return f"{b}B"


def env(d):
    return " ".join(f"{k}={v}" for k, v in d.items())


def staging(s):
    n = s["workers"]
    base = {"CELERITY_COPYLIB_QUEUES": n, "CELERITY_COPYLIB_STAGING_BYTES": n * 4 * MiB, "CELERITY_COPYLIB_CHUNK_BYTES": 4 * MiB,
            "COPYLIB_WORKER_CPUS": ",".join(map(str, s["cores"][:n])), "COPYLIB_PLAN_ORDER": "dynamic"}
    c = {"base": base}
    for b in (256 * KiB, 512 * KiB, MiB, 2 * MiB, 8 * MiB, 16 * MiB, 32 * MiB, 64 * MiB):
        c[f"chunk_{size_name(b)}"] = {**base, "CELERITY_COPYLIB_STAGING_BYTES": n * b, "CELERITY_COPYLIB_CHUNK_BYTES": b}
    for order in ("block", "interleaved"):
        c[f"order_{order}"] = {**base, "COPYLIB_PLAN_ORDER": order}
    c["wait_poll"] = {**base, "COPYLIB_WAIT": "poll"}
    c["pageable"] = {**base, "COPYLIB_HOST_STAGING": "pageable"}
    c["sdma_off"] = {**base, "HSA_ENABLE_SDMA": 0}
    if "alloc_far" in s:
        c["alloc_far"] = {**base, "COPYLIB_ALLOC_CPU_IDS": s["alloc_far"]}
    return {k: (v, [STRIDED, ROWS]) for k, v in c.items()}


def host_kernel(s):
    base = {"COPYLIB_WORKER_CPUS": s["hk_cpus"], "COPYLIB_HOST_KERNEL": 1}
    c = {"base": base}
    for name, b in (("whole", 0), ("256KiB", 256 * KiB), ("1MiB", MiB), ("4MiB", 4 * MiB), ("64MiB", 64 * MiB), ("256MiB", 256 * MiB)):
        c[f"chunk_{name}"] = {**base, "CELERITY_COPYLIB_CHUNK_BYTES": b}
    for q in (1, 4, 8):
        c[f"queues_{q}"] = {**base, "COPYLIB_WORKER_CPUS": ",".join(map(str, s["cores"][:q])), "CELERITY_COPYLIB_QUEUES": q,
                            "CELERITY_COPYLIB_CHUNK_BYTES": 16 * MiB}
    c["queues_8_hw_queues_8"] = {**c["queues_8"], "GPU_MAX_HW_QUEUES": 8}
    for order in ("dynamic", "interleaved"):
        c[f"order_{order}"] = {**base, "COPYLIB_PLAN_ORDER": order}
    c["wait_poll"] = {**base, "COPYLIB_WAIT": "poll"}
    for w in (16, 64, 128, 256, 1024):
        c[f"wg_{w}"] = {**base, "COPYLIB_WG_SIZE": w}
    for e in (2, 4, 16):
        c[f"elems_{e}"] = {**base, "COPYLIB_ELEMS_PER_ITEM": e}
    c["warmup"] = {**base, "COPYLIB_WARMUP": 1}
    c["coherent"] = {**base, "HIP_HOST_COHERENT": 1}
    shapes = {k: [STRIDED, ROWS] for k in c}
    for b in (4, 8, 16, 32):
        c[f"max_elem_{b}"] = {**base, "COPYLIB_MAX_ELEM_SIZE": b}
        shapes[f"max_elem_{b}"] = [WIDE_ROWS]
    return {k: (v, shapes[k]) for k, v in c.items()}


def q(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def write(system, name, variant, e, shapes, prefix):
    lines = ["# generated by make_defaults_yamls.py", "iterations: 3", "warmup_iterations: 1",
             f"output_csv: 12_defaults/{system}/results/{name}.csv", "", "applications:"]
    for shape in shapes:
        for app, source, impl in IMPLS:
            binary = f"~/finalizing-work/build/{BINARY[shape['program']].format(impl)}/{shape['program']}"
            command = f"hostname; {source}{prefix + ' ' if prefix else ''}{{env}} {binary} {shape['args']}"
            lines += [f"  - name: {app}", f"    command: {q(command)}", "    parameters:", f"      env: [{q(e)}]",
                      f"      N: [{', '.join(map(str, shape['N']))}]"]
            lines += [f"      {k}: [{', '.join(map(str, shape[k]))}]" for k in ("M", "W") if k in shape]
            lines.append("    metrics:")
            lines += [f"      {k}: {q(v)}" for k, v in METRICS.items()]
            static = {"celerity": "3dcopylib-bench 014e21a", "program": shape["program"], "variant": variant, "config": name,
                      **shape["static"], **({"prefix": prefix} if prefix else {})}
            lines += ["    static: {" + ", ".join(f"{k}: {q(v) if isinstance(v, str) else v}" for k, v in static.items()) + "}", ""]
    with open(os.path.join(HERE, system, name + ".yaml"), "w") as f:
        f.write("\n".join(lines).rstrip() + "\n")


def main():
    for old in glob.glob(os.path.join(HERE, "*", "*.yaml")):
        os.remove(old)
    for system, s in SYSTEMS.items():
        os.makedirs(os.path.join(HERE, system, "results"), exist_ok=True)
        names = []
        for variant, prefix_name, configs in (("staging", "staging", staging(s)), ("host kernel", "hk", host_kernel(s))):
            for name, (e, shapes) in configs.items():
                write(system, f"{prefix_name}_{name}", variant, env(e), shapes, s["prefix"])
                names.append(f"{prefix_name}_{name}")
        order = [n for n in names if n.endswith("_base")] + [n for n in names if not n.endswith("_base")]
        with open(os.path.join(HERE, system, "run_order.txt"), "w") as f:
            f.write("".join(f"12_defaults/{system}/{n}.yaml\n" for n in order))
        print(f"{system}: {len(names)} configurations")


if __name__ == "__main__":
    main()
