#!/bin/bash
# Runs on a LUMI standard-g node (never on a login node), in the environment of scripts/env-lumi.sh: builds hk_probe for gfx90a, then
# runs 13_hk_probe/lumi_slots.yaml (GCD 4, ROCR_VISIBLE_DEVICES=4 in the YAML) through the unchanged benchmark_wrapper.py.
#SBATCH --account=project_XXXXXXXXX
#SBATCH --partition=standard-g
#SBATCH --nodes=1
#SBATCH --gpus-per-node=8
#SBATCH --time=00:30:00
#SBATCH --job-name=fw-bench
#SBATCH --output=/scratch/project_XXXXXXXXX/finalizing-work/logs/slurm-fw-bench-slots-%j.log
cd "$HOME/finalizing-work"
source scripts/env-lumi.sh
cd benchmarks
echo "node: $(hostname)  start: $(date)"
"$ROCM_DIR/bin/hipcc" -O3 --offload-arch=gfx90a 13_hk_probe/hk_probe.hip -o 13_hk_probe/hk_probe 2>&1 | grep -v "warning:" || true
[ -x 13_hk_probe/hk_probe ] || { echo "EXIT=build failed"; exit 1; }
md5sum benchmark_wrapper.py
python3 -u benchmark_wrapper.py "${1:-hk_probe/lumi_slots.yaml}"
echo "EXIT=$?  end: $(date)"
