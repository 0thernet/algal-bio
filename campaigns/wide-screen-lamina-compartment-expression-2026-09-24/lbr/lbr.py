#!/usr/bin/env python3
"""Fresh-cohort test of the LBR sign reversal (lbr/protocol.json). 'fetch' after freeze, then 'run'."""
import hashlib, json, sys, urllib.request, warnings
from pathlib import Path
import numpy as np
from scipy.stats import rankdata, spearmanr
warnings.filterwarnings("ignore", category=RuntimeWarning)
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code")); import screen as S
sys.path.insert(0, str(ROOT / "panel")); from panel import tile_track
P = json.load(open(ROOT / "lbr/protocol.json"))
D = ROOT / "lbr/data"
PRIM, PLAC, FLAT = ("P_r13", "P_r14"), ("PL_batch", "PL_st"), ("FL_r13", "FL_r14")
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def fetch():
    fz = json.load(open(ROOT / "lbr/freeze.json"))
    assert fz["sha256"]["lbr/protocol.json"] == sha(ROOT / "lbr/protocol.json")
    rec = {}
    for k, f in P["samples"].items():
        dest = D / f
        if not dest.exists():
            part = dest.with_name(f + ".part")
            urllib.request.urlretrieve(P["url_template"].format(gsm=f.split("_")[0], file=f), part); part.replace(dest)
        rec[k] = {"file": f, "bytes": dest.stat().st_size, "sha256": sha(dest)}
        print(k, rec[k]["bytes"], flush=True)
    json.dump({"freeze_sha256": sha(ROOT / "lbr/freeze.json"), "files": rec}, open(ROOT / "lbr/intake.json", "w"), indent=1)

def quantile_map(src, ref):
    """Rank-preserving map of src onto the empirical distribution of ref (tiles finite in both)."""
    out = np.full_like(src, np.nan); m = np.isfinite(src) & np.isfinite(ref)
    r = (rankdata(src[m]) - 0.5) / m.sum()
    out[m] = np.quantile(ref[m], r)
    return out

def flex_basis(b):
    """[u, u^2, u^3, (u-q)_+^3 at quartiles], u = rank(b)/n - 0.5 over finite b; NaN elsewhere."""
    m = np.isfinite(b); u = np.full_like(b, np.nan); u[m] = rankdata(b[m]) / m.sum() - 0.5
    q = np.quantile(u[m], [0.25, 0.5, 0.75])
    cols = [u, u ** 2, u ** 3] + [np.where(np.isfinite(u), np.clip(u - k, 0, None) ** 3, np.nan) for k in q]
    return cols

def test_design(x, y, tss, base_cols, chrom, n_shift, seed):
    """test_pair with prebuilt (not re-ranked) baseline columns; tss is ranked as in screen.test_pair."""
    ok = np.isfinite(x) & np.isfinite(y) & np.isfinite(tss)
    for c in base_cols: ok &= np.isfinite(c)
    xr, yr, ch = rankdata(x[ok]), rankdata(y[ok]), chrom[ok]
    Z = np.column_stack([np.ones(ok.sum()), rankdata(tss[ok])] + [c[ok] for c in base_cols])
    ry = S.resid(yr, Z)
    def stat(xx):
        rx = S.resid(xx, Z); d = np.sqrt((rx @ rx) * (ry @ ry))
        return float(rx @ ry / d) if d > 0 else float("nan")
    obs = stat(xr); rng = np.random.default_rng(seed)
    null = np.array([stat(S.shift_within(xr, ch, rng)) for _ in range(n_shift)])
    return {"n": int(ok.sum()), "rho": obs, "p_neg": float((1 + (null <= obs).sum()) / (1 + n_shift)),
            "p_pos": float((1 + (null >= obs).sum()) / (1 + n_shift)), "null_sd": float(null.std())}

def label(r):
    prim = [r[k] for k in PRIM]
    ok = all(x["rho"] >= 0.05 and x["p_pos"] <= 0.01 for x in prim)
    opp = all(x["rho"] <= -0.05 and x["p_neg"] <= 0.01 for x in prim)
    m = np.mean([x["rho"] for x in prim])
    plac = all(abs(r[k]["rho"]) < 0.5 * m for k in PLAC)
    flat = all(r[k]["rho"] < 0.5 * m for k in FLAT)
    if ok and plac and flat: return "SUPPORTED"
    if ok and plac: return "FLATTENING_EXPLAINED"
    if ok: return "DIRECTION_ONLY"
    return "OPPOSITE" if opp else "NOT_SUPPORTED"

def final_label(lin, flex):
    if lin == flex == "SUPPORTED": return "SUPPORTED"
    if lin == "SUPPORTED": return "NOT_ROBUST_TO_ADJUSTMENT"
    return lin

def tests_for(t):
    B = (t["ST_r6"] + t["ST_r7"]) / 2; W = (t["WT_r13"] + t["WT_r14"]) / 2
    d = {"P_r13": (t["LBRKO_r13"] - t["WT_r13"], B), "P_r14": (t["LBRKO_r14"] - t["WT_r14"], B),
         "PL_batch": (t["WT_r13"] - t["WT_r14"], B), "PL_st": (t["ST_r6"] - t["ST_r7"], W),
         "FL_r13": (quantile_map(t["WT_r14"], t["LBRKO_r13"]) - t["WT_r13"], B),
         "FL_r14": (quantile_map(t["WT_r13"], t["LBRKO_r14"]) - t["WT_r14"], B)}
    for k in ("T2B_r13", "T2B_r14"): d[k] = (t["WT_" + k] - t["WT_" + k[-3:]], B)
    for k in ("LBRKO_T2B_r13", "LBRKO_T2B_r14"): d[k] = (t[k] - t["WT_" + k[-3:]], B)
    return d

def noise_matched(sim, wt, ko, seed):
    """sim + N(0, s^2), s by bisection so Spearman(sim', wt) matches Spearman(ko, wt) over tiles finite in all."""
    m = np.isfinite(sim) & np.isfinite(wt) & np.isfinite(ko)
    target = spearmanr(ko[m], wt[m])[0]
    e = np.random.default_rng(seed).normal(size=sim.size); sd = np.nanstd(sim[m])
    lo, hi = 0.0, 20.0 * sd
    for _ in range(40):
        mid = (lo + hi) / 2
        if spearmanr(sim[m] + mid * e[m], wt[m])[0] > target: lo = mid
        else: hi = mid
    return sim + (lo + hi) / 2 * e, float((lo + hi) / 2), float(target)

def run():
    import pyBigWig
    fz = json.load(open(ROOT / "lbr/freeze.json"))
    for f, h in fz["sha256"].items(): assert sha(ROOT / f) == h, f"changed since freeze: {f}"
    it = json.load(open(ROOT / "lbr/intake.json"))
    assert it["freeze_sha256"] == sha(ROOT / "lbr/freeze.json")
    for k, r in it["files"].items(): assert sha(D / r["file"]) == r["sha256"], f"data changed since intake: {k}"
    rows = [l.rstrip("\n").split("\t") for l in open(ROOT / "features/tiles.tsv")][1:]
    chrom = np.array([r[1] for r in rows]); start = np.array([int(r[2]) for r in rows])
    _, cols = S.load(ROOT / "features/tiles.tsv")
    for f in P["samples"].values():
        L = pyBigWig.open(str(D / f)).chroms(); c1 = L.get("chr1", L.get("1"))
        if c1 != 248956422: sys.exit(f"ABORT (no label): chr1 length {c1} in {f}")
    t = {k: tile_track(D / f, chrom, start) for k, f in P["samples"].items()}
    tss, gc = cols["tss_count"], cols["gc"]
    ok = np.all([np.isfinite(v) for v in t.values()], axis=0)
    diag = {"sd": {k: float(np.nanstd(v)) for k, v in t.items()},
            "spearman": {f"{a}~{b}": float(spearmanr(t[a][ok], t[b][ok])[0]) for a, b in
                         [("WT_r13", "WT_r14"), ("WT_r13", "ST_r6"), ("WT_r13", "ST_r7"), ("WT_r14", "ST_r6"), ("WT_r14", "ST_r7"), ("ST_r6", "ST_r7"),
                          ("LBRKO_r13", "LBRKO_r14"), ("WT_r13", "LBRKO_r13"), ("WT_r14", "LBRKO_r14")]}}
    out = {"diagnostics": diag}
    tests = tests_for(t)
    B = (t["ST_r6"] + t["ST_r7"]) / 2
    for j, (b, o) in enumerate((("r13", "r14"), ("r14", "r13"))):
        sim, sd, target = noise_matched(quantile_map(t["WT_" + o], t["LBRKO_" + b]), t["WT_" + b], t["LBRKO_" + b], 20261201 + j)
        tests["FLn_" + b] = (sim - t["WT_" + b], B); diag["FLn_" + b] = {"added_sd": sd, "target_spearman": target}
    for arm, off in (("linear", 0), ("flexible", 100)):
        res = {}
        for i, (k, (y, b)) in enumerate(tests.items()):
            seed = 20261101 + i + off
            r = S.test_pair(gc, y, [tss, b], chrom, 5000, seed) if arm == "linear" else test_design(gc, y, tss, flex_basis(b), chrom, 5000, seed)
            if r["n"] < P["min_n_per_test"] or not np.isfinite(r["rho"]): sys.exit(f"ABORT (no label): {arm} {k} n {r['n']}")
            m = np.isfinite(y) & np.isfinite(b); r["slope_on_baseline"] = float(np.polyfit(b[m], y[m], 1)[0])
            res[k] = r
            print(f"{arm:<9} {k:<14} rho {r['rho']:+.3f} n {r['n']} p- {r['p_neg']:.4f} p+ {r['p_pos']:.4f} slope {r['slope_on_baseline']:+.3f}", flush=True)
        res["label"] = label(res); out[arm] = res
    out["label"] = final_label(out["linear"]["label"], out["flexible"]["label"])
    print("diagnostics", json.dumps(diag))
    print("LABEL", out["label"], "(linear", out["linear"]["label"], "/ flexible", out["flexible"]["label"] + ")")
    json.dump(out, open(ROOT / "lbr/results/result.json", "w"), indent=1)

if __name__ == "__main__":
    {"fetch": fetch, "run": run}[sys.argv[1]]()
