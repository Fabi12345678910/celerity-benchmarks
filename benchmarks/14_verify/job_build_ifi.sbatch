#!/bin/bash
# Runs on an IFIAMD node (never on the head node): builds 3dcopylib-bench for one implementation (unit tests and variable checks included),
# then strided_transfer, strided_rows_transfer and strided_both_transfer against it, for gfx1151. Argument: acpp or dpcpp0326.
#SBATCH --partition=IFIAMD
#SBATCH --nodes=1
#SBATCH --cpus-per-task=32
#SBATCH --mem=0
#SBATCH --gres=gpu:1
#SBATCH --exclusive
#SBATCH --time=02:00:00
#SBATCH --job-name=fw-verify-build
#SBATCH --output=/home/%u/finalizing-work/logs/slurm-%x-%j.log
cd "$HOME/finalizing-work"
echo "node: $(hostname)  start: $(date)  celerity: $(git -C src/celerity-bench log -1 --format=%h)"
export GPU_ARCH=gfx1151
scripts/setup_celerity_bench.sh "$1" && scripts/setup_transfer.sh "$1" && benchmarks/10_rows/build_rows.sh "$1" && benchmarks/08_both_strided/build_both.sh "$1"
status=$?; echo "EXIT=$status  end: $(date)"; exit $status
