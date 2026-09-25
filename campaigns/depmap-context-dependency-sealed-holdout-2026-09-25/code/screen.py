#!/usr/bin/env python3
"""Discovery screen: covariate-adjusted context -> dependency associations.

Runs on the Avana (AV) discovery models only. Writes the full association
summary and, under the registered selection rule, the candidate pair list that
the freeze binds before any sealed dependency data is opened.

  python code/screen.py real          # real contexts
  python code/screen.py placebo SEED  # contexts permuted within lineage
"""
import json, os, re, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stats as ST
import contexts as CX

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = f"{ROOT}/data/depmap24q4"
PREP = f"{ROOT}/data/prep"
OUT = f"{ROOT}/results"

# --- registered selection rule ---
MIN_ABS_BETA = 0.30      # adjusted gene-effect shift, Chronos units
MIN_BETA_LB = 0.20       # the 95% lower bound must itself clear two thirds of that,
                         # so a pair cannot be selected on an imprecise estimate alone
MAX_Q = 0.01             # BH q over every tested pair
STRATA = {"genetic": ("MUT_DAM", "MUT_HOT", "DEL", "SIG"), "expression": ("EXPR_LOW",)}
STRATUM_N = {"genetic": 50, "expression": 50}
MAX_PER_CONTEXT = 3      # diversity cap, applied to the correlation GROUP of a context
MAX_PER_DEP = 3          # diversity cap
KY_MIN_POS = 10          # context-positive KY (tier A) models required to select a pair
KY_ONLY_MIN_POS = 3      # context-positive KY-only models needed for a tier B test at all
KY_ONLY_POWERED = 6      # ... and for the primary tier B denominator
DEP_MIN_EXPR = 1.0       # the dependency gene must be expressed (median log2(TPM+1))
                         # in the context-positive models: an unexpressed gene's
                         # apparent dependency is the noise floor by construction
LB_Z = 1.96              # pairs are ranked by |beta| - LB_Z * SE, not by |beta|


def locus(loc):
    """'11q11' -> ('11', '11q', 11.0). Unparsable -> (None, None, None)."""
    if not isinstance(loc, str):
        return None, None, None
    m = re.match(r"^(\d+|X|Y)([pq])([\d.]*)", loc.strip())
    if not m:
        return None, None, None
    try:
        band = float(m.group(3)) if m.group(3) else None
    except ValueError:
        band = None
    return m.group(1), f"{m.group(1)}{m.group(2)}", band


def load():
    dep = np.load(f"{PREP}/dep.npz", allow_pickle=False)
    ctx = np.load(f"{PREP}/ctx.npz", allow_pickle=False)
    assert list(dep["models"]) == list(ctx["models"])
    return dep, ctx


def ky_prevalence(ctx_names):
    """Context-positive counts among KY screens' models.

    Uses the shared omics files only. The KY dependency matrix stays sealed.
    """
    smap = pd.read_csv(f"{D}/CRISPRScreenMap.csv")
    smap["lib"] = smap.ScreenID.str.extract(r"\.([A-Z]+)\d+$")
    libs = smap.groupby("ModelID").lib.agg(lambda s: set(s))
    ky_all = [m for m, v in libs.items() if "KY" in v]
    ky_only = [m for m, v in libs.items() if v == {"KY"}]
    names = sorted(set(ctx_names))
    Xa = CX.build(names, ky_all)
    Xo = CX.build(names, ky_only)
    out = {c: {"ky_all": int(np.nansum(Xa[c].to_numpy(dtype=float) == 1)),
               "ky_only": int(np.nansum(Xo[c].to_numpy(dtype=float) == 1))} for c in names}
    return out, len(ky_all), len(ky_only)


def dep_expression(models, genes):
    """Median log2(TPM+1) of each dependency gene, over a model list."""
    fn = "OmicsExpressionProteinCodingGenesTPMLogp1.csv"
    head = pd.read_csv(f"{D}/{fn}", nrows=0)
    colmap = {}
    for c in head.columns[1:]:
        colmap.setdefault(re.sub(r"\s*\(\d+\)$", "", c), c)
    want = [colmap[g] for g in genes if g in colmap]
    df = pd.read_csv(f"{D}/{fn}", index_col=0, usecols=[head.columns[0]] + want)
    df.columns = [re.sub(r"\s*\(\d+\)$", "", c) for c in df.columns]
    return df.reindex(models)


def run(mode, seed=None):
    dep, ctx = load()
    Y = dep["dep"]
    models = list(dep["models"])
    lineage = dep["lineage"]
    dep_genes = list(dep["genes"])
    X = ctx["ctx"]
    names = list(ctx["names"])
    kinds = list(ctx["kinds"])
    ctx_group = json.load(open(f"{PREP}/ctx_group.json"))
    Z = CX.covariates_for(models)          # the same design object as the confirmation run

    if mode == "placebo":
        rng = np.random.default_rng(int(seed))
        perm = ST.permute_within(lineage, rng)
        X = X[perm, :]

    gene = pd.read_csv(f"{D}/Gene.csv", low_memory=False)
    loc = {s: locus(l) for s, l in zip(gene.symbol, gene.location)}
    fam = {s: (g if isinstance(g, str) else None) for s, g in zip(gene.symbol, gene.gene_group)}

    rows = []
    for kind in ["MUT_DAM", "MUT_HOT", "DEL", "EXPR_LOW", "SIG"]:
        cols = [i for i, k in enumerate(kinds) if k == kind]
        if not cols:
            continue
        Xk = X[:, cols]
        mask = np.isfinite(Xk).all(axis=1)
        if kind == "SIG" or mask.sum() < 0.8 * len(models):
            for c in cols:                     # per-column coverage
                m = np.isfinite(X[:, c])
                b, r, p, se, df = ST.associate(Y[m], X[m][:, [c]], Z[m])
                rows.append((np.array([names[c]]), b, r, p, se, df, int(m.sum())))
            continue
        b, r, p, se, df = ST.associate(Y[mask], Xk[mask], Z[mask])
        rows.append((np.array([names[i] for i in cols]), b, r, p, se, df, int(mask.sum())))

    ctx_name = np.concatenate([x[0] for x in rows])
    beta = np.vstack([x[1] for x in rows])
    rr = np.vstack([x[2] for x in rows])
    pp = np.vstack([x[3] for x in rows])
    sse = np.vstack([x[4] for x in rows])
    n_used = np.concatenate([np.full(len(x[0]), x[6]) for x in rows])
    df_used = np.concatenate([np.full(len(x[0]), x[5]) for x in rows])

    q = ST.bh_qvalues(pp).reshape(pp.shape)
    tested = pp.size

    cand = (np.abs(beta) >= MIN_ABS_BETA) & (np.abs(beta) - LB_Z * sse >= MIN_BETA_LB) & (q <= MAX_Q)
    ci, di = np.where(cand)
    cand_rows = []
    for i, j in zip(ci, di):
        cname = ctx_name[i]
        ckind, cgene = cname.split(":", 1)
        dgene = dep_genes[j]
        if ckind != "SIG" and cgene == dgene:
            continue
        cchr, carm, cband = loc.get(cgene, (None, None, None)) if ckind != "SIG" else (None, None, None)
        dchr, darm, dband = loc.get(dgene, (None, None, None))
        # Fail closed: if either locus cannot be parsed the pair cannot be shown
        # to be distant, so it is treated as proximal and kept out of the pool.
        if ckind == "SIG":
            same_chrom = same_arm = False
            unknown_locus = False
        else:
            unknown_locus = cchr is None or dchr is None
            same_chrom = bool(unknown_locus or cchr == dchr)
            same_arm = bool(unknown_locus or carm == darm)
        cand_rows.append({
            "context": cname, "context_kind": ckind, "context_gene": None if ckind == "SIG" else cgene,
            "ctx_group": ctx_group.get(cname, cname),
            "dep_gene": dgene, "beta": float(beta[i, j]), "r": float(rr[i, j]),
            "se": float(sse[i, j]), "beta_lb": float(abs(beta[i, j]) - LB_Z * sse[i, j]),
            "p": float(pp[i, j]), "q": float(q[i, j]), "n_models": int(n_used[i]),
            "df": int(df_used[i]), "same_arm": bool(same_arm), "same_chrom": bool(same_chrom),
            "unknown_locus": bool(unknown_locus),
            "band_distance": (abs(cband - dband) if (same_arm and cband is not None
                                                     and dband is not None) else None),
            "same_gene_family": bool(ckind != "SIG" and fam.get(cgene) is not None
                                     and fam.get(cgene) == fam.get(dgene)),
        })
    cand_df = pd.DataFrame(cand_rows)

    kyprev, n_ky_all, n_ky_only = ky_prevalence([c["context"] for c in cand_rows]) if cand_rows else ({}, 0, 0)
    if len(cand_df):
        cand_df["ky_all_pos"] = [kyprev.get(c, {}).get("ky_all", 0) for c in cand_df.context]
        cand_df["ky_only_pos"] = [kyprev.get(c, {}).get("ky_only", 0) for c in cand_df.context]
        cand_df["testable_ky"] = cand_df.ky_all_pos >= KY_MIN_POS
        cand_df["testable_ky_only"] = cand_df.ky_only_pos >= KY_ONLY_MIN_POS
        cand_df["powered_ky_only"] = cand_df.ky_only_pos >= KY_ONLY_POWERED

        # the dependency gene must be expressed in the models that carry the context
        ex = dep_expression(models, sorted(set(cand_df.dep_gene)))
        Xc = CX.build(sorted(set(cand_df.context)), models)
        med = {}
        for c, g in zip(cand_df.context, cand_df.dep_gene):
            if (c, g) in med or g not in ex.columns:
                continue
            pos = Xc[c].to_numpy(dtype=float) == 1
            v = ex[g].to_numpy(dtype=float)[pos]
            v = v[np.isfinite(v)]
            med[(c, g)] = float(np.median(v)) if v.size else float("nan")
        cand_df["dep_expr_in_context"] = [med.get((c, g), float("nan"))
                                          for c, g in zip(cand_df.context, cand_df.dep_gene)]
        cand_df["dep_expressed"] = cand_df.dep_expr_in_context >= DEP_MIN_EXPR

    # registered ranked selection: the pool excludes pairs on the same chromosome,
    # pairs with an unexpressed dependency gene, and pairs with too few holdout
    # models to test; it is ranked by the shrunken effect size
    sel = []
    per_group, per_dep = {}, {}
    pool = (cand_df[(~cand_df.same_chrom) & cand_df.testable_ky & cand_df.dep_expressed].copy()
            if len(cand_df) else cand_df)
    if len(pool):
        pool = pool.sort_values("beta_lb", ascending=False, kind="stable")
        for stratum, kinds_in in STRATA.items():
            taken = 0
            for _, row in pool[pool.context_kind.isin(kinds_in)].iterrows():
                if per_group.get(row.ctx_group, 0) >= MAX_PER_CONTEXT:
                    continue
                if per_dep.get(row.dep_gene, 0) >= MAX_PER_DEP:
                    continue
                r = row.copy()
                r["stratum"] = stratum
                sel.append(r)
                per_group[row.ctx_group] = per_group.get(row.ctx_group, 0) + 1
                per_dep[row.dep_gene] = per_dep.get(row.dep_gene, 0) + 1
                taken += 1
                if taken >= STRATUM_N[stratum]:
                    break
    sel_df = pd.DataFrame(sel)

    tag = "real" if mode == "real" else f"placebo{seed}"
    os.makedirs(OUT, exist_ok=True)
    cand_df.to_csv(f"{OUT}/candidates.{tag}.csv", index=False)
    sel_df.to_csv(f"{OUT}/selection.{tag}.csv", index=False)
    summary = {
        "mode": mode, "seed": seed, "models_discovery": len(models),
        "dep_genes": len(dep_genes), "context_features": len(ctx_name),
        "pairs_tested": int(tested), "candidates_passing_filters": int(len(cand_df)),
        "candidates_excluding_same_chrom": int((~cand_df.same_chrom).sum()) if len(cand_df) else 0,
        "candidates_testable_in_ky": int(cand_df.testable_ky.sum()) if len(cand_df) else 0,
        "selection_pool": int(len(pool)) if len(cand_df) else 0,
        "selected": int(len(sel_df)),
        "selected_testable_ky_only": int(sel_df.testable_ky_only.sum()) if len(sel_df) else 0,
        "selected_powered_ky_only": int(sel_df.powered_ky_only.sum()) if len(sel_df) else 0,
        "selected_by_kind": sel_df.context_kind.value_counts().to_dict() if len(sel_df) else {},
        "ky_models_all": n_ky_all, "ky_models_only": n_ky_only,
        "rule": {"MIN_ABS_BETA": MIN_ABS_BETA, "MIN_BETA_LB": MIN_BETA_LB, "MAX_Q": MAX_Q,
                 "STRATUM_N": STRATUM_N, "MAX_PER_CONTEXT": MAX_PER_CONTEXT,
                 "MAX_PER_DEP": MAX_PER_DEP, "KY_MIN_POS": KY_MIN_POS,
                 "KY_ONLY_MIN_POS": KY_ONLY_MIN_POS, "KY_ONLY_POWERED": KY_ONLY_POWERED,
                 "DEP_MIN_EXPR": DEP_MIN_EXPR, "LB_Z": LB_Z},
    }
    json.dump(summary, open(f"{OUT}/screen.{tag}.json", "w"), indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "real"
    run(mode, sys.argv[2] if len(sys.argv) > 2 else None)
