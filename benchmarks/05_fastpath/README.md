# 05_fastpath

**Goal:** Short check of the fixed-width host copies (c4ee4f1) and the non-temporal pack stores (014e21a) against the night sweep.

**Result:** Staging 6-8x faster on gpuc4, 10-24x on ifi, 7-17x on LUMI; NT stores +3-18% host-to-device. Tables: `compare.py`, `compare_nt.py`.
