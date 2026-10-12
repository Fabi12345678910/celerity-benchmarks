#!/bin/sh
# runs every YAML of this system one after another (gpuc4); resumes after a crash by skipping finished CSVs
cd ~/finalizing-work/benchmarks
md5sum benchmark_wrapper.py
for f in 25_final/gpuc4/validate2_strided_clean2.yaml 25_final/gpuc4/validate2_strided_bench.yaml 25_final/gpuc4/validate2_block_clean2.yaml 25_final/gpuc4/validate2_block_bench.yaml 25_final/gpuc4/validate2_both_clean2.yaml 25_final/gpuc4/validate2_both_bench.yaml 25_final/gpuc4/validate2_rows_clean2.yaml 25_final/gpuc4/validate2_rows_bench.yaml 25_final/gpuc4/validate2_device_clean2.yaml 25_final/gpuc4/validate2_device_bench.yaml; do
	csv=$(sed -n 's/^output_csv: //p' $f)
	[ -s "$csv" ] && continue
	echo "=== $f $(date +%H:%M)"
	timeout 3h python3 -u benchmark_wrapper.py $f | grep -E "phase|Done|Error|Traceback"
done
echo VALIDATE-DONE $(date +%H:%M)
