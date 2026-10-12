#!/usr/bin/env python3
"""The overview of the final sweep (layout: ../overview.py, as 21_sweep4/plot_overview.py): one A4 page per program and variant, one row per swept
setting, one cell per system x direction, each cell a 2 x 4 glyph (top AdaptiveCpp, bottom DPC++; left to right the copy sizes). Colour = bandwidth
relative to the anchor of the same job (same node, minutes apart; the base config where a job has no anchor of that variant), median of 3 runs,
geometric mean over M = 2 and 4 for strided. Blue faster, red slower, 0.5x .. 2x. The ifi AdaptiveCpp host-to-device glyphs are drawn but drift with
time (see README), so read that column with care.
Usage: python3 plot_overview.py [strided] [block] ; writes overview_<program>_<stg|hk>.png/.pdf here."""
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from overview import draw, gm  # noqa: E402

from analyze_final import SIZES, load  # noqa: E402

SYSTEMS = [("gpuc4", "RX 9060 XT"), ("ifi", "Radeon 8060S"), ("lumi", "MI250X")]
SIZE_LABEL = {"strided": ["64Ki", "1Mi", "4Mi", "16Mi"], "block": ["64Ki", "1Mi", "16Mi", "256Mi"]}
FAMILY = ["base", "place", "min_bytes", "queues", "staging_bytes", "chunk", "grid", "plan_order", "wait_poll", "pageable", "sdma_on",
          "preload_off", "max_elem_size", "elems_per_item", "wg_size"]
UNIT = {"B": 1, "KiB": 1024, "MiB": 1 << 20, "GiB": 1 << 30}
BASE_TEXT = {"stg": "staging defaults: 4 queues x 1 MiB, 32 MiB staging, SDMA off",
             "hk": "host-kernel defaults: 2 queues x 4 MiB, MAX_ELEM_SIZE 16, 1 elem/item, WG 32, SDMA off"}


def ratios(med, tag):
    own = med[med.config.str.startswith(f"{tag}_")]
    anchors = own[own.config.str.startswith(f"{tag}_anchor_")]
    cfgs = own[~own.config.str.startswith(f"{tag}_anchor_")]
    keys = ["system", "application", "dir", "N", "M"]
    base = cfgs[cfgs.config == f"{tag}_base"].groupby(keys).gbps.median().rename("ref_base").reset_index()
    a = anchors.groupby(keys + ["job"]).gbps.median().rename("ref_job").reset_index()
    m = cfgs.merge(base, on=keys).merge(a, on=keys + ["job"], how="left")
    m["ratio"] = m.gbps / m.ref_job.fillna(m.ref_base)
    return m.groupby(["config", "system", "dir", "application", "N"]).ratio.apply(gm).to_dict(), sorted(cfgs.config.unique())


def order(c, tag):
    rest = c[len(tag) + 1:]
    fam = next((f for f in FAMILY if rest == f or rest.startswith(f + "_")), "zz")
    val = rest[len(fam) + 1:] if rest.startswith(fam + "_") else ""
    g = re.match(r"q(\d+)_c(\d+)(\w+)", val)
    m = re.match(r"(\d+)(B|KiB|MiB|GiB)?$", val)
    num = (int(g.group(1)) * 10 ** 12 + int(g.group(2)) * UNIT[g.group(3)]) if g else (int(m.group(1)) * UNIT.get(m.group(2) or "B", 1) if m else 0)
    return FAMILY.index(fam) if fam in FAMILY else 99, num, val


def main():
    progs = [a for a in sys.argv[1:] if a in ("strided", "block")] or ["strided", "block"]
    import pandas as pd
    for program in progs:
        med = pd.concat([load(program, s) for s, _ in SYSTEMS], ignore_index=True)
        for tag in ("stg", "hk"):
            g, cfgs = ratios(med, tag)
            rows = []
            for c in sorted(cfgs, key=lambda c: order(c, tag)):
                fam = order(c, tag)[0]
                rows.append((c[len(tag) + 1:].replace("_", " "), fam, c))
            name = {"stg": "staging", "hk": "host kernel"}[tag]
            what = "strided_transfer (4-byte rows, M = 2 and 4)" if program == "strided" else "block_transfer (all copies routed through copylib)"
            sub = (f"Each cell: top row AdaptiveCpp, bottom row DPC++; left to right {', '.join(SIZE_LABEL[program])} "
                   f"{'rows' if program == 'strided' else 'elements'} per copy. Median of 3 runs{', geometric mean over M' if program == 'strided' else ''}.\n"
                   f"Reference: the anchor of the same job (same node, minutes apart) = {BASE_TEXT[tag]}.\n"
                   f"Blue faster, red slower, 0.5x to 2x. Radeon 8060S AdaptiveCpp H>D drifts with time: read with care.")
            for ext in ("png", "pdf"):
                out = os.path.join(HERE, f"overview_{program}_{tag}.{ext}")
                draw(out, f"Final sweep, {name}: bandwidth relative to the defaults, {what}", sub, [(None, rows)],
                     lambda k, s, dk, app, zi: g.get((k, s, dk, app, SIZES[program][zi])), SIZE_LABEL[program], systems=SYSTEMS)
            print(out, len(rows), "rows")


if __name__ == "__main__":
    main()
