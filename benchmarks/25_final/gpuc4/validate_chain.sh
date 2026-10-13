#!/bin/sh
# runs every YAML of this system one after another (gpuc4); resumes after a crash by skipping finished CSVs
cd ~/finalizing-work/benchmarks
md5sum benchmark_wrapper.py
for f in 25_final/gpuc4/validate_strided_clean.yaml 25_final/gpuc4/validate_strided_bench.yaml 25_final/gpuc4/validate_block_clean.yaml 25_final/gpuc4/validate_block_bench.yaml 25_final/gpuc4/validate_both_clean.yaml 25_final/gpuc4/validate_both_bench.yaml 25_final/gpuc4/validate_rows_clean.yaml 25_final/gpuc4/validate_rows_bench.yaml 25_final/gpuc4/validate_device_clean.yaml 25_final/gpuc4/validate_device_bench.yaml; do
	csv=$(sed -n 's/^output_csv: //p' $f)
	[ -s "$csv" ] && continue
	echo "=== $f $(date +%H:%M)"
	timeout 3h python3 -u benchmark_wrapper.py $f | grep -E "phase|Done|Error|Traceback"
done
echo VALIDATE-DONE $(date +%H:%M)
