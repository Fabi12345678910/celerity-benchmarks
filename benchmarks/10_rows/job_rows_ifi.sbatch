#!/bin/bash
# Runs on an IFIAMD node (never on the head node): builds strided_rows_transfer for both implementations (build_rows.sh, gfx1151), then
# runs 10_rows/ifi_rows.yaml through the unchanged benchmark_wrapper.py.
#SBATCH --partition=IFIAMD
#SBATCH --nodes=1
#SBATCH --cpus-per-task=32
#SBATCH --mem=0
#SBATCH --gres=gpu:1
#SBATCH --exclusive
#SBATCH --time=01:30:00
#SBATCH --job-name=fw-bench
#SBATCH --output=/home/%u/finalizing-work/logs/slurm-fw-bench-rows-%j.log
cd "$HOME/finalizing-work"
echo "node: $(hostname)  start: $(date)"
for impl in ${2:-acpp dpcpp0326}; do GPU_ARCH=gfx1151 benchmarks/10_rows/build_rows.sh $impl > logs/build_rows-$impl.log 2>&1 || { echo "EXIT=build $impl failed"; exit 1; }; tail -2 logs/build_rows-$impl.log; done
cd benchmarks
md5sum benchmark_wrapper.py
# arguments (optional): the YAML to run and the implementations to build (default: 10_rows/ifi_rows.yaml, acpp and dpcpp0326)
for y in "${1:-rows/ifi_rows.yaml}"; do python3 -u benchmark_wrapper.py "$y"; done
echo "EXIT=$?  end: $(date)"
