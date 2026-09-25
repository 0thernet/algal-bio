#!/usr/bin/env python3
"""EXPLORATORY, post-outcome. Not registered. Vectorized re-implementation of explore/fine_scale.py.

The original run (logs/fine_scale.log) was interrupted after 3 of its 10 tests because its per-tile Python
loops were slow. This file computes the same statistics with the same test list, the same bins, the same
seed and the same order of random draws; only the within-tile demeaning is vectorized (np.bincount).
Acceptance check before reading new rows: the first three rows must reproduce logs/fine_scale.log.

Reading rule (copied verbatim from explore/fine_scale.py, written before its first run):
technical library GC bias is expected to act at fragment/bin level, so it should show a fine-scale partial rho
comparable to the coarse one; a domain-level lamina change should show a coarse rho with a much smaller
fine-scale one. Fine: bin values demeaned within their 500 kb tile (delta, gc, baseline), partial Spearman of
gc vs delta given baseline. Coarse: tile means, partial Spearman given tile baseline (no tss here).
Null for fine: shift gc bins within chromosome by >= 50 bins, then demean; 200 shifts (as implemented)."""
import json, warnings
from pathlib import Path
import numpy as np, pyBigWig
from scipy.stats import rankdata
warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
GC = pyBigWig.open(str(ROOT / "data/external/hg38.gc5Base.bw"))
AUTO = [f"chr{i}" for i in range(1, 23)]

def binned(bw_path, binsize):
    bw = pyBigWig.open(str(bw_path)); out = {}
    for c in AUTO:
        n = bw.chroms()[c] // binsize
        out[c] = np.array(bw.stats(c, 0, n * binsize, nBins=n, type="mean", exact=True), dtype=float)
    return out

_gc = {}
def gc_bins(binsize):
    if binsize not in _gc:
        _gc[binsize] = {c: np.array(GC.stats(c, 0, (GC.chroms()[c] // binsize) * binsize, nBins=GC.chroms()[c] // binsize,
                                             type="mean", exact=True), dtype=float) for c in AUTO}
    return _gc[binsize]

def pr(x, y, z):
    x, y, z = rankdata(x), rankdata(y), rankdata(z)
    Z = np.column_stack([np.ones_like(z), z])
    rx = x - Z @ np.linalg.lstsq(Z, x, rcond=None)[0]; ry = y - Z @ np.linalg.lstsq(Z, y, rcond=None)[0]
    return float(rx @ ry / np.sqrt((rx @ rx) * (ry @ ry)))

def demean(v, tile, ok, per_tile):
    """Same as the original loop: subtract the tile mean over ok bins, only in tiles with >= per_tile // 2 ok bins."""
    t = tile[ok]; nt = int(tile.max()) + 1
    cnt = np.bincount(t, minlength=nt); s = np.bincount(t, weights=v[ok], minlength=nt)
    good = cnt >= per_tile // 2
    mean = np.divide(s, cnt, out=np.full(nt, np.nan), where=cnt > 0)
    out = np.full_like(v, np.nan); sel = ok & good[tile]
    out[sel] = v[sel] - mean[tile[sel]]
    return out

def analyse(delta, base, binsize, seed=0):
    per_tile = 500000 // binsize
    g = gc_bins(binsize); rows = []
    for c in AUTO:
        n = min(len(delta[c]), len(base[c]), len(g[c]))
        rows.append((c, delta[c][:n], base[c][:n], g[c][:n], np.arange(n) // per_tile))
    def fine(shift_rng=None):
        X, Y, Zb = [], [], []
        for c, d, b, gg, tile in rows:
            if shift_rng is not None: gg = np.roll(gg, shift_rng.integers(50, len(gg) - 50))
            ok = np.isfinite(d) & np.isfinite(b) & np.isfinite(gg)
            dd, bb, g2 = demean(d, tile, ok, per_tile), demean(b, tile, ok, per_tile), demean(gg, tile, ok, per_tile)
            k = np.isfinite(dd) & np.isfinite(bb) & np.isfinite(g2)
            X.append(g2[k]); Y.append(dd[k]); Zb.append(bb[k])
        X, Y, Zb = map(np.concatenate, (X, Y, Zb))
        return pr(X, Y, Zb), len(X)
    obs, n = fine()
    rng = np.random.default_rng(seed); null = np.array([fine(rng)[0] for _ in range(200)])
    X, Y, Zb = [], [], []
    for c, d, b, gg, tile in rows:
        for t in np.unique(tile):
            m = (tile == t) & np.isfinite(d) & np.isfinite(b) & np.isfinite(gg)
            if m.sum() >= per_tile // 2: X.append(gg[m].mean()); Y.append(d[m].mean()); Zb.append(b[m].mean())
    return {"fine_rho": obs, "fine_n": n, "fine_null_sd": float(null.std()), "fine_z": float((obs - null.mean()) / null.std()),
            "coarse_rho": pr(np.array(X), np.array(Y), np.array(Zb)), "coarse_n": len(X)}

def sub(a, b): return {c: a[c] - b[c] for c in AUTO}
def mean(*a): return {c: np.nanmean([x[c] for x in a], axis=0) for c in AUTO}

if __name__ == "__main__":
    out = {}
    K = ROOT / "damid/data"; P = json.load(open(ROOT / "damid/protocol.json"))["samples"]
    k = {n: binned(K / f, 25000) for n, f in P.items()}
    wt12 = mean(k["WT_r1"], k["WT_r2"])
    tests = {"K562 LMNA P_batch (LMNA_r8-WT_r3)": (sub(k["LMNAKO_r2"], k["WT_r3"]), wt12),
             "K562 LMNA r7 (LMNA_r7-WT_r1)": (sub(k["LMNAKO_r1"], k["WT_r1"]), k["WT_r2"]),
             "K562 PL_within (WT_r1-WT_r2)": (sub(k["WT_r1"], k["WT_r2"]), k["WT_r3"]),
             "K562 PL_cross (WT_r3-WT_r1)": (sub(k["WT_r3"], k["WT_r1"]), k["WT_r2"]),
             "K562 LBR r8 (LBR_r8-WT_r3)": (sub(k["LBRKO_r3"], k["WT_r3"]), wt12)}
    R = ROOT / "lbr/data"; Q = json.load(open(ROOT / "lbr/protocol.json"))["samples"]
    r = {n: binned(R / f, 20000) for n, f in Q.items()}
    B = mean(r["ST_r6"], r["ST_r7"]); W = mean(r["WT_r13"], r["WT_r14"])
    tests2 = {"RPE1 LBR P_r13": (sub(r["LBRKO_r13"], r["WT_r13"]), B), "RPE1 LBR P_r14": (sub(r["LBRKO_r14"], r["WT_r14"]), B),
              "RPE1 PL_batch": (sub(r["WT_r13"], r["WT_r14"]), B), "RPE1 PL_st": (sub(r["ST_r6"], r["ST_r7"]), W),
              "RPE1 T2B r13": (sub(r["WT_T2B_r13"], r["WT_r13"]), B)}
    for name, (d, b) in list(tests.items()):
        out[name] = analyse(d, b, 25000); print(f"{name:<36} {json.dumps({x: round(y, 3) for x, y in out[name].items()})}", flush=True)
    for name, (d, b) in tests2.items():
        out[name] = analyse(d, b, 20000); print(f"{name:<36} {json.dumps({x: round(y, 3) for x, y in out[name].items()})}", flush=True)
    json.dump(out, open(ROOT / "explore/fine_scale.json", "w"), indent=1)
