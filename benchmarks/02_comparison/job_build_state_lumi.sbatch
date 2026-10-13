#!/bin/bash -l
# Builds the c4ee4f1 state (AdaptiveCpp) as a LUMI small-g job, never on a login node. Usage: sbatch job_build_state_lumi.sbatch
#SBATCH --account=project_XXXXXXXXX
#SBATCH --partition=small-g
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gpus-per-node=1
#SBATCH --cpus-per-task=32
#SBATCH --mem=240G
#SBATCH --time=02:00:00
#SBATCH --job-name=fw-build-state
#SBATCH --output=/scratch/project_XXXXXXXXX/finalizing-work/logs/slurm-%x-%j.log
cd "$HOME/finalizing-work"
source scripts/env-lumi.sh
echo "node: $(hostname)  cpus: $(nproc)  start: $(date)"
GPU_ARCH=gfx90a scripts/build_state.sh acpp c4ee4f1
echo "EXIT=$?  end: $(date)"
