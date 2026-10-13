#!/bin/bash -l
# LUMI check: is plain HIP's 25 GB/s (vs Celerity's ~40 GB/s with SDMA off) a NUMA placement effect? GCD 4 is next to NUMA 0 (cores 1-7).
# Runs memcpy_hip (pinned, 1 GiB) unbound, bound to NUMA 0, bound to NUMA 3, SDMA off and on, 3 times each. Usage: sbatch job_lumi_numa.sbatch
#SBATCH --account=project_XXXXXXXXX
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --time=00:15:00
#SBATCH --job-name=fw-memcpy-numa
#SBATCH --output=/scratch/project_XXXXXXXXX/finalizing-work/logs/slurm-%x-%j.log
cd "$HOME/finalizing-work"
source scripts/env-lumi.sh
echo "node: $(hostname)  start: $(date)"
for sdma in 0 1; do
	for bind in "" "numactl --cpunodebind=0 --membind=0" "numactl --cpunodebind=3 --membind=3"; do
		for i in 1 2 3; do
			echo "sdma=$sdma bind=${bind:-none} run=$i: $(ROCR_VISIBLE_DEVICES=4 HSA_ENABLE_SDMA=$sdma $bind build/memcpy/memcpy_hip 1073741824 10 pinned | grep -E '^(H2D|D2H):' | sed -E 's/us median.*, ([0-9.]+ GB\/s).*/\1/' | paste -sd' ')"
		done
	done
done
echo "EXIT=0  end: $(date)"
