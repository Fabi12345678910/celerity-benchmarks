**Goal:** does the kernel preload (`COPYLIB_PRELOAD_KERNELS`) make the whole program faster or only the measured copy, and what does it cost where no kernel is used (staging)?

**Result:** only the measured copy: it gets 1.2-2.4x faster, in staging too, but the process takes the same time or 2-20 ms longer (1-5%). The preload moves start-up work out of the timed copy into the untimed start.

---

# Preload study (2026-10-06)

Celerity `3dcopylib-bench` `2dda28f`, `strided_transfer`, both SYCL implementations, on all three systems. `make_preload_yamls.py` generates one
YAML per system with four variants side by side: staging and host kernel (the base configurations of `15_sweep3`), each with
`COPYLIB_PRELOAD_KERNELS=1` and `=0`.

- **Same node, back to back:** all four variants are in one YAML (one job), and the wrapper's iterations are the outer loop with the env as the
  innermost parameter, so on and off run one after the other at every point and drift cancels. This fixes the earlier pair in `15_sweep3`,
  which ran on different ifi nodes. ifi ran on two nodes (gc20 and gc22, the second in reversed order) to see the node effect.
- **Points:** N = 1 (pure start-up), 1Ki, 64Ki, 1Mi, 16Mi rows; M = 2 (strided, copylib runs) and M = 1 (contiguous, copylib never runs: the program only pays the start-up). 8 runs + 1 warm-up each.
- **Metric:** `runtime_sec`, the wall time of the whole process (wrapper), next to the measured first-access copy bandwidth and the buffer-creation bandwidth.
- `python3 analyze_preload.py` prints the tables and writes `preload.csv` (needs pandas). Raw runs: `<system>/results/preload*.csv`. `submit.sh` and `gpuc4/chain.sh` start the jobs.

## Results

Process wall time, on minus off (ms, median over the sizes; the noise is a standard deviation of 4-9 ms per run, 8 runs per point):

| | gpuc4 (0.16 s) | ifi gc20 / gc22 (2.2 s) | LUMI (0.58 s) |
|---|---|---|---|
| acpp, staging | +2 to +4 | +17 to +20 | +4 |
| acpp, host kernel | +1 to +3 | +9 to +12 | +2 to +4 |
| DPC++, staging | +4 to +7 | -2 to +10 | +6 to +14 |
| DPC++, host kernel | -1 to +8 | -2 to +8 | +4 to +16 |

- **The measured copy gets faster** (first access, M = 2, geometric mean over the sizes): gpuc4 1.2-1.55x, ifi 1.25-2.35x (acpp about 2.3x), LUMI 1.15-1.45x.
  This holds for staging too, where no copylib kernel runs: the preload evidently also takes work out of the first copy that staging would otherwise pay (not investigated further).
- **The whole program does not get faster:** it is 1-5% longer. With M = 1 (copylib never runs) the cost is the same, so it is a fixed start-up cost, independent of the copy.
- **Where the cost goes:** with DPC++ the buffer-creation phase gets slower by 10-30% (bandwidth 0.69-0.90x), with acpp it does not (0.97-0.99x) and the cost shows in the process time instead (largest on ifi, +9 to +20 ms).
- **Nodes:** gc20 and gc22 agree within the noise.
- **For the default:** the preload is worth keeping if the application does other work before its first copy (it runs asynchronously, so a few ms to 20 ms hide there), and it makes copy timings in benchmarks cleaner. A program that copies at once, or one that never uses a copylib kernel, pays 2-20 ms for nothing.
