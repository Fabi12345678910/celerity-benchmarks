# 02_comparison

**Goal:** The original transfer charts redrawn over the code states, each in its default configuration: before copylib, first copylib, after the fast path, tuned.

**Result:** Strided host-to-device on gpuc4 rose from about 0.0005 to 6 GB/s; block copies did not change, as they never went through copylib by default. `plot_milestones.py` -> `milestones_*.png`; `plot_acpp_comparison.py` made the first version (`*_acpp.png`).

**Lines charts** (`plot_lines.py` -> `lines_{staging,hostkernel}_{gpuc4,ifi,lumi}.png`): the same chart with very few lines, AdaptiveCpp only. Staging: M = 1 (contiguous, regular path), M = 2 before copylib, right after the first copylib build, after the fast path, and with the current defaults. Host kernel: M = 1, M = 2 with the first host-kernel build (f8d348b) and with the current defaults. `lines_*_d2h_<system>.png` are the device-to-host versions (the early runs did not record it, so those lines are missing). `lines_defaults_*.png`: M = 1 against the current defaults, staging and host kernel (M = 2). Lines that have no data on a system (before copylib exists for gpuc4 only) are left out.

**Small sizes of the after-fastpath line:** `05_fastpath` only measured N >= 2^22 rows. `build_state.sh` builds the c4ee4f1 state next to the current one (worktree `src/celerity-bench-c4ee4f1`, `build/celerity-acpp-c4ee4f1`, `build/bench-transfer-acpp-c4ee4f1`; AdaptiveCpp only, no tests; ifi and LUMI via `job_build_state_*.sbatch`), and `fastpath_small_<system>.yaml` ran N = 1..2^24, M = 2 on it with the same base as `05_fastpath` (two pinned workers). Where both runs overlap (2^22, 2^24 rows) they agree within 4% (`results/fastpath_small_<system>.csv`). Both plot scripts pool the two runs.
