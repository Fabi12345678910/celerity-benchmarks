# The staging pack loop in machine code: fixed vs. run-time row width

copylib's staged copies pack the strided host side into a contiguous staging buffer before the DMA copy (host → device), and
unpack it afterwards (device → host). `cpu_pack` (one directory up) isolates this CPU step and measured that the loop itself,
not memory, limits copylib's staging. This directory shows why, instruction by instruction, for three ways of writing that loop:

| Variant | Code | What a row costs |
|---|---|---|
| **copylib today** | `for_each_copy_run` + `memcpy` (gpu3dcopylib `execute_copy`) | position computed from scratch with divisions, then a `memcpy` call |
| **run-time width** | plain row loop, `memcpy(dst, src, width)` | a `memcpy` call with a length the compiler doesn't know |
| **fixed width** | the same loop, `memcpy(dst, src, W)` with `W` a template parameter | one load and one store |

The fixed-width loop is what the proposed copylib change (`../host_copy.hpp`, `copy_full_rows<W, Pack>`) uses for row widths of
1, 2, 4, 8, 12, 16, 24, 32 and 64 bytes. Its default branch, for every other width, is the run-time-width loop.

## Results

Packing 4-byte rows (the column of `strided_transfer`):

| Variant | Instructions per row | Divisions per row | Calls per row | ns per row (ifi, M=2) | GB/s (ifi, M=2, 1 / 2 / 4 workers) |
|---|---|---|---|---|---|
| copylib today | **156** | 8 | 1 | 11.91 | 0.34 / 0.67 / 1.31 |
| run-time width | **22.5** | 0 | 1 | 1.18 | 3.40 / 5.83 / 11.56 |
| fixed width | **3.25** | 0 | 0 | 0.27 | 14.63 / 22.44 / 30.27 |

- **Instructions per row** were counted by executing the code under gdb (`instructions_per_row.txt`), `memcpy` included.
- **ns and GB/s per row** come from `cpu_pack` on ifi (`../results/cpu_pack_ifi.csv`): N = 2^28 rows (1 GiB), pack direction,
  median of 3 runs. GB/s counts the useful 4 bytes per row.
- **copylib today** spends 140 of its 156 instructions per row in the loop around the copy: position arithmetic, reloads of
  layout fields, stack spills and run merging. The 8 integer divisions dominate the time: the next row's position depends on two of them, so the core can't overlap rows. 11.9 ns per row is the same for M = 2, 3
  and 4, so the loop is limited by its own computation, not by memory.
- **Run-time width** removes the divisions. What's left is a library call per row, of which 16 instructions are spent inside
  glibc to find the size class and copy 4 bytes. It's also limited by computation: 1.18 ns per row for every M.
- **Fixed width** compiles `memcpy` into one 4-byte load and one 4-byte store, plus a share of the loop counter. It's limited by
  memory: per-row time rises with M (0.27 / 0.33 / 0.46 ns for M = 2 / 3 / 4), because each row pulls in M× the useful bytes.

## How the listings were made

- **Compiler:** clang 20.1.8, the LLVM the benchmark builds use (`install/llvm`). Flags `-O3 -std=c++20`, the same as `cpu_pack`
  on ifi. Without `-march` this targets the x86-64 baseline (SSE2). The `x86-64-v3` (AVX2) listing is for comparison.
  `-fno-asynchronous-unwind-tables` only removes `.cfi` directives from the listing and doesn't change the code.
- **Execution traces** were recorded on gpuc4 (Intel Core i9-12900, AVX2, glibc 2.39). glibc picks its `memcpy`
  implementation at load time from the CPU's features. A CPU with AVX-512 may get a different variant than
  `__memcpy_avx_unaligned_erms`; that wasn't traced.
- **Regenerating:** `./generate.sh` on gpuc4 recreates every `.s` and `.txt` file here. It needs clang and the gpu3dcopylib
  headers; their paths can be overridden with `CXX` and `COPYLIB_INCLUDE`. Two runs produced byte-identical files.

| File | Content |
|---|---|
| [copy_loops.cpp](copy_loops.cpp) | the loops: `copy_copylib`, `rows_runtime`, `rows_fixed4` (exactly as in `cpu_pack.cpp`) and `pack_var`, `pack_fixed<4/8/12/16/64>` (as in `host_copy.hpp`) |
| [copy_loops.s](copy_loops.s) | generated assembly, x86-64 baseline (what `cpu_pack` ran) |
| [copy_loops.x86-64-v3.s](copy_loops.x86-64-v3.s) | generated assembly with `-march=x86-64-v3` (AVX2) |
| [trace_memcpy.cpp](trace_memcpy.cpp), [trace_memcpy.gdb](trace_memcpy.gdb) | single-steps one `memcpy` of n bytes |
| `trace_n4.txt`, `trace_n8.txt`, `trace_n12.txt`, `trace_n16.txt`, `trace_n64.txt` | every instruction that `memcpy` executed for n = 4, 8, 12, 16, 64 |
| [trace_rows.cpp](trace_rows.cpp), [trace_rows.gdb](trace_rows.gdb) | runs each variant on 256 and 512 rows and counts the executed instructions |
| [instructions_per_row.txt](instructions_per_row.txt) | the counts: (count at 512 rows − count at 256 rows) / 256, so the per-call cost drops out |
| [generate.sh](generate.sh) | builds and runs everything above |

Functions in `copy_loops.s`:
- `copy_copylib`: [line 7](copy_loops.s#L7)
- `rows_runtime`: [line 294](copy_loops.s#L294)
- `rows_fixed4`: [line 379](copy_loops.s#L379)
- `pack_var`: [line 452](copy_loops.s#L452)
- `pack_fixed4` / `8` / `12` / `16` / `64`: lines [533](copy_loops.s#L533), [595](copy_loops.s#L595), [657](copy_loops.s#L657),
  [719](copy_loops.s#L719), [770](copy_loops.s#L770)

The names in the `.s` files are mangled, e.g. `_Z11pack_fixed4PSt4bytePKS_ll`. `c++filt` turns them back into C++ names. The
excerpts below are taken unchanged from `copy_loops.s`; only the comments after `#` were added.

## 1. Run-time width: one call into glibc per row

```cpp
void pack_var(std::byte* c, const std::byte* s, int64_t rows, int64_t pitch, int64_t w) {
	for(int64_t r = 0; r < rows; ++r) { std::memcpy(c, s, static_cast<size_t>(w)); s += pitch; c += w; }
}
```

The compiler can't know `w`, so `memcpy` stays a library call. clang unrolls the loop 4×, but every row is still a full call:

```asm
.LBB3_3:                                # =>This Inner Loop Header: Depth=1
	mov	rdi, r12                        # argument 1: destination
	mov	rsi, r15                        # argument 2: source
	mov	rdx, rbx                        # argument 3: length (w, only known at run time)
	call	memcpy@PLT
	add	r15, r14                        # s += pitch
	add	r12, rbx                        # c += w
	mov	rdi, r12                        # row 2
	...                                     # rows 2 to 4: the same 6 instructions
	add	r13, -4                         # 4 rows done
	jne	.LBB3_3
```

- **Saved registers:** `memcpy` may overwrite the caller-saved registers, so the loop keeps its state in callee-saved registers.
  That costs 6 pushes and pops around the loop (`push rbp … push rbx`), once per call of `pack_var`, not per row.
- **The `cpu_pack` version** (`rows_runtime`, [line 294](copy_loops.s#L294)) indexes with `r * stride` instead of advancing
  pointers. It's unrolled 2× and costs the same per row: 13 instructions per 2 rows in the loop.

Inside the library, the call goes through the PLT to the `memcpy` implementation glibc picked at load time. This is
`trace_n4.txt`, every instruction one 4-byte copy executes. Addresses are shortened and comments added. The first line is
`trace_memcpy`'s own tail call and isn't counted below.

```asm
<copy_one(void*, void const*, unsigned long)>:	jmp    <memcpy@plt>
<memcpy@plt>:	jmp    QWORD PTR [rip+0x2f92]        # indirect jump through the GOT
<__memcpy_avx_unaligned_erms>:	endbr64                    # indirect-branch target marker (CET)
<__memcpy_avx_unaligned_erms+4>:	mov    rax,rdi             # return value = destination
<__memcpy_avx_unaligned_erms+7>:	cmp    rdx,0x20            # size < 32?
<__memcpy_avx_unaligned_erms+11>:	jb     <+48>
<__memcpy_avx_unaligned_erms+48>:	cmp    edx,0x10            # size >= 16?
<__memcpy_avx_unaligned_erms+51>:	jae    <+98>
<__memcpy_avx_unaligned_erms+53>:	cmp    edx,0x8             # size >= 8?
<__memcpy_avx_unaligned_erms+56>:	jae    <+128>
<__memcpy_avx_unaligned_erms+58>:	cmp    edx,0x4             # size >= 4: class 4..7 bytes
<__memcpy_avx_unaligned_erms+61>:	jae    <+85>
<__memcpy_avx_unaligned_erms+85>:	mov    ecx,DWORD PTR [rsi+rdx*1-0x4]   # last 4 bytes
<__memcpy_avx_unaligned_erms+89>:	mov    esi,DWORD PTR [rsi]             # first 4 bytes
<__memcpy_avx_unaligned_erms+91>:	mov    DWORD PTR [rdi+rdx*1-0x4],ecx   # for n = 4 both are the same 4 bytes,
<__memcpy_avx_unaligned_erms+95>:	mov    DWORD PTR [rdi],esi             # so they're copied twice
<__memcpy_avx_unaligned_erms+97>:	ret
instructions executed: 17
```

- **Size dispatch:** 8 instructions (4 compares, 4 conditional branches), only to find the size class.
- **Overlap trick:** each class covers a range of sizes without a loop by copying the first and the last k bytes, which may
  overlap. For n = 4 that means 2 loads and 2 stores for 4 bytes.
- **Per row:** a `call`, an indirect `jmp` through the GOT, the dispatch, the copy and a `ret`. That's 16 instructions inside glibc
  plus 6.5 in the loop, which gives the 22.5 instructions per row measured in `instructions_per_row.txt`.

The other traced sizes, counting only the glibc instructions:

| n | Size class | Glibc instructions | Copy instructions |
|---|---|---|---|
| 4 | 4..7 | 16 | 2 × 4-byte load and store (same bytes twice) |
| 8 | 8..15 | 14 | 2 × 8-byte load and store (same bytes twice) |
| 12 | 8..15 | 14 | 2 × 8-byte load and store, overlapping by 4 bytes |
| 16 | 16..31 | 12 | 2 × 16-byte `vmovdqu xmm` (same bytes twice) |
| 64 | 32..64 | 13 | 2 × 32-byte `vmovdqu ymm`, then `vzeroupper` |

The cost per call barely depends on the size: 12 to 16 instructions inside glibc. For a 4-byte row they copy 4 bytes; for a
64-byte row, 13 instructions copy 64 bytes. The overhead per byte falls with the row width, which is why `host_copy.hpp` only
specializes widths up to 64 bytes.

## 2. Fixed width: `memcpy` becomes a load and a store

```cpp
template <int64_t W>
void pack_fixed(std::byte* c, const std::byte* s, int64_t rows, int64_t pitch) {
	for(int64_t r = 0; r < rows; ++r) { std::memcpy(c, s, W); s += pitch; c += W; }
}
```

With `W = 4` known at compile time, clang treats `memcpy` as a built-in and replaces it with one 4-byte move. There's no call, no
size check and no saved registers. The loop is unrolled 8×:

```asm
.LBB4_3:                                # =>This Inner Loop Header: Depth=1
	mov	r9d, dword ptr [rsi]            # row 0: load 4 bytes
	mov	dword ptr [rdi], r9d            #        store 4 bytes
	mov	r9d, dword ptr [rsi + rcx]      # row 1: load from s + pitch
	add	rsi, rcx                        #        s += pitch
	mov	dword ptr [rdi + 4], r9d        #        store at a constant offset in staging
	mov	r9d, dword ptr [rcx + rsi]      # row 2
	add	rsi, rcx
	mov	dword ptr [rdi + 8], r9d
	...                                     # rows 3 to 6: the same 3 instructions
	mov	r9d, dword ptr [rcx + rsi]      # row 7
	mov	dword ptr [rdi + 28], r9d
	add	rsi, r8                         # s += 2 * pitch
	add	rdi, 32                         # c += 8 rows * 4 bytes
	add	rdx, -8                         # 8 rows done
	jne	.LBB4_3
```

That's 26 instructions for 8 rows, 3.25 per row: 1 load, 1 store, about 1 address add, and a share of the loop counter. There's
one branch per 8 rows. `cpu_pack`'s `rows_fixed4` ([line 379](copy_loops.s#L379)) does the same with `[r15 + 2*rcx]` addressing,
unrolled 4×, and also costs 3.25 instructions per row.

What the other specialized widths compile to:

| W | Per row | Unrolled |
|---|---|---|
| 4 | `mov r32` load and store | 8× |
| 8 | `mov r64` load and store | 8× |
| 12 | `mov r64` + `mov r32`: two load and store pairs | 4× |
| 16 | `movups xmm` load and store (SSE) | 4× |
| 64 | 4 × `movups xmm` load and store | 4× |

**`memcpy` vs. a typed access:** `memcpy(c, s, 4)` produces exactly the instruction that `*(uint32_t*)c = *(const uint32_t*)s`
would. Unlike the typed access, it's defined behaviour for any alignment and doesn't break the aliasing rules. So `host_copy.hpp`
keeps `memcpy` and loses nothing.

**No vectorization across rows:** consecutive source rows are `pitch` bytes apart, a value only known at run time. Combining
several rows into one vector would need gather loads. The x86-64 baseline has none, and even with AVX2 clang doesn't use
`vpgatherdd` here (see section 4). One load and one store per row is the minimum without changing the data layout.

## 3. copylib today: eight divisions per row

```cpp
for(int64_t i = 0; i < length;) {
	const int64_t source_offset = source.offset_at(source.start + i);   // 3 divisions
	const int64_t target_offset = target.offset_at(target.start + i);   // 3 divisions
	const int64_t take = std::min({source_row - (source.start + i) % source_row,   // 1 division
	                               target_row - (target.start + i) % target_row,   // 1 division
	                               length - i});
	... // if the run is interrupted (every row here, the source rows aren't adjacent): f(...) = memcpy(…, run_length)
	i += take;
}
```

`offset_at` computes `i_d0 = p % d0_size`, `i_d1 = (p % d1_size) / d0_size` and `i_d2 = p / d1_size`. The compiler merges
`p % d1_size` and `p / d1_size` into one division, which leaves 3 divisions per side. The two modulos for `take` add 2 more,
8 in total. They can't reuse earlier results, because the layout fields are reloaded from memory after every `memcpy` call
(see below).

Each division appears twice in the listing:

```asm
.LBB0_2:                                # =>This Inner Loop Header: Depth=1   (one iteration = one row here)
	mov	qword ptr [rsp + 8], r8         # 8-byte Spill
	mov	qword ptr [rsp + 16], rdx       # 8-byte Spill
	mov	rdi, qword ptr [rbx + 80]       # source.start (reloaded every row)
	add	rdi, rbp                        # p = source.start + i
	mov	rsi, qword ptr [rbx + 56]       # source.d0_end_offset
	mov	rax, qword ptr [rbx + 32]       # source.d0_start_offset
	mov	r9, qword ptr [rbx + 40]
	mov	qword ptr [rsp + 80], rax       # 8-byte Spill
	sub	rsi, rax                        # d0_size
	mov	r8, qword ptr [rbx + 64]
	mov	rax, rdi
	or	rax, rsi
	shr	rax, 32                         # do p and d0_size both fit in 32 bits?
	je	.LBB0_3
# %bb.4:
	mov	rax, rdi
	cqo
	idiv	rsi                             # no: 64-bit signed division
	jmp	.LBB0_5
.LBB0_3:
	mov	eax, edi
	xor	edx, edx
	div	esi                             # yes: 32-bit division, i_d0 = p % d0_size
```

- **Two versions of each division:** this is LLVM's "bypass slow division" for x86-64. Before each division, a run-time check
  picks the cheaper 32-bit `div` when both operands fit in 32 bits, otherwise the 64-bit `idiv`. That's why the listing contains
  16 division instructions: 8 `div r32` and 8 `idiv r64`.
- **Which path runs:** in `cpu_pack` the offsets stay below 2^32 (1 GiB of rows), so 8 `div r32` execute per row. Copies with
  windows above 4 GiB would take the slower 64-bit path.

The rest of the iteration consists of:
- **The divisions:** 7 more blocks like the one above (`.LBB0_5` to `.LBB0_26`), for the second division of the source side, the
  three of the target side, and the two modulos for `take`.
- **Field reloads:** 18 loads of layout fields per row (`[rbx + …]`). The `memcpy` call could change any memory, including the
  `copy_spec`, so the compiler can't keep the fields in registers across rows.
- **Stack spills:** 21 spills and reloads per row (`# 8-byte Spill` / `Reload`). The loop needs more live values than x86-64 has
  registers.
- **Run merging:** the check whether the run continues, which fails every row here because source rows are `pitch` apart.
- **The call:**

```asm
.LBB0_30:
	mov	rdi, qword ptr [rbx + 104]      # target base pointer
	add	rdi, rdx                        #   + run_target
	mov	rsi, qword ptr [rbx + 8]        # source base pointer
	add	rsi, r8                         #   + run_source
	mov	rdx, rcx                        # run_length (4 bytes)
	call	memcpy@PLT                      # the 16-instruction path from section 1
```

**The total:** following the path a pack takes gives 140 instructions in the loop plus 16 in `memcpy`. That's the 156 instructions
per row that gdb counted.

**Why divisions dominate the time:** the next row's dividend `start + i` depends on `take`, which needs this row's two modulos.
So each row has to wait for the previous row's division results, and all 8 divisions share the divider. That fits the measured
11.9 ns per row being independent of M.

**The proposed replacement** (`host_cursor` in `host_copy.hpp`) computes the position with divisions only once, at the start of
the window. After that it only adds the pitch and counts rows, which leaves the loop of section 2.

## 4. With `-march=x86-64-v3` (AVX2)

[copy_loops.x86-64-v3.s](copy_loops.x86-64-v3.s), compared function by function with the baseline:

| Function | Change |
|---|---|
| `copy_copylib` | identical: still 8 divisions and 1 call per row |
| `pack_fixed4`, `pack_fixed8` | identical |
| `rows_fixed4`, `pack_fixed12` | same instructions per row, unrolled 8× instead of 4× |
| `pack_fixed16` | VEX `vmovups xmm` instead of `movups`, unrolled 8× instead of 4× |
| `pack_fixed64` | 2 × 32-byte `vmovups ymm` per row instead of 4 × 16-byte `movups xmm` |
| `pack_var`, `rows_runtime` | unrolled further, still one `memcpy` call per row |

So AVX2 doesn't change the conclusion. For narrow rows the gain comes entirely from knowing the width at compile time. Wider
vectors only help rows of 32 bytes and more.

## What this means for copylib

1. **The 10× step comes from removing the per-row position arithmetic:** from 156 to 22.5 instructions per row, and from 11.9 to
   1.18 ns.
2. **The further 2.6–4.4× comes from the fixed width:** from 22.5 to 3.25 instructions per row, with no call. After that the loop
   is limited by memory (per-row time rises with M), so more CPU-side tuning has little left to gain. Further speed comes from
   more workers on memory channels that aren't saturated.
3. **`host_copy.hpp` covers both:** a cursor that adds the pitch per row instead of dividing, and `copy_full_rows<W, Pack>` for
   1, 2, 4, 8, 12, 16, 24, 32 and 64 bytes. All other widths, e.g. 20-byte rows, use the run-time-width loop. That still removes
   the divisions (the 10× step); only the call per row remains.
