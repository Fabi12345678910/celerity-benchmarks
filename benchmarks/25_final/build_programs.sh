#!/bin/bash
# Builds the extra benchmark programs (strided_both_transfer, strided_rows_transfer, device_strided_transfer) for one implementation against the
# final installs, with the machine's own scripts/setup_transfer_final{,_bench}.sh (the per-machine setup scripts: same compilers and flags as
# strided_transfer), retargeted to each program's source folder and to build/bench-<program>-<impl>-<final|final2|final3|final-bench|...>.
# Usage: [GPU_ARCH=...] build_programs.sh <acpp|dpcpp0326> <final|final2|final3|final-bench|...>   (LUMI: inside scripts/env-lumi.sh)
set -euo pipefail
WORK="$HOME/finalizing-work"
impl=$1; variant=$2
setup=setup_transfer_${variant//-/_}.sh  # final, final2, final3, final-bench, ...: the machine's scripts/setup_transfer_<variant>.sh
[ -f "$WORK/scripts/$setup" ] || { echo "no scripts/$setup"; exit 1; }
for spec in "08_both_strided both_strided strided_both_transfer 4096 4" "10_rows rows strided_rows_transfer 4096 64 8" \
	"22_device_strided device_strided device_strided_transfer 4096 4"; do
	read -r dir name prog args <<< "$spec"
	tmp=$(mktemp)
	sed -e "s#\$WORK/benchmarks/transfer#\$WORK/benchmarks/$dir#" -e "s#bench-transfer-#bench-$name-#" \
		-e "s#for run in \"strided_transfer 4096 4\" \"block_transfer 1048576\"; do#for run in \"$prog $args\"; do#" "$WORK/scripts/$setup" > "$tmp"
	grep -q "benchmarks/$dir" "$tmp" && grep -q "bench-$name-" "$tmp" && grep -q "\"$prog $args\"" "$tmp" || { echo "$setup did not match for $prog"; exit 1; }
	bash "$tmp" "$impl"
	rm -f "$tmp"
done
