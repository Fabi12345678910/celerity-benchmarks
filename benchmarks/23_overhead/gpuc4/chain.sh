#!/bin/sh
# runs the overhead study on gpuc4
cd ~/finalizing-work/benchmarks
md5sum benchmark_wrapper.py
for f in 23_overhead/gpuc4/overhead_plain.yaml 23_overhead/gpuc4/overhead_celerity.yaml 23_overhead/gpuc4/overhead_celerity_strided.yaml 23_overhead/gpuc4/overhead_celerity_native.yaml; do
	csv=$(sed -n 's/^output_csv: //p' $f)
	[ -s "$csv" ] && continue
	echo "=== $f $(date +%H:%M)"
	timeout 3h python3 -u benchmark_wrapper.py $f | grep -E "phase|Done|Error|Traceback"
done
echo OVERHEAD-DONE $(date +%H:%M)
