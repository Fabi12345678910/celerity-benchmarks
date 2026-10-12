#!/bin/bash
# Build and smoke test of device_strided_transfer on an NVIDIA node. Usage: sbatch job_nvidia_test.sbatch
#SBATCH --partition=IFIgpu2070
#SBATCH --nodes=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=00:40:00
#SBATCH --job-name=fw-device-strided-test
#SBATCH --output=/home/%u/finalizing-work/logs/slurm-%x-%j.log
#SBATCH --gres=gpu:1
cd "$HOME/finalizing-work"
echo "node: $(hostname)  start: $(date)"
benchmarks/22_device_strided/build_nvidia.sh
echo "EXIT=$?  end: $(date)"
