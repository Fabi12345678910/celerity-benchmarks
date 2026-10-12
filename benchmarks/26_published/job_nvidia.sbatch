#!/bin/bash
# Runs benchmark configs on an exclusive IFIgpu2070 node (never the head node): sbatch 26_published/job_nvidia.sbatch 26_published/nvidia/<yaml> ...
#SBATCH --partition=IFIgpu2070
#SBATCH --nodes=1
#SBATCH --cpus-per-task=32
#SBATCH --mem=0
#SBATCH --time=02:00:00
#SBATCH --job-name=fw-published-lines
#SBATCH --output=/home/%u/finalizing-work/logs/slurm-%x-%j.log
#SBATCH --gres=gpu:1
#SBATCH --exclusive
cd "$HOME/finalizing-work"
echo "node: $(hostname)  start: $(date)"
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
cd benchmarks
md5sum benchmark_wrapper.py
status=0
for config in "$@"; do python3 -u benchmark_wrapper.py "$config" || { status=$?; break; }; done
echo "EXIT=$status  end: $(date)"
