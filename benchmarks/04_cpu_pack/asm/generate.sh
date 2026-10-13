#!/bin/bash
# Regenerates the assembly listings and memcpy traces in this directory (run on gpuc4: clang 20.1.8 and gdb are installed there):
#   copy_loops.s            clang -O3 -std=c++20 -S, the flags cpu_pack was built with (no -march: x86-64 baseline, SSE2)
#   copy_loops.x86-64-v3.s  the same with -march=x86-64-v3 (AVX2)
#   trace_n<n>.txt          every instruction one glibc memcpy of n bytes executes (gdb single-step)
#   instructions_per_row.txt  instructions each variant of copy_loops.cpp executes per 4-byte row, memcpy included (gdb
#                           single-step of 256 and 512 rows; the difference / 256 leaves out the per-call cost)
# Usage: [CXX=<clang++>] [COPYLIB_INCLUDE=<gpu3dcopylib include dir>] ./generate.sh
set -e
cd "$(dirname "$0")"
CXX=${CXX:-$HOME/finalizing-work/install/llvm/bin/clang++}
COPYLIB_INCLUDE=${COPYLIB_INCLUDE:-$HOME/finalizing-work/build/celerity-acpp-bench/_deps/gpu3dcopylib-src/include}
FLAGS="-O3 -std=c++20 -I$COPYLIB_INCLUDE -S -masm=intel -fno-asynchronous-unwind-tables"

$CXX $FLAGS copy_loops.cpp -o copy_loops.s
$CXX $FLAGS -march=x86-64-v3 copy_loops.cpp -o copy_loops.x86-64-v3.s

$CXX -O3 -std=c++20 -I$COPYLIB_INCLUDE -Wl,-z,now copy_loops.cpp trace_rows.cpp -o trace_rows
count() { gdb -q -batch -x trace_rows.gdb --args ./trace_rows $1 $2 2>&1 | sed -n 's/^instructions executed: //p'; }
{
	echo "# instructions per 4-byte row (pack, pitch 8 bytes), $(lscpu | sed -n 's/^Model name: *//p'), $(ldd --version | head -1)"
	for v in copylib rows_runtime rows_fixed4 pack_var pack_fixed4; do
		a=$(count $v 256)
		b=$(count $v 512)
		echo "$v: 256 rows $a, 512 rows $b, per row $(echo "scale=2; ($b - $a) / 256" | bc)"
	done
} > instructions_per_row.txt
rm trace_rows

$CXX -O3 -std=c++20 -Wl,-z,now trace_memcpy.cpp -o trace_memcpy
for n in 4 8 12 16 64; do
	{
		echo "# memcpy($n bytes), $(lscpu | sed -n 's/^Model name: *//p'), $(ldd --version | head -1)"
		gdb -q -batch -x trace_memcpy.gdb --args ./trace_memcpy $n 2>&1 | grep -E "^=>|instructions executed" | sed 's/^=> //'
	} > trace_n$n.txt
done
rm trace_memcpy
