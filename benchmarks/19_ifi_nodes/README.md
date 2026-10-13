**Goal:** How much do the eight ifi nodes (gc20-gc27, one APU each) differ from each other, so that a single run on one node can be judged?

**Result:** Host-to-device is the same on all nodes (spread 6-14% between the best and worst node). Device-to-host varies by 30-60% between nodes, and gc20 is consistently the slowest (0.68-0.89 of the median). Run-to-run noise on one node is 2-7% host-to-device and 9-28% device-to-host, so about half of the device-to-host spread is noise and the rest is gc20.

---

# Node-to-node variety on ifi (2026-10-06)

No new runs: the anchor runs of sweep 3 (`15_sweep3/ifi/results/*_anchor_gc*.csv`), copies of the base config of each variant and program, two repeats on every node (jobs pinned with `--nodelist`; the script asserts that each ran on the node it was pinned to). Strided: M 2 and 4, N 2^16..2^28 step 4; block: four sizes, `ROUTE=all`; both variants (staging, host kernel), both implementations.
`python3 analyze_nodes.py` writes `node_variety.csv` and `node_variety.png`: each node's bandwidth relative to the median over the nodes at the same point, geometric mean over the points; plus the spread between the two repeats on the same node.

- **gc20 is the slow node** for device-to-host: 0.68-0.89 of the median in all 16 rows, and it is also the lowest in host-to-device (0.91-0.99). Its full-grid base rerun (`15_sweep3`, `*_rerun_r1`, node gc20) is the one that shows device-to-host at 0.73-0.77.
- **Other nodes** scatter between 0.8 and 1.25 in device-to-host without a clear pattern (gc22, gc23, gc25, gc26 each have a few low or high cells); with two repeats per node this is hard to tell from noise.
- **Consequence:** compare ifi device-to-host only against a reference from the same node (anchors), and prefer host-to-device for conclusions that must hold across nodes. The single-run bases of sweep 3 ran on gc20, gc22 and gc26, which is why their device-to-host columns shifted.
- gc20 and gc22 have the same process start-up time (`17_preload`).
