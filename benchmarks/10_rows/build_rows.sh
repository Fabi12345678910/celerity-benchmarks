#!/bin/bash
# Builds strided_rows_transfer for one implementation with the machine's own scripts/setup_transfer.sh (same compilers and flags as
# strided_transfer), retargeted to benchmarks/rows and build/bench-rows-<impl>-bench.
# Usage: [GPU_ARCH=...] build_rows.sh <acpp|dpcpp0326>   (LUMI: inside scripts/env-lumi.sh)
set -euo pipefail
WORK="$HOME/finalizing-work"
tmp=$(mktemp)
sed -e 's#$WORK/benchmarks/transfer#$WORK/benchmarks/rows#' -e 's#bench-transfer-#bench-rows-#' \
	-e 's#for run in "strided_transfer 4096 4" "block_transfer 1048576"; do#for run in "strided_rows_transfer 4096 64 8"; do#' \
	"$WORK/scripts/setup_transfer.sh" > "$tmp"
grep -q rows "$tmp" && grep -q '"strided_rows_transfer 4096 64 8"' "$tmp" || { echo "setup_transfer.sh did not match"; exit 1; }
bash "$tmp" "$1"
rm -f "$tmp"
