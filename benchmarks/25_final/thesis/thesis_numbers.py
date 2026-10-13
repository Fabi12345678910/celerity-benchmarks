#!/usr/bin/env python3
"""Numbers for thesis chapter 6, from the newest data with SDMA off. PROVISIONAL source until the final sweep is analysed: sweep 4 (21_sweep4,
build 2dda28f, env-set configs), 22_device_strided, 07_limits, 18_ifi_nvidia, native strided from 15_sweep3 (CELERITY_COPYLIB=off; the native
path runs at about 1 MB/s with or without SDMA). Staging = sweep 4 staging base (4 queues x 1 MiB = the final default); host kernel = sweep 4
grid q2 x 4 MiB (the final default queues/chunk; its kernel shape was MAX_ELEM_SIZE 4, 4 elements/item, WG 256, the final default is 16 / 1 / 32).
Medians of the runs per point (3 runs, sweep 4 base configs also pooled with their same-node anchors where the program/N/M match).
Usage: python3 thesis_numbers.py [--final] > numbers.txt
--final: the FINAL sweep instead (25_final, build 3dcopylib-final-bench f24e5f0 = the final defaults: staging 4 queues x 1 MiB, host kernel 2 queues x
4 MiB, MAX_ELEM_SIZE 16, 1 element per item, WG 32, preload on, SDMA off): staging = sweep_*_stg_base + its anchors, host kernel = sweep_*_hk_base +
anchors, native = sweep_strided_native / sweep_block_native, device-strided = prog_device (pinning on). The validated clean build performs the same."""
import glob
import os

import numpy as np
import pandas as pd

import sys

B = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
FINAL = "--final" in sys.argv
SW = "25_final" if FINAL else "21_sweep4"
P = "sweep_" if FINAL else ""  # config file prefix in 25_final
SYS = ["gpuc4", "ifi", "lumi"]
APPS = {"Celerity-acpp": "acpp", "Celerity-dpcpp": "dpcpp"}
DIRS = {"copy_bandwidth": "H>D", "d2h_gbps": "D>H"}


def rd(path):
    d = pd.read_csv(path)
    if "M" not in d:
        d["M"] = 0
    return d


def med(files, ok_only=True):
    d = pd.concat([rd(f).assign(system=f.split(os.sep)[-3]) for f in files], ignore_index=True)
    if ok_only:
        d = d[d.check == "ok"]
    return d.groupby(["system", "application", "M", "N"])[list(DIRS)].median()


def files(study, system, pattern):
    return sorted(glob.glob(os.path.join(B, study, system, "results", pattern)))


def correctness():
    print("## 6.1 Correctness: runs and non-ok checks per study (all systems)")
    rows = []
    for study in ("21_sweep4", "22_device_strided", "15_sweep3", "14_verify", "20_sdma_defaults", "17_preload", "25_final", "26_published"):
        for f in glob.glob(os.path.join(B, study, "**", "*.csv"), recursive=True):
            try:
                d = pd.read_csv(f, usecols=lambda c: c in ("check", "machine"))
            except Exception:
                continue
            if "check" not in d:
                continue
            rows.append((study, len(d), int((d.check != "ok").sum())))
    for f in glob.glob(os.path.join(B, "18_ifi_nvidia", "results", "*.csv")):
        d = pd.read_csv(f)
        rows.append(("18_ifi_nvidia", len(d), int((d.check != "ok").sum())))
    t = pd.DataFrame(rows, columns=["study", "runs", "non_ok"]).groupby("study").sum()
    print(t.to_string())


def limits():
    print("\n## Link limits (07_limits, plain HIP: hipMemcpy DMA of 1 GiB pinned, and a kernel reading/writing host memory; GB/s, median)")
    out = {}
    for s in SYS:
        d = pd.read_csv(os.path.join(B, "07_limits", "results", f"{s}_linkbw.csv"))
        for f in glob.glob(os.path.join(B, "07_limits", "results", f"{s}_linkbw_sdma_off.csv")):
            d = pd.concat([d, pd.read_csv(f)])
        d["sdma"] = np.where(d.env.fillna("").str.contains("SDMA=0"), "off", "on")
        m = d[d.mib == d.mib.max()].groupby(["sdma", "test"]).gbps.median().unstack(0)
        out[s] = m
        print(f"{s}:", {t: f"on {m.loc[t].get('on', float('nan')):.1f} / off {m.loc[t].get('off', float('nan')):.1f}" for t in ("dma_h2d", "dma_d2h", "kernel_read", "kernel_write", "kernel_read_s4", "kernel_write_s4")})
    return out


def block():
    print("\n## 6.2 Block (contiguous) at 2^28 elements = 1 GiB, GB/s (median), SDMA off; Celerity native = regular copy path, copylib = ROUTE=all")
    nat = med([f for s in SYS for f in files(SW, s, f"{P}block_native{'' if FINAL else '_base'}.csv")])
    stg = med([f for s in SYS for f in files(SW, s, f"{P}block_stg_base.csv") + files(SW, s, f"{P}block_stg_anchor_j*.csv")])
    hk = med([f for s in SYS for f in files(SW, s, f"{P}block_hk_base.csv") + files(SW, s, f"{P}block_hk_anchor_j*.csv")])
    rows = []
    for s in SYS:
        for app, a in APPS.items():
            for dr, dn in DIRS.items():
                k = (s, app, 0, 2 ** 28)
                rows.append((s, a, dn, nat.loc[k, dr], stg.loc[k, dr], hk.loc[k, dr]))
    t = pd.DataFrame(rows, columns=["system", "impl", "dir", "celerity_native", "copylib_staging", "copylib_hostkernel"])
    t["staging/native"] = t.copylib_staging / t.celerity_native
    print(t.round(2).to_string(index=False))
    return nat


def strided(block_nat):
    print("\n## 6.3 Strided column copies (4-byte rows, host pitch M*4 B, device contiguous), GB/s of useful data (median), SDMA off")
    if FINAL:
        nat = med([f for s in SYS for f in files(SW, s, "sweep_strided_native.csv")])
        hk = med([f for s in SYS for f in files(SW, s, "sweep_strided_hk_base.csv") + files(SW, s, "sweep_strided_hk_anchor_j*.csv")])
    else:
        nat = med([f for s in SYS for f in files("15_sweep3", s, "strided_native_copylib_off_*.csv")])
        hk = med([f for s in SYS for f in files(SW, s, "strided_hk_grid_q2_c4MiB.csv")])
    stg = med([f for s in SYS for f in files(SW, s, f"{P}strided_stg_base.csv") + files(SW, s, f"{P}strided_stg_anchor_j*.csv")])
    rows = []
    for s in SYS:
        for app, a in APPS.items():
            for dr, dn in DIRS.items():
                bref = block_nat.loc[(s, app, 0, 2 ** 28), dr]
                for m in (2, 4):
                    for n in (2 ** 20, 2 ** 23, 2 ** 28):
                        k = (s, app, m, n)
                        nv = nat[dr].get(k, np.nan)
                        sv, hv = stg[dr].get(k, np.nan), hk[dr].get(k, np.nan)
                        rows.append((s, a, dn, m, f"2^{int(np.log2(n))}", nv, sv, hv, sv / nv, hv / nv, sv / bref, hv / bref))
    t = pd.DataFrame(rows, columns=["system", "impl", "dir", "M", "N", "native", "staging", "hostkernel", "stg/native", "hk/native", "stg/block", "hk/block"])
    print(t.round(3).to_string(index=False))
    print("(native measured only up to 2^23 rows; 'block' = Celerity native contiguous copy of 1 GiB on the same system/impl/direction)")


def device_strided():
    if not FINAL:
        print("\n## 6.4 Host-strided vs device-strided (M = 4, N = 2^28 rows, AdaptiveCpp, GB/s): see 22_device_strided/README.md (same table)")
        p = os.path.join(B, "22_device_strided", "README.md")
        txt = open(p).read()
        i = txt.find("| | | gpuc4 | ifi | LUMI |")
        print(txt[i:txt.find("\n\n", i)])
        return
    print("\n## 6.4 Host-strided vs device-strided (M = 4, N = 2^28 rows, AdaptiveCpp, GB/s, median; final sweep, pinning on)")
    print("| | | " + " | ".join(SYS) + " |\n|---|---|" + "---|" * len(SYS))
    for dr, dn in DIRS.items():
        for side in ("host-strided", "device-strided"):
            for v in ("staging", "host kernel"):
                vals = []
                for s in SYS:
                    if side == "host-strided":
                        d = pd.concat([rd(f) for f in files(SW, s, f"sweep_strided_{'stg' if v == 'staging' else 'hk'}_base.csv")])
                    else:
                        d = rd(os.path.join(B, SW, s, "results", "prog_device.csv"))
                        d = d[d.env == ("HSA_ENABLE_SDMA=0" + ("" if v == "staging" else " COPYLIB_HOST_KERNEL=1"))]
                    d = d[(d.check == "ok") & (d.application == "Celerity-acpp") & (d.M == 4) & (d.N == 2 ** 28)]
                    vals.append(f"{d[dr].median():.2f}")
                print(f"| {dn} | {side}, {v} | " + " | ".join(vals) + " |")


def nvidia():
    print("\n## 6.5 NVIDIA (ifi RTX 2070, PCIe 3.0 x16, AdaptiveCpp + Celerity's CUDA backend), strided D>H GB/s (median); H>D not usable (first-use cost)")
    d = pd.concat([rd(f).assign(cfg=os.path.basename(f)[:-4]) for f in glob.glob(os.path.join(B, "18_ifi_nvidia", "results", "*.csv"))])
    d["cfg"] = d.cfg.str.replace("_large", "")
    m = d[d.check == "ok"].groupby(["cfg", "M", "N"]).d2h_gbps.median().unstack("cfg")
    print(m.loc[[(mm, n) for mm in (1, 2) for n in (2 ** 16, 2 ** 20, 2 ** 24, 2 ** 28) if (mm, n) in m.index]].round(3).to_string())


def main():
    pd.set_option("display.width", 250)
    pd.set_option("display.max_rows", 500)
    correctness()
    limits()
    nat = block()
    strided(nat)
    device_strided()
    nvidia()


if __name__ == "__main__":
    main()
