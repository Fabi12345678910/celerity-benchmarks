#!/bin/bash
# Runs on an IFIAMD node (never the head node): optionally builds device_strided_transfer for both implementations (first argument "build"), then runs the
# given YAMLs through the unchanged benchmark_wrapper.py. Usage: sbatch [--dependency=...] job_ifi.sbatch <build|run> <yaml>...
#SBATCH --partition=IFIAMD
#SBATCH --nodes=1
#SBATCH --cpus-per-task=32
#SBATCH --mem=0
#SBATCH --gres=gpu:1
#SBATCH --exclusive
#SBATCH --time=02:00:00
#SBATCH --job-name=fw-device-strided
#SBATCH --output=/home/%u/finalizing-work/logs/slurm-%x-%j.log
cd "$HOME/finalizing-work"
echo "node: $(hostname)  start: $(date)"
mode=$1; shift
if [[ $mode == build ]]; then
	for impl in acpp dpcpp0326; do GPU_ARCH=gfx1151 benchmarks/22_device_strided/build_device.sh $impl > logs/build_device-$impl.log 2>&1 || { echo "EXIT=build $impl failed"; exit 1; }; tail -2 logs/build_device-$impl.log; done
fi
cd benchmarks
md5sum benchmark_wrapper.py
status=0
for y in "$@"; do python3 -u benchmark_wrapper.py "$y" || { status=$?; break; }; done
echo "EXIT=$status  end: $(date)"
