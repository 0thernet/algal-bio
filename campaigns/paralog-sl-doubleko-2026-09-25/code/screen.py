#!/usr/bin/env python3
"""Conjunctive discovery screen: paralog-loss context -> paralog dependency.

The hypothesis space is the directed paralog pair universe only: for a context
K:A (a paralog-loss event on gene A) the dependency genes tested are A's
Ensembl paralog partners. One routine runs the covariate-adjusted association
on each single-KO arm; selection requires the AV arm to pass the registered
effect/FDR filters AND the KY arm to confirm at the registered relaxed rule.
Multiple testing is corrected over the universe pairs only.

  python code/screen.py real          # real contexts
  python code/screen.py placebo SEED  # AV contexts permuted within lineage;
                                      # the KY arm stays real, so the placebo
                                      # exercises the whole conjunctive rule
"""
import json, os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import campaign as C

ST = C.ST
CX = C.CX
OUT = C.OUT

# --- registered selection rule ---
AV_MIN_BETA = -0.30      # dependency direction: context must make the gene MORE essential
AV_MIN_LB = 0.20         # shrunken lower bound |beta| - LB_Z*se
AV_MAX_Q = 0.01          # BH q over the directed universe pairs only
KY_MIN_BETA = -0.15      # relaxed confirmation rule on the second library
KY_MAX_P = 0.05          # one-sided, in the dependency direction
LB_Z = 1.96
MAX_PER_CONTEXT = 3      # diversity cap on a context's correlation group
MAX_PER_DEP = 3          # diversity cap per dependency gene
MAX_PER_PAIR = 1         # one directed selection per unordered pair
STRATA = {"deletion": ("DEL",), "expression": ("EXPR_LOW",), "lof": ("LOF",)}
STRATUM_N = {"deletion": 30, "expression": 40, "lof": 30}
DEP_MIN_EXPR = 1.0       # dep gene median log2(TPM+1) among context-positive AV models


def load():
    dep_av = np.load(f"{C.PREP}/dep_av.npz", allow_pickle=False)
    dep_ky = np.load(f"{C.PREP}/dep_ky.npz", allow_pickle=False)
    ctx = np.load(f"{C.PREP}/ctx_paralog.npz", allow_pickle=False)
    assert list(ctx["models"]) == list(dep_av["models"]), \
        "context and dependency matrices have different model orderings"
    uni = pd.read_csv(f"{C.PREP}/pair_universe.csv")
    return dep_av, dep_ky, ctx, uni


def arm_associate(Y, models, X, names, lineage, seed=None):
    """beta/r/p/se for every context x every dep gene on one arm."""
    Z = CX.covariates_for(models)
    if seed is not None:
        rng = np.random.default_rng(int(seed))
        X = X[ST.permute_within(lineage, rng), :]
    rows = []
    for c in range(X.shape[1]):
        m = np.isfinite(X[:, c])
        if m.sum() < 30:
            rows.append((c, None))
            continue
        b, r, p, se, df = ST.associate(Y[m], X[m][:, [c]], Z[m], min_df=10)
        rows.append((c, (b[0], r[0], p[0], se[0], df, int(m.sum()))))
    return rows


def run(mode, seed=None):
    dep_av, dep_ky, ctx, uni = load()
    av_models, ky_models = list(dep_av["models"]), list(dep_ky["models"])
    genes = list(dep_av["genes"])
    gix = {g: j for j, g in enumerate(genes)}
    names, kinds = list(ctx["names"]), list(ctx["kinds"])
    ctx_group = json.load(open(f"{C.PREP}/ctx_group.json"))
    lin = pd.read_csv(f"{C.DD}/Model.csv", index_col=0).OncotreeLineage
    lin_av = lin.reindex(av_models).fillna("UNKNOWN").to_numpy(dtype=str)

    Y_av = dep_av["dep"]
    Y_ky = dep_ky["dep"].astype(np.float64)
    ky_names_ok = json.load(open(f"{C.PREP}/ky_pos.json"))

    non_lof = [n for n in names if not n.startswith("LOF:")]
    Xk = CX.build(non_lof, ky_models)
    lof_map = json.load(open(f"{C.PREP}/lof_gene_models.json"))
    profiled = set(lof_map.get("__profiled__", ()))
    X_ky = np.column_stack([
        (np.array([np.nan if m not in profiled else
                   (1.0 if m in set(lof_map.get(n.split(":", 1)[1], ()))
                    else 0.0) for m in ky_models])
         if n.startswith("LOF:") else Xk[n].to_numpy(dtype=float))
        for n in names])
    X_av = ctx["ctx"].astype(np.float64)

    av_rows = arm_associate(Y_av, av_models, X_av, names, lin_av,
                            seed=(seed if mode == "placebo" else None))
    # The KY arm always runs on real contexts. Under mode=placebo the permuted
    # AV context columns are carried into the KY lookup by name, so a placebo
    # "selection" must additionally satisfy the real KY confirmation rule.
    ky_rows = arm_associate(Y_ky, ky_models, X_ky, names,
                            lin.reindex(ky_models).fillna("UNKNOWN").to_numpy(dtype=str))
    ky_by_ctx = {names[c]: v for c, v in ky_rows if v is not None}

    # universe restriction + q over universe only
    uni["ctx_idx"] = uni.context.map({n: i for i, n in enumerate(names)})
    uni["dep_idx"] = uni.dep_gene.map(gix)
    uni = uni[uni.ctx_idx.notna() & uni.dep_idx.notna()].copy()
    uni["ctx_idx"] = uni.ctx_idx.astype(int)
    uni["dep_idx"] = uni.dep_idx.astype(int)

    p_all, seen = [], []
    for _, r in uni.iterrows():
        v = av_rows[r.ctx_idx][1]
        p_all.append(np.nan if v is None else v[2][r.dep_idx])
        seen.append(True)
    uni["av_p"] = p_all
    uni["av_q"] = ST.bh_qvalues(np.nan_to_num(np.array(p_all, dtype=float), nan=1.0))

    # per-pair values
    rec = []
    for _, r in uni.iterrows():
        c, j = r.ctx_idx, r.dep_idx
        v = av_rows[c][1]
        b_av, se_av, n_av = (np.nan, np.nan, 0) if v is None else (v[0][j], v[3][j], v[5])
        vk = ky_by_ctx.get(r.context)
        b_ky = p_ky = np.nan
        if vk is not None:
            m = np.isfinite(X_ky[:, c])
            b_ky = vk[0][j]
            p_ky = vk[2][j]
        rec.append({"context": r.context, "context_kind": r.context.split(":", 1)[0],
                    "context_gene": r.context_gene, "dep_gene": r.dep_gene,
                    "pair": r.pair, "ctx_group": ctx_group.get(r.context, r.context),
                    "ky_pos": r.ky_pos, "ky_evaluable": r.ky_evaluable,
                    "beta_av": b_av, "se_av": se_av,
                    "beta_lb_av": (abs(b_av) - LB_Z * se_av) if np.isfinite(b_av) else np.nan,
                    "p_av": (v[2][j] if v is not None else np.nan),
                    "q_av": r.av_q, "n_av": n_av,
                    "beta_ky": b_ky, "p_ky_two": p_ky})
    cand = pd.DataFrame(rec)

    def p_one_sided(row):
        b, p = row.beta_ky, row.p_ky_two
        if not (np.isfinite(b) and np.isfinite(p)):
            return np.nan
        return (p / 2.0) if b < 0 else (1.0 - p / 2.0)

    cand["p_ky_one"] = cand.apply(p_one_sided, axis=1)
    cand["av_pass"] = ((cand.beta_av <= AV_MIN_BETA)
                       & (cand.beta_lb_av >= AV_MIN_LB)
                       & (cand.q_av <= AV_MAX_Q))
    cand["ky_pass"] = (cand.ky_evaluable & np.isfinite(cand.beta_ky)
                       & (cand.beta_ky <= KY_MIN_BETA)
                       & (cand.p_ky_one < KY_MAX_P))

    # dep gene must be expressed among context-positive AV models; the check is
    # only needed where the conjunctive flags hold
    cand["dep_expr_in_context"] = np.nan
    cand["dep_expressed"] = False
    need = cand[cand.av_pass & cand.ky_pass]
    if len(need):
        fn = "OmicsExpressionProteinCodingGenesTPMLogp1.csv"
        colmap = CX._colmap(fn)
        want = [colmap[g] for g in sorted(set(need.dep_gene)) if g in colmap]
        ex = CX._read_cols(fn, want)
        expr_ok = {}
        for cn in set(need.context):
            m = X_av[:, names.index(cn)] == 1
            for g in set(need.loc[need.context == cn, "dep_gene"]):
                if g in colmap and colmap[g] in ex.columns:
                    v = ex[colmap[g]].reindex(av_models).to_numpy(dtype=float)[m]
                    v = v[np.isfinite(v)]
                    expr_ok[(cn, g)] = float(np.median(v)) if v.size else np.nan
        cand["dep_expr_in_context"] = [expr_ok.get((c, g), np.nan)
                                       for c, g in zip(cand.context, cand.dep_gene)]
        cand["dep_expressed"] = cand.dep_expr_in_context >= DEP_MIN_EXPR

    pool = cand[cand.av_pass & cand.ky_pass & cand.dep_expressed].copy()
    sel, per_group, per_dep, per_pair = [], {}, {}, {}
    if len(pool):
        pool = pool.sort_values("beta_lb_av", ascending=False, kind="stable")
        for stratum, kds in STRATA.items():
            taken = 0
            for _, row in pool[pool.context_kind.isin(kds)].iterrows():
                if per_group.get(row.ctx_group, 0) >= MAX_PER_CONTEXT:
                    continue
                if per_dep.get(row.dep_gene, 0) >= MAX_PER_DEP:
                    continue
                if per_pair.get(row.pair, 0) >= MAX_PER_PAIR:
                    continue
                r = row.copy()
                r["stratum"] = stratum
                sel.append(r)
                per_group[row.ctx_group] = per_group.get(row.ctx_group, 0) + 1
                per_dep[row.dep_gene] = per_dep.get(row.dep_gene, 0) + 1
                per_pair[row.pair] = 1
                taken += 1
                if taken >= STRATUM_N[stratum]:
                    break
    sel_df = pd.DataFrame(sel)

    tag = "real" if mode == "real" else f"placebo{seed}"
    os.makedirs(OUT, exist_ok=True)
    cand.to_csv(f"{OUT}/candidates.{tag}.csv", index=False)
    sel_df.to_csv(f"{OUT}/selection.{tag}.csv", index=False)
    summary = {
        "mode": mode, "seed": seed,
        "models_av": len(av_models), "models_ky": len(ky_models),
        "contexts": len(names), "universe_pairs": int(len(uni)),
        "av_pass": int(cand.av_pass.sum()), "ky_pass": int(cand.ky_pass.sum()),
        "conjunctive": int((cand.av_pass & cand.ky_pass).sum()),
        "dep_expressed": int(cand.dep_expressed.sum()) if "dep_expressed" in cand else 0,
        "selection_pool": int(len(pool)), "selected": int(len(sel_df)),
        "selected_pairs": int(sel_df.pair.nunique()) if len(sel_df) else 0,
        "selected_by_kind": sel_df.context_kind.value_counts().to_dict() if len(sel_df) else {},
        "rule": {"AV_MIN_BETA": AV_MIN_BETA, "AV_MIN_LB": AV_MIN_LB, "AV_MAX_Q": AV_MAX_Q,
                 "KY_MIN_BETA": KY_MIN_BETA, "KY_MAX_P": KY_MAX_P, "LB_Z": LB_Z,
                 "MAX_PER_CONTEXT": MAX_PER_CONTEXT, "MAX_PER_DEP": MAX_PER_DEP,
                 "MAX_PER_PAIR": MAX_PER_PAIR, "STRATUM_N": STRATUM_N,
                 "DEP_MIN_EXPR": DEP_MIN_EXPR},
    }
    json.dump(summary, open(f"{OUT}/screen.{tag}.json", "w"), indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "real"
    run(mode, sys.argv[2] if len(sys.argv) > 2 else None)
