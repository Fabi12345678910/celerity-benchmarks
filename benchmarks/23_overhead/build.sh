#!/usr/bin/env bash
# Builds the overhead benchmark programs on one machine (layout ~/finalizing-work, like scripts/setup_transfer.sh).
# Usage: [GPU_ARCH=gfx1200] [ROCM_DIR=/opt/rocm-7.1.0] build.sh <target> [more]   targets: acpp dpcpp hip opencl celerity-acpp celerity-dpcpp0326 all
# Output: ~/finalizing-work/build/overhead/overhead_<target>
# Celerity is linked against install/celerity-<impl>-bench (3dcopylib-bench); with and without copylib are the SAME binary, switched by CELERITY_COPYLIB=off.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
WORK="${FW_ROOT:-$HOME/finalizing-work}"
I="$WORK/install"
ROCM_DIR="${ROCM_DIR:-/opt/rocm-7.1.0}"
GPU_ARCH="${GPU_ARCH:-gfx1200}"
DPCPP_ENV="${DPCPP_ENV:-$I/dpcpp-nightly-2026-03-26/env.sh}"
out="$WORK/build/overhead"
mkdir -p "$out"
common="-I$here/common -std=c++20 -O2"

build_acpp() { "$I/acpp/bin/acpp" $common --acpp-targets=generic -DBENCH_IMPL='"sycl-acpp"' "$here/sycl/overhead_sycl.cpp" -o "$out/overhead_acpp"; }
build_dpcpp() {
	# shellcheck disable=SC1090
	source "$DPCPP_ENV"
	clang++ $common -fsycl -fsycl-targets=amdgcn-amd-amdhsa -Xsycl-target-backend --offload-arch="$GPU_ARCH" --rocm-path="$ROCM_DIR" -DBENCH_IMPL='"sycl-dpcpp"' \
		"$here/sycl/overhead_sycl.cpp" -o "$out/overhead_dpcpp"
}
build_hip() { "${HIPCC:-hipcc}" $common ${HIPCC_FLAGS:-} --offload-arch="$GPU_ARCH" "$here/hip/overhead_hip.cpp" -o "$out/overhead_hip"; }
build_opencl() { ${CXX:-g++} $common "$here/opencl/overhead_opencl.cpp" -o "$out/overhead_opencl" -lOpenCL ${OPENCL_INCLUDE:+-I$OPENCL_INCLUDE} ${OPENCL_LIBDIR:+-L$OPENCL_LIBDIR}; }
build_celerity() { # $1 = acpp | dpcpp0326
	local impl="$1" bdir="$out/cmake-celerity-$1" args sycl_prefix=""
	if [ "$impl" = acpp ]; then
		args=(-DCELERITY_SYCL_IMPL=AdaptiveCpp -DACPP_TARGETS=generic -DCMAKE_C_COMPILER="$I/llvm/bin/clang" -DCMAKE_CXX_COMPILER="$I/llvm/bin/clang++")
		sycl_prefix="$I/acpp"
	else
		# shellcheck disable=SC1090
		source "$DPCPP_ENV"
		args=(-DCELERITY_SYCL_IMPL=DPC++ -DCELERITY_DPCPP_TARGETS=amdgcn-amd-amdhsa -DCMAKE_C_COMPILER="$DPCPP_ROOT/bin/clang" -DCMAKE_CXX_COMPILER="$DPCPP_ROOT/bin/clang++"
			"-DDPCPP_FLAGS=-Xsycl-target-backend=amdgcn-amd-amdhsa;--offload-arch=$GPU_ARCH;--rocm-path=$ROCM_DIR")
	fi
	cmake --fresh -S "$here/celerity" -B "$bdir" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH="$I/celerity-$impl-bench;$sycl_prefix" \
		-DBENCH_IMPL="celerity-$impl" -DCELERITY_ENABLE_MPI=OFF "${args[@]}"
	cmake --build "$bdir"
	cp "$bdir/overhead_celerity" "$out/overhead_celerity_$impl"
}

targets=("$@")
[ ${#targets[@]} -eq 0 ] && { sed -n 2,5p "$0"; exit 2; }
[ "${targets[0]}" = all ] && targets=(acpp dpcpp hip opencl celerity-acpp celerity-dpcpp0326)
for t in "${targets[@]}"; do
	echo "== building $t"
	case "$t" in
	acpp) build_acpp ;; dpcpp) build_dpcpp ;; hip) build_hip ;; opencl) build_opencl ;;
	celerity-acpp) build_celerity acpp ;; celerity-dpcpp0326) build_celerity dpcpp0326 ;;
	*) echo "unknown target $t"; exit 2 ;;
	esac
done
