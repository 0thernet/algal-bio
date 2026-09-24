#!/usr/bin/env python3
"""Panel shape test (panel/protocol.json). 'fetch' downloads references after the freeze;
'run' computes and labels."""
import gzip, hashlib, json, sys, urllib.request
import warnings; warnings.filterwarnings("ignore", category=RuntimeWarning)
from pathlib import Path
import numpy as np
from scipy.stats import spearmanr, rankdata
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code")); import screen as S
P = json.load(open(ROOT / "panel/protocol.json"))
D = ROOT / "panel/data"
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def fetch():
    fz = json.load(open(ROOT / "panel/freeze.json"))
    assert fz["sha256"]["panel/protocol.json"] == sha(ROOT / "panel/protocol.json")
    rec = {}
    for name, acc in P["references"].items():
        dest = D / f"{acc}.bigWig"
        if not dest.exists():
            part = dest.with_name(dest.name + ".part")
            urllib.request.urlretrieve(P["url_template"].format(acc=acc), part)
            part.replace(dest)
        rec[name] = {"acc": acc, "bytes": dest.stat().st_size, "sha256": sha(dest)}
        print(name, rec[name]["bytes"], flush=True)
    json.dump({"freeze_sha256": sha(ROOT / "panel/freeze.json"), "files": rec}, open(ROOT / "panel/intake.json", "w"), indent=1)

def tile_track(bw_path, chrom, start):
    import pyBigWig
    bw = pyBigWig.open(str(bw_path)); L = bw.chroms()
    name = {}
    for c0 in L:  # normalise 'chr1' vs '1'
        name[c0 if c0.startswith("chr") else "chr" + c0] = c0
    v = np.full(len(chrom), np.nan)
    for k, (c, s) in enumerate(zip(chrom, start)):
        if c not in name: continue
        cb = name[c]; e = min(s + 500000, L[cb])
        if e <= s: continue
        cov = bw.stats(cb, s, e, type="coverage", exact=True)[0]
        if cov is None or cov < 0.5: continue
        m = bw.stats(cb, s, e, type="mean", exact=True)[0]
        if m is not None: v[k] = m
    return v

def orient(v, chrom, tss):
    out = v.copy()
    for c in np.unique(chrom):
        i = (chrom == c) & np.isfinite(v) & np.isfinite(tss)
        if i.sum() < 10: out[chrom == c] = np.nan; continue
        r = spearmanr(v[i], tss[i])[0]
        if not np.isfinite(r) or abs(r) < 0.2: out[chrom == c] = np.nan
        elif r < 0: out[chrom == c] = -v[chrom == c]
    return out

def label(res):
    nc = P["non_cardiac"]
    p1_pass = [n for n in nc if all(res[n][s]["rho"] >= 0.05 and res[n][s]["p_pos"] <= 0.05 / 6 for s in ("A", "B"))]
    P1 = len(p1_pass) >= 5
    P2 = all(res["LV_specific"][s]["rho"] <= -0.05 and res["LV_specific"][s]["p_neg"] <= 0.01 for s in ("A", "B"))
    leak = all(res["heart_LV"][s]["rho"] - np.median([res[n][s]["rho"] for n in nc]) >= 0.05 for s in ("A", "B")) or \
           all(res["LV_specific"][s]["rho"] >= 0.05 and res["LV_specific"][s]["p_pos"] <= 0.01 for s in ("A", "B"))
    lab = "LEAK_PATTERN" if leak else "EROSION_SUPPORTED" if (P1 and P2) else "P1_ONLY" if P1 else "NOT_SUPPORTED"
    return {"label": lab, "P1": P1, "P1_passing": p1_pass, "P2": P2, "leak": bool(leak)}

def run():
    fz = json.load(open(ROOT / "panel/freeze.json"))
    for f, h in fz["sha256"].items(): assert sha(ROOT / f) == h, f"changed since freeze: {f}"
    rows = [l.rstrip("\n").split("\t") for l in open(ROOT / "features/tiles.tsv")][1:]
    chrom = np.array([r[1] for r in rows]); start = np.array([int(r[2]) for r in rows])
    _, cols = S.load(ROOT / "features/tiles.tsv")
    G = Path("<research-root>/biology-compartment-2026-09-24/data/GSE126459")
    tid = {(c, s): k for k, (c, s) in enumerate(zip(chrom, start))}
    def bg(g):
        v = np.full(len(chrom), np.nan)
        for line in gzip.open(next(G.glob(f"{g}_*.bedGraph.gz")), "rt"):
            if line.startswith("track"): continue
            c, s, e, x = line.split()[:4]; c = c if c.startswith("chr") else "chr" + c
            k = tid.get((c, int(s) // 500000 * 500000))
            if k is not None: v[k] = float(x)
        return v
    c1 = (bg("GSM3602088") + bg("GSM3602089")) / 2; c2 = (bg("GSM3602090") + bg("GSM3602091")) / 2
    mut = (bg("GSM3602092") + bg("GSM3602093")) / 2
    swaps = {"A": (mut - c1, c2), "B": (mut - c2, c1)}
    tss = cols["tss_count"]
    ref = {n: orient(tile_track(D / f"{a}.bigWig", chrom, start), chrom, tss) for n, a in P["references"].items()}
    res_fin = {n: int(np.isfinite(v).sum()) for n, v in ref.items()}
    low = [n for n, k in res_fin.items() if k < P["min_finite_tiles"]]
    if low: sys.exit(f"ABORT (no label): references below min_finite_tiles: {low} {res_fin}")
    def rk(v):
        o = np.full(len(v), np.nan); i = np.isfinite(v); o[i] = rankdata(v[i]) / (i.sum() + 1); return o
    R6 = np.array([rk(ref[n]) for n in P["non_cardiac"]])
    cons = np.where(np.isfinite(R6).sum(0) >= 4, np.nanmean(R6, axis=0), np.nan)
    base = [cols["gc"], tss, cols["siScr_mCh"]]
    res = {"n_finite": {n: int(np.isfinite(v).sum()) for n, v in ref.items()}}
    names = list(P["references"]) + ["LV_specific"]
    for i, n in enumerate(names):
        res[n] = {}
        for j, (s, (y, b)) in enumerate(swaps.items()):
            x = ref["heart_LV"] if n == "LV_specific" else ref[n]
            covs = base + [b] + ([cons] if n == "LV_specific" else [])
            r = S.test_pair(x, y, covs, chrom, 5000, 20261001 + 10 * i + j)
            if r["n"] < P["min_n_per_test"] or not np.isfinite(r["rho"]):
                sys.exit(f"ABORT (no label): {n} swap{s} n {r['n']} rho {r['rho']}")
            res[n][s] = r
            print(f"{n:<15} swap{s} rho {r['rho']:+.3f} n {r['n']} p+ {r['p_pos']:.4f} p- {r['p_neg']:.4f}", flush=True)
    res["verdict"] = label(res)
    print(json.dumps(res["verdict"]))
    json.dump(res, open(ROOT / "panel/results/result.json", "w"), indent=1)

if __name__ == "__main__":
    {"fetch": fetch, "run": run}[sys.argv[1]]()
