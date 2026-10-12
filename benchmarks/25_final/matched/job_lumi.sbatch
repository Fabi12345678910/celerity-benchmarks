#!/bin/bash -l
# Matched copy measurement and CPU facts for the thesis review (items 25, 31): one LUMI standard-g node, never the login node.
#SBATCH --account=project_XXXXXXXXX
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --exclusive
#SBATCH --time=00:15:00
#SBATCH --job-name=fw-matched
#SBATCH --output=/scratch/project_XXXXXXXXX/finalizing-work/logs/slurm-%x-%j.log
cd "$HOME/finalizing-work"
source scripts/env-lumi.sh
D=benchmarks/25_final/matched
hostname; lscpu | grep -E "Model name|Socket|Core\(s\) per|Thread\(s\) per|^CPU\(s\)|NUMA node\(s\)"; free -g | head -2
"$ROCM_DIR/bin/hipcc" -O3 --offload-arch=gfx90a $D/first_copy.hip -o $D/first_copy_lumi || exit 1
for sdma in 0 1; do for dir in h2d d2h; do echo "== SDMA=$sdma $dir"; ROCR_VISIBLE_DEVICES=4 HSA_ENABLE_SDMA=$sdma taskset -c 1 $D/first_copy_lumi $dir 1024; done; done
echo "== Celerity block_transfer 2^28 (final-bench, defaults, SDMA off), first access as measured in the sweeps"
for i in 1 2 3; do ROCR_VISIBLE_DEVICES=4 HSA_ENABLE_SDMA=0 build/bench-transfer-acpp-final-bench/block_transfer 268435456 | grep -E "first access|device to host"; done
