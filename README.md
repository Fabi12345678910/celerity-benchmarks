# Celerity strided-transfer benchmarks

Benchmark programs, configurations, raw results and analysis scripts of the
bachelor thesis *Optimizing Strided Data Transfers on AMD Hardware* (Fabian
Pfaff, Distributed and Parallel Systems Group, University of Innsbruck, 2026).
This repository holds every study, from the first measurements before
gpu3dcopylib through the configuration sweeps to the final sweep that the
thesis evaluation is based on.

## Code under test

| Component | Where | Commit |
|---|---|---|
| Celerity, release build | github.com/Fabi12345678910/celerity-runtime, `master` | `536d754` |
| Celerity, benchmark build | github.com/Fabi12345678910/celerity-runtime, `bench` | `d7ce718` (source tree identical to the measured build `f24e5f0`) |
| gpu3dcopylib | github.com/Fabi12345678910/gpu3dcopylib | `843fafe` |

Earlier studies used intermediate builds; each study's `README.md` names its
build.

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
- `benchmarks/`: one folder per study, numbered in the order they were run.
  `benchmarks/README.md` lists every study with its goal and result. Each
  folder has its own `README.md`, the YAML configurations (`output_csv` names
  the result file), Slurm job scripts and the results as CSV.

The thesis uses mainly `25_final` (the final sweep, release-build validation,
and the scripts for all numbers and figures of the evaluation in
`25_final/thesis/`), `26_published`, `07_limits` and `04_cpu_pack`.

## Reproducing the thesis numbers and figures

Requires Python 3 with pandas, numpy and matplotlib.

```sh
cd benchmarks/25_final/thesis
python3 thesis_numbers.py --final > numbers.txt   # tables and values of Section 6
python3 plot_thesis.py --final                    # figures of Section 6
python3 plot_appendix.py --final                  # figures of the appendix
```

## Building and running

The programs are Celerity applications (`find_package(Celerity)`), built
against the Celerity builds above with AdaptiveCpp or DPC++. The build scripts
in the study folders call per-machine setup scripts
(`$WORK/scripts/setup_transfer_*.sh`) that hold the compiler paths and flags of
each system; they are not part of this repository. Appendix 8.2 and 8.3 of the
thesis describe the build recipe and how the YAML configurations are run.
In the Slurm job scripts and job logs, the LUMI project account is replaced by
`project_XXXXXXXXX`.
