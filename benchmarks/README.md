# Benchmarks, in the order they were run

Folders are numbered by date (renamed 2026-10-06; the mirrors on the machines use the same names). Paths in YAMLs and scripts are relative to
this folder. Details per study: the folder's `README.md`. `overview.py` holds the shared overview layout.

| # | Folder | Run | Goal | Result |
|---|---|---|---|---|
| 00 | `00_old` | before 10-03 | The original transfer benchmarks before copylib (block, strided, overhead, raw SYCL/HIP baselines) | Strided copies stuck at about 0.5 MB/s; block at the link limit. Reference only |
| 01 | `01_default` | 10-03 | First runs of the copylib build with its defaults (af82e39, f8d348b) | Strided copies 2-3 orders of magnitude faster; block unchanged |
| 02 | `02_comparison` | 10-03, redrawn 10-06 | Transfer charts over the code states (before copylib, first copylib, after fastpath, tuned) | Strided host-to-device on gpuc4: 0.0005 to 6 GB/s; block unchanged |
| 03 | `03_config` | 10-03/04 | Sweep 1: every option one at a time on the untuned build | Untuned: host kernel and larger chunks/staging far better than the base (`overview.png`). Superseded |
| 04 | `04_cpu_pack` | 10-04 | The CPU pack/unpack loop in isolation, assembler analysis | Fixed-width loops: 156 to 3.25 instructions per row; led to the fast path |
| 05 | `05_fastpath` | 10-04 | Fixed-width host copies (c4ee4f1) and NT stores (014e21a) | Staging 6-24x faster; NT stores +3-18% host-to-device |
| 06 | `06_cores` | 10-04 | Staging worker count, placement and plan order | 4-5 / 8 (4+4) / 3-4 workers on gpuc4 / ifi / LUMI; dynamic order never worse |
| 07 | `07_limits` | 10-04 | Hardware limits: host memory, DMA link, CPU load during DMA | gpuc4 staging at the hardware limit; ifi host-to-device at 46-68%; LUMI pack and DMA serialize |
| 08 | `08_both_strided` | 10-04 | Source and build of `strided_both_transfer` (strided on host and device) | Program only, used by 09 and 14 |
| 09 | `09_sparse` | 10-04 | Sparse rows (pitch 64-256 B) and both sides strided: staging vs host kernel | gpuc4: staging wins from pitch 16 B host-to-device; ifi/LUMI: host kernel wins or ties |
| 10 | `10_rows` | 10-04 | Row widths 4-256 B: staging vs host kernel | Host kernel better on ifi/LUMI and for wide rows on gpuc4 |
| 11 | `11_consistency` | 10-04 | Which method wins over 78 scenarios | Host kernel wins 56/78 but collapses to 3% on gpuc4 device-to-host; staging never worse than 4x |
| 12 | `12_defaults` | 10-04 | Sweep 2: the best default per option, per variant | The new defaults (`results/overview.png`) |
| 13 | `13_hk_probe` | 10-04 | Why the host kernel is slow on gpuc4; a proposed fix on all systems | PCIe partial-line writes; the fix helps gpuc4 but hurts ifi/LUMI, rejected |
| 14 | `14_verify` | 10-05 | New vs old defaults on all programs, systems, compilers | Staging 1.07-2.38x, host kernel 1.13-2.76x; one regression (LUMI acpp staging, 8-64 MiB) |
| 15 | `15_sweep3` | 10-05/06 | Sweep 3: the first sweep's options (+ MAX_ELEM_SIZE, PLAN_ORDER) on the best earlier combination, both variants, strided and block | The defaults are near the optimum; pitfalls: tiny chunks/staging, MIN_BYTES >= 1 MiB; lever: SDMA off (`overview_*.png`) |
| 16 | `16_analyses` | 10-06 | Cross-study questions: host kernel as default, kernel preload | Host kernel always correct but not a safe default on PCIe; preload speeds up the measured copy, not the whole program |
| 17 | `17_preload` | 10-06 | Preload on/off on the same node, staging and host kernel, all systems | Measured copy 1.15-2.35x faster, whole process 1-5% (2-20 ms) slower |
| 18 | `18_ifi_nvidia` | 10-06 | The lines charts on the NVIDIA nodes of ifi (RTX 2070, partition IFIgpu2070) | Device-to-host as on gpuc4 (host kernel about 50x slower than staging); host-to-device dominated by first-use cost |
| 19 | `19_ifi_nodes` | 10-06 | Node-to-node variety on ifi, from the sweep 3 anchors | Host-to-device equal on all nodes; device-to-host varies 30-60%, gc20 slowest |
| 20 | `20_sdma_defaults` | 10-06 | The current defaults with and without `HSA_ENABLE_SDMA=0`, same node, back to back | Host-to-device staging and native 1.5-4x at small and medium sizes, host kernel unaffected; LUMI device-to-host staging worse |
| 21 | `21_sweep4` | 10-06 | Sweep 4: the options on the new base (4 queues, 1 MiB, SDMA off) without the slow values, with 2 queues and a queues x chunk grid | Base at the optimum for staging; host kernel +7-11% with 2 queues x 4 MiB; LUMI AdaptiveCpp device-to-host 5-7x faster with Celerity thread pinning off (fixed ~10 ms cost) |
| 22 | `22_device_strided` | 10-06 | Contiguous host, strided device (new program): why gpuc4 device-to-host is slow | Host kernel collapse on gpuc4 comes from strided host writes: with a strided device side the host kernel is best everywhere (14.5 GB/s device-to-host on gpuc4, 80x) |
| 23 | `23_overhead` | 10-07 | Task/launch overhead: one tiny kernel submitted N times in HIP, OpenCL, plain SYCL (acpp, DPC++) and Celerity (copylib staging, host kernel, off) | Smoke test on gpuc4, then all three systems |
| 24 | `24_memcpy` | 10-07 | Contiguous memcpy host-to-device and device-to-host in HIP, OpenCL, plain SYCL (acpp, DPC++, pinned and pageable host) and Celerity, SDMA off and on, plus rocprofv3 traces | How much each library adds around the HIP/ROCclr copy |
| 25 | `25_final` | 10-08/09 | The final sweep: every study on the final build and defaults, plus thread pinning off; clean-build validation | Defaults at the optimum; pinning off LUMI 1.5x, ifi up to 1.35x, gpuc4 worse; all 356,892 runs ok |
| 26 | `26_published` | 10-09 | The lines benchmark of the published Celerity master (GitHub 536d754, gpu3dcopylib 843fafe) on all four systems | All 3,564 runs ok; same picture as the final sweep (`lines_acpp.pdf`) |
