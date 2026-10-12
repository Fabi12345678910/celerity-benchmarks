#!/bin/bash
# Builds check_deployed against a gpu3dcopylib source tree (default: the acpp bench build's copy on the machines) and runs it.
# The deployed host copy (copy_rows_fixed .. copy_host_to_host in src/backend.cpp's anonymous namespace) is extracted into
# deployed_body.inc, so the check always tests the source as built. Runs on any x86-64 host with g++ >= 11 (C++20), no GPU needed.
# Usage: build.sh [copylib source dir] [cases]   (also builds an ASan/UBSan variant and runs it on 50k cases)
set -euo pipefail
cd "$(dirname "$0")"
SRC="${1:-$HOME/finalizing-work/build/celerity-acpp-bench/_deps/gpu3dcopylib-src}"
awk '/template <int64_t W, bool Pack>/ && !s {s = 1} s {print} s && /^\tvoid copy_host_to_host/ {f = 1} f && /^\t}$/ {exit}' \
	"$SRC/src/backend.cpp" > deployed_body.inc
grep -q "copy_host_to_host" deployed_body.inc || { echo "could not extract copy_host_to_host from $SRC/src/backend.cpp"; exit 1; }
mkdir -p include/copylib
cp "$SRC/include/copylib/core.hpp" include/copylib/core.hpp
cp ../host_copy.hpp include/copylib/host_copy.hpp
"${CXX:-g++}" -std=c++20 -O2 -Iinclude -I. check_deployed.cpp -o check_deployed
"${CXX:-g++}" -std=c++20 -O1 -g -fsanitize=address,undefined -Iinclude -I. check_deployed.cpp -o check_deployed_san
./check_deployed "${2:-200000}"
./check_deployed_san 50000
