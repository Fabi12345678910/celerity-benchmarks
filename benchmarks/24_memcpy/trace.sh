#!/bin/bash
# Traces every memcpy program with rocprofv3 (HIP API, HSA core + AMD API, kernel dispatches, memory copies, allocations) at 4 B
# host pinned / pageable, SDMA off / on, 5 copies per direction: which runtime calls and which copy engine (SDMA copy vs blit kernel)
# each library ends in. Usage on the machine, from ~/finalizing-work: benchmarks/24_memcpy/trace.sh <system>   (LUMI: inside a job)
# Output: benchmarks/24_memcpy/<system>/trace/<app>_<bytes>_<host>_sdma<0|1>/ (CSV per trace kind) and trace.log
set -u
cd "$HOME/finalizing-work"
system=$1
out=benchmarks/24_memcpy/$system/trace
mkdir -p "$out"
pre=""; [[ $system == lumi ]] && pre="ROCR_VISIBLE_DEVICES=4"
DPCPP=". $HOME/finalizing-work/install/dpcpp-nightly-2026-03-26/env.sh &&"
PROF="rocprofv3 --hip-runtime-trace --hsa-core-trace --hsa-amd-trace --kernel-trace --memory-copy-trace --memory-allocation-trace --output-format csv"
for sdma in 0 1; do
	for bytes in 4; do
		for app in hip opencl acpp dpcpp celerity_acpp celerity_dpcpp0326; do
			hosts="pinned pageable"; [[ $app == celerity* ]] && hosts=celerity
			for host in $hosts; do
				name=${app}_${bytes}_${host}_sdma$sdma
				src=""; [[ $app == *dpcpp* ]] && src=$DPCPP
				arg=$host; [[ $host == celerity ]] && arg=""
				echo "=== $name $(date +%H:%M:%S)"
				bash -c "$src env $pre HSA_ENABLE_SDMA=$sdma $PROF -d $out/$name -o trace -- build/memcpy/memcpy_$app $bytes 5 $arg" 2>&1 | grep -E "^(H2D|D2H|Check)|rror"
			done
		done
	done
done 2>&1 | tee "$out/trace.log"
echo TRACE-DONE
