#!/usr/bin/env python3
"""Second registered holdout for GC-correlated same-condition library variation
(libvar2/protocol.json): GSE181693 mouse ESC LMNB1 pA-DamID, 46 same-condition pairs.
'fetch' after freeze (all tracks first-receipt), then 'run'. Reuses libvar/ machinery."""
import hashlib, json, sys, urllib.request, warnings
from pathlib import Path
import numpy as np
warnings.filterwarnings("ignore", category=RuntimeWarning)
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "libvar")); import libvar as V
P = json.load(open(ROOT / "libvar2/protocol.json"))
D = ROOT / "libvar2/data"
FEATS = ROOT / "libvar/features/mm10_tiles.tsv"
ARMS = (("raw", 0), ("scale_free", 100))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def fetch():
    fz = json.load(open(ROOT / "libvar2/freeze.json"))
    assert fz["sha256"]["libvar2/protocol.json"] == sha(ROOT / "libvar2/protocol.json")
    cfg = P["cohorts"]["esc"]; rec = {}
    for k, f in cfg["files"].items():
        gsm = f.split("_")[0]; prefix = gsm[:-3] + "nnn"
        dest = D / f
        if not dest.exists():
            part = dest.with_name(f + ".part")
            urllib.request.urlretrieve(cfg["url_template"].format(prefix=f"{prefix}/{gsm}", file=f), part)
            part.replace(dest)
        rec[f"esc:{k}"] = {"file": f, "dir": cfg["dir"], "bytes": dest.stat().st_size, "sha256": sha(dest)}
        print(k, rec[f"esc:{k}"]["bytes"], flush=True)
    json.dump({"freeze_sha256": sha(ROOT / "libvar2/freeze.json"), "files": rec},
              open(ROOT / "libvar2/intake.json", "w"), indent=1)

def pooled_label(res):
    raw = {k: v["raw"] for k, v in res.items()}
    absr = {k: abs(v["rho"]) for k, v in raw.items()}
    med = float(np.median(list(absr.values())))
    p1 = float(np.mean([v >= 0.10 for v in absr.values()])) >= 0.60
    elig = [v for k, v in res.items() if abs(v["raw"]["rho"]) >= 0.05]
    ratio = float(np.median([abs(v["scale_free"]["rho"]) / abs(v["raw"]["rho"]) for v in elig])) if elig else None
    p2 = len(elig) >= 4 and ratio >= 0.5
    p3 = med >= P["registered_predictions"]["benchmark_median"] / 3
    gmed = {g: float(np.median([absr[k] for k in ks]))
            for g, ks in P["generality_groups"].items() if g != "note"}
    passing = {g for g, m in gmed.items() if m >= 0.05}
    p4 = len(passing) >= 4 and len({g.split("_")[0] for g in passing}) >= 2
    lab = "SYSTEMATIC" if (p1 and p2 and p3 and p4) else "PARTIAL" if (p1 and p2 and p3) else "NOT_SUPPORTED"
    return lab, {"median_abs_rho": med, "frac_abs_ge_0.10": float(np.mean([v >= 0.10 for v in absr.values()])),
                 "n_p2_eligible": len(elig), "p2_median_ratio": ratio, "group_medians": gmed,
                 "p1": p1, "p2": p2, "p3": p3, "p4": p4}

def cond_class(k):
    if any(t in k for t in ("_dmso", "_eed", "_gsk")): return "drug_control"
    if "_0h" in k or k.endswith("0h"): return "untreated_0h"
    return "iaa_treated"

def run():
    fz = json.load(open(ROOT / "libvar2/freeze.json"))
    for f, h in fz["sha256"].items(): assert sha(ROOT / f) == h, f"changed since freeze: {f}"
    it = json.load(open(ROOT / "libvar2/intake.json"))
    assert it["freeze_sha256"] == sha(ROOT / "libvar2/freeze.json")
    cfg = P["cohorts"]["esc"]
    files = {k: D / f for k, f in cfg["files"].items()}
    for ck, r in it["files"].items():
        assert sha(D / r["file"]) == r["sha256"], f"data changed since intake: {ck}"
    for k, f in files.items():
        if not f.exists(): sys.exit(f"ABORT (no label): missing file {f.name}")
        if not V.check_build(f, cfg["chr1"]): sys.exit(f"ABORT (no label): chr1 length is not mm10 in {f.name}")
    chrom, start, end, cols = V.load_features(FEATS)
    gc, tss = cols["gc"], cols["tss_count"]
    t = {k: V.tile_values(f, chrom, start, end, 0.5) for k, f in files.items()}; cov = 0.5
    if min(int(np.isfinite(v).sum()) for v in t.values()) < 3500:
        t = {k: V.tile_values(f, chrom, start, end, 0.1) for k, f in files.items()}; cov = 0.1
    res = {}
    mine = {k: (v["a"], v["b"]) for k, v in P["pairs"].items()}
    for arm, off in ARMS:
        tt = {k: V.zscore(v) for k, v in t.items()} if arm == "scale_free" else t
        r = V.run_pairs(mine, tt, gc, tss, chrom, 20263101 + off, P["min_n_per_test"])
        for k, v in r.items(): res.setdefault(k, {})[arm] = v
    xc = {}
    for i, (k, v) in enumerate(P["cross_condition_reported_only"].items()):
        r = V.pair_test(t[v["a"]], t[v["b"]], gc, tss, chrom, 20263301 + i)
        for key in ("rho", "slope_on_baseline"):
            if not np.isfinite(r[key]): r[key] = None
        xc[k] = r
    label, pooled = pooled_label(res)
    sds = {k: float(np.nanstd(v)) for k, v in t.items()}
    finite = {k: int(np.isfinite(v).sum()) for k, v in t.items()}
    out = {"pairs": res, "cross_condition": xc, "label": label, "pooled": pooled,
           "diagnostics": {"track_sd": sds, "finite_tiles": finite, "coverage_threshold": cov,
                           "sd_ratio": {k: round(max(sds[P["pairs"][k]["a"]], sds[P["pairs"][k]["b"]]) /
                                                min(sds[P["pairs"][k]["a"]], sds[P["pairs"][k]["b"]]), 4)
                                        for k in P["pairs"]},
                           "class_median_abs_rho": {c: float(np.median([abs(res[k]["raw"]["rho"])
                                                    for k in P["pairs"] if cond_class(k) == c]))
                                                    for c in ("untreated_0h", "iaa_treated", "drug_control")}}}
    for k in P["pairs"]:
        r = out["pairs"][k]
        print(f"{k:18s} raw {r['raw']['rho']:+.3f} (n {r['raw']['n']}) sf {r['scale_free']['rho']:+.3f}", flush=True)
    print("LABEL", label, json.dumps(pooled))
    json.dump(out, open(ROOT / "libvar2/results/result.json", "w"), indent=1)

if __name__ == "__main__":
    {"fetch": fetch, "run": run}[sys.argv[1]]()
