**Goal:** Find out why device-to-host copies are so slow on gpuc4 with the host kernel (and what else depends on which side is strided): a new program with the host side contiguous and the device side strided, both directions, against `strided_transfer` (host strided, device contiguous).

**Result:** The host-kernel collapse on gpuc4 comes from the strided *host* writes, not from the kernel: with the host side contiguous and the device strided, device-to-host with the host kernel runs at 14.5 GB/s on gpuc4 (0.17 GB/s with a strided host, 80x more), and it beats staging (10.4 GB/s) on all three systems. Whenever the strided side is the device, the host kernel is the best method; it only loses on PCIe when it must write strided host memory.

---

# Contiguous host, strided device (2026-10-06)

- **Program (`device_strided_transfer.cpp`, usage `N M`, output as `strided_transfer`):** a kernel first initializes the whole N x M buffer on the device (the device allocation is N x M); the host then only writes column 0, so its allocation is the contiguous N x 1 box. "First access (host to device)" copies that contiguous box into the strided device region, "device to host" copies the strided device column back into the contiguous host box. Check: first and last element after a device-side update.
- **Why:** the host kernel's device-to-host collapse on gpuc4 (5-30x slower than staging for narrow rows, `13_hk_probe`) was explained by partial-line writes over PCIe into the strided host memory. If that is the cause, contiguous host writes must not collapse; if they do, the cause is the strided device reads.
- **Configs (`make_yamls.py`, sweep 4 base values, SDMA off):** `device_stg_base` (4 queues, 1 MiB chunks), `device_hk_base` (the same plus `MAX_ELEM_SIZE` 4, 4 elements per item, work-group 256), `device_native_1/_2` (`CELERITY_COPYLIB=off`, N up to 2^23). Both implementations, M 1, 2, 4, N 1..2^28; 3 iterations + warm-up.
- **Build:** `build_device.sh <acpp|dpcpp0326>` retargets the machine's `setup_transfer.sh` as `08_both_strided/build_both.sh` does (`build/bench-device_strided-<impl>-bench`); `build_nvidia.sh` for the NVIDIA toolchain.
- **Queue (`queue.sh`):** gpuc4 waits for `SWEEP4-DONE`, builds and runs `gpuc4/chain.sh`; on ifi and LUMI the build + staging + host kernel job depends on every sweep 4 job (`afterany`) and the native job on that one (jobs 1707575/1707576 on ifi, 22585845/22585846 on LUMI).

## Results (2026-10-07; 3 systems, all 91-98k runs ok, `<system>/results/device_*.csv`)

AdaptiveCpp, M = 4, N = 2^28 rows (1 GiB of worked data), GB/s, sweep 4 base configs with SDMA off. "host-strided" is `strided_transfer` from sweep 4 (`21_sweep4/<system>/results/strided_{stg,hk}_base.csv`), "device-strided" is this program.

| | | gpuc4 | ifi | LUMI |
|---|---|---|---|---|
| device-to-host | host-strided, staging | 2.9 | 8.9 | 3.7 |
| | host-strided, host kernel | **0.17** | 22.1 | 4.4 |
| | device-strided, staging | 10.4 | 30.6 | 10.1 |
| | device-strided, host kernel | **14.5** | **39.1** | **24.6** |
| host-to-device | host-strided, staging | 4.6 | 7.5 | 6.7 |
| | host-strided, host kernel | 2.8 | 17.5 | 9.6 |
| | device-strided, staging | 9.2 | 13.2 | 18.1 |
| | device-strided, host kernel | **11.1** | 13.3 | **29.5** |

- **Cause of the gpuc4 collapse:** the same host kernel that writes host memory strided over PCIe (partial cache-line writes, `13_hk_probe`) reaches 0.17 GB/s, and the same kernel reading strided device memory and writing contiguous host memory reaches 14.5 GB/s. The kernel, its work-group and element settings are the same in both.
- **Proposed switch for the default:** the host kernel unless the copy is device-to-host into strided host memory on a discrete (PCIe) GPU, which goes to staging. With a strided device side the host kernel is the best method everywhere, up to 2.4x staging on LUMI.
- **Staging also benefits when the host side is contiguous** (device-to-host 2.9 -> 10.4 GB/s on gpuc4), since no strided pack on the host is needed.
- **Native (copylib off) path:** about 1 MB/s (0.001 GB/s) at all measured sizes (N up to 2^23) on all three AMD systems.
