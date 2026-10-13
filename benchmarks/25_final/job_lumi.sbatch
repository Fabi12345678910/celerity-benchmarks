#!/bin/bash -l
# Final sweep job (one whole node, never the head/login node): optionally builds the extra programs against the final and final-bench installs
# (first argument "build"), then runs the given YAMLs through the unchanged benchmark_wrapper.py. Usage: sbatch job_lumi.sbatch <build|build2|run> <yaml>...
#SBATCH --account=project_XXXXXXXXX
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --exclusive
#SBATCH --time=02:00:00
#SBATCH --job-name=fw-final
#SBATCH --output=/scratch/project_XXXXXXXXX/finalizing-work/logs/slurm-%x-%j.log
cd "$HOME/finalizing-work"
source scripts/env-lumi.sh
echo "node: $(hostname)  start: $(date)"
mode=$1; shift
if [[ $mode == build || $mode == build2 ]]; then
	variants="final final-bench"; [[ $mode == build2 ]] && variants="${BUILD_VARIANTS:-final2}"  # BUILD_VARIANTS=published on ifi and gpuc4
	for impl in acpp dpcpp0326; do for v in $variants; do
		GPU_ARCH=gfx90a benchmarks/25_final/build_programs.sh $impl $v > logs/build_final_programs-$impl-$v.log 2>&1 || { echo "EXIT=build $impl $v failed"; exit 1; }
		grep -E "Check|SETUP" logs/build_final_programs-$impl-$v.log | tr "\n" " "; echo
	done; done
fi
cd benchmarks
md5sum benchmark_wrapper.py
status=0
for y in "$@"; do python3 -u benchmark_wrapper.py "$y" || { status=$?; break; }; done
echo "EXIT=$status  end: $(date)"
