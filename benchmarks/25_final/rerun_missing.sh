#!/bin/bash
# Resubmits every YAML of <system>/jobs.txt whose CSV is missing or empty (e.g. a job hit the 2 h limit), packed into jobs of at most
# <per_job> YAMLs (default 6). Run on the ifi head node or a LUMI login node AFTER all sweep jobs have ended (check squeue), from ~/finalizing-work:
#   benchmarks/25_final/rerun_missing.sh <ifi|lumi> [per_job]      (dry run: DRY=1). Job ids go to logs/final_sweep_<system>_jobs.txt.
set -e
system=$1; per=${2:-6}
[[ $system == ifi || $system == lumi ]] || { echo "usage: $0 <ifi|lumi> [per_job]"; exit 1; }
cd "$HOME/finalizing-work"
missing=()
for y in $(cat benchmarks/25_final/$system/jobs.txt); do
	c=benchmarks/$(sed -n 's/^output_csv: //p' benchmarks/$y)
	[ -s "$c" ] || missing+=("$y")
done
echo "${#missing[@]} YAMLs without results"
for ((i = 0; i < ${#missing[@]}; i += per)); do
	part=("${missing[@]:i:per}")
	if [[ -n $DRY ]]; then echo "would submit: ${part[*]}"; continue; fi
	id=$(sbatch --parsable benchmarks/25_final/job_$system.sbatch run "${part[@]}")
	echo "rerun -> $id: ${part[*]}" | tee -a "logs/final_sweep_${system}_jobs.txt"
done
