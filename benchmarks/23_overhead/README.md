# 23_overhead

**Goal:** what does the programming model cost per task? One tiny kernel (`p[i] += 1` on ints) submitted N times, the same protocol in six implementations: plain SYCL (AdaptiveCpp and DPC++), Celerity (copylib on, and off: `CELERITY_COPYLIB=off`), OpenCL, HIP. Sources in `common/`, `sycl/`, `hip/`, `opencl/` and `celerity/`; `PROTOCOL.md` describes the protocol and the output; `celerity/CMakeLists.txt` uses the bench branch install.

**Result:** For a chain of tasks Celerity adds almost nothing per task on top of SYCL (kernel-only, 1 element: 0.5-1 µs on ifi and gpuc4, about 0-3 µs on LUMI); its cost is in latency on gpuc4 and LUMI, where one blocking task takes about 2x SYCL's round trip (+17-25 µs); on ifi the latency difference is only +1-4 µs (unexplained). The per-task cost of SYCL itself is 2-3x that of HIP or OpenCL. Strided copies per task are dominated by the copy, and copylib is about 100-130x faster than the native path there.

---

## Protocol (`common/bench_common.h`)

- Warm-up 64 tasks, then 7 repetitions of N submissions + one wait, then 200 single-task round trips. Medians.
- **Total** = (submit + complete) / N: throughput, the host submits ahead of the GPU.
- **Submit** = host time to enqueue N tasks / N.
- **Latency** = one task submitted, waited for, median of 200. Not overlapped.
- Tasks: `buffers=1` is a dependency chain; `buffers=64` gives mostly independent tasks.
- Celerity `strided=1`: every task is a kernel over `elems x 16` plus a host task reading column 0, so each task needs a strided device-to-host copy.
- All runs: `HSA_ENABLE_SDMA=0` (the standing default); copylib staging and host kernel use the sweep 4 base values.
- Programs are built by `build.sh` (`~/finalizing-work/build/overhead/`), runs go through `benchmark_wrapper.py` (`make_yamls.py`, `submit.sh` for ifi and LUMI, `gpuc4/chain.sh`).

## Results (1000 tasks, chain, medians, µs)

Total per task / latency (single task + wait):

| | gpuc4 | ifi | LUMI |
|---|---|---|---|
| HIP | 3.1 / 20 | 2.0 / 7 | 2.8 / 11 |
| OpenCL | 3.4 / 28 | 2.2 / 16 | 2.1 / 25 |
| SYCL AdaptiveCpp | 7.1 / 20 | 4.5 / 18 | 8.4 / 18 |
| SYCL DPC++ | 7.2 / 21 | 4.5 / 18 | 9.6 / 18 |
| Celerity AdaptiveCpp, kernel only | 6.7-7.2 / 37 | 5.0-5.8 / 19 | 6.7 / 39 |
| Celerity DPC++, kernel only | 7.3 / 44 | 5.2-5.3 / 22 | 12.4 / 43 |

Kernel time with 1 Mi elements (4 MiB per kernel, total per task): gpuc4 about 15-20 µs for all, ifi 11-17 µs, LUMI 7-22 µs (HIP and OpenCL 7, SYCL and Celerity 19-22). Strided copy per task (1024 rows, Celerity): host kernel 29-31 µs on ifi, staging 31-35 µs; native path 4.9 ms per task (about 130x slower than copylib at this size, 1 row: no difference).

## Not used / open

- The 64-buffer rows on gpuc4 (Celerity 14 µs vs 7-10 µs on LUMI for the same work) and DPC++ on LUMI (+3 µs over plain DPC++) are not explained. `CELERITY_THREAD_PINNING` would be the first thing to test on gpuc4.
- Kernel time is inferred from the 1 vs 1 Mi difference, not measured with a profiler.
- Strided rows are included in the data, but they are dominated by the copy and are not an overhead measure.

## Files

- `<system>/results/overhead_{plain,celerity,celerity_strided,celerity_strided_acpp,celerity_strided_dpcpp,celerity_native}.csv`: one row per run (`check` column: all ok on all three systems).
- `summary_<system>.csv` and `analyze_overhead.py`: medians per setting and the Celerity overhead per task (Celerity total minus plain SYCL total of the same implementation).
- Repeat spread (max/min over the 3 iterations, median per setting): 1.01 on every system, 1-2% of the value, a few settings up to 1.7x.
