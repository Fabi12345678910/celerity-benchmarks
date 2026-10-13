#!/bin/bash -l
# Runs on a LUMI standard-g node (never a login node): optionally builds device_strided_transfer for both implementations (first argument "build"), then runs
# the given YAMLs. Usage: sbatch [--dependency=...] job_lumi.sbatch <build|run> <yaml>...
#SBATCH --account=project_XXXXXXXXX
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --time=02:00:00
#SBATCH --job-name=fw-device-strided
#SBATCH --output=/scratch/project_XXXXXXXXX/finalizing-work/logs/slurm-%x-%j.log
cd "$HOME/finalizing-work"
source scripts/env-lumi.sh
echo "node: $(hostname)  start: $(date)"
mode=$1; shift
if [[ $mode == build ]]; then
	for impl in acpp dpcpp0326; do GPU_ARCH=gfx90a benchmarks/22_device_strided/build_device.sh $impl > logs/build_device-$impl.log 2>&1 || { echo "EXIT=build $impl failed"; exit 1; }; tail -2 logs/build_device-$impl.log; done
fi
cd benchmarks
md5sum benchmark_wrapper.py
status=0
for y in "$@"; do python3 -u benchmark_wrapper.py "$y" || { status=$?; break; }; done
echo "EXIT=$status  end: $(date)"
