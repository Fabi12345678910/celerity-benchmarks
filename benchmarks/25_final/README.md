**Goal:** The final sweep (decided 2026-10-08): every earlier study on the final build with the new defaults, plus Celerity thread pinning off, and the validation of the clean release build.

**Result:** The final defaults (staging 4 queues x 1 MiB, host kernel 2 queues x 4 MiB) are at the optimum: no setting beats them consistently (best alternatives 1.07-1.12, system-specific, base vs its own anchor 0.96-1.02). Celerity thread pinning off is the largest single effect (1.14-1.21 overall): LUMI 1.48-1.57 (AdaptiveCpp device-to-host 6-45x at small/medium sizes), ifi 1.0-1.35, gpuc4 0.86-0.96 (worse for small copies): a per-system recommendation, not a default. All 356,892 runs passed their checks. The clean build validates against final-bench on all systems.

---

# Final sweep (2026-10-08/09)

- **Build:** `3dcopylib-final-bench` f24e5f0 (clean code + env switches + host-kernel mode), defaults = the final defaults: staging 4 queues x 1 MiB chunks, host kernel 2 queues x 4 MiB, MAX_ELEM_SIZE 16, 1 element per item, WG 32 (AMD), preload on; `HSA_ENABLE_SDMA=0` everywhere except the SDMA configs.
- **Generator:** `make_final_yamls.py` (header has the design). `sweep_*`: the sweep 4 option set on the new base, grid centred on the new defaults, placements incl. `celerity_pinning_off` on all systems, anchors per job. `prog_*`: sparse, both-strided, row widths, device-strided, each staging / host kernel x pinning on / off (env innermost), plus the native path. `pair_*`: preload and SDMA on/off, back to back.
- **Ran:** LUMI 2026-10-08 12:20-15:50 (one job hit the 2 h limit, rerun), ifi 12:15-05:00 (7 host-kernel jobs hit the limit, 13 YAMLs rerun 2 per job), gpuc4 11:46-07:39. gpuc4 279, ifi 373+, LUMI 297 sweep YAMLs; all checks ok.
- **Analysis:** `python3 analyze_final.py [systems] [--keep-ifi-acpp-h2d]` (sweep 4 method; the drifting ifi AdaptiveCpp host-to-device cell is left out by default). Output: `final_analysis.txt`.
- **Thesis numbers and figures:** `thesis/thesis_numbers.py --final` (`thesis/numbers_final.txt`), `thesis/plot_thesis.py --final`, `thesis/plot_appendix.py --final`.

## Validation of the clean build
- **4f88016** (first clean build) vs final-bench, staging defaults, all programs: `validate_*`, all checks ok on gpuc4, ifi, LUMI; large copies equal.
- **final2 / published** (clean build with the minimal configuration: `CELERITY_COPYLIB`, `COPYLIB_HOST_KERNEL`, `COPYLIB_WORKER_CPUS`; LUMI: final2 at d239713, ifi: the published GitHub master 536d754, same code): `validate2_*`, staging and host kernel, all checks ok, equal to final-bench at large sizes (LUMI 0.98-1.04, ifi 0.94-1.03 within its noise). The 81b2cb2 results (`lumi/results/validate2_81b2cb2/`) showed a 10-15% DPC++ gap for strided device targets, closed by the kernel index used since d239713 (`ab/`, A/B on LUMI).

## Matched copy measurement (`matched/`, thesis review item 31)
One host-timed 1 GiB `hipMemcpy` vs Celerity's contiguous copy: wall clock and HIP events agree everywhere, so the timing method is not the cause of the Celerity values above the single-copy DMA rate.
LUMI: hipMemcpy 25.5 GB/s, Celerity native host-to-device 36.7 GB/s (nominal link 36 GB/s). gpuc4: hipMemcpy 11.8-12.0 GB/s, Celerity native 10.8-11.2, Celerity with copylib routed 14.0 (H>D) / 15.0-15.2 (D>H).
