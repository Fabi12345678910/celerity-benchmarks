# 10_rows

**Goal:** Row widths 4/32/64/128/256 B per 256-byte pitch: staging vs host kernel.

**Result:** Host kernel better on ifi and LUMI and for wide rows on gpuc4; its slow LUMI device-to-host was fixed later by MAX_ELEM_SIZE (12).
