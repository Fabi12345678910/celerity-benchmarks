#!/bin/bash
# Matched copy measurement on gpuc4 (thesis review item 31), run directly on the machine once nothing else runs there.
# Usage (from ~/finalizing-work): benchmarks/25_final/matched/run_gpuc4.sh > benchmarks/25_final/matched/gpuc4_first_copy.log 2>&1
cd "$HOME/finalizing-work"
D=benchmarks/25_final/matched
hostname; lscpu | grep -E "Model name|Socket|Core\(s\) per|Thread\(s\) per|^CPU\(s\)"
/opt/rocm-7.1.0/bin/hipcc -O3 --offload-arch=gfx1200 $D/first_copy.hip -o $D/first_copy_gpuc4 || exit 1
for sdma in 0 1; do for dir in h2d d2h; do echo "== SDMA=$sdma $dir"; HSA_ENABLE_SDMA=$sdma taskset -c 1 $D/first_copy_gpuc4 $dir 1024; done; done
echo "== Celerity block_transfer 2^28 (final-bench, defaults, SDMA off), first access as measured in the sweeps"
for i in 1 2 3; do HSA_ENABLE_SDMA=0 build/bench-transfer-acpp-final-bench/block_transfer 268435456 | grep -E "first access|device to host"; done
echo "== same, copylib routed (CELERITY_COPYLIB_ROUTE=all, staging defaults)"
for i in 1 2 3; do HSA_ENABLE_SDMA=0 CELERITY_COPYLIB_ROUTE=all build/bench-transfer-acpp-final-bench/block_transfer 268435456 | grep -E "first access|device to host"; done
