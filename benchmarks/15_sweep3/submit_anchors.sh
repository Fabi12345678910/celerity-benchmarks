#!/bin/bash
# Submits the post-sweep anchor jobs (make_sweep3_yamls.py --post-anchors) of one Slurm system. Run on the ifi head node or a LUMI login node:
#   cd ~/finalizing-work && benchmarks/15_sweep3/submit_anchors.sh <ifi|lumi>
# Each line of 15_sweep3/<system>/anchors_post_jobs.txt is "<node or -> <yamls>"; ifi jobs are pinned to their node (--nodelist), so every
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
	echo "anchor job $n (${node}) -> $id" | tee -a "logs/sweep3_${system}_anchor_jobs.txt"
done < "benchmarks/15_sweep3/$system/anchors_post_jobs.txt"
