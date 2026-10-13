#!/bin/bash
# Builds the c4ee4f1 state (AdaptiveCpp) on an IFIAMD node, never on the head node. Usage: sbatch job_build_state_ifi.sbatch
#SBATCH --partition=IFIAMD
#SBATCH --nodes=1
#SBATCH --cpus-per-task=32
#SBATCH --mem=0
#SBATCH --time=02:00:00
#SBATCH --job-name=fw-build-state
#SBATCH --output=/home/%u/finalizing-work/logs/slurm-%x-%j.log
#SBATCH --gres=gpu:1
cd "$HOME/finalizing-work"
echo "node: $(hostname)  start: $(date)"
GPU_ARCH=gfx1151 scripts/build_state.sh acpp c4ee4f1
echo "EXIT=$?  end: $(date)"
