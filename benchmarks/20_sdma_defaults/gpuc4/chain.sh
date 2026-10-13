#!/bin/sh
# runs the SDMA study on gpuc4
cd ~/finalizing-work/benchmarks
md5sum benchmark_wrapper.py
for f in 20_sdma_defaults/gpuc4/strided_stg_sdma.yaml 20_sdma_defaults/gpuc4/strided_hk_sdma.yaml; do
	echo "=== $f $(date +%H:%M)"
	timeout 3h python3 -u benchmark_wrapper.py $f | grep -E "phase|Done|Error|Traceback"
done
echo SDMA-DONE $(date +%H:%M)
