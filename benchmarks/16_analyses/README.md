# 16_analyses

**Goal:** answer cross-study questions from the existing data (no new runs): can the host kernel be the default, and does the kernel
preload make programs faster or only the measured copy?

**Result:** the host kernel is always correct but not a safe default on a discrete PCIe GPU; the preload speeds up the measured copy,
not the whole program.

## Host kernel as the default (`analyze_hk_default.py` -> `hk_default.csv`)

Host kernel vs staging, both at the build's defaults (2dda28f): sweep 3 (strided M 2/4, block with ROUTE=all) and the verification
(strided, rows 4/32/128 B, both sides strided). Ratio = host kernel / staging bandwidth, geometric mean.

- **Correctness:** all 3030 host-kernel runs passed their check. It is usable for every shape tested.
- **Always applicable:** Celerity allocates its host memory (`host_memory_id`) with `sycl::aligned_alloc_host`, i.e. pinned and
  device-accessible (`src/backend/sycl_backend.cc:322` at 2dda28f), and device memories exchange data only with that host memory (user
  memory reaches a device only through it, lines 236-244). So every copy the host kernel gets touches pinned memory.
- **ifi (APU):** the host kernel wins nearly everywhere (geomean 0.9-6.9x), up to 13x for narrow rows device-to-host.
- **LUMI (MI250X):** wins on every strided shape with DPC++ (1.4-7.7x) and host-to-device with acpp (1.1-5.4x); loses device-to-host with acpp for rows
  and narrow strided copies (0.63-0.84x).
- **gpuc4 (discrete, PCIe):** device-to-host with narrow strided rows is 5-30x slower (0.03-0.19x; partial-line writes over PCIe,
  see 13_hk_probe), host-to-device with 4/32-byte rows of a 256-byte pitch also loses (worst 0.18-0.35x). Wide rows (128 B) win (1.7-2.2x).
- **Block (contiguous) copies:** equal (0.87-1.10x); irrelevant for the default anyway, which does not route contiguous copies to copylib.

**Answer:** it can be the default on APUs and MI250X-class nodes, but not globally: on a PCIe GPU it turns some device-to-host copies
5-30x slower. Options: a per-device default (host kernel where host memory is reached without PCIe partial-write limits), or the
per-direction / row-width switch.

## Kernel preload: whole program or only the measured copy? (`analyze_preload.py` -> `preload.csv`)

Sweep 3 pairs `<program>_hk_preload_off` vs `<program>_hk_base`, identical except the preload. `runtime_sec` is the wall time of the
whole process, measured by the wrapper.

| | gpuc4 | ifi | LUMI |
|---|---|---|---|
| Measured copy, first access host-to-device, on/off | 1.26-1.58x | 1.29-2.89x | 1.21-1.45x |
| Whole process wall time, on minus off (median) | -0.5 to +4 ms | -130 to +5 ms (see below) | -0.3 to +11 ms |
| Buffer-creation phase, on/off | acpp 0.97, DPC++ 0.84 | acpp 1.0, DPC++ 0.8 | acpp 1.0, DPC++ 0.75-0.78 |

- **The measured copy gets faster** (up to 2.9x), because loading the kernels no longer happens inside it.
- **The whole program does not:** on gpuc4 and LUMI the process takes the same time or a few ms longer (it loads every copy kernel,
  including ones the program never uses). With DPC++ the cost visibly moves into buffer creation (0.75-0.85x).
- **ifi in sweep 3 is not conclusive:** on and off ran on different nodes (gc22 vs gc20), whose 2 s process start differs by more than the effect.
- **Confirmed by `../17_preload/`** (same node, on and off back to back, staging and host kernel, two ifi nodes): the whole process is 1-5% longer
  with the preload (+2 to +20 ms), the measured copy 1.15-2.35x faster, in staging too. See its README.
- A whole-program gain needs the preload to overlap with other work: it runs asynchronously on the executor thread, so a real
  application that does setup work before its first copy can hide it; these benchmarks start copying almost at once.
