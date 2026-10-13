# 09_sparse

**Goal:** Sparse rows (4-byte rows, pitch 64-256 B) and copies strided on both sides: staging vs host kernel.

**Result:** gpuc4: staging wins host-to-device from pitch 16 B (up to 4.6x at 256 B); ifi and LUMI: the host kernel wins or ties.
