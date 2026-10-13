#!/bin/bash -l
# Runs on a LUMI standard-g node (never a login node): optionally builds all memcpy programs (first argument "build"), then runs the given YAMLs and (with build) the rocprofv3 traces (OpenCL: system ICD loader; the vendor file names libamdocl64.so without a path, so env-lumi.sh makes it ROCm 6.4.4)
# through the unchanged benchmark_wrapper.py. Usage: sbatch [--time=...] [--dependency=...] job_lumi.sbatch <build|run> <yaml>...
#SBATCH --account=project_XXXXXXXXX
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --time=02:00:00
#SBATCH --job-name=fw-memcpy
#SBATCH --output=/scratch/project_XXXXXXXXX/finalizing-work/logs/slurm-%x-%j.log
cd "$HOME/finalizing-work"
source scripts/env-lumi.sh
echo "node: $(hostname)  start: $(date)"
mode=$1; shift
if [[ $mode == build ]]; then
	OPENCL_INCLUDE=$ROCM_DIR/include benchmarks/24_memcpy/build.sh all > logs/build_memcpy_lumi.log 2>&1 || { tail -20 logs/build_memcpy_lumi.log; echo "EXIT=build failed"; exit 1; }
	ls build/memcpy/memcpy_*
fi
cd benchmarks
md5sum benchmark_wrapper.py
status=0
for y in "$@"; do python3 -u benchmark_wrapper.py "$y" || { status=$?; break; }; done
cd .. && [[ $status == 0 && $mode == build ]] && benchmarks/24_memcpy/trace.sh lumi > /dev/null 2>&1 && echo "trace done: $(date)"
echo "EXIT=$status  end: $(date)"
