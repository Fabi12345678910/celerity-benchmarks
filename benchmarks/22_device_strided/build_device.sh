#!/bin/bash
# Builds device_strided_transfer for one implementation with the machine's own scripts/setup_transfer.sh (same compilers and flags as
# strided_transfer), retargeted to benchmarks/22_device_strided and build/bench-device_strided-<impl>-bench.
# Usage: [GPU_ARCH=...] build_device.sh <acpp|dpcpp0326>   (LUMI: inside scripts/env-lumi.sh)
set -euo pipefail
WORK="$HOME/finalizing-work"
tmp=$(mktemp)
sed -e 's#$WORK/benchmarks/transfer#$WORK/benchmarks/22_device_strided#' -e 's#bench-transfer-#bench-device_strided-#' \
	-e 's#for run in "strided_transfer 4096 4" "block_transfer 1048576"; do#for run in "device_strided_transfer 4096 4"; do#' \
	"$WORK/scripts/setup_transfer.sh" > "$tmp"
grep -q device_strided "$tmp" && grep -q '"device_strided_transfer 4096 4"' "$tmp" || { echo "setup_transfer.sh did not match"; exit 1; }
bash "$tmp" "$1"
rm -f "$tmp"
