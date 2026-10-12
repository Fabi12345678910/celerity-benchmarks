#!/bin/bash
# Runs on an IFIAMD node (never on the head node, which has no ROCm): builds membw and linkbw (hipcc pinned to GCC 13 as in scripts/pin_gcc13.sh), then runs the ifi limit benchmarks
# through the unchanged benchmark_wrapper.py.
#SBATCH --partition=IFIAMD
#SBATCH --nodes=1
#SBATCH --cpus-per-task=32
#SBATCH --mem=0
#SBATCH --gres=gpu:1
#SBATCH --exclusive
#SBATCH --time=01:30:00
#SBATCH --job-name=fw-bench
#SBATCH --output=/home/%u/finalizing-work/logs/slurm-fw-bench-limits-%j.log
cd "$HOME/finalizing-work/benchmarks"
echo "node: $(hostname)  start: $(date)"
HIPCC_FLAGS="--gcc-install-dir=/usr/lib/gcc/x86_64-linux-gnu/13" 07_limits/build_limits.sh gfx1151 || { echo "EXIT=build failed"; exit 1; }
md5sum benchmark_wrapper.py
# arguments: the YAMLs to run (default: all three)
configs=("$@"); [[ ${#configs[@]} -gt 0 ]] || configs=(07_limits/ifi_membw.yaml 07_limits/ifi_linkbw.yaml 07_limits/ifi_concurrent.yaml)
for y in "${configs[@]}"; do python3 -u benchmark_wrapper.py "$y"; done
echo "EXIT=$?  end: $(date)"
