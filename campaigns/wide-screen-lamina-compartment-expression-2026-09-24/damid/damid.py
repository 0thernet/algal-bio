#!/usr/bin/env python3
"""Fresh-cohort replication (damid/protocol.json). 'fetch' after freeze, then 'run'."""
import hashlib, json, sys, urllib.request, warnings
from pathlib import Path
import numpy as np
warnings.filterwarnings("ignore", category=RuntimeWarning)
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code")); import screen as S
sys.path.insert(0, str(ROOT / "panel")); from panel import tile_track
P = json.load(open(ROOT / "damid/protocol.json"))
D = ROOT / "damid/data"
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def fetch():
    fz = json.load(open(ROOT / "damid/freeze.json"))
    assert fz["sha256"]["damid/protocol.json"] == sha(ROOT / "damid/protocol.json")
    rec = {}
    for k, f in P["samples"].items():
        dest = D / f
        if not dest.exists():
            part = dest.with_name(f + ".part")
            urllib.request.urlretrieve(P["url_template"].format(gsm=f.split("_")[0], file=f), part); part.replace(dest)
        rec[k] = {"file": f, "bytes": dest.stat().st_size, "sha256": sha(dest)}
        print(k, rec[k]["bytes"], flush=True)
    json.dump({"freeze_sha256": sha(ROOT / "damid/freeze.json"), "files": rec}, open(ROOT / "damid/intake.json", "w"), indent=1)

def label(r):
    prim = [r["P_batch"], r["P_all"]]
    ok = all(x["rho"] <= -0.05 and x["p_neg"] <= 0.01 for x in prim)
    opp = all(x["rho"] >= 0.05 and x["p_pos"] <= 0.01 for x in prim)
    bound = 0.5 * np.mean([abs(x["rho"]) for x in prim])
    plac = all(abs(r[k]["rho"]) < bound for k in ("PL_within", "PL_cross"))
    return "REPLICATED" if ok and plac else "DIRECTION_ONLY" if ok else "OPPOSITE" if opp else "NOT_REPLICATED"

def run():
    import pyBigWig
    fz = json.load(open(ROOT / "damid/freeze.json"))
    for f, h in fz["sha256"].items(): assert sha(ROOT / f) == h, f"changed since freeze: {f}"
    rows = [l.rstrip("\n").split("\t") for l in open(ROOT / "features/tiles.tsv")][1:]
    chrom = np.array([r[1] for r in rows]); start = np.array([int(r[2]) for r in rows])
    _, cols = S.load(ROOT / "features/tiles.tsv")
    for f in P["samples"].values():
        L = pyBigWig.open(str(D / f)).chroms(); c1 = L.get("chr1", L.get("1"))
        if c1 != 248956422: sys.exit(f"ABORT (no label): chr1 length {c1} in {f}")
    t = {k: tile_track(D / f, chrom, start) for k, f in P["samples"].items()}
    tss, gc = cols["tss_count"], cols["gc"]
    def z(v): return (v - np.nanmean(v)) / np.nanstd(v)
    def tests_for(t):
        wt12 = (t["WT_r1"] + t["WT_r2"]) / 2; ko = (t["LMNAKO_r1"] + t["LMNAKO_r2"]) / 2
        return {"P_batch": (t["LMNAKO_r2"] - t["WT_r3"], wt12), "P_all": (ko - wt12, t["WT_r3"]),
                "PL_within": (t["WT_r1"] - t["WT_r2"], t["WT_r3"]), "PL_cross": (t["WT_r3"] - t["WT_r1"], t["WT_r2"]),
                "LBR_batch": (t["LBRKO_r3"] - t["WT_r3"], wt12), "DKO_batch": (t["DKO_r2"] - t["WT_r3"], wt12)}
    out = {"diagnostics": {"sd": {k: float(np.nanstd(v)) for k, v in t.items()}}}
    from scipy.stats import spearmanr
    ok = np.all([np.isfinite(v) for v in t.values()], axis=0)
    out["diagnostics"]["replicate_spearman"] = {f"{a}~{b}": float(spearmanr(t[a][ok], t[b][ok])[0]) for a, b in
        [("WT_r1", "WT_r2"), ("WT_r1", "WT_r3"), ("WT_r2", "WT_r3"), ("LMNAKO_r1", "LMNAKO_r2")]}
    for arm, tt, off in [("raw", t, 0), ("scale_free", {k: z(v) for k, v in t.items()}, 100)]:
        res = {}
        for i, (k, (y, b)) in enumerate(tests_for(tt).items()):
            r = S.test_pair(gc, y, [tss, b], chrom, 5000, 20261010 + i + off)
            if r["n"] < P["min_n_per_test"] or not np.isfinite(r["rho"]): sys.exit(f"ABORT (no label): {arm} {k} n {r['n']}")
            m = np.isfinite(y) & np.isfinite(b); r["slope_on_baseline"] = float(np.polyfit(b[m], y[m], 1)[0])
            res[k] = r
            print(f"{arm:<10} {k:<10} rho {r['rho']:+.3f} n {r['n']} p- {r['p_neg']:.4f} p+ {r['p_pos']:.4f} slope {r['slope_on_baseline']:+.3f}", flush=True)
        res["label"] = label(res); out[arm] = res
    raw, sf = out["raw"]["label"], out["scale_free"]["label"]
    out["label"] = "REPLICATED" if raw == sf == "REPLICATED" else "NOT_ROBUST_TO_SCALE" if raw == "REPLICATED" else raw
    print("diagnostics", json.dumps(out["diagnostics"]))
    print("LABEL", out["label"], "(raw", raw, "/ scale-free", sf + ")")
    json.dump(out, open(ROOT / "damid/results/result.json", "w"), indent=1)

if __name__ == "__main__":
    {"fetch": fetch, "run": run}[sys.argv[1]]()
