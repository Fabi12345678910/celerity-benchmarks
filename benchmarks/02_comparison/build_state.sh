#!/bin/bash
# Builds one older Celerity code state (a commit of the 3dcopylib-bench branch) next to the current build, without touching src/celerity-bench,
# build/celerity-<impl>-bench or install/celerity-<impl>-bench: a detached worktree src/celerity-bench-<commit>, build/celerity-<impl>-<commit>,
# install/celerity-<impl>-<commit>, and the transfer benchmarks (benchmarks/transfer) against it in build/bench-transfer-<impl>-<commit>.
# Same compilers and flags as setup_celerity_bench.sh / setup_transfer.sh; no unit tests. Used for the "after fastpath" line of the lines charts.
# Usage: [GPU_ARCH=gfx1151] build_state.sh <acpp|dpcpp0326> <commit>   (run on a compute node on ifi and LUMI, never on the login node)
set -euo pipefail

WORK="$HOME/finalizing-work"
SRC0="$WORK/src/celerity-bench"
I="$WORK/install"
ROCM_DIR=/opt/rocm-7.1.0
JOBS="${JOBS:-16}"
GPU_ARCH="${GPU_ARCH:-gfx1200}"
NAME=$1
COMMIT=$2
SRC="$WORK/src/celerity-bench-$COMMIT"

case "$NAME" in
acpp)
	ARGS=(-DCELERITY_SYCL_IMPL=AdaptiveCpp -DACPP_TARGETS=generic -DCMAKE_C_COMPILER="$I/llvm/bin/clang" -DCMAKE_CXX_COMPILER="$I/llvm/bin/clang++")
	SYCL_PREFIX="$I/acpp"
	;;
dpcpp0326)
	source "$I/dpcpp-nightly-2026-03-26/env.sh"
	ARGS=(-DCELERITY_SYCL_IMPL=DPC++ -DCELERITY_DPCPP_TARGETS=amdgcn-amd-amdhsa -DCMAKE_C_COMPILER="$DPCPP_ROOT/bin/clang"
		-DCMAKE_CXX_COMPILER="$DPCPP_ROOT/bin/clang++" "-DDPCPP_FLAGS=-Xsycl-target-backend=amdgcn-amd-amdhsa;--offload-arch=$GPU_ARCH;--rocm-path=$ROCM_DIR")
	SYCL_PREFIX=""
	;;
*) echo "usage: [GPU_ARCH=...] $0 <acpp|dpcpp0326> <commit>" >&2; exit 1 ;;
esac
ARGS+=(-DCELERITY_ENABLE_MPI=OFF)

if [[ ! -d "$SRC" ]]; then
	git -C "$SRC0" worktree add --detach "$SRC" "$COMMIT"
	# the vendored submodules of the worktree are the checked-out ones of src/celerity-bench, which must be at the same pins
	for m in $(git -C "$SRC0" submodule status | awk '{print $2}'); do
		[[ "$(git -C "$SRC0" ls-tree "$COMMIT" "$m" | awk '{print $3}')" == "$(git -C "$SRC0" ls-tree HEAD "$m" | awk '{print $3}')" ]] || { echo "submodule $m differs"; exit 1; }
		rmdir "$SRC/$m" 2>/dev/null || true
		cp -a "$SRC0/$m" "$SRC/$m"
	done
fi
git -C "$SRC" log -1 --format="source: %h %s"

build="$WORK/build/celerity-$NAME-$COMMIT"
cmake --fresh -S "$SRC" -B "$build" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$I/celerity-$NAME-$COMMIT" -DCMAKE_PREFIX_PATH="$SYCL_PREFIX" \
	-DCELERITY_ENABLE_COPYLIB=ON "${ARGS[@]}"
cmake --build "$build" -j "$JOBS" --target install

tb="$WORK/build/bench-transfer-$NAME-$COMMIT"
cmake --fresh -S "$WORK/benchmarks/transfer" -B "$tb" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH="$I/celerity-$NAME-$COMMIT;$SYCL_PREFIX" "${ARGS[@]}"
cmake --build "$tb"
echo "strided_transfer 4096 2: $("$tb"/strided_transfer 4096 2 2>&1 | grep -E "first access|Check" | tr "\n" " ")"
echo "BUILD DONE $NAME $COMMIT"
