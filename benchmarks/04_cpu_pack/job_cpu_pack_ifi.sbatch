#!/bin/bash
# Runs on an IFIAMD node (never on the head node): builds cpu_pack against copylib's header with the clang that built copylib, checks it
# once per variant, then runs cpu_pack_ifi.yaml through the unchanged benchmark_wrapper.py.
#SBATCH --partition=IFIAMD
#SBATCH --nodes=1
#SBATCH --cpus-per-task=32
#SBATCH --mem=0
#SBATCH --gres=gpu:1
#SBATCH --exclusive
#SBATCH --time=02:00:00
#SBATCH --job-name=fw-bench
#SBATCH --output=/home/%u/finalizing-work/logs/slurm-fw-bench-cpu_pack-%j.log
cd "$HOME/finalizing-work/benchmarks/cpu_pack"
echo "node: $(hostname)  start: $(date)"
CXX="$HOME/finalizing-work/install/llvm/bin/clang++"
[ -x "$CXX" ] || CXX=g++
INC="$HOME/finalizing-work/build/celerity-acpp-bench/_deps/gpu3dcopylib-src/include"
"$CXX" --version | head -1
"$CXX" -O3 -std=c++20 -I"$INC" cpu_pack.cpp -o cpu_pack -pthread || { echo "EXIT=build failed"; exit 1; }
for v in copylib rowloop fixed; do for d in pack unpack; do echo "$v $d: $(./cpu_pack $v $d 1048577 3 5,6 | grep -E 'copy|Check' | tr '\n' ' ')"; done; done
mkdir -p results
cd ..
md5sum benchmark_wrapper.py
python3 -u benchmark_wrapper.py 04_cpu_pack/cpu_pack_ifi.yaml
echo "EXIT=$?  end: $(date)"
