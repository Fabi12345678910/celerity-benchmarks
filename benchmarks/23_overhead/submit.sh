#!/bin/bash
# Submits the overhead study on ifi or LUMI, one job per line of <system>/jobs.txt: the first job builds all programs, the others wait for it (afterok).
# LUMI: the strided job gets 3 h (about 70 min on gpuc4), at most 7 node-hours = 28 GPU-h in total. Usage, from ~/finalizing-work: benchmarks/23_overhead/submit.sh <ifi|lumi>
set -euo pipefail
cd "$HOME/finalizing-work"
system=$1
D=benchmarks/23_overhead
script=$D/job_$system.sbatch
log=logs/overhead_${system}_jobs.txt
first=""
while read -r yamls; do
	time=()
	[[ $system == lumi && $yamls == *strided.yaml ]] && time=(--time=03:00:00)
	if [[ -z $first ]]; then
		first=$(sbatch --parsable "${time[@]}" $script build $yamls)
		echo "$(date +%m-%d\ %H:%M) build + $yamls -> $first" | tee -a $log
	else
		j=$(sbatch --parsable "${time[@]}" --dependency=afterok:$first $script run $yamls)
		echo "$(date +%m-%d\ %H:%M) $yamls -> $j after $first" | tee -a $log
	fi
done < $D/$system/jobs.txt
