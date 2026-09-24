#!/usr/bin/env python3
"""Artifact control for confirmed delta pairs (see protocol.json). Prints a table."""
import gzip, hashlib, json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import screen as S
ROOT = Path(__file__).resolve().parents[1]
P = json.load(open(ROOT / "control/protocol.json"))
G = Path("<research-root>/biology-compartment-2026-09-24/data/GSE126459")
rows = [l.rstrip("\n").split("\t") for l in open(ROOT / "features/tiles.tsv")]
tid = {(r[1], int(r[2])): k for k, r in enumerate(rows[1:])}
chrom, cols = S.load(ROOT / "features/tiles.tsv")
def bg(gsm):
    v = np.full(len(chrom), np.nan)
    for line in gzip.open(next(G.glob(f"{gsm}_*.bedGraph.gz")), "rt"):
        if line.startswith("track"): continue
        c, s, e, x = line.split()[:4]; c = c if c.startswith("chr") else "chr" + c
        k = tid.get((c, int(s) // 500000 * 500000))
        if k is not None: v[k] = float(x)
    return v
corr1 = np.nanmean([bg("GSM3602088"), bg("GSM3602089")], axis=0)
corr2 = np.nanmean([bg("GSM3602090"), bg("GSM3602091")], axis=0)
mut = np.nanmean([bg("GSM3602092"), bg("GSM3602093")], axis=0)
def run(x, y, covn, extra, half, seed):
    m = S.half(chrom, half)
    covs = [cols[c][m] for c in covn] + [e[m] for e in extra]
    return S.test_pair(x[m], y[m], covs, chrom[m], 5000, seed)
out = {"protocol_sha256": hashlib.sha256((ROOT / "control/protocol.json").read_bytes()).hexdigest(), "pairs": {}}
for i, (h, p) in enumerate(P["pairs"].items(), 1):
    x = cols[p["predictor"]]; sg = p["sign"]
    base = [c for c in ["gc", "tss_count", "siScr_mCh"] if c != p["predictor"]]
    if h == "H1":
        arms = {"indep_baseline": (cols["dlam_mCh"], [c for c in ["tss_count", "pc1_cm_base", "siScr_DNK"]], [])}
    else:
        arms = {"swapA": (mut - corr1, base, [corr2]), "swapB": (mut - corr2, base, [corr1]),
                "placebo": (corr2 - corr1, base, [mut])}
    res = {}
    for j, (a, (y, covn, extra)) in enumerate(arms.items()):
        for half in ("even", "odd"):
            r = run(x, y, covn, extra, half, 20260928 + i * 10 + j)
            r["p_dir"] = r["p_neg"] if sg < 0 else r["p_pos"]
            r["ok"] = bool(sg * r["rho"] >= 0.05 and r["p_dir"] <= 0.01)
            res[f"{a}_{half}"] = r
            print(f"{h} {p['predictor']:>13}~{p['outcome']:<9} {a:>14} {half:>4} rho {r['rho']:+.3f} n {r['n']} p {r['p_dir']:.4f} nullsd {r['null_sd']:.3f}", flush=True)
    ctrl = [a for a in arms if a != "placebo"]
    passed = all(res[f"{a}_{hh}"]["ok"] for a in ctrl for hh in ("even", "odd"))
    if "placebo" in arms:
        mean_mut = np.mean([abs(res[f"{a}_even"]["rho"]) for a in ctrl])
        passed = passed and abs(res["placebo_even"]["rho"]) < 0.5 * mean_mut
    res["label"] = "SURVIVES_ARTIFACT_CONTROL" if passed else "FAILS_ARTIFACT_CONTROL"
    print(h, res["label"], flush=True)
    out["pairs"][h] = res
json.dump(out, open(ROOT / "control/result.json", "w"), indent=1)
