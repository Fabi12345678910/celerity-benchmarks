#!/bin/bash
# Runs on a LUMI standard-g node (never on a login node), in the environment of scripts/env-lumi.sh: builds strided_rows_transfer for both
# implementations (build_rows.sh, gfx90a from env-lumi.sh), then runs 10_rows/lumi_rows.yaml through the unchanged benchmark_wrapper.py.
#SBATCH --account=project_XXXXXXXXX
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --time=01:30:00
#SBATCH --job-name=fw-bench
#SBATCH --output=/scratch/project_XXXXXXXXX/finalizing-work/logs/slurm-fw-bench-rows-%j.log
cd "$HOME/finalizing-work"
source scripts/env-lumi.sh
echo "node: $(hostname)  start: $(date)"
for impl in ${2:-acpp dpcpp0326}; do benchmarks/10_rows/build_rows.sh $impl > /scratch/project_XXXXXXXXX/finalizing-work/logs/build_rows-$impl.log 2>&1 || { echo "EXIT=build $impl failed"; exit 1; }; tail -2 /scratch/project_XXXXXXXXX/finalizing-work/logs/build_rows-$impl.log; done
cd benchmarks
md5sum benchmark_wrapper.py
# arguments (optional): the YAML to run and the implementations to build (default: 10_rows/lumi_rows.yaml, acpp and dpcpp0326)
for y in "${1:-rows/lumi_rows.yaml}"; do python3 -u benchmark_wrapper.py "$y"; done
echo "EXIT=$?  end: $(date)"
