#!/usr/bin/env python3
"""GDSC2 discovery screen: per (context, drug) covariate-adjusted
association on LN_IC50, mirroring the depmap campaign machinery.

beta < 0 means marker+ => lower LN_IC50 => SENSITIVE. Registered selection
keeps sensitizing associations only (beta <= -SEL_BETA with shrunken lower
bound, BH q <= SEL_Q), requires the drug to match PRISM via inchikey1, and
caps contexts per drug. Placebo seeds permute context labels within
lineage strata.
"""
import json, os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import campaign as C

ST = C.ST
CX = C.CX

SEL_BETA = 0.35          # |LN_IC50| shift; >= the depmap campaign's 0.30
SEL_Q = 0.01
MIN_POS = 8              # sensitive-biomarker positives per drug-arm
MIN_NEG = 8
MIN_N = 40               # models with a fitted curve for this drug
MAX_PER_DRUG = 6         # diversity cap
MAX_PREV = 0.6           # context prevalence cap
PRED = {"MUT_DAM": ("OmicsSomaticMutationsMatrixDamaging.csv",
                    lambda a: a > 0),
        "MUT_HOT": ("OmicsSomaticMutationsMatrixHotspot.csv",
                    lambda a: a > 0),
        "DEL": ("OmicsAbsoluteCNGene.csv", lambda a: a < CX.DEEP_DEL_CN),
        "EXPR_LOW": ("OmicsExpressionProteinCodingGenesTPMLogp1.csv",
                     lambda a: a < CX.EXPR_LOW)}


def candidate_contexts(models):
    """All KIND:GENE passing the prevalence window on mapped models."""
    out = []
    n = len(models)
    for kind, (fn, pred) in PRED.items():
        df = pd.read_csv(f"{C.DD}/{fn}", index_col=0)
        df = df.reindex(models)
        vals = df.to_numpy(dtype=float)
        ctx = pred(vals)
        npos = (ctx == 1).sum(0) if ctx.dtype != bool else ctx.sum(0)
        nnan = np.isnan(vals).all(0)
        npos = np.where(nnan, 0, npos)
        nneg = np.where(nnan, 0, (ctx == 0).sum(0)
                        if ctx.dtype != bool else (~ctx).sum(0))
        ok = (npos >= MIN_POS) & (npos <= MAX_PREV * n) & (nneg >= MIN_POS)
        out += [f"{kind}:{str(g).split(' ')[0]}" for g in df.columns[ok]]
        del df, vals, ctx
    return out


def lineage_shuffle(x, lin, seed):
    xp = x.copy()
    rng = np.random.default_rng(int(seed))
    pos = np.arange(len(lin))
    for _, idx in pd.Series(pos).groupby(pd.Series(lin).fillna("U")):
        sh = xp[idx.to_numpy()].copy()
        rng.shuffle(sh)
        xp[idx.to_numpy()] = sh
    return xp


def arm_screen(placebo=None):
    """Vectorized screen: one residual regression per
    (drug-finite-mask x source-profile-mask) group covering all contexts.

    The math matches stats.associate: Q from the covariate basis,
    residualized X and Y, beta = sxy/sxx, t from clipped partial r.
    Context unprofiled-NaN is constant within each omics source file, so
    group masks are drug-mask ∩ source-profile-mask - fixed rows per
    (group, kind), letting all contexts in a kind share one matmul."""
    import stats as _S
    from scipy.stats import t as spt

    z = np.load(f"{C.PREP}/gdsc2.npz", allow_pickle=False)
    ic50 = pd.DataFrame(z["ic50"], index=z["models"], columns=z["drugs"])
    models = list(ic50.index)
    lin = pd.read_csv(f"{C.DD}/Model.csv",
                      index_col=0).OncotreeLineage.reindex(models).to_numpy()
    Z = CX.covariates_for(models)
    contexts = candidate_contexts(models)
    ctx_df = CX.build(contexts, models)     # models x contexts
    X_all = ctx_df.to_numpy(dtype=float).T  # contexts x models
    kind_of = np.array([c.split(":")[0] for c in contexts])
    Y = ic50.to_numpy(dtype=float)
    fin = np.isfinite(Y)

    # profiled-models mask per context kind (x is NaN only on unprofiled)
    prof = {}
    for kind in PRED:
        idx = np.where(kind_of == kind)[0]
        if len(idx):
            prof[kind] = np.isfinite(X_all[idx[0]])  # constant within kind
    # group drug columns by identical missingness
    mask_groups = {}
    for j in range(Y.shape[1]):
        mask_groups.setdefault(fin[:, j].tobytes(), []).append(j)

    if placebo is not None:
        # one global lineage-stratified permutation per context column
        rng = np.random.default_rng(int(placebo))
        strata = pd.Series(lin).fillna("U").to_numpy()
        X_perm = X_all.copy()
        for i in range(X_perm.shape[0]):
            row = X_perm[i]
            for s in np.unique(strata):
                idx = np.nonzero((strata == s) & np.isfinite(row))[0]
                sub = row[idx].copy()
                rng.shuffle(sub)
                row[idx] = sub
            X_perm[i] = row
        X_all = X_perm

    rows = []
    for kind in PRED:
        if kind not in prof:
            continue
        ctx_idx = np.where(kind_of == kind)[0]
        Xk = X_all[ctx_idx]                 # ctxs x models
        pm = prof[kind]
        for cols in mask_groups.values():
            m = fin[:, cols[0]] & pm        # drug-mask ∩ source-profiled
            n_j = int(m.sum())
            if n_j < MIN_N:
                continue
            Zc = Z[m]
            keep = Zc.std(axis=0) > 0
            keep[0] = True
            Zc = Zc[:, keep]
            try:
                Qc, rank = ST.basis(Zc)
            except (ValueError, np.linalg.LinAlgError):
                continue
            df = n_j - rank - 1
            if df < 10:
                continue
            Ym = Y[m][:, cols]
            Yres = Ym - Qc @ (Qc.T @ Ym)
            syy = np.einsum("ij,ij->j", Yres, Yres)
            Xm = Xk[:, m]                   # ctxs x group models
            # placebo permutation already applied globally above
            # residualize each context column-block on the group covariates
            Xres = Xm - (Qc @ (Qc.T @ Xm.T)).T
            sxx = np.einsum("ij,ij->i", Xres, Xres)
            Xd = Xm - Xm.mean(axis=1, keepdims=True)
            sxx_raw = np.einsum("ij,ij->i", Xd, Xd)
            npos = (Xm == 1).sum(1)
            nneg = (Xm == 0).sum(1)
            ok_ctx = (npos >= MIN_POS) & (nneg >= MIN_NEG) & (
                sxx > np.maximum(_S.IDENT_FRAC * sxx_raw, _S.IDENT_ABS))
            for ci in np.nonzero(ok_ctx)[0]:
                sxy = Yres.T @ Xres[ci]
                with np.errstate(divide="ignore", invalid="ignore"):
                    beta = sxy / sxx[ci]
                    rr = sxy / np.sqrt(sxx[ci] * syy)
                rr = np.clip(np.nan_to_num(rr, nan=0.0),
                             -0.999999, 0.999999)
                t = rr * np.sqrt(df / (1.0 - rr ** 2))
                pp = 2.0 * spt.sf(np.abs(t), df)
                resvar = np.maximum(syy - beta * beta * sxx[ci], 0.0) / df
                se = np.sqrt(resvar / sxx[ci])
                for k, jj in enumerate(cols):
                    if not np.isfinite(se[k]):
                        continue
                    rows.append({"context": contexts[ctx_idx[ci]],
                                 "drug": ic50.columns[jj],
                                 "beta": float(beta[k]), "r": float(rr[k]),
                                 "se": float(se[k]),
                                 "beta_lb": float(abs(beta[k])
                                                  - 1.96 * se[k]),
                                 "p": float(pp[k]), "n_models": n_j,
                                 "df": int(df)})
    return pd.DataFrame(rows)


def select(cand):
    """Registered selection."""
    c = cand.copy()
    if not len(c):
        return c
    c["q"] = ST.bh_qvalues(c.p.to_numpy())
    cw = json.load(open(f"{C.PREP}/drug_crosswalk.json"))
    matchable = {d for d, v in cw.items() if v["prism_broad_ids"]}
    c = c[(c.beta <= -SEL_BETA) & (c.beta_lb > 0)
          & (c.q <= SEL_Q) & c.drug.isin(matchable)]
    c = c.sort_values("beta").groupby("drug").head(MAX_PER_DRUG)
    return c.sort_values(["drug", "beta"]).reset_index(drop=True)


def main():
    placebo = None
    if "--placebo" in sys.argv:
        placebo = sys.argv[sys.argv.index("--placebo") + 1]
    cand = arm_screen(placebo)
    tag = f".placebo{placebo}" if placebo else ""
    os.makedirs(C.OUT, exist_ok=True)
    cand.to_csv(f"{C.OUT}/candidates{tag}.csv", index=False)
    sel = select(cand)
    sel.to_csv(f"{C.OUT}/selection{tag}.csv", index=False)
    print(json.dumps({"contexts_screened": cand.context.nunique()
                      if len(cand) else 0,
                      "candidate_events": len(cand),
                      "selected": len(sel)}, indent=1))


if __name__ == "__main__":
    main()
