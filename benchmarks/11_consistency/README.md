# 11_consistency

**Goal:** Which method wins over 78 scenarios (3 systems x 2 directions x 13 shapes, acpp), before sweep 2.

**Result:** Host kernel wins 56 times but collapses to 3% of staging on gpuc4 device-to-host with narrow rows; staging is never more than 4x off the best.
