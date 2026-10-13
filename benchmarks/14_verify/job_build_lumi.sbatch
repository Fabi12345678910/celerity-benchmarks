#!/bin/bash -l
# Builds 3dcopylib-bench for one implementation (unit tests and variable checks included), then strided_transfer, strided_rows_transfer and
# strided_both_transfer against it. Runs as a LUMI small-g job (never on a login node), in scripts/env-lumi.sh. Argument: acpp or dpcpp0326.
#SBATCH --account=project_XXXXXXXXX
#SBATCH --partition=small-g
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gpus-per-node=1
#SBATCH --cpus-per-task=32
#SBATCH --mem=240G
#SBATCH --time=02:00:00
#SBATCH --job-name=fw-verify-build
#SBATCH --output=/scratch/project_XXXXXXXXX/finalizing-work/logs/slurm-%x-%j.log
cd "$HOME/finalizing-work"
source scripts/env-lumi.sh
echo "node: $(hostname)  cpus: $(nproc)  start: $(date)  celerity: $(git -C src/celerity-bench log -1 --format=%h)"
scripts/setup_celerity_bench.sh "$1" && scripts/setup_transfer.sh "$1" && benchmarks/10_rows/build_rows.sh "$1" && benchmarks/08_both_strided/build_both.sh "$1"
status=$?; echo "EXIT=$status  end: $(date)"; exit $status
