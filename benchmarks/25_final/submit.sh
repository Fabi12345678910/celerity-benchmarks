#!/bin/bash
# Submits jobs of the final sweep on a Slurm system. Run on the ifi head node or a LUMI login node (sbatch only, no benchmarks there):
#   cd ~/finalizing-work && benchmarks/25_final/submit.sh <ifi|lumi> <validate|validate2|sweep> [first_job [last_job]]
# validate / validate2: the first line of <system>/validate_jobs.txt builds the extra programs (validate: final + final-bench, validate2: final2) and runs; the other lines wait for it (afterok).
# AFTER=<id[:id...]> makes the first validate job wait for those jobs (e.g. the build jobs).
# sweep: every line of <system>/jobs.txt is one job. Job ids go to logs/final_<mode>_<system>_jobs.txt.
set -e
system=$1; mode=$2; first=${3:-1}; last=${4:-100000}
[[ $system == ifi || $system == lumi ]] && [[ $mode == validate || $mode == validate2 || $mode == sweep ]] || { echo "usage: $0 <ifi|lumi> <validate|validate2|sweep> [first [last]]"; exit 1; }
cd "$HOME/finalizing-work"
list=benchmarks/25_final/$system/$([[ $mode == sweep ]] && echo jobs.txt || echo ${mode}_jobs.txt)
script=benchmarks/25_final/job_$system.sbatch
n=0; dep=""
while read -r line; do
	n=$((n + 1))
	[[ $n -ge $first && $n -le $last ]] || continue
	if [[ $mode != sweep && $n == 1 ]]; then
		id=$(sbatch --parsable ${AFTER:+--dependency=afterok:$AFTER} $script $([[ $mode == validate2 ]] && echo build2 || echo build) $line); dep="--dependency=afterok:$id"
	else
		id=$(sbatch --parsable $dep $script run $line)
	fi
	echo "job $n -> $id: ${line%% *} .." | tee -a "logs/final_${mode}_${system}_jobs.txt"
done < "$list"
