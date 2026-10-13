#!/bin/bash
# Runs on an IFIAMD node (never the head node): optionally builds all memcpy programs (first argument "build"), then runs the given YAMLs and (with build) the rocprofv3 traces
# through the unchanged benchmark_wrapper.py. Usage: sbatch [--dependency=...] job_ifi.sbatch <build|run> <yaml>...
# Env: BUILD_TARGETS (default all), NO_TRACE=1 skips the traces. 4 B runs: sbatch --export=ALL,BUILD_TARGETS="hip celerity-acpp celerity-dpcpp0326",NO_TRACE=1 job_ifi.sbatch build 24_memcpy/ifi/memcpy_4b.yaml
#SBATCH --partition=IFIAMD
#SBATCH --nodes=1
#SBATCH --cpus-per-task=32
#SBATCH --mem=0
#SBATCH --gres=gpu:1
#SBATCH --exclusive
#SBATCH --time=02:00:00
#SBATCH --job-name=fw-memcpy
#SBATCH --output=/home/%u/finalizing-work/logs/slurm-%x-%j.log
cd "$HOME/finalizing-work"
echo "node: $(hostname)  start: $(date)"
mode=$1; shift
if [[ $mode == build ]]; then
	HIPCC=${HIPCC:-/opt/rocm-7.1.0/bin/hipcc} HIPCC_FLAGS=--gcc-install-dir=/usr/lib/gcc/x86_64-linux-gnu/13 GPU_ARCH=gfx1151 benchmarks/24_memcpy/build.sh ${BUILD_TARGETS:-all} > logs/build_memcpy_ifi.log 2>&1 || { tail -20 logs/build_memcpy_ifi.log; echo "EXIT=build failed"; exit 1; }
	ls build/memcpy/memcpy_*
fi
cd benchmarks
md5sum benchmark_wrapper.py
status=0
for y in "$@"; do python3 -u benchmark_wrapper.py "$y" || { status=$?; break; }; done
cd .. && [[ $status == 0 && $mode == build && -z ${NO_TRACE:-} ]] && benchmarks/24_memcpy/trace.sh ifi > /dev/null 2>&1 && echo "trace done: $(date)"
echo "EXIT=$status  end: $(date)"
