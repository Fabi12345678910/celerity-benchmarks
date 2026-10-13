#!/bin/bash
# Submits the preload study jobs of one Slurm system (sbatch only; run on the ifi head node or a LUMI login node):
#   cd ~/finalizing-work && benchmarks/17_preload/submit.sh <ifi|lumi>
# Each line of 17_preload/<system>/jobs.txt is "<node or -> <yaml>"; ifi jobs are pinned to their node. Job ids go to logs/preload_<system>_jobs.txt.
set -e
system=$1
[[ $system == ifi || $system == lumi ]] || { echo "usage: $0 <ifi|lumi>"; exit 1; }
cd "$HOME/finalizing-work"
while read -r node line; do
	opts=(); [[ $node != - ]] && opts=(--nodelist="$node")
	id=$(sbatch --parsable "${opts[@]}" scripts/job_bench.sbatch $line)
	echo "preload job (${node}) $line -> $id" | tee -a "logs/preload_${system}_jobs.txt"
done < "benchmarks/17_preload/$system/jobs.txt"
