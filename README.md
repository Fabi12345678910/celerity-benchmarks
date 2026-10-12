# Celerity strided-transfer benchmarks

Benchmark programs, configurations, raw results and analysis scripts behind the
bachelor thesis *Optimizing Strided Data Transfers on AMD Hardware* (Fabian
Pfaff, Distributed and Parallel Systems Group, University of Innsbruck, 2026).

This is the part of the benchmark work that the thesis relies on: the final
sweep, from which every figure and table of the evaluation is produced, the
validation of the published release build, the hardware-limit measurements and
the programs. The earlier exploratory studies and configuration sweeps that led
to the final defaults are not included. Their run counts appear in Section 6.1
of the thesis, but their data is not part of this repository.

## Code under test

| Component | Where | Commit |
|---|---|---|
| Celerity, release build | github.com/Fabi12345678910/celerity-runtime, `master` | `536d754` |
| Celerity, benchmark build | github.com/Fabi12345678910/celerity-runtime, `bench` | `d7ce718` (source tree identical to the measured build `f24e5f0`) |
| gpu3dcopylib | github.com/Fabi12345678910/gpu3dcopylib | `843fafe` |

## Systems

The folders use the machine names; the thesis uses the GPU names.

| Folder | Thesis name | Machine |
|---|---|---|
| `gpuc4` | RX 9060 XT | workstation, Intel Core i9-12900, PCIe 5.0 x16 |
| `ifi` | Radeon 8060S | AMD partition of the ifi cluster, AMD Ryzen AI Max+ 395 |
| `lumi` | MI250X | LUMI-G, one GCD, AMD EPYC 7A53 |
| `nvidia` | RTX 2070 | NVIDIA partition of the ifi cluster |

## Layout

- `src/`: the main benchmark programs (`strided_transfer`, `block_transfer`)
  and the plain HIP, OpenCL and SYCL block-transfer baselines.
- `benchmarks/`: one folder per study, each with its own `README.md`, the
  YAML configurations (`output_csv` names the result file), Slurm job scripts
  and the results as CSV (`<system>/results/`). The folder numbers are those
  of the full study list, so they have gaps.

| Folder | Content | Used in the thesis |
|---|---|---|
| `04_cpu_pack` | The host packing loop in isolation, assembler analysis, and the randomized test against a reference implementation (200,000 cases, `deployed_check/`) | 4.3, 5.3 |
| `07_limits` | Hardware limits: plain-HIP DMA and host-memory kernels over the link, host memory bandwidth | 6.2, 6.5 (limit model) |
| `08_both_strided` | Source of `strided_both_transfer` (strided on both sides) | program only |
| `10_rows` | Source of `strided_rows_transfer` (row widths) | program; the row-width figure uses the final sweep |
| `22_device_strided` | Source of `device_strided_transfer` (host contiguous, device strided) and its first study | program; 6.4 uses the final sweep |
| `25_final` | The final sweep on all AMD systems, release-build validation (`validate*`), matched single-copy measurement (`matched/`), thesis numbers and figures (`thesis/`) | Section 6, Appendix 8.5 |
| `26_published` | The default benchmark of the published release build on all four systems, including the NVIDIA comparison | 6.1, 6.5 (NVIDIA figure) |

## Reproducing the thesis numbers and figures

Requires Python 3 with pandas, numpy and matplotlib.

```sh
cd benchmarks/25_final/thesis
python3 thesis_numbers.py --final > numbers.txt   # tables and values of Section 6
python3 plot_thesis.py --final                    # figures of Section 6
python3 plot_appendix.py --final                  # figures of the appendix
```

The figures are reproduced exactly from the data in this repository. In
`thesis_numbers.py`, the run counts of Section 6.1 cover only the included
studies, and they also count validation runs of the published build that were
added after `numbers_final.txt` was written (the final sweep itself comprises
356,892 runs). Without `--final`, the scripts read earlier studies that are not
included.

## Building and running

The programs are Celerity applications (`find_package(Celerity)`), built
against the Celerity builds above with AdaptiveCpp or DPC++. The build scripts
in the study folders call per-machine setup scripts
(`$WORK/scripts/setup_transfer_*.sh`) that hold the compiler paths and flags of
each system; they are not part of this repository. Appendix 8.2 and 8.3 of the
thesis describe the build recipe and how the YAML configurations are run.
In the Slurm job scripts, the LUMI project account is replaced by
`project_XXXXXXXXX`.
