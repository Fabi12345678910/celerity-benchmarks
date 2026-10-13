#!/bin/bash
# Runs on an IFIAMD node (never the head node): optionally builds all overhead programs (first argument "build"), then runs the given YAMLs
# through the unchanged benchmark_wrapper.py. Usage: sbatch [--dependency=...] job_ifi.sbatch <build|run> <yaml>...
#SBATCH --partition=IFIAMD
#SBATCH --nodes=1
#SBATCH --cpus-per-task=32
#SBATCH --mem=0
#SBATCH --gres=gpu:1
#SBATCH --exclusive
#SBATCH --time=02:00:00
#SBATCH --job-name=fw-overhead
#SBATCH --output=/home/%u/finalizing-work/logs/slurm-%x-%j.log
cd "$HOME/finalizing-work"
echo "node: $(hostname)  start: $(date)"
mode=$1; shift
if [[ $mode == build ]]; then
	HIPCC_FLAGS=--gcc-install-dir=/usr/lib/gcc/x86_64-linux-gnu/13 GPU_ARCH=gfx1151 benchmarks/23_overhead/build.sh all > logs/build_overhead_ifi.log 2>&1 || { tail -20 logs/build_overhead_ifi.log; echo "EXIT=build failed"; exit 1; }
	ls build/overhead/overhead_*
fi
cd benchmarks
md5sum benchmark_wrapper.py
status=0
for y in "$@"; do python3 -u benchmark_wrapper.py "$y" || { status=$?; break; }; done
echo "EXIT=$status  end: $(date)"
