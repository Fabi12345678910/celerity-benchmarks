#!/bin/bash
# Queues the device-strided study behind sweep 4. Usage on the machine, from ~/finalizing-work:
#   gpuc4:      benchmarks/22_device_strided/queue.sh gpuc4     (background process: waits for SWEEP4-DONE in logs/sweep4_gpuc4.log, builds, runs)
#   ifi, LUMI:  benchmarks/22_device_strided/queue.sh <ifi|lumi>  (sbatch only: the build + staged/host-kernel job depends on every sweep 4 job, the native job on that one)
set -euo pipefail
cd "$HOME/finalizing-work"
system=$1
D=benchmarks/22_device_strided
if [[ $system == gpuc4 ]]; then
	until grep -q SWEEP4-DONE logs/sweep4_gpuc4.log 2>/dev/null; do sleep 60; done
	for impl in acpp dpcpp0326; do $D/build_device.sh $impl > logs/build_device-$impl.log 2>&1 || { echo "build $impl failed"; exit 1; }; done
	cd benchmarks && sh 22_device_strided/gpuc4/chain.sh
	exit
fi
dep=$(grep -oE -- "-> [0-9]+" "logs/sweep4_${system}_jobs.txt" | awk '{print $2}' | paste -sd:)
script=$D/job_$system.sbatch
j1=$(sbatch --parsable --dependency=afterany:$dep $script build $(sed -n 1p "$D/$system/jobs.txt"))
echo "device-strided job 1 (build + staging + host kernel) -> $j1 after $(echo $dep | tr ':' '\n' | wc -l) sweep 4 jobs" | tee -a "logs/device_strided_${system}_jobs.txt"
j2=$(sbatch --parsable --dependency=afterany:$j1 $script run $(sed -n 2p "$D/$system/jobs.txt"))
echo "device-strided job 2 (native) -> $j2 after $j1" | tee -a "logs/device_strided_${system}_jobs.txt"
