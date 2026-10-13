**Goal:** The last benchmark (2026-10-08): the default "lines" benchmark of the published Celerity, no sweep, on all four systems.

**Result:** All 3,564 runs ok on the RX 9060 XT, Radeon 8060S, MI250X and RTX 2070. The published build behaves as the final sweep measured: copylib staging lifts strided copies from Celerity's own path (about 1 MB/s on AMD, about 0.2 GB/s device-to-host with CUDA's 2D copies on the RTX 2070) to several GB/s; the host kernel is best on the APU and MI250X and collapses device-to-host on the PCIe GPUs. Charts: `lines_acpp.pdf`, `lines_dpcpp.pdf`.

---

# Lines benchmark of the published Celerity (2026-10-09)

- **Build:** GitHub `Fabi12345678910/celerity-runtime` master **536d754** with `Fabi12345678910/gpu3dcopylib` main **843fafe**, fresh recursive clones built as `celerity-<impl>-published` on gpuc4, ifi (AMD and NVIDIA) and LUMI.
- **Program:** `strided_transfer`, 4-byte rows, M = 1 (contiguous reference) and M = 2, N = 1..2^28; defaults (staging) and `COPYLIB_HOST_KERNEL=1` (one YAML, env innermost), `CELERITY_COPYLIB=off` (separate YAML; M = 2 up to 2^23 on AMD). SDMA off on AMD, one GCD on LUMI; AdaptiveCpp and DPC++ on AMD, AdaptiveCpp (CUDA backend) on NVIDIA. 3 iterations + 1 warm-up. `make_lines_yamls.py`.
- **Runs:** NVIDIA 2026-10-09 00:05-00:43, ifi and LUMI 08:00-09:40, gpuc4 11:57-12:34 (after the published build there). Job scripts: `../25_final/job_{ifi,lumi}.sbatch run`, `job_nvidia.sbatch`, gpuc4 directly.
- **Validation:** the published build was validated against final-bench (the build of the final sweep) on all three AMD systems (`../25_final/*/results/validate2_*`): all checks ok, equal at large sizes (RX 9060 XT 0.998-1.021, MI250X 0.98-1.04 as final2 d239713, Radeon 8060S 0.94-1.03).
- **Charts:** `python3 plot_lines.py [acpp|dpcpp]` -> `lines_<impl>.pdf/.png` (median of 3 runs).
