#!/bin/bash
# Submits the sdma study jobs of one Slurm system (sbatch only; run on the ifi head node or a LUMI login node):
#   cd ~/finalizing-work && benchmarks/20_sdma_defaults/submit.sh <ifi|lumi>
# Each line of 20_sdma_defaults/<system>/jobs.txt is "<node or -> <yamls>"; ifi jobs are pinned to their node. Job ids go to logs/sdma_<system>_jobs.txt.
set -e
system=$1
[[ $system == ifi || $system == lumi ]] || { echo "usage: $0 <ifi|lumi>"; exit 1; }
cd "$HOME/finalizing-work"
while read -r node line; do
	opts=(); [[ $node != - ]] && opts=(--nodelist="$node")
	id=$(sbatch --parsable "${opts[@]}" scripts/job_bench.sbatch $line)
	echo "sdma job (${node}) $line -> $id" | tee -a "logs/sdma_${system}_jobs.txt"
done < "benchmarks/20_sdma_defaults/$system/jobs.txt"
