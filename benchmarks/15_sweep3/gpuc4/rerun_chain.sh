#!/bin/sh
# runs the base reruns one after another (gpuc4)
cd ~/finalizing-work/benchmarks
md5sum benchmark_wrapper.py
for f in 15_sweep3/gpuc4/strided_stg_rerun_r1.yaml 15_sweep3/gpuc4/strided_hk_rerun_r1.yaml 15_sweep3/gpuc4/block_stg_rerun_r1.yaml 15_sweep3/gpuc4/block_hk_rerun_r1.yaml 15_sweep3/gpuc4/strided_stg_rerun_r2.yaml 15_sweep3/gpuc4/strided_hk_rerun_r2.yaml 15_sweep3/gpuc4/block_stg_rerun_r2.yaml 15_sweep3/gpuc4/block_hk_rerun_r2.yaml 15_sweep3/gpuc4/strided_stg_rerun_r3.yaml 15_sweep3/gpuc4/strided_hk_rerun_r3.yaml 15_sweep3/gpuc4/block_stg_rerun_r3.yaml 15_sweep3/gpuc4/block_hk_rerun_r3.yaml; do
	csv=$(sed -n 's/^output_csv: //p' $f)
	[ -s "$csv" ] && continue
	echo "=== $f $(date +%H:%M)"
	timeout 3h python3 -u benchmark_wrapper.py $f | grep -E "phase|Done|Error|Traceback"
done
echo RERUN-DONE $(date +%H:%M)
