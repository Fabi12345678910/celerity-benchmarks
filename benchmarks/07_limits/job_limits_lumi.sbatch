#!/bin/bash
# Runs on a LUMI standard-g node (never on a login node), in the environment of scripts/env-lumi.sh: builds membw and linkbw, then runs
# the LUMI limit benchmarks through the unchanged benchmark_wrapper.py (Python 3.11 from env-lumi.sh). The whole node, so the memory
# benchmarks can use all 56 cores; linkbw uses GCD 4 (ROCR_VISIBLE_DEVICES=4 in the YAML).
#SBATCH --account=project_XXXXXXXXX
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --time=01:00:00
#SBATCH --job-name=fw-bench
#SBATCH --output=/scratch/project_XXXXXXXXX/finalizing-work/logs/slurm-fw-bench-limits-%j.log
cd "$HOME/finalizing-work"
source scripts/env-lumi.sh
cd benchmarks
echo "node: $(hostname)  start: $(date)"
07_limits/build_limits.sh gfx90a || { echo "EXIT=build failed"; exit 1; }
md5sum benchmark_wrapper.py
for y in 07_limits/lumi_membw.yaml 07_limits/lumi_linkbw.yaml 07_limits/lumi_concurrent.yaml; do python3 -u benchmark_wrapper.py "$y"; done
echo "EXIT=$?  end: $(date)"
