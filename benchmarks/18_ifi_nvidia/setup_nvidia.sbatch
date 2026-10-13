#!/bin/bash
# Runs on an IFIgpu2070 node (never on the head node): builds the NVIDIA toolchain, see setup_nvidia.sh.
#SBATCH --partition=IFIgpu2070
#SBATCH --nodes=1
#SBATCH --cpus-per-task=32
#SBATCH --mem=0
#SBATCH --time=06:00:00
#SBATCH --job-name=fw-setup-nvidia
#SBATCH --output=/home/%u/finalizing-work/logs/slurm-%x-%j.log
#SBATCH --gres=gpu:1
cd "$HOME/finalizing-work"
echo "node: $(hostname)  start: $(date)"
scripts/setup_nvidia.sh
echo "EXIT=$?  end: $(date)"
