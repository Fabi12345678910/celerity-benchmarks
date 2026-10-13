# 04_cpu_pack

**Goal:** The CPU pack/unpack loop in isolation: copylib's loop vs a row loop vs fixed-width copies, assembler analysis (`asm/`), correctness checks (`deployed_check/`).

**Result:** Fixed-width loops need 3.25 instead of 156 instructions per row; this became the fast path (05).
