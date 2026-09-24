#!/usr/bin/env python3
"""Wide screen engine. Rank-partial Spearman between predictor X and outcome Y, adjusted for
covariates, with a within-chromosome circular-shift null of X.

discovery: odd autosomes, every (X, Y) pair in the config minus excluded pairs; writes the
  survivor list (pairs passing the selection rule) and ONLY counts to stdout.
confirm:   even autosomes, only the frozen survivor list; one-sided test in the discovery sign.
"""
import argparse, hashlib, json, sys
from pathlib import Path
import numpy as np
from scipy.stats import rankdata

def load(path):
    rows = [l.rstrip("\n").split("\t") for l in open(path)]
    h, rows = rows[0], rows[1:]
    chrom = np.array([r[1] for r in rows])
    cols = {c: np.array([float(r[i]) for r in rows]) for i, c in enumerate(h) if i >= 3}
    return chrom, cols

def half(chrom, which):
    num = np.array([int(c[3:]) for c in chrom])
    return (num % 2 == 1) if which == "odd" else (num % 2 == 0)

def resid(v, Z):
    if Z is None: return v - v.mean()
    beta, *_ = np.linalg.lstsq(Z, v, rcond=None)
    return v - Z @ beta

def partial_rho(x, y, Z):
    rx, ry = resid(x, Z), resid(y, Z)
    d = np.sqrt((rx @ rx) * (ry @ ry))
    return float(rx @ ry / d) if d > 0 else float("nan")

MIN_SHIFT = 10  # tiles; avoids near-identity shifts (review minor)

def shift_within(x, chrom, rng, min_shift=MIN_SHIFT):
    out = x.copy()
    for c in np.unique(chrom):
        idx = np.flatnonzero(chrom == c); L = len(idx)
        if L > 2 * min_shift: out[idx] = np.roll(x[idx], rng.integers(min_shift, L - min_shift + 1))
        elif L > 2: out[idx] = np.roll(x[idx], rng.integers(1, L))
    return out

def test_pair(x, y, covs, chrom, n_shift, seed):
    ok = np.isfinite(x) & np.isfinite(y)
    for z in covs: ok &= np.isfinite(z)
    x, y, ch = rankdata(x[ok]), rankdata(y[ok]), chrom[ok]
    Z = np.column_stack([np.ones(ok.sum())] + [rankdata(z[ok]) for z in covs])
    ry = resid(y, Z)
    def stat(xx):
        rx = resid(xx, Z); d = np.sqrt((rx @ rx) * (ry @ ry))
        return float(rx @ ry / d) if d > 0 else float("nan")
    obs = stat(x)
    rng = np.random.default_rng(seed)
    null = np.array([stat(shift_within(x, ch, rng)) for _ in range(n_shift)])
    p_neg = (1 + (null <= obs).sum()) / (1 + n_shift)
    p_pos = (1 + (null >= obs).sum()) / (1 + n_shift)
    return {"n": int(ok.sum()), "rho": obs, "p_neg": float(p_neg), "p_pos": float(p_pos),
            "null_sd": float(null.std())}

def pairs_from(cfg):
    ex = {frozenset(p) for p in cfg["excluded_pairs"]}
    same = cfg.get("same_source_groups", [])
    def same_src(a, b): return any(a in g and b in g for g in same)
    out, seen = [], set()
    for y in cfg["outcomes"]:
        for x in cfg["predictors"]:
            key = frozenset((x, y))
            if x == y or key in ex or same_src(x, y) or key in seen: continue
            seen.add(key); out.append((x, y))
    return out  # unordered pairs tested once (rank-partial rho is symmetric)

def pair_covariates(cfg, x, y):
    """base covariates minus the pair's own features, plus feature-specific extras (e.g. the
    WT baseline PC1 for a KO-minus-WT delta), again minus the pair's own features."""
    names = list(cfg["covariates"])
    for f in (x, y):
        names += cfg.get("feature_extra_covariates", {}).get(f, [])
    out = []
    for c in names:
        if c not in (x, y) and c not in out: out.append(c)
    return out

def sha_path(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["discovery", "confirm"])
    ap.add_argument("--features", required=True); ap.add_argument("--config", required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--survivors")
    a = ap.parse_args()
    cfg = json.load(open(a.config)); chrom, cols = load(a.features)
    sel = cfg["selection"]; conf = cfg["confirmation"]
    res = []
    if a.mode == "discovery":
        m = half(chrom, "odd")
        for k, (x, y) in enumerate(pairs_from(cfg)):
            cn = pair_covariates(cfg, x, y); covs = [cols[c][m] for c in cn]
            r = test_pair(cols[x][m], cols[y][m], covs, chrom[m], sel["n_shift"], sel["seed"] + k)
            r["covariates"] = cn
            p = min(r["p_neg"], r["p_pos"])
            r.update({"predictor": x, "outcome": y, "sign": -1 if r["rho"] < 0 else 1,
                      "selected": bool(r["n"] >= sel["min_n"] and abs(r["rho"]) >= sel["min_abs_rho"] and p <= sel["p_max"])})
            res.append(r)
        surv = [{"predictor": r["predictor"], "outcome": r["outcome"], "sign": r["sign"]} for r in res if r["selected"]]
        all_path = str(Path(a.out).with_name(Path(a.out).stem + "-all.json"))
        json.dump({"schema": "bio.wide-screen-discovery-all.v1", "all": res}, open(all_path, "w"), indent=1)
        json.dump({"schema": "bio.wide-screen-discovery.v2", "config_sha256": sha_path(a.config),
                   "features_sha256": sha_path(a.features), "all_sha256": sha_path(all_path),
                   "n_pairs": len(res), "survivors": surv}, open(a.out, "w"), indent=1)
        print(f"pairs tested {len(res)}; survivors {len(surv)}")
    else:
        pre_p = Path(a.config).resolve().parent / "freeze-pre-discovery.json"
        if pre_p.exists():
            pre = json.load(open(pre_p))["sha256"]
            if pre.get("code/screen.py") not in (None, sha_path(__file__)): sys.exit("refusing: screen.py changed since freeze")
        fz = json.load(open(Path(a.config).resolve().parent / "freeze-survivors.json"))["sha256"]
        if fz["results/discovery.json"] != sha_path(a.survivors): sys.exit("refusing: survivor list differs from its freeze")
        d = json.load(open(a.survivors))
        if d["config_sha256"] != sha_path(a.config) or d["features_sha256"] != sha_path(a.features):
            sys.exit("refusing: config or features differ from discovery")
        surv = d["survivors"]; k = max(1, len(surv))
        m = half(chrom, "even")
        for j, s in enumerate(surv):
            x, y = s["predictor"], s["outcome"]
            cn = pair_covariates(cfg, x, y); covs = [cols[c][m] for c in cn]
            r = test_pair(cols[x][m], cols[y][m], covs, chrom[m], conf["n_shift"], conf["seed"] + j)
            r["covariates"] = cn
            p = r["p_neg"] if s["sign"] < 0 else r["p_pos"]
            r.update({"predictor": x, "outcome": y, "sign": s["sign"], "p_directional": p,
                      "confirmed": bool(r["n"] >= conf["min_n"] and s["sign"] * r["rho"] >= conf["min_abs_rho"] and p <= conf["alpha"] / k)})
            res.append(r)
        json.dump({"schema": "bio.wide-screen-confirmation.v1", "survivors_sha256": hashlib.sha256(open(a.survivors, "rb").read()).hexdigest(),
                   "bonferroni_k": k, "results": res}, open(a.out, "w"), indent=1)
        print(f"survivors tested {len(res)}; confirmed {sum(r['confirmed'] for r in res)}")

if __name__ == "__main__":
    main()
