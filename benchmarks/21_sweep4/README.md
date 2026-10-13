**Goal:** Configuration sweep on the new base (4 queues, 1 MiB chunks, `HSA_ENABLE_SDMA=0` in every config), without the values that were unreasonably slow in sweep 3, with 2 queues included and a queues x chunk grid.

**Result:** Run on all three systems (2026-10-06/07, 91-98k runs per system, all ok). Overviews: `overview_{strided,block}_{stg,hk}_anchor.png` (against the node-matched anchors) and `*_{stg,hk}.png` (against the single base run). Numeric analysis (2026-10-08, `analyze_sweep4.py`, section below): the base is at the optimum for staging; the host kernel gains 5-10% with 4-8 MiB chunks and 2 queues; on LUMI, `CELERITY_THREAD_PINNING=false` removes a fixed cost of about 10 ms from AdaptiveCpp device-to-host (5-7x at 64Ki-1Mi rows). First reading of the overviews: staging below 256 KiB and chunks below 64 KiB lose everywhere, SDMA on loses host-to-device everywhere but wins device-to-host on LUMI, chunks of 2 MiB and more help host-to-device, and the ifi AdaptiveCpp host-to-device reference varies 3x between nodes and jobs.

---

# Sweep 4

`python3 make_sweep4_yamls.py [--no-block] [--no-anchors]` writes `<system>/*.yaml`, `jobs.txt`, `chain.sh` and `estimate.txt`; `python3 preview.py [HH:MM]` prints the value table and the finish estimates (below). It is derived from `15_sweep3/make_sweep3_yamls.py`; the differences are listed in its header:

- **Base:** staging and host kernel with 4 queues and 1 MiB chunks (host kernel also `MAX_ELEM_SIZE` 4, 4 elements per item, work-group 256), SDMA off. `defaults` is the build's defaults with SDMA off, `sdma_on` the only config with SDMA on.
- **Dropped (geometric mean below 0.75 of the base in sweep 3):** `MIN_BYTES` 1, 4 and 16 MiB; staging 4 KiB (staging) ; chunks 1 and 4 KiB (both), 16 KiB (host kernel); 64 queues (staging); `ELEMS_PER_ITEM` 1024 and `WG_SIZE` 1 (host kernel, strided); worker placement `inherit`; the `old` reference; the native strided path (`CELERITY_COPYLIB=off`). Block: chunks up to 64 KiB, staging up to 256 KiB.
- **New:** 2 queues in all queue lists, and `grid` (queues 2, 4, 8 x chunk 1, 2, 4 MiB for staging and 1, 4, 16 MiB for the host kernel).
- **Anchors** (reduced-grid copies of the base at the end of every job) are on by default; the overviews can use them as in sweep 3.
- **Estimates** are the measured sweep 3 runtimes of the same config (new configs: the base of the same program and variant) + 10%.

## ifi: node differences or jumpiness? (2026-10-07)

From the sweep 4 anchors (3-4 anchors per node, taken at different times of the sweep): between-node spread is small, run-to-run spread within a node is large.

| ifi, strided, anchors, sd of the ratio to the median (%) | acpp H>D | acpp D>H | dpcpp H>D | dpcpp D>H |
|---|---|---|---|---|
| staging: between nodes / within a node | 15 / 74 | 5 / 29 | 1 / 4 | 6 / 34 |
| host kernel: between nodes / within a node | 5 / 26 | 6 / 38 | 2 / 3 | 8 / 41 |

- **AdaptiveCpp host-to-device is the jumpy one, and it jumps with time, not with the node:** at 1 Mi rows the staging anchors of the first eight jobs (all nodes, first wave) are 0.09-0.40 GB/s, jobs 9-12 about 0.6, and every anchor from job 13 on is about 1.0 GB/s on every node; DPC++ stays within 4%. The cause is not known (the shared AdaptiveCpp kernel cache in the shared home is a candidate, cluster load another).
- **Node effects that remain:** gc20 is the slowest in device-to-host (0.85-0.9 of the median, as in `19_ifi_nodes`).
- **Reading the overviews:** `--ref=job` (`overview_*_job.png`) compares every config with the anchor of its own job (same node, minutes apart) and is the best reference on ifi; `--ref=anchor` matches only the node and shows a red top row for ifi AdaptiveCpp host-to-device because early configs ran in the slow phase. Even within a job the anchors vary (min..max of 3 runs up to 2.5x), so single cells of that row stay unreliable.

## Numeric analysis (2026-10-08)

`python3 analyze_sweep4.py` (the analogue of `15_sweep3/analyze_defaults.py`): per config, the ratio of its median to the reference at the same point (geometric mean over M = 2 and 4), geometric mean over the four overview sizes, per cell = system x implementation x direction (12 cells; LUMI-only placements 4). It writes `candidates_<program>_<stg|hk>_<job|anchor>.csv` (per config: geomean, worst and best cell, cells above 1.05 / below 0.95, per direction, per system) and `cells_<program>_<tag>_job.csv` (every cell). Reference `job` = the anchor of the same job (same node, minutes apart); `anchor` = the anchors of the same node. Both agree on every conclusion below except where noted.

**Noise floor:** the base row against its own job anchor spans 0.89-1.08 per cell (strided staging), 0.94-1.04 (block staging), but up to 1.67 for single host-kernel cells. A setting counts only with a geomean of at least 1.05, a worst cell of at least 0.95, and the same sign under both references.

| Program, variant | Best consistent change (job ref / anchor ref: geomean, worst cell) | Where it gains | Verdict |
|---|---|---|---|
| strided, staging | `STAGING_BYTES` 1 GiB: 1.09 / 1.08, worst 0.96 / 0.99, 7 of 12 cells > 1.05 | device-to-host 1.12-1.16 (gpuc4 1.2-1.4, LUMI acpp 1.26) | Real but small; 128 MiB gives 1.03 (worst 0.98). Chunks 2-8 MiB and the queues x chunk grid: 1.02-1.05 with cells down to 0.84-0.93, within noise. **The base (4 queues, 1 MiB) stays.** |
| strided, host kernel | 2 queues x 4 MiB chunks: 1.11 / 1.07, worst 0.99; 8 MiB chunks: 1.09 / 1.08, worst 0.89 / 1.00; 4 queues x 16 MiB: 1.09 / 1.09, worst 0.96 / 0.94 | host-to-device 1.13-1.17 on all systems, ifi most (1.2-1.3) | **Candidate: host kernel with 2 queues and 4-8 MiB chunks** (+7-11%). 2 queues alone: 1.03 / 1.07. |
| block, staging | 2 queues: 1.10 / 1.10, worst 0.83 / 0.85 | LUMI 1.27, ifi 1.09; gpuc4 0.95-0.97 | LUMI-specific; chunks 4-8 MiB the same pattern (LUMI 1.22-1.27, gpuc4 0.90-0.93). Not a global change. |
| block, host kernel | the build's defaults: 1.11 / 1.12, worst 0.87 / 0.89; 8 MiB chunks 1.10, 2 queues 1.08 | LUMI 1.27-1.36; gpuc4 0.94-1.02 | Again LUMI-driven. |

- **LUMI, `CELERITY_THREAD_PINNING=false` (place `celerity_pinning_off`, LUMI only):** 1.43-1.48 geomean in all four tables, entirely from AdaptiveCpp device-to-host: 5.5-7.2x. Absolute (staging, strided, M 2 and 4): 64Ki rows 0.03 -> 0.85 GB/s, 1Mi rows 0.37 -> 3.41 GB/s, 16Mi rows 5.2 -> 5.5 GB/s; block the same (64Ki 0.03 -> 1.24, 1Mi 0.43 -> 9.1, 16Mi unchanged). That is a fixed cost of about 8-11 ms per device-to-host copy with pinning on, gone with pinning off; DPC++ is unaffected (0.87-0.91), host-to-device loses 9-15%. Not run on gpuc4 and ifi (the placement list there has no pinning-off entry). **The largest single effect in sweep 4.** Cause not investigated (candidate: AdaptiveCpp's completion/host thread competing with Celerity's pinned threads on CPUs 1-4). It also bears on the 23_overhead latency gap (+17-25 us on gpuc4/LUMI).
- **The build's defaults vs the base:** strided staging 1.01 / 0.92, host kernel 1.03 / 0.96, with single cells from 0.23 to 2.6; the large cells are ifi AdaptiveCpp host-to-device, i.e. the time drift, not the config. Block staging defaults lose on gpuc4 (0.57-0.85 device-to-host). No reason to prefer the build's defaults over the base.
- **Confirmed losers (both references, all systems):** `HSA_ENABLE_SDMA=1` 0.59-0.65 (host-to-device 0.44-0.50; only LUMI device-to-host gains), staging <= 1 MiB (0.51-0.94), staging chunks <= 256 KiB (0.56-0.82), host-kernel chunks <= 256 KiB (0.79-0.96), 12 or more queues (0.81-0.97), `same_core` placement (0.85-0.93), pageable staging (0.90), preload off (0.85-0.88, host-to-device 0.72-0.74), host-kernel work-group 2 (0.84), `PLAN_ORDER=interleaved` for block staging (0.82, gpuc4 0.63).
- **Neutral (within noise everywhere):** `MIN_BYTES` 64 B..256 KiB, `PLAN_ORDER` dynamic vs block, `WAIT=poll`, host-kernel `MAX_ELEM_SIZE`, `ELEMS_PER_ITEM` 2-32, `WG_SIZE` 16-1024, host-kernel `STAGING_BYTES` (unused by it).

**Proposals (not decided):** (1) test `CELERITY_THREAD_PINNING=false` (or pinning away from the GPU's runtime threads) on all systems, paired, with device-to-host at 64Ki-1Mi rows; (2) host kernel default 2 queues x 4 MiB chunks, to be confirmed in a paired run against the base; (3) keep staging at the base.
