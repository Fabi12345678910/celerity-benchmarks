#!/bin/sh
# runs every YAML of this system one after another (gpuc4); resumes after a crash by skipping finished CSVs
cd ~/finalizing-work/benchmarks
md5sum benchmark_wrapper.py
for f in 15_sweep3/gpuc4/strided_stg_anchor_pr1.yaml 15_sweep3/gpuc4/strided_hk_anchor_pr1.yaml 15_sweep3/gpuc4/block_stg_anchor_pr1.yaml 15_sweep3/gpuc4/block_hk_anchor_pr1.yaml 15_sweep3/gpuc4/strided_stg_anchor_pr2.yaml 15_sweep3/gpuc4/strided_hk_anchor_pr2.yaml 15_sweep3/gpuc4/block_stg_anchor_pr2.yaml 15_sweep3/gpuc4/block_hk_anchor_pr2.yaml 15_sweep3/gpuc4/strided_stg_anchor_pr3.yaml 15_sweep3/gpuc4/strided_hk_anchor_pr3.yaml 15_sweep3/gpuc4/block_stg_anchor_pr3.yaml 15_sweep3/gpuc4/block_hk_anchor_pr3.yaml 15_sweep3/gpuc4/strided_stg_anchor_pr4.yaml 15_sweep3/gpuc4/strided_hk_anchor_pr4.yaml 15_sweep3/gpuc4/block_stg_anchor_pr4.yaml 15_sweep3/gpuc4/block_hk_anchor_pr4.yaml; do
	csv=$(sed -n 's/^output_csv: //p' $f)
	[ -s "$csv" ] && continue
	echo "=== $f $(date +%H:%M)"
	timeout 3h python3 -u benchmark_wrapper.py $f | grep -E "phase|Done|Error|Traceback"
done
echo ANCHORS-DONE $(date +%H:%M)
