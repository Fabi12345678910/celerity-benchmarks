# 06_cores

**Goal:** Staging workers: count (1-52), placement (near, far, mixed, all) and chunk order (block vs dynamic), 4 MiB chunks.

**Result:** Saturation at 4-5 P-cores on gpuc4, 8 split over both L3 groups on ifi, 3-4 on LUMI; dynamic order never worse, up to +24%.
