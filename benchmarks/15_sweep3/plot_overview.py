#!/usr/bin/env python3
"""The overview of sweep 3 (layout: ../overview.py): one A4 page per program and variant, one row per swept setting.
Strided: copy sizes 64Ki / 1Mi / 4Mi / 16Mi rows of 4 bytes, geometric mean over M = 2 and 4 (M = 1 is a contiguous copy that never reaches
copylib, so it would only dilute every effect). Block: 64Ki / 1Mi / 16Mi / 256Mi elements (ROUTE=all, so copylib copies them; the native
rows are Celerity's own copy path).
Reference (--ref): base = the variant's base config (the best combination of the earlier tuning; run once, so subject to node variance),
median = the median over all configs of the variant at the same point, anchor = the anchor runs (copies of the base) from the node the
config ran on, else from all nodes of the system, rerun = the median of the three reruns of the base (make_base_rerun.py; the single base
run was skewed by node and time).
Usage: python3 plot_overview.py [strided] [block] [--ref=base|median|anchor|rerun] ; writes overview_<program>_<stg|hk>[_<ref>].png here."""
import glob
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from overview import draw, gm, SYSTEMS, DIRS  # noqa: E402

SIZES = {"strided": [1 << 16, 1 << 20, 1 << 22, 1 << 24], "block": [1 << 16, 1 << 20, 1 << 24, 1 << 28]}
SIZE_LABEL = {"strided": ["64Ki", "1Mi", "4Mi", "16Mi"], "block": ["64Ki", "1Mi", "16Mi", "256Mi"]}
FAMILY = {"base": "ref", "defaults": "ref", "old": "ref", "place": "place", "min_bytes": "min_bytes", "queues": "queues",
          "staging_bytes": "staging_bytes", "chunk": "chunk", "plan_order": "plan_order", "wait_poll": "misc", "pageable": "misc",
          "sdma_off": "misc", "preload_off": "misc", "max_elem_size": "max_elem", "elems_per_item": "elems", "wg_size": "wg",
          "copylib_off": "native"}
GROUPS = ["ref", "native", "place", "min_bytes", "queues", "staging_bytes", "chunk", "plan_order", "misc", "max_elem", "elems", "wg"]
REF_TEXT = {"base": "the base config of the variant ({base})",
            "median": "median of all configs of the variant at the same point; the base has its own row ({base})",
            "anchor": "anchor runs (copies of the base, {base}) from the same node, else all anchors of the system; the base has its own row",
            "rerun": "median of 3 reruns of the base ({base}); the original base run has its own row"}
BASE_TEXT = {"stg": "4 queues, 1 MiB chunks", "hk": "4 queues, 1 MiB chunks, MAX_ELEM_SIZE 4, 4 elements per item, work-group 256"}
UNIT = {"B": 1, "KiB": 1024, "MiB": 1 << 20, "GiB": 1 << 30}
ORDER = {"all": 0, "inherit": 1, "dedicated": 2, "same_core": 3, "far": 4, "celerity_pinning_off": 5, "block": 0, "dynamic": 1, "interleaved": 2}


def load(program):
    cols = ["application", "N", "copy_bandwidth", "d2h_gbps", "check", "config", "option", "machine"]
    frames = []
    for system, _ in SYSTEMS:
        for f in sorted(glob.glob(os.path.join(HERE, system, "results", f"{program}_*.csv"))):
            d = pd.read_csv(f, usecols=lambda c: c in cols + ["M"])
            d["system"] = system
            frames.append(d[d.check == "ok"])
    d = pd.concat(frames, ignore_index=True)
    d["M"] = d["M"].fillna(0) if "M" in d else 0
    if program == "strided":
        d = d[d.M >= 2]
    return d[d.N.isin(SIZES[program])]


def medians(d):
    long = d.melt(id_vars=["system", "application", "config", "N", "M", "machine"], value_vars=[k for k, _ in DIRS], var_name="dir", value_name="gbps")
    return long[long.gbps > 0].groupby(["system", "application", "config", "dir", "N", "M", "machine"]).gbps.median().reset_index()


def ratios(d, program, tag, ref):
    """(config, system, dir, app, N) -> geomean over M of median / reference."""
    own = d.config.str.startswith(f"{program}_{tag}_") | ((tag == "stg") & d.config.str.startswith(f"{program}_native_"))
    med = medians(d[own])
    anchors = med[med.config.str.contains("_anchor_")]
    reruns = med[med.config.str.contains("_rerun_")]
    med = med[~med.config.str.contains("_anchor_") & ~med.config.str.contains("_rerun_")]
    keys = ["system", "application", "dir", "N", "M"]
    if ref == "base":
        r = med[med.config == f"{program}_{tag}_base"].drop(columns=["config", "machine"]).rename(columns={"gbps": "ref"})
        m = med.merge(r, on=keys)
    elif ref == "rerun":
        r = reruns.groupby(keys).gbps.median().rename("ref").reset_index()
        m = med.merge(r, on=keys)
    elif ref == "median":
        r = med[~med.config.str.contains("_native_")].groupby(keys).gbps.median().rename("ref").reset_index()
        m = med.merge(r, on=keys)
    else:
        a = anchors[anchors.config.str.startswith(f"{program}_{tag}_anchor")]
        r_node = a.groupby(keys + ["machine"]).gbps.median().rename("ref_node").reset_index()
        r_sys = a.groupby(keys).gbps.median().rename("ref_sys").reset_index()
        m = med.merge(r_sys, on=keys).merge(r_node, on=keys + ["machine"], how="left")
        m["ref"] = m.ref_node.fillna(m.ref_sys)
    m["ratio"] = m.gbps / m.ref
    return m.groupby(["config", "system", "dir", "application", "N"]).ratio.apply(gm).to_dict()


def rows(d, program, tag, ref):
    sub = d[d.config.str.startswith(f"{program}_{tag}_") | ((tag == "stg") & d.config.str.startswith(f"{program}_native_"))]
    sub = sub[~sub.config.str.contains("_anchor_") & ~sub.config.str.contains("_rerun_")][["config", "option"]].drop_duplicates()
    if ref == "base":
        sub = sub[sub.config != f"{program}_{tag}_base"]

    def key(row):
        c, opt = row
        val = c.split(f"_{opt}_", 1)[1] if f"_{opt}_" in c else ""
        digits = val.rstrip("BKiMG")
        num = ORDER.get(val, int(digits) * UNIT.get(val[len(digits):], 1) if digits.isdigit() else 0)
        return GROUPS.index(FAMILY[opt]), {"base": 0, "defaults": 1, "old": 2}.get(opt, 0), num

    out = []
    for c, opt in sorted(sub.itertuples(index=False), key=key):
        label = c.split("_", 2)[2].replace("_", " ")
        if c.startswith(f"{program}_native_"):
            label = "native " + label  # Celerity's own copy path (strided: CELERITY_COPYLIB=off; block: not routed to copylib)
        out.append((label, FAMILY[opt], c))
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    ref = next((a.split("=")[1] for a in sys.argv if a.startswith("--ref=")), "base")
    for program in args or ["strided", "block"]:
        d = load(program)
        for tag in ("stg", "hk"):
            g = ratios(d, program, tag, ref)
            rr = rows(d, program, tag, ref)
            name = {"stg": "staging", "hk": "host kernel"}[tag]
            what = "strided_transfer (4-byte rows, M = 2 and 4)" if program == "strided" else "block_transfer (ROUTE=all)"
            unit = "rows per copy" if program == "strided" else "elements per copy"
            sub = (f"Each cell: top row acpp, bottom row DPC++; left to right {', '.join(SIZE_LABEL[program])} {unit}. "
                   f"{'Geometric mean over M, ' if program == 'strided' else ''}median of 3 runs.\n"
                   f"Reference: {REF_TEXT[ref].format(base=BASE_TEXT[tag])}.\n"
                   f"Blue faster, red slower, 0.5x to 2x. Empty outlined cell = no data (not run on that system or not finished).")
            out = os.path.join(HERE, f"overview_{program}_{tag}" + ("" if ref == "base" else f"_{ref}") + ".png")
            draw(out, f"Sweep 3, {name}: bandwidth relative to the {'base' if ref == 'base' else ref}, {what}", sub, [(None, rr)],
                 lambda k, s, dk, app, zi: g.get((k, s, dk, app, SIZES[program][zi])), SIZE_LABEL[program])
            print(out, len(rr), "rows")


if __name__ == "__main__":
    main()
