#!/usr/bin/env python3
"""EXPLORATORY, descriptive only (no pass rule): robustness of H4 (pc1_lcl_base ~ dpc1_cm) and
H5 (gc ~ dpc1_cm) after the artifact control. All autosomes, 1000 shifts, seed 20260930."""
import gzip, json, sys
from pathlib import Path
import numpy as np
from scipy.stats import rankdata
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import screen as S
ROOT = Path(__file__).resolve().parents[1]
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
s = {g: bg(g) for g in ["GSM3602088", "GSM3602089", "GSM3602090", "GSM3602091", "GSM3602092", "GSM3602093"]}
c1 = (s["GSM3602088"] + s["GSM3602089"]) / 2; c2 = (s["GSM3602090"] + s["GSM3602091"]) / 2
m1, m2 = s["GSM3602092"], s["GSM3602093"]
out = {}
def t(label, x, y, covs, mask=None):
    m = np.ones(len(chrom), bool) if mask is None else mask
    r = S.test_pair(x[m], y[m], [z[m] for z in covs], chrom[m], 1000, 20260930)
    out[label] = r
    print(f"{label:<44} rho {r['rho']:+.3f} n {r['n']:>5} p+ {r['p_pos']:.3f} p- {r['p_neg']:.3f}", flush=True)
gc, tss, lam, lcl = cols["gc"], cols["tss_count"], cols["siScr_mCh"], cols["pc1_lcl_base"]
for name, x, oth in [("H4 lcl", lcl, [gc]), ("H5 gc", gc, [lcl])]:
    base = [tss, lam] + ([gc] if x is lcl else [])
    for mn, mm in [("mut1", m1), ("mut2", m2)]:
        t(f"{name} {mn}-c1 | c2", x, mm - c1, base + [c2])
        t(f"{name} {mn}-c2 | c1", x, mm - c2, base + [c1])
    t(f"{name} placebo m1-m2 | c1", x, m1 - m2, base + [c1])
    # nonlinear baseline: rank, rank^2, rank^3 of independent baseline
    r2 = rankdata(np.where(np.isfinite(c2), c2, 0)); r2 = (r2 - r2.mean()) / r2.std()
    r2[~np.isfinite(c2)] = np.nan
    t(f"{name} (m-c1)|c2 cubic", x, (m1 + m2) / 2 - c1, base + [c2, r2**2, r2**3])
    # both predictors jointly
    t(f"{name} (m-c1)|c2 + other survivor", x, (m1 + m2) / 2 - c1, base + [c2] + oth)
    # within baseline tertiles of c2
    q = np.nanquantile(c2, [1/3, 2/3])
    for k, (lo, hi) in enumerate([(-np.inf, q[0]), (q[0], q[1]), (q[1], np.inf)]):
        t(f"{name} (m-c1)|c2 tertile{k+1}", x, (m1 + m2) / 2 - c1, base + [c2], (c2 > lo) & (c2 <= hi))
json.dump(out, open(ROOT / "control/robust_explore.json", "w"), indent=1)
