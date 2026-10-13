#!/bin/sh
# runs the preload study on gpuc4
cd ~/finalizing-work/benchmarks
md5sum benchmark_wrapper.py
for f in 17_preload/gpuc4/preload.yaml; do
	echo "=== $f $(date +%H:%M)"
	timeout 3h python3 -u benchmark_wrapper.py $f | grep -E "phase|Done|Error|Traceback"
done
echo PRELOAD-DONE $(date +%H:%M)
