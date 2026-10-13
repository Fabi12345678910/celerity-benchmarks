#!/bin/bash
# gpuc4: waits for the overhead study (OVERHEAD-DONE in logs/overhead_gpuc4.log), then builds the memcpy programs, checks each once at 1 MiB,
# runs the YAML and the rocprofv3 traces. Usage, from ~/finalizing-work: setsid nohup benchmarks/24_memcpy/queue_gpuc4.sh > logs/memcpy_gpuc4.log 2>&1 &
cd "$HOME/finalizing-work"
D=benchmarks/24_memcpy
until grep -q OVERHEAD-DONE logs/overhead_gpuc4.log 2>/dev/null; do sleep 60; done
echo "build $(date +%H:%M)"
GPU_ARCH=gfx1200 $D/build.sh all > logs/build_memcpy_gpuc4.log 2>&1 || { tail -20 logs/build_memcpy_gpuc4.log; echo "MEMCPY-FAILED build"; exit 1; }
for b in hip opencl acpp dpcpp celerity_acpp celerity_dpcpp0326; do
	src=""; [[ $b == *dpcpp* ]] && src=". install/dpcpp-nightly-2026-03-26/env.sh &&"
	echo "smoke $b: $(bash -c "$src HSA_ENABLE_SDMA=0 timeout 120 build/memcpy/memcpy_$b 1048576 5" 2>&1 | grep -E "^H2D:|Check|rror" | tr '\n' ' ')"
done
cd benchmarks
md5sum benchmark_wrapper.py
echo "=== 24_memcpy/gpuc4/memcpy.yaml $(date +%H:%M)"
timeout 3h python3 -u benchmark_wrapper.py 24_memcpy/gpuc4/memcpy.yaml | grep -E "phase|Done|Error|Traceback"
cd ..
echo "trace $(date +%H:%M)"
$D/trace.sh gpuc4 > /dev/null 2>&1
echo "MEMCPY-DONE $(date +%H:%M)"
