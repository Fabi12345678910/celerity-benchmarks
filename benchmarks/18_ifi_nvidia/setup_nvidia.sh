#!/bin/bash
# Builds an NVIDIA toolchain for the IFIgpu2070 nodes (RTX 2070, CUDA toolkits in /usr/local/cuda-*) next to the AMD one, without touching it:
#   install/llvm-cuda   LLVM 20.1.8 (clang, lld, openmp) with the X86 and NVPTX targets (our install/llvm only has AMDGPU)
#   install/acpp-cuda   AdaptiveCpp 25.10 with the CUDA backend
#   install/celerity-acpp-cuda-bench   Celerity 3dcopylib-bench (the commit checked out in src/celerity-bench) against it
#   build/bench-transfer-acpp-cuda-bench   benchmarks/transfer (strided_transfer, block_transfer)
# Runs as a Slurm job on an IFIgpu2070 node (needs the node's CUDA toolkit and a GPU for the final test), never on the head node. DPC++ is not
# built: the nightly we use has the HIP backend only. Usage: sbatch setup_nvidia.sbatch
set -euo pipefail

WORK="$HOME/finalizing-work"
LLVM_VERSION=20.1.8
ACPP_VERSION=v25.10.0
JOBS=32
CUDA=${CUDA:-$(ls -d /usr/local/cuda-12.* | sort -V | tail -1)}
LLVM="$WORK/install/llvm-cuda"
ACPP="$WORK/install/acpp-cuda"
CEL="$WORK/install/celerity-acpp-cuda-bench"
echo "cuda toolkit: $CUDA ($(ls "$CUDA/bin" | grep -c .) files in bin; nvcc: $(ls "$CUDA/bin/nvcc" 2>&1))"
cd "$WORK/src"

if [[ ! -x "$LLVM/bin/clang" ]]; then
	cmake -S "llvm-project-$LLVM_VERSION.src/llvm" -B "$WORK/build/llvm-cuda" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$LLVM" \
		-DLLVM_ENABLE_PROJECTS="clang;lld" -DLLVM_ENABLE_RUNTIMES=openmp -DLLVM_TARGETS_TO_BUILD="X86;NVPTX" -DLLVM_ENABLE_RTTI=ON \
		-DLLVM_BUILD_LLVM_DYLIB=ON -DLLVM_LINK_LLVM_DYLIB=ON -DCLANG_LINK_CLANG_DYLIB=ON -DLLVM_PARALLEL_LINK_JOBS=4 \
		-DLLVM_INCLUDE_TESTS=OFF -DLLVM_INCLUDE_BENCHMARKS=OFF -DLLVM_INCLUDE_EXAMPLES=OFF
	cmake --build "$WORK/build/llvm-cuda" -j "$JOBS"
	cmake --install "$WORK/build/llvm-cuda"
	ln -sf x86_64-unknown-linux-gnu/libomp.so "$LLVM/lib/libomp.so"
fi
echo "LLVM DONE $(date)"

if [[ ! -x "$ACPP/bin/acpp" ]]; then
	cmake -S AdaptiveCpp -B "$WORK/build/acpp-cuda" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$ACPP" \
		-DCMAKE_C_COMPILER="$LLVM/bin/clang" -DCMAKE_CXX_COMPILER="$LLVM/bin/clang++" \
		-DLLVM_DIR="$LLVM/lib/cmake/llvm" -DCLANG_EXECUTABLE_PATH="$LLVM/bin/clang++" \
		-DWITH_CUDA_BACKEND=ON -DCUDAToolkit_ROOT="$CUDA" -DCUDA_TOOLKIT_ROOT_DIR="$CUDA" -DWITH_ROCM_BACKEND=OFF -DWITH_OPENCL_BACKEND=OFF -DWITH_LEVEL_ZERO_BACKEND=OFF
	cmake --build "$WORK/build/acpp-cuda" -j "$JOBS"
	cmake --install "$WORK/build/acpp-cuda"
fi
"$ACPP/bin/acpp-info" -l || true
echo "ACPP DONE $(date)"

ARGS=(-DCELERITY_SYCL_IMPL=AdaptiveCpp -DACPP_TARGETS=generic -DCMAKE_C_COMPILER="$LLVM/bin/clang" -DCMAKE_CXX_COMPILER="$LLVM/bin/clang++" -DCELERITY_ENABLE_MPI=OFF)
SRC="$WORK/src/celerity-bench"
git -C "$SRC" log -1 --format="celerity source: %h %s"
build="$WORK/build/celerity-acpp-cuda-bench"
rm -rf "$build"/_deps/gpu3dcopylib-*
cmake --fresh -S "$SRC" -B "$build" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$CEL" -DCMAKE_PREFIX_PATH="$ACPP" -DCELERITY_ENABLE_COPYLIB=ON "${ARGS[@]}"
cmake --build "$build" -j "$JOBS" --target install
tb="$WORK/build/bench-transfer-acpp-cuda-bench"
cmake --fresh -S "$WORK/benchmarks/transfer" -B "$tb" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH="$CEL;$ACPP" "${ARGS[@]}"
cmake --build "$tb"
for run in "strided_transfer 4096 2" "block_transfer 1048576"; do
	echo "$run: $("$tb"/$run 2>&1 | grep -E "first access|device to host|Check" | tr "\n" " ")"
done
echo "SETUP DONE $(date)"
