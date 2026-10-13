#!/bin/bash
# gpuc4: builds hip and Celerity (acpp, DPC++) memcpy programs and runs memcpy_4b.yaml.
# Usage, from ~/finalizing-work: setsid nohup benchmarks/24_memcpy/run_4b_gpuc4.sh > logs/memcpy_4b_gpuc4.log 2>&1 < /dev/null &
cd "$HOME/finalizing-work"
echo "build $(date +%H:%M)"
GPU_ARCH=gfx1200 benchmarks/24_memcpy/build.sh hip celerity-acpp celerity-dpcpp0326 > logs/build_memcpy_gpuc4.log 2>&1 || { tail -20 logs/build_memcpy_gpuc4.log; echo "MEMCPY4B-FAILED build"; exit 1; }
cd benchmarks
md5sum benchmark_wrapper.py
echo "=== 24_memcpy/gpuc4/memcpy_4b.yaml $(date +%H:%M)"
timeout 1h python3 -u benchmark_wrapper.py 24_memcpy/gpuc4/memcpy_4b.yaml | grep -E "phase|Done|Error|Traceback"
echo "MEMCPY4B-DONE $(date +%H:%M)"
