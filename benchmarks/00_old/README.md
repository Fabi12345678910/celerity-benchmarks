# 00_old

**Goal:** The original transfer benchmarks before copylib: block, strided and overhead runs, plus raw SYCL/HIP block baselines (gpuc4).

**Result:** Strided copies stalled at about 0.5 MB/s, block copies reached the link limit. Read-only reference; `results/analyze_*.py` made its plots.
