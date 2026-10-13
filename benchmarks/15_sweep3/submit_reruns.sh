#!/bin/bash
# Submits the base rerun jobs (make_base_rerun.py) of one Slurm system. Run on the ifi head node or a LUMI login node:
#   cd ~/finalizing-work && benchmarks/15_sweep3/submit_reruns.sh <ifi|lumi>
# Each line of 15_sweep3/<system>/rerun_jobs.txt is "<node or -> <yamls>"; ifi jobs are pinned to their node (--nodelist), so every
# node gets its own reference runs. Job ids go to logs/sweep3_<system>_anchor_jobs.txt.
set -e
system=$1
[[ $system == ifi || $system == lumi ]] || { echo "usage: $0 <ifi|lumi>"; exit 1; }
cd "$HOME/finalizing-work"
n=0
while read -r node line; do
	n=$((n + 1))
	opts=(); [[ $node != - ]] && opts=(--nodelist="$node")
	id=$(sbatch --parsable "${opts[@]}" scripts/job_bench.sbatch $line)
	echo "rerun job $n (${node}) -> $id" | tee -a "logs/sweep3_${system}_rerun_jobs.txt"
done < "benchmarks/15_sweep3/$system/rerun_jobs.txt"
