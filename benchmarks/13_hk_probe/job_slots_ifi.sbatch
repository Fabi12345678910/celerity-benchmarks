#!/bin/bash
# Runs on an IFIAMD node (never on the head node, which has no ROCm): builds hk_probe for gfx1151 (hipcc pinned to GCC 13 as in
# 07_limits/job_limits_ifi.sbatch), then runs 13_hk_probe/ifi_slots.yaml through the unchanged benchmark_wrapper.py.
#SBATCH --partition=IFIAMD
#SBATCH --nodes=1
#SBATCH --cpus-per-task=32
#SBATCH --mem=0
#SBATCH --gres=gpu:1
#SBATCH --exclusive
#SBATCH --time=00:45:00
#SBATCH --job-name=fw-bench
#SBATCH --output=/home/%u/finalizing-work/logs/slurm-fw-bench-slots-%j.log
cd "$HOME/finalizing-work/benchmarks"
echo "node: $(hostname)  start: $(date)"
"${ROCM_DIR:-/opt/rocm-7.1.0}/bin/hipcc" -O3 --gcc-install-dir=/usr/lib/gcc/x86_64-linux-gnu/13 --offload-arch=gfx1151 13_hk_probe/hk_probe.hip \
	-o 13_hk_probe/hk_probe 2>&1 | grep -v "warning:" || true
[ -x 13_hk_probe/hk_probe ] || { echo "EXIT=build failed"; exit 1; }
md5sum benchmark_wrapper.py
python3 -u benchmark_wrapper.py "${1:-hk_probe/ifi_slots.yaml}"
echo "EXIT=$?  end: $(date)"
