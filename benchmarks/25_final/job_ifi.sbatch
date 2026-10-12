#!/bin/bash
# Final sweep job (one whole node, never the head/login node): optionally builds the extra programs against the final and final-bench installs
# (first argument "build"), then runs the given YAMLs through the unchanged benchmark_wrapper.py. Usage: sbatch job_ifi.sbatch <build|build2|run> <yaml>...
#SBATCH --partition=IFIAMD
#SBATCH --nodes=1
#SBATCH --cpus-per-task=32
#SBATCH --mem=0
#SBATCH --gres=gpu:1
#SBATCH --exclusive
#SBATCH --time=02:00:00
#SBATCH --job-name=fw-final
#SBATCH --output=/home/%u/finalizing-work/logs/slurm-%x-%j.log
cd "$HOME/finalizing-work"
echo "node: $(hostname)  start: $(date)"
mode=$1; shift
if [[ $mode == build || $mode == build2 ]]; then
	variants="final final-bench"; [[ $mode == build2 ]] && variants="${BUILD_VARIANTS:-final2}"  # BUILD_VARIANTS=published on ifi and gpuc4
	for impl in acpp dpcpp0326; do for v in $variants; do
		GPU_ARCH=gfx1151 benchmarks/25_final/build_programs.sh $impl $v > logs/build_final_programs-$impl-$v.log 2>&1 || { echo "EXIT=build $impl $v failed"; exit 1; }
		grep -E "Check|SETUP" logs/build_final_programs-$impl-$v.log | tr "\n" " "; echo
	done; done
fi
cd benchmarks
md5sum benchmark_wrapper.py
status=0
for y in "$@"; do python3 -u benchmark_wrapper.py "$y" || { status=$?; break; }; done
echo "EXIT=$status  end: $(date)"
