**Goal:** The first sweep's options (+ MAX_ELEM_SIZE, PLAN_ORDER) on the best earlier combination, both variants, strided and block, with anchor runs.

**Result:** The build's defaults are at or near the optimum (staging at the median, host kernel 7-11% above the old best combination). Pitfalls: chunks or staging <= 4 KiB (0.07-0.33x), MIN_BYTES >= 1 MiB (routes small copies to the slow native path). Lever: HSA_ENABLE_SDMA=0 for staging (1.2-2.35x, process-wide). Overviews: `overview_*.png`.

---

# Sweep 3: the first configuration sweep's options, on top of the best combination of the earlier tuning

The option set and value lists of `03_config/` (the first "night sweep") plus `COPYLIB_MAX_ELEM_SIZE` and `COPYLIB_PLAN_ORDER`, run on Celerity
`3dcopylib-bench` `2dda28f` for both copylib variants. `make_sweep3_yamls.py` has the full design in its header; the short version:

- **Base (`base`):** the best combination of the earlier tuning, split by variant. Staging: 4 queues, 1 MiB chunks. Host kernel: 4 queues,
  1 MiB chunks, `MAX_ELEM_SIZE` 4, 4 elements per item, work-group 256. Every option is swept on top of it, one at a time; a value equal to the
  base is the base and is left out.
- **Other references per variant:** `defaults` (the build's new defaults, nothing set) and `old` (the defaults before `2dda28f`, by env), so
  results tie back to `14_verify/` and the first sweep. `native` is `CELERITY_COPYLIB=off` (strided) and the unrouted copy (block).
- **Variants:** `stg` (staging) and `hk` (host kernel, `COPYLIB_HOST_KERNEL=1`), each with the options that act on it.
- **Options and values:** `MIN_BYTES` 64 B..16 MiB (10), `QUEUES` 1..64 (10; block also 2), `STAGING_BYTES` 4 KiB..1 GiB (11), `CHUNK_BYTES`
  1 KiB..8 MiB (10; strided also 16 MiB and 32 MiB: host kernel as is, staging with `STAGING_BYTES` = 4 x chunk, as its chunks are capped at staging / queues), `PLAN_ORDER` block / dynamic / interleaved, `WAIT=poll`, `ELEMS_PER_ITEM` 2..1024 (9, hk), `WG_SIZE` 1..1024 (10, hk),
  `MAX_ELEM_SIZE` 1..64 (7, hk), preload off (hk), `HOST_STAGING=pageable` and `HSA_ENABLE_SDMA=0` (stg), and the worker placements of
  `03_config/workers` (all CPUs, inherit, two dedicated cores, both hyper-threads of one core; LUMI also far CCD and Celerity thread pinning off).
- **Programs:** `strided_transfer` (N 1..2^28, M 1, 2, 4; one YAML per configuration) and `block_transfer` (N 1..2^31, `ROUTE=all`; 1 KiB / 4 KiB
  chunks and 4 KiB staging only up to 2^28). 3 iterations + 1 warmup, both SYCL implementations.
- **Not swept:** worker count lists (`06_cores/`), `HIP_HOST_COHERENT`, `GPU_MAX_HW_QUEUES`, `ALLOC_CPU_IDS`, multi-GCD runs.

CSV columns: the wrapper's, plus `env` (the full env of the run) and the static `variant`, `config`, `option`, `value`, `program`, `celerity`.

## Running

| System | How | Estimated time |
|---|---|---|
| gpuc4 | `nohup 15_sweep3/gpuc4/chain.sh > ../logs/sweep3_gpuc4.log &` (skips finished CSVs, prints `SWEEP3-DONE`) | see `<system>/estimate.txt` |
| ifi | `benchmarks/15_sweep3/submit.sh ifi` from `~/finalizing-work` on the head node | one job per line of `ifi/jobs.txt` |
| LUMI | `benchmarks/15_sweep3/submit.sh lumi` | one job per line of `lumi/jobs.txt` |

Estimates are the first sweep's measured runtimes for the same env, plus 15%. Configurations are packed by option family, so a family
shares one node (ifi nodes differ by about 10% in device-to-host). Use the median of all configurations of a variant at the same point
as the reference, as in `12_defaults/`.

Every gpuc4 configuration ran once with a small N (acpp, plus DPC++ for the references) and printed `Check: ok` before the sweep was
handed over.

## Anchors (reference runs against node variance)

A single base run is a weak reference: ifi nodes differ by about 10 percent and a run can land in the slow mode. Therefore:
- **Default for every sweep generated from now on:** each job ends with a reduced-grid copy of the base of each variant and program it contains
  (`<program>_<stg|hk>_anchor_j<job>`; N 2^16..2^28 step 4 for strided with M 1, 2, 4, and 4 sizes for block; about 15 percent of a base run;
  25 min of every job are reserved for them). Any config can then be compared to a base from the same node and time.
  `python3 make_sweep3_yamls.py --no-anchors` reproduces the sweep that ran on 2026-10-05, which has none.
- **Sweep 3 itself (no anchors in its jobs):** `python3 make_sweep3_yamls.py --post-anchors` adds standalone anchors afterwards:
  gpuc4 4 repeats in a chain (`gpuc4/anchors_post_chain.sh`, started automatically after the main chain), ifi 2 repeats on each of the 8 nodes
  (jobs pinned with `--nodelist`, `submit_anchors.sh ifi`), LUMI 4 jobs with 2 repeats (`submit_anchors.sh lumi`; LUMI nodes cannot be matched).
- **Plotting:** `python3 plot_overview.py strided --ref=base|median|anchor`. `anchor` uses the anchors of the node a config ran on
  (CSV column `machine`), else all anchors of the system. `median` is the median over all configs of the variant at the same point.

## Base reruns (2026-10-06)

The single base run of each variant was skewed by node and time (on ifi and LUMI the bases ran on different nodes). `make_base_rerun.py`
reruns the four bases (strided and block, staging and host kernel; full grid, the YAMLs unchanged) three times per system: gpuc4 in a chain, ifi on
gc20, gc22 and gc26 (the nodes the original bases ran on), LUMI as three jobs (`submit_reruns.sh`; CSVs `*_rerun_r<k>.csv`).
`python3 plot_overview.py --ref=rerun` draws the overviews against the median of the three reruns (`overview_*_rerun.png`); the original base keeps its row.
Against that median the original base was within 3% in most cells; the exceptions are ifi device-to-host (0.73-0.96 for single runs, depending on the node), gpuc4 block host kernel device-to-host (0.86) and LUMI strided staging host-to-device (1.11).
