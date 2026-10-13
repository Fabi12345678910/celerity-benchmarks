#!/bin/sh
# runs the device-strided study on gpuc4
cd ~/finalizing-work/benchmarks
md5sum benchmark_wrapper.py
for f in 22_device_strided/gpuc4/device_stg_base.yaml 22_device_strided/gpuc4/device_hk_base.yaml 22_device_strided/gpuc4/device_native_1.yaml 22_device_strided/gpuc4/device_native_2.yaml; do
	csv=$(sed -n 's/^output_csv: //p' $f)
	[ -s "$csv" ] && continue
	echo "=== $f $(date +%H:%M)"
	timeout 3h python3 -u benchmark_wrapper.py $f | grep -E "phase|Done|Error|Traceback"
done
echo DEVICE-DONE $(date +%H:%M)
