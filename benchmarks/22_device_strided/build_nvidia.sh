#!/bin/bash
# Builds device_strided_transfer against the NVIDIA toolchain of 18_ifi_nvidia (AdaptiveCpp CUDA) into build/bench-device_strided-acpp-cuda-bench and runs
# small sizes. Runs inside an IFIgpu2070 job.
set -euo pipefail
WORK="$HOME/finalizing-work"
LLVM="$WORK/install/llvm-cuda"; ACPP="$WORK/install/acpp-cuda"; CEL="$WORK/install/celerity-acpp-cuda-bench"
tb="$WORK/build/bench-device_strided-acpp-cuda-bench"
cmake --fresh -S "$WORK/benchmarks/22_device_strided" -B "$tb" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH="$CEL;$ACPP" \
	-DCELERITY_SYCL_IMPL=AdaptiveCpp -DACPP_TARGETS=generic -DCMAKE_C_COMPILER="$LLVM/bin/clang" -DCMAKE_CXX_COMPILER="$LLVM/bin/clang++" -DCELERITY_ENABLE_MPI=OFF
cmake --build "$tb"
for run in "4096 1" "4096 4" "1048576 4" "16777216 4"; do
	echo "device_strided_transfer $run: $("$tb"/device_strided_transfer $run 2>&1 | grep -E "first access|device to host|Check|rror" | tr "\n" " ")"
done
for run in "1048576 4"; do
	echo "copylib off: $(CELERITY_COPYLIB=off "$tb"/device_strided_transfer $run 2>&1 | grep -E "first access|device to host|Check|rror" | tr "\n" " ")"
	echo "host kernel: $(COPYLIB_HOST_KERNEL=1 "$tb"/device_strided_transfer $run 2>&1 | grep -E "first access|device to host|Check|rror" | tr "\n" " ")"
done
echo "BUILD DONE"
