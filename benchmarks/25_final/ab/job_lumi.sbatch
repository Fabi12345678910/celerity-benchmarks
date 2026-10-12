#!/bin/bash -l
# A/B kernel test on one LUMI standard-g node: builds the extra programs against final3, then runs ab_device and ab_both (final2 / final3 / final-bench).
#SBATCH --account=project_XXXXXXXXX
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --exclusive
#SBATCH --time=02:00:00
#SBATCH --job-name=fw-final-ab
#SBATCH --output=/scratch/project_XXXXXXXXX/finalizing-work/logs/slurm-%x-%j.log
cd "$HOME/finalizing-work"
source scripts/env-lumi.sh
echo "node: $(hostname)  start: $(date)  final3 source: $(git -C src/celerity-final3 log -1 --oneline)"
for impl in acpp dpcpp0326; do
	GPU_ARCH=gfx90a benchmarks/25_final/build_programs.sh $impl final3 > logs/build_final_programs-$impl-final3.log 2>&1 || { echo "EXIT=build $impl final3 failed"; exit 1; }
done
cd benchmarks
md5sum benchmark_wrapper.py
status=0
for y in 25_final/ab/lumi/ab_device.yaml 25_final/ab/lumi/ab_both.yaml; do python3 -u benchmark_wrapper.py "$y" || { status=$?; break; }; done
echo "EXIT=$status  end: $(date)"
