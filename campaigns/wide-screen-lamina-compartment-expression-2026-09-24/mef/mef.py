#!/usr/bin/env python3
"""Third-cohort test of the GC-lamina result (mef/protocol.json). 'fetch' after freeze, then 'run'."""
import hashlib, json, sys, urllib.request, warnings
from pathlib import Path
import numpy as np
from scipy.stats import rankdata, spearmanr
warnings.filterwarnings("ignore", category=RuntimeWarning)
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code")); import screen as S
sys.path.insert(0, str(ROOT / "lbr")); import lbr as LB
P = json.load(open(ROOT / "mef/protocol.json"))
D = ROOT / "mef/data"
FEAT = ROOT / "mef/features/mm9_tiles.tsv"
MM9_CHR1 = 197195432
PRIM, PLAC, RANGE = ("P_p15", "P_x17"), ("PL_15_18", "PL_x17_18", "PL_x17_15"), ("FL_p15", "FL_x17")
DRUGS = [f"D_{d}_{p}" for d in ("BIX", "DZN", "TSA") for p in ("p18", "x17")]
ARMS = (("raw", 0), ("flexible", 100), ("scale_free", 200))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def fetch():
    fz = json.load(open(ROOT / "mef/freeze.json"))
    assert fz["sha256"]["mef/protocol.json"] == sha(ROOT / "mef/protocol.json")
    rec = {}
    for k, f in P["samples"].items():
        dest = D / f
        if not dest.exists():
            part = dest.with_name(f + ".part")
            urllib.request.urlretrieve(P["url_template"].format(file=f), part); part.replace(dest)
        rec[k] = {"file": f, "bytes": dest.stat().st_size, "sha256": sha(dest)}
        print(k, rec[k]["bytes"], flush=True)
    json.dump({"freeze_sha256": sha(ROOT / "mef/freeze.json"), "files": rec}, open(ROOT / "mef/intake.json", "w"), indent=1)

def load_features(path=FEAT):
    rows = [l.rstrip("\n").split("\t") for l in open(path)][1:]
    start = np.array([int(r[2]) for r in rows]); end = np.array([int(r[0].rsplit("-", 1)[1]) for r in rows])
    chrom, cols = S.load(path)
    return chrom, start, end, cols

def check_build(bw_path):
    import pyBigWig
    L = pyBigWig.open(str(bw_path)).chroms()
    return L.get("chr1", L.get("1")) == MM9_CHR1

def tile_values(bw_path, chrom, start, end, min_cov):
    import pyBigWig
    bw = pyBigWig.open(str(bw_path)); L = bw.chroms(); v = np.full(len(chrom), np.nan)
    name = {(c0 if c0.startswith("chr") else "chr" + c0): c0 for c0 in L}  # 'chr1' vs '1', as panel.tile_track
    for k, (c, s, e) in enumerate(zip(chrom, start, end)):
        if c not in name: continue
        cb = name[c]; e = min(int(e), L[cb])
        if e <= s: continue
        cov = bw.stats(cb, int(s), e, type="coverage", exact=True)[0]
        if cov is None or cov < min_cov: continue
        m = bw.stats(cb, int(s), e, type="mean", exact=True)[0]
        if m is not None: v[k] = m
    return v

def tile_all(files, chrom, start, end):
    """Coverage 0.5; pre-declared fallback to 0.1 for every track if any track has < 3500 finite tiles."""
    t = {k: tile_values(f, chrom, start, end, 0.5) for k, f in files.items()}
    if min(int(np.isfinite(v).sum()) for v in t.values()) >= 3500: return t, 0.5
    return {k: tile_values(f, chrom, start, end, 0.1) for k, f in files.items()}, 0.1

def zscore(v): return (v - np.nanmean(v)) / np.nanstd(v)

def tests_for(t):
    wt = lambda *ks: np.mean([t["WT_" + k] for k in ks], axis=0)
    other = {"p15": ("p18", "x17"), "p18": ("p15", "x17"), "x17": ("p15", "p18")}
    d = {"P_p15": (t["AC_p15"] - t["WT_p15"], wt("p18", "x17")), "P_x17": (t["AC_x17"] - t["WT_x17"], wt("p15", "p18")),
         "PL_15_18": (t["WT_p15"] - t["WT_p18"], wt("x17")), "PL_x17_18": (t["WT_x17"] - t["WT_p18"], wt("p15")),
         "PL_x17_15": (t["WT_x17"] - t["WT_p15"], wt("p18")),
         "FL_p15": (LB.quantile_map(t["WT_p18"], t["AC_p15"]) - t["WT_p15"], wt("x17")),
         "FL_x17": (LB.quantile_map(t["WT_p18"], t["AC_x17"]) - t["WT_x17"], wt("p15"))}
    for k in DRUGS:
        drug, pup = k.split("_")[1:]
        d[k] = (t[f"{drug}_{pup}"] - t["WT_" + pup], wt(*other[pup]))
    return d

def label(r):
    prim = [r[k] for k in PRIM]
    ok = all(x["rho"] <= -0.05 and x["p_neg"] <= 0.01 for x in prim)
    opp = all(x["rho"] >= 0.05 and x["p_pos"] <= 0.01 for x in prim)
    m = np.mean([x["rho"] for x in prim])
    plac = all(abs(r[k]["rho"]) < 0.5 * abs(m) for k in PLAC)
    rng_ok = all(r[k]["rho"] > 0.5 * m for k in RANGE)
    if ok and plac: return "REPLICATED" if rng_ok else "RANGE_EXPLAINED"
    return "DIRECTION_ONLY" if ok else "OPPOSITE" if opp else "NOT_REPLICATED"

def final_label(raw, flex, sf):
    if raw == flex == sf == "REPLICATED": return "REPLICATED"
    return "NOT_ROBUST" if raw == "REPLICATED" else raw

def specificity(raw_res, final):
    if final != "REPLICATED": return "NOT_APPLICABLE"
    m = np.mean([raw_res[k]["rho"] for k in PRIM]); dr = [raw_res[k]["rho"] for k in DRUGS]
    if all(x > m / 2 for x in dr): return "SPECIFIC"
    return "GENERIC" if np.mean(dr) <= m / 2 else "MIXED"

def run_tests(t, gc, tss, chrom, n_shift=5000, seed0=20261301):
    """All arms; returns {arm: {test: stats, 'label': ...}} or raises SystemExit on an abort condition."""
    out = {}
    for arm, off in ARMS:
        tt = {k: zscore(v) for k, v in t.items()} if arm == "scale_free" else t
        res = {}
        for i, (k, (y, b)) in enumerate(tests_for(tt).items()):
            seed = seed0 + i + off
            r = LB.test_design(gc, y, tss, LB.flex_basis(b), chrom, n_shift, seed) if arm == "flexible" else S.test_pair(gc, y, [tss, b], chrom, n_shift, seed)
            if r["n"] < P["min_n_per_test"] or not np.isfinite(r["rho"]): raise SystemExit(f"ABORT (no label): {arm} {k} n {r['n']}")
            m = np.isfinite(y) & np.isfinite(b); r["slope_on_baseline"] = float(np.polyfit(b[m], y[m], 1)[0])
            res[k] = r
        res["label"] = label(res); out[arm] = res
    return out

def gc_slope(gc, y, tss, b, ref_sd):
    m = np.isfinite(gc) & np.isfinite(y) & np.isfinite(tss) & np.isfinite(b)
    z = lambda v: (v - v.mean()) / v.std()
    X = np.column_stack([np.ones(m.sum()), z(gc[m]), z(rankdata(tss[m])), z(b[m])])
    return float(np.linalg.lstsq(X, y[m], rcond=None)[0][1] / ref_sd)

def run():
    fz = json.load(open(ROOT / "mef/freeze.json"))
    for f, h in fz["sha256"].items(): assert sha(ROOT / f) == h, f"changed since freeze: {f}"
    it = json.load(open(ROOT / "mef/intake.json"))
    assert it["freeze_sha256"] == sha(ROOT / "mef/freeze.json")
    for k, r in it["files"].items(): assert sha(D / r["file"]) == r["sha256"], f"data changed since intake: {k}"
    files = {k: D / f for k, f in P["samples"].items()}
    for k, f in files.items():
        if not check_build(f): sys.exit(f"ABORT (no label): chr1 length is not mm9 in {f.name}")
    chrom, start, end, cols = load_features()
    t, min_cov = tile_all(files, chrom, start, end)
    gc, tss = cols["gc"], cols["tss_count"]
    out = {"coverage_threshold": min_cov}
    out.update(run_tests(t, gc, tss, chrom))
    raw, flex, sf = out["raw"]["label"], out["flexible"]["label"], out["scale_free"]["label"]
    out["label"] = final_label(raw, flex, sf)
    out["specificity"] = specificity(out["raw"], out["label"])
    sd = {k: float(np.nanstd(v)) for k, v in t.items()}
    sd.update({"sim_" + k: float(np.nanstd(LB.quantile_map(t["WT_p18"], t["AC_" + k[3:]]))) for k in RANGE})  # the mapped track in each FL delta
    ok = np.all([np.isfinite(v) for v in t.values()], axis=0)
    pairs = [("WT_p15", "WT_p18"), ("WT_p15", "WT_x17"), ("WT_p18", "WT_x17"), ("AC_p15", "WT_p15"), ("AC_x17", "WT_x17")]
    members = {"P_p15": ("AC_p15", "WT_p15"), "P_x17": ("AC_x17", "WT_x17"), "PL_15_18": ("WT_p15", "WT_p18"),
               "PL_x17_18": ("WT_x17", "WT_p18"), "PL_x17_15": ("WT_x17", "WT_p15"),
               "FL_p15": ("sim_FL_p15", "WT_p15"), "FL_x17": ("sim_FL_x17", "WT_x17")}
    members.update({k: (f"{k.split('_')[1]}_{k.split('_')[2]}", "WT_" + k.split("_")[2]) for k in DRUGS})
    out["diagnostics"] = {"sd": sd, "finite_tiles": {k: int(np.isfinite(v).sum()) for k, v in t.items()},
                          "spearman": {f"{a}~{b}": float(spearmanr(t[a][ok], t[b][ok])[0]) for a, b in pairs},
                          "gc_slope_per_track_sd": {k: gc_slope(gc, y, tss, b, np.mean([sd[x] for x in members[k]])) for k, (y, b) in tests_for(t).items()}}
    out["probe_cpg"] = {k: S.test_pair(gc, y, [tss, b, cols["cpg_n"]], chrom, 1000, 20261401 + i)
                        for i, (k, (y, b)) in enumerate(list(tests_for(t).items())[:2])}
    for arm, _ in ARMS:
        for k, r in out[arm].items():
            if k != "label": print(f"{arm:<10} {k:<10} rho {r['rho']:+.3f} n {r['n']} p- {r['p_neg']:.4f} p+ {r['p_pos']:.4f} slope {r['slope_on_baseline']:+.3f}", flush=True)
    print("diagnostics", json.dumps(out["diagnostics"]))
    print("probe_cpg", json.dumps({k: round(v["rho"], 3) for k, v in out["probe_cpg"].items()}))
    print("coverage_threshold", min_cov)
    print("LABEL", out["label"], f"(raw {raw} / flexible {flex} / scale-free {sf}); specificity {out['specificity']}")
    json.dump(out, open(ROOT / "mef/results/result.json", "w"), indent=1)

if __name__ == "__main__":
    {"fetch": fetch, "run": run}[sys.argv[1]]()
