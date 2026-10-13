#!/bin/bash
# Submits the sweep 3 jobs of one Slurm system. Run on the ifi head node or a LUMI login node (sbatch only, no benchmarks there):
#   cd ~/finalizing-work && benchmarks/21_sweep4/submit.sh <ifi|lumi> [first_job [last_job]]
# Each line of 21_sweep4/<system>/jobs.txt is one job (at most 105 estimated minutes, inside the 2 h limit). The job ids go to
# logs/sweep4_<system>_jobs.txt; results land in benchmarks/21_sweep4/<system>/results/ on the machine.
set -e
system=$1; first=${2:-1}; last=${3:-100000}
[[ $system == ifi || $system == lumi ]] || { echo "usage: $0 <ifi|lumi> [first_job [last_job]]"; exit 1; }
cd "$HOME/finalizing-work"
n=0
while read -r line; do
	n=$((n + 1))
	[[ $n -ge $first && $n -le $last ]] || continue
	id=$(sbatch --parsable scripts/job_bench.sbatch $line)
	echo "job $n -> $id: ${line%% *} .." | tee -a "logs/sweep4_${system}_jobs.txt"
done < "benchmarks/21_sweep4/$system/jobs.txt"
