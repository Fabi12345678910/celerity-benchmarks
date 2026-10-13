#!/bin/bash
# Probe of the IFIgpu2070 partition (RTX 2070 nodes, gc1-7): what GPU, driver, CUDA toolkit, compilers and CPUs a node offers. Runs on a compute node
# only (never the head node), changes nothing. Usage: sbatch 18_ifi_nvidia/probe.sbatch
#SBATCH --partition=IFIgpu2070
#SBATCH --nodes=1
#SBATCH --cpus-per-task=32
#SBATCH --mem=0
#SBATCH --time=00:10:00
#SBATCH --job-name=fw-nvidia-probe
#SBATCH --output=/home/%u/finalizing-work/logs/slurm-%x-%j.log
#SBATCH --gres=gpu:1
echo "node: $(hostname)  start: $(date)"
echo "--- gpu"; nvidia-smi -L; nvidia-smi --query-gpu=name,driver_version,memory.total,pcie.link.gen.max,pcie.link.width.max --format=csv; nvidia-smi topo -m 2>&1 | head -12
echo "--- cuda"; ls -d /usr/local/cuda* /opt/cuda* 2>&1 | head; which nvcc; nvcc --version 2>&1 | tail -2; ldconfig -p | grep -E "libcuda\.|libcudart" | head -3
echo "--- compilers"; which gcc g++ clang cmake ninja 2>&1; gcc --version | head -1
echo "--- modules"; (module avail 2>&1 | head -30) || true
echo "--- cpu"; lscpu | grep -E "Model name|^CPU\(s\)|Thread|Socket|NUMA node\(s\)|L3"
echo "--- mem"; free -g | head -2
echo "--- toolchain of ours"; ls ~/finalizing-work/install | head -20; ls ~/finalizing-work/install/llvm/bin 2>/dev/null | head -3
echo "EXIT=0  end: $(date)"
