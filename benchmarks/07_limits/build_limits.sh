#!/bin/bash
# Builds membw and linkbw in this directory. Usage: build_limits.sh <gpu arch> (gpuc4 gfx1200, ifi gfx1151, LUMI gfx90a)
# hipcc: $ROCM_DIR/bin/hipcc (LUMI: from scripts/env-lumi.sh), otherwise /opt/rocm-7.1.0/bin/hipcc; extra flags in HIPCC_FLAGS.
set -e
cd "$(dirname "$0")"
"${CXX:-g++}" -O3 -std=c++20 -pthread membw.cpp -o membw
"${ROCM_DIR:-/opt/rocm-7.1.0}/bin/hipcc" -O3 $HIPCC_FLAGS --offload-arch="$1" linkbw.hip -o linkbw 2>&1 | grep -v "warning:" || true
[ -x linkbw ] && [ -x membw ] && echo "built membw and linkbw for $1"
