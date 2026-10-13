**Goal:** What does `HSA_ENABLE_SDMA=0` (copies on the compute engines instead of the SDMA engines, process-wide) do to the current defaults (2dda28f), for staging, the host kernel and the contiguous native path?

**Result:** It is a large host-to-device gain for staging below about 2^20 rows (3.3x on gpuc4, 3.3x LUMI, 1.5x ifi) and for the contiguous native path (M = 1: 3.4x / 4.0x / 1.6x), but nothing for the host kernel (1.0x). Device-to-host: about equal on gpuc4, 1.2x on ifi, and 0.57x (worse) for staging on LUMI.

---

# Current defaults with and without SDMA (2026-10-06)

`make_yamls.py` generates, per system, one YAML per variant (staging, host kernel `COPYLIB_HOST_KERNEL=1`) with the defaults and the defaults plus `HSA_ENABLE_SDMA=0` as one parameter list (env innermost), so the two settings run back to back on the same node. `strided_transfer`, AdaptiveCpp only, M = 1 (contiguous, native path) and M = 2 (copylib), N 1..2^28, 3 iterations + 1 warm-up. ifi was pinned to the nodes of the sweep 3 defaults runs (staging gc20, host kernel gc22), LUMI cannot be pinned. `submit.sh` and `gpuc4/chain.sh` start the jobs. The lines with SDMA off are drawn in `02_comparison/lines_*.png` (dashed; M = 1 dash-dot).

Ratio off / on, geometric mean over N 2^16..2^28 (median of the runs):

| | | gpuc4 | ifi | LUMI |
|---|---|---|---|---|
| host-to-device | M = 1 native | 3.4 | 1.6 | 4.0 |
| | staging M = 2 | 3.3 | 1.5 | 3.3 |
| | host kernel M = 2 | 1.0 | 1.0 | 1.0 |
| device-to-host | M = 1 native | 1.1 | 1.2 | 0.75 |
| | staging M = 2 | 1.06 | 1.18 | 0.57 |
| | host kernel M = 2 | 1.0 | 0.97 | 0.98 |

- **The gain is at small and medium sizes:** staging host-to-device on gpuc4 is 9.4x at 2^16 rows, 1.6x at 2^24 and 1x at 2^28; the large copies are limited by the link either way.
- **The host kernel is unaffected:** its host-to-device reads go through the host-memory path and not the SDMA engines.
- **LUMI device-to-host gets worse** with staging (0.5-0.6x below 2^22 rows, 0.21 around 2^22), while the contiguous path is 0.75x. Sweep 3 saw the same for acpp native (0.76x).
- **Caveat:** `HSA_ENABLE_SDMA` is process-wide, so it affects all copies of an application, not just copylib's.
