#!/usr/bin/env python3
"""Cross-cohort GC-correlated same-condition library variation (libvar/protocol.json).
'fetch' after freeze (downloads only the opc holdout files; opened-cohort tracks are
hash-verified in place against their earlier intake receipts), then 'run'."""
import hashlib, json, sys, urllib.request, warnings
from pathlib import Path
import numpy as np
warnings.filterwarnings("ignore", category=RuntimeWarning)
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code")); import screen as S
P = json.load(open(ROOT / "libvar/protocol.json"))
D = ROOT / "libvar/data"
FEATS = {"hg38": ROOT / "features/tiles.tsv", "mm9": ROOT / "mef/features/mm9_tiles.tsv", "mm10": ROOT / "libvar/features/mm10_tiles.tsv"}
RECEIPTS = {"k562": ROOT / "damid/intake.json", "rpe1": ROOT / "lbr/intake.json", "mef": ROOT / "mef/intake.json"}
ARMS = (("raw", 0), ("scale_free", 100))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def cohort_dir(c):
    d = P["cohorts"][c]["dir"]
    return Path(d) if d.startswith("/") else ROOT / d

def prior_sha(cohort, fname):
    """sha256 recorded for this file under an earlier registration, or None."""
    r = RECEIPTS.get(cohort)
    if r is None or not r.exists(): return None
    rec = json.load(open(r))
    files = rec.get("files")
    if isinstance(files, dict):                          # intake-style receipts {key: {file, sha256}}
        for v in files.values():
            if v.get("file") == fname: return v["sha256"]
    elif isinstance(files, list):                        # inputs.discovery.json style [{path, sha256}]
        for v in files:
            if v.get("path") == fname: return v["sha256"]
    return None

def fetch():
    fz = json.load(open(ROOT / "libvar/freeze.json"))
    assert fz["sha256"]["libvar/protocol.json"] == sha(ROOT / "libvar/protocol.json")
    rec, cross = {}, {}
    for c, cfg in P["cohorts"].items():
        if not cfg.get("holdout"):
            r = RECEIPTS.get(c)
            assert r is not None and r.exists(), f"no prior receipt for non-holdout cohort {c}"
        d = cohort_dir(c)
        for k, f in cfg["files"].items():
            dest = d / f
            if cfg.get("holdout") and not dest.exists():
                part = dest.with_name(f + ".part")
                urllib.request.urlretrieve(cfg["url_template"].format(file=f), part); part.replace(dest)
            assert dest.exists(), f"missing {c}:{k} {dest}"
            h = sha(dest); rec[f"{c}:{k}"] = {"file": f, "dir": cfg["dir"], "bytes": dest.stat().st_size, "sha256": h}
            old = prior_sha(c, f); cross[f"{c}:{k}"] = old
            if old is not None: assert old == h, f"{c}:{k} changed since its earlier intake"
            print(c, k, rec[f"{c}:{k}"]["bytes"], "cross-verified" if old else "first-receipt", flush=True)
    json.dump({"freeze_sha256": sha(ROOT / "libvar/freeze.json"), "files": rec, "prior_receipt_sha256": cross},
              open(ROOT / "libvar/intake.json", "w"), indent=1)

def load_features(path):
    rows = [l.rstrip("\n").split("\t") for l in open(path)][1:]
    start = np.array([int(r[2]) for r in rows]); end = np.array([int(r[0].rsplit("-", 1)[1]) for r in rows])
    chrom, cols = S.load(path)
    return chrom, start, end, cols

def check_build(bw_path, chr1):
    import pyBigWig
    L = pyBigWig.open(str(bw_path)).chroms()
    return L.get("chr1", L.get("1")) == chr1

def tile_values(bw_path, chrom, start, end, min_cov):
    import pyBigWig
    bw = pyBigWig.open(str(bw_path)); L = bw.chroms(); v = np.full(len(chrom), np.nan)
    name = {(c0 if c0.startswith("chr") else "chr" + c0): c0 for c0 in L}
    for k, (c, s, e) in enumerate(zip(chrom, start, end)):
        if c not in name: continue
        cb = name[c]; e = min(int(e), L[cb])
        if e <= s: continue
        cov = bw.stats(cb, int(s), e, type="coverage", exact=True)[0]
        if cov is None or cov < min_cov: continue
        m = bw.stats(cb, int(s), e, type="mean", exact=True)[0]
        if m is not None: v[k] = m
    return v

def zscore(v): return (v - np.nanmean(v)) / np.nanstd(v)

def pair_test(t_a, t_b, gc, tss, chrom, seed):
    y = t_a - t_b; b = np.nanmean([t_a, t_b], axis=0)
    r = S.test_pair(gc, y, [tss, b], chrom, 5000, seed)
    m = np.isfinite(y) & np.isfinite(b)
    r["slope_on_baseline"] = float(np.polyfit(b[m], y[m], 1)[0]) if m.sum() >= 10 else float("nan")
    return r

def run_pairs(pairs, tracks, gc, tss, chrom, seed0, n_shift_check=None):
    """pairs: {id: (a_key, b_key)}; tracks: {key: tile vector}; returns {id: stats}."""
    out = {}
    for i, (k, (a, b)) in enumerate(pairs.items()):
        r = pair_test(tracks[a], tracks[b], gc, tss, chrom, seed0 + i)
        if n_shift_check and (r["n"] < n_shift_check or not np.isfinite(r["rho"])):
            raise SystemExit(f"ABORT (no label): {k} n {r['n']}")
        out[k] = r
    return out

def pooled_label(res):
    raw = {k: v["raw"] for k, v in res.items()}
    absr = {k: abs(v["rho"]) for k, v in raw.items()}
    med = float(np.median(list(absr.values())))
    p1 = float(np.mean([v >= 0.10 for v in absr.values()])) >= 0.60
    elig = [v for k, v in res.items() if abs(v["raw"]["rho"]) >= 0.05]
    p2 = len(elig) >= 4 and float(np.median([abs(v["scale_free"]["rho"]) / abs(v["raw"]["rho"]) for v in elig])) >= 0.5
    p3 = med >= P["registered_predictions"]["benchmark_median"] / 3
    hold = [k for k in absr if k.startswith("LV_opc")]
    p4 = sum(absr[k] >= 0.05 for k in hold) >= 4
    lab = "SYSTEMATIC" if (p1 and p2 and p3 and p4) else "PARTIAL" if (p1 and p2 and p3) else "NOT_SUPPORTED"
    return lab, {"median_abs_rho": med, "frac_abs_ge_0.10": float(np.mean([v >= 0.10 for v in absr.values()])),
                 "n_p2_eligible": len(elig), "p2_median_ratio": (float(np.median([abs(v["scale_free"]["rho"]) / abs(v["raw"]["rho"]) for v in elig])) if elig else None),
                 "p1": p1, "p2": p2, "p3": p3, "p4": p4, "holdout_abs": {k: absr[k] for k in hold}}

def run():
    fz = json.load(open(ROOT / "libvar/freeze.json"))
    for f, h in fz["sha256"].items(): assert sha(ROOT / f) == h, f"changed since freeze: {f}"
    it = json.load(open(ROOT / "libvar/intake.json"))
    assert it["freeze_sha256"] == sha(ROOT / "libvar/freeze.json")
    for ck, r in it["files"].items():
        c = ck.split(":")[0]; assert sha(cohort_dir(c) / r["file"]) == r["sha256"], f"data changed since intake: {ck}"
    tracks_by_cohort, feats_by_cohort, cov_used = {}, {}, {}
    for c, cfg in P["cohorts"].items():
        files = {k: cohort_dir(c) / f for k, f in cfg["files"].items()}
        for k, f in files.items():
            if not check_build(f, cfg["chr1"]): sys.exit(f"ABORT (no label): chr1 length is not {cfg['build']} in {f.name}")
        chrom, start, end, cols = load_features(FEATS[cfg["build"]])
        t = {k: tile_values(f, chrom, start, end, 0.5) for k, f in files.items()}; cov = 0.5
        if min(int(np.isfinite(v).sum()) for v in t.values()) < 3500:
            t = {k: tile_values(f, chrom, start, end, 0.1) for k, f in files.items()}; cov = 0.1
        tracks_by_cohort[c], feats_by_cohort[c] = t, (chrom, cols); cov_used[c] = cov
    res, sds, finite = {}, {}, {}
    pair_index = 0
    for c, cfg in P["cohorts"].items():
        chrom, cols = feats_by_cohort[c]; gc, tss = cols["gc"], cols["tss_count"]
        t = tracks_by_cohort[c]
        sds.update({f"{c}:{k}": float(np.nanstd(v)) for k, v in t.items()})
        finite.update({f"{c}:{k}": int(np.isfinite(v).sum()) for k, v in t.items()})
        mine = {k: (v["a"], v["b"]) for k, v in P["pairs"].items() if v["cohort"] == c}
        for arm, off in ARMS:
            tt = {k: zscore(v) for k, v in t.items()} if arm == "scale_free" else t
            r = run_pairs(mine, tt, gc, tss, chrom, 20262701 + off + pair_index, P["min_n_per_test"])
            for k, v in r.items(): res.setdefault(k, {})[arm] = v
        pair_index += len(mine)
    xc = {}
    for i, a in enumerate(("PF_8", "PF_9", "PF_10")):
        for j, b in enumerate(("T3_18", "T3_19", "T3_20")):
            r = pair_test(tracks_by_cohort["opc"][a], tracks_by_cohort["opc"][b],
                          feats_by_cohort["opc"][1]["gc"], feats_by_cohort["opc"][1]["tss_count"],
                          feats_by_cohort["opc"][0], 20262901 + 3 * i + j)
            if not np.isfinite(r["rho"]): r["rho"] = None   # JSON has no NaN
            xc[f"XC_{a}_{b}"] = r
    label, pooled = pooled_label(res)
    out = {"pairs": res, "cross_condition": xc, "label": label, "pooled": pooled,
           "diagnostics": {"track_sd": sds, "finite_tiles": finite, "coverage_threshold": cov_used,
                           "n_pairs_per_cohort": {c: sum(1 for k in P["pairs"] if P["pairs"][k]["cohort"] == c) for c in P["cohorts"]},
                           "n_previously_computed_pairs": 7,
                           "sd_ratio": {k: round(max(sds[f"{P['pairs'][k]['cohort']}:{P['pairs'][k]['a']}"], sds[f"{P['pairs'][k]['cohort']}:{P['pairs'][k]['b']}"]) /
                                                min(sds[f"{P['pairs'][k]['cohort']}:{P['pairs'][k]['a']}"], sds[f"{P['pairs'][k]['cohort']}:{P['pairs'][k]['b']}"]), 4)
                                        for k in P["pairs"]},
                           "cohort_median_abs_rho": {c: float(np.median([abs(res[k]["raw"]["rho"]) for k in res if P["pairs"][k]["cohort"] == c])) for c in P["cohorts"]}}}
    for k in P["pairs"]:
        r = out["pairs"][k]
        print(f"{k:18s} raw {r['raw']['rho']:+.3f} (n {r['raw']['n']}) sf {r['scale_free']['rho']:+.3f}", flush=True)
    print("LABEL", label, json.dumps(pooled))
    json.dump(out, open(ROOT / "libvar/results/result.json", "w"), indent=1)

if __name__ == "__main__":
    {"fetch": fetch, "run": run}[sys.argv[1]]()
