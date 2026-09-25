#!/usr/bin/env python3
"""Build the paralog-restricted discovery matrices.

Everything here is discovery-side: the Avana and KY per-library dependency
matrices (both seen data for this campaign), collapsed per model and filtered
with the earlier campaign's rules except one registered difference: reference
essentials are NOT excluded. A paralog partner that is semi-essential in every
line can still be MORE essential when its paralog is lost - conditional
essentiality is the mechanism under test - while a constitutively essential
gene cannot show context dependence because the variability filter still
applies. Dropping the named list also removes the earlier campaign's reliance
on the Hart/Blomen external list for the dependency universe.

Never reads data/sealed/.
"""
import json, os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import campaign as C

D = C.DD
OUT = C.PREP
os.makedirs(OUT, exist_ok=True)

# registered constants
PARALOG_KINDS = ("DEL", "EXPR_LOW", "LOF")   # paralog LOSS events only. MUT_DAM
# is not used: the damaging-mutation matrix does not mark LoF specifically, and
# missense GOF/DN calls would poison the loss direction. LOF is built here from
# the raw somatic-mutation table using the depositor's own LikelyLoF call.
KY_MIN_POS = 5          # context-positive KY models needed for the conjunctive arm
DEP_MIN_SD = 0.20
DEP_MIN_HIT = -0.50
DEP_MIN_HITS = 3
DEP_MAX_MISS = 0.05
# context qualification mirrors the earlier campaign's rules (AV models)
CTX_MIN_POS = 15
CTX_MAX_POS_FRAC = 0.40
CTX_MIN_LINEAGES = 2
CTX_MIN_POS_PER_LINEAGE = 3


def build_lof_contexts(models, paralog_set, admitted, lineage):
    """LOF:G binary context columns over `models` from the raw mutation table.

    A model is context-positive when it carries at least one registered LoF
    class variant in the gene. Qualification mirrors the earlier campaign:
    CTX_MIN_POS <= positives <= CTX_MAX_POS_FRAC*n, at least CTX_MIN_LINEAGES
    lineages each carrying CTX_MIN_POS_PER_LINEAGE positives, gene in the
    protein-coding universe and a paralog source gene.
    """
    fn = f"{D}/OmicsSomaticMutations.csv"
    head = pd.read_csv(fn, nrows=0).columns.tolist()
    idcol = next((c for c in head if c.lower() in ("modelid", "model_id",
                                                 "depmap_id")), head[0])
    gcol = next((c for c in head if c.lower() in ("hugo_symbol", "hugosymbol",
                                                "gene", "genesymbol")), None)
    lcol = next((c for c in head if c.lower() == "likelylof"), None)
    if gcol is None or lcol is None:
        sys.exit(f"refusing: mutation table columns unresolved: {head}")
    want = [idcol, gcol, lcol]
    lof_by_model, profiled = {}, set()
    for chunk in pd.read_csv(fn, usecols=want, chunksize=2_000_000,
                             low_memory=False):
        profiled.update(chunk[idcol].astype(str).unique())
        chunk = chunk[chunk[lcol].astype(str).str.lower() == "true"]
        for m, g in zip(chunk[idcol].to_numpy(dtype=str),
                        chunk[gcol].to_numpy(dtype=str)):
            lof_by_model.setdefault(m, set()).add(g)
    # returned to main() (which writes the prep output); keeping the write out
    # of this function means a test run can never overwrite the real artifact.
    # __profiled__ carries the set of models the mutation table covers at all:
    # a model absent from it is UNPROFILED (context unknown), not wildtype.
    gene_models = {}
    for m, gs in lof_by_model.items():
        for g in gs:
            gene_models.setdefault(g, set()).add(m)
    lof_gene_models = {g: sorted(ms) for g, ms in gene_models.items()
                       if g in paralog_set}
    lof_gene_models["__profiled__"] = sorted(profiled)
    n = len(models)
    max_pos = int(CTX_MAX_POS_FRAC * n)
    cols, names = [], []
    for g in sorted(paralog_set & admitted):
        pos = np.array([np.nan if m not in profiled else
                        (1.0 if g in lof_by_model.get(m, ()) else 0.0)
                        for m in models])
        npos = np.nansum(pos)
        if npos < CTX_MIN_POS or npos > max_pos or \
                np.isfinite(pos).sum() - npos < CTX_MIN_POS:
            continue
        prof = np.isfinite(pos)
        spread = sum(((pos[(lineage == lv) & prof]).sum()
                      >= CTX_MIN_POS_PER_LINEAGE)
                     for lv in np.unique(lineage[prof]))
        if spread < CTX_MIN_LINEAGES:
            continue
        names.append(f"LOF:{g}")
        cols.append(pos)
    return (names, (np.column_stack(cols) if cols else np.zeros((n, 0))),
            lof_gene_models)


def dep_matrix(path, label, s2m, admitted, keep_screens=None):
    """ScreenGeneEffect per-library file -> collapsed per-model matrix with the
    per-gene behavioral filter. Returns (df, stats)."""
    df = pd.read_csv(path, index_col=0)
    n_in = len(df)
    if keep_screens is not None:
        df = df.loc[[s for s in df.index if s in keep_screens]]
    missing = [s for s in df.index if s not in s2m]
    if missing:
        sys.exit(f"refusing: {label} screens absent from CRISPRScreenMap.csv: {missing[:5]}")
    df.index = [s2m[s] for s in df.index]
    df.columns = C.CX.strip_entrez(df.columns)
    df = df.groupby(level=0).mean()
    df = df.loc[:, ~df.columns.duplicated()]
    A = df.to_numpy(dtype=np.float64)
    keep = ((np.isnan(A).mean(axis=0) < DEP_MAX_MISS)
            & (np.nanstd(A, axis=0) >= DEP_MIN_SD)
            & (np.nansum(A <= DEP_MIN_HIT, axis=0) >= DEP_MIN_HITS)
            & np.array([g in admitted for g in df.columns]))
    dep_genes = list(np.array(df.columns)[keep])
    n_genes_in = int(len(df.columns))
    A = A[:, keep]
    # column-mean imputation, identical to the earlier campaign's prep:
    # kept genes retain up to 5% missing and would otherwise carry NaNs into
    # every association
    col_mean = np.nanmean(A, axis=0)
    miss = np.isnan(A)
    A[miss] = np.take(col_mean, np.where(miss)[1])
    df = pd.DataFrame(A, index=df.index, columns=dep_genes)
    stats = {"label": label, "screens_in": n_in, "screens_used": int(df.index.size),
             "models": int(len(df)), "genes_in": n_genes_in,
             "genes_kept": len(dep_genes), "imputed_cells": int(miss.sum())}
    return df, stats


def main():
    receipt = {"inputs": {}, "outputs": {},
               "params": {"PARALOG_MIN_PCTID": C.PARALOG_MIN_PCTID,
                          "PARALOG_KINDS": PARALOG_KINDS, "KY_MIN_POS": KY_MIN_POS,
                          "DEP_MIN_SD": DEP_MIN_SD, "DEP_MIN_HIT": DEP_MIN_HIT,
                          "DEP_MIN_HITS": DEP_MIN_HITS, "DEP_MAX_MISS": DEP_MAX_MISS,
                          "EXPR_LOW": C.CX.EXPR_LOW, "DEEP_DEL_CN": C.CX.DEEP_DEL_CN,
                          "reference_essentials_excluded": False}}

    inputs = [f"{C.DEPMAP}/data/discovery/ScreenGeneEffect.AV.csv",
              f"{C.DISC}/ScreenGeneEffect.KY.csv",
              C.REF_PARALOG_TSV,
              f"{D}/CRISPRScreenMap.csv", f"{D}/Gene.csv", f"{D}/Model.csv",
              f"{D}/OmicsAbsoluteCNGene.csv",
              f"{D}/OmicsExpressionProteinCodingGenesTPMLogp1.csv",
              f"{D}/OmicsSomaticMutationsMatrixDamaging.csv",
              f"{D}/OmicsSomaticMutations.csv",
              f"{D}/OmicsSignatures.csv",
              f"{D}/AchillesScreenQCReport.csv",
              f"{C.DEPMAP}/data/prep/ctx.npz", f"{C.DEPMAP}/data/prep/ctx_group.json"]
    for rel in inputs:
        receipt["inputs"][os.path.relpath(rel, C.ROOT)] = C.sha(rel)

    directed, undirected = C.paralog_pairs()
    paralog_set = {g for e in undirected for g in e}
    receipt["pair_map"] = {"ref": os.path.relpath(C.REF_PARALOG_TSV, C.ROOT),
                           "min_pctid": C.PARALOG_MIN_PCTID,
                           "directed_edges": len(directed),
                           "unordered_pairs": len(undirected),
                           "paralog_genes": len(paralog_set)}

    gene = pd.read_csv(f"{D}/Gene.csv", low_memory=False)
    admitted = set(gene.symbol[(gene.locus_type == "gene with protein product")
                               & ~gene.gene_group.fillna("").str.contains(
                                   "Olfactory receptor", case=False)].astype(str))
    smap = pd.read_csv(f"{D}/CRISPRScreenMap.csv")
    s2m = dict(zip(smap.ScreenID, smap.ModelID))

    # ---- dependency matrices, same filter on both arms ----
    qc = pd.read_csv(f"{D}/AchillesScreenQCReport.csv")
    good = set(qc.ScreenID[qc.PassesQC.fillna(False) & qc.CanInclude.fillna(False)])
    dep_av_full = f"{C.DEPMAP}/data/discovery/ScreenGeneEffect.AV.csv"
    dep_av, av_stats = dep_matrix(dep_av_full, "AV", s2m, admitted, keep_screens=good)
    dep_ky, ky_stats = dep_matrix(f"{C.DISC}/ScreenGeneEffect.KY.csv", "KY", s2m, admitted)
    av_models, ky_models = list(dep_av.index), list(dep_ky.index)

    dep_genes_joint = sorted(set(dep_av.columns) & set(dep_ky.columns))
    dep_gene_set = set(dep_genes_joint)

    # ---- paralog-loss context features, qualified subset of the earlier ctx
    #      plus LOF contexts built here from the raw mutation table ----
    ctx = np.load(f"{C.DEPMAP}/data/prep/ctx.npz", allow_pickle=False)
    names, kinds = list(ctx["names"]), list(ctx["kinds"])
    keep_idx = [i for i, (nm, kd) in enumerate(zip(names, kinds))
                if kd in ("DEL", "EXPR_LOW") and nm.split(":", 1)[1] in paralog_set]
    ctx_names = [names[i] for i in keep_idx]
    X_av = ctx["ctx"][:, keep_idx]
    ctx_group_all = json.load(open(f"{C.DEPMAP}/data/prep/ctx_group.json"))
    ctx_group = {nm: ctx_group_all.get(nm, nm) for nm in ctx_names}

    lof_ctx, X_lof, lof_map = build_lof_contexts(
        av_models, paralog_set, admitted,
        pd.read_csv(f"{D}/Model.csv", index_col=0)
        .OncotreeLineage.reindex(av_models)
        .fillna("UNKNOWN").to_numpy(dtype=str))
    json.dump(lof_map, open(f"{OUT}/lof_gene_models.json", "w"))
    if lof_ctx:
        X_av = np.concatenate([X_av, X_lof], axis=1)
        ctx_names.extend(lof_ctx)
        for cn in lof_ctx:
            ctx_group[cn] = cn

    non_lof = [c for c in ctx_names if not c.startswith("LOF:")]
    Xk = C.CX.build(non_lof, ky_models)
    ky_pos = {c: int(np.nansum(Xk[c].to_numpy(dtype=float) == 1)) for c in non_lof}
    ky_set = set(ky_models)
    prof = set(lof_map.get("__profiled__", ()))
    for c in ctx_names:
        if c.startswith("LOF:"):
            ky_pos[c] = len(ky_set & prof & set(
                lof_map.get(c.split(":", 1)[1], ())))
    ky_eval = {c: ky_pos[c] >= KY_MIN_POS for c in ctx_names}

    # ---- guide cross-targeting (Fortin 2019 confound for paralogs) ----
    # A Chronos-used guide with nAlignments > 1 on the dependency gene can cut
    # the partner paralog's locus and manufacture the association. Exclude a
    # pair when its dep gene carries any such guide in EITHER library; a guide
    # sequence listed under two different genes is a second failure mode,
    # excluded symmetrically.
    def guide_sets(fn):
        gm = pd.read_csv(f"{D}/{fn}", usecols=["sgRNA", "Gene", "nAlignments",
                                             "UsedByChronos"])
        gm = gm[gm.UsedByChronos.fillna(False)]
        gm["sym"] = C.CX.strip_entrez(gm.Gene)
        multi = set(gm.sym[gm.nAlignments > 1])
        sg2g = gm.groupby("sgRNA").sym.agg(set)
        cross = {g for s in sg2g.values if len(s) > 1 for g in s}
        return multi, cross

    av_multi, av_cross = guide_sets("AvanaGuideMap.csv")
    ky_multi, ky_cross = guide_sets("KYGuideMap.csv")
    tainted_dep = av_multi | ky_multi | av_cross | ky_cross
    for fn in ("AvanaGuideMap.csv", "KYGuideMap.csv"):
        receipt["inputs"][os.path.relpath(f"{D}/{fn}", C.ROOT)] = C.sha(f"{D}/{fn}")

    # ---- directed pair universe ----
    edge_set = set(directed)
    partners = {}
    for a, b in edge_set:
        partners.setdefault(a, set()).add(b)
    pairs = []
    n_mt = 0
    for cn in ctx_names:
        kd, g = cn.split(":", 1)
        for b in partners.get(g, ()):
            if b not in dep_gene_set or b == g:
                continue
            if b in tainted_dep:
                n_mt += 1
                continue
            pairs.append({"context": cn, "context_gene": g, "dep_gene": b,
                          "pair": "|".join(sorted((g, b))),
                          "ky_pos": ky_pos[cn], "ky_evaluable": ky_eval[cn]})
    pdf = (pd.DataFrame(pairs).drop_duplicates(["context", "dep_gene"])
           .reset_index(drop=True) if pairs else
           pd.DataFrame(columns=["context", "context_gene", "dep_gene", "pair",
                                 "ky_pos", "ky_evaluable"]))

    np.savez_compressed(f"{OUT}/dep_av.npz",
                        dep=dep_av.loc[:, dep_genes_joint].to_numpy(dtype=np.float64),
                        models=np.array(av_models), genes=np.array(dep_genes_joint))
    np.savez_compressed(f"{OUT}/dep_ky.npz",
                        dep=dep_ky.loc[:, dep_genes_joint].to_numpy(dtype=np.float64),
                        models=np.array(ky_models), genes=np.array(dep_genes_joint))
    np.savez_compressed(f"{OUT}/ctx_paralog.npz", ctx=X_av, names=np.array(ctx_names),
                        kinds=np.array([n.split(":", 1)[0] for n in ctx_names]),
                        models=np.array(av_models))
    pdf.to_csv(f"{OUT}/pair_universe.csv", index=False)
    json.dump(ctx_group, open(f"{OUT}/ctx_group.json", "w"))
    json.dump(ky_pos, open(f"{OUT}/ky_pos.json", "w"))

    receipt["universe"] = {
        "multitarget_dep_pairs_excluded": int(n_mt),
        "contexts": len(ctx_names),
        "contexts_by_kind": pd.Series([n.split(":", 1)[0] for n in ctx_names])
        .value_counts().to_dict(),
        "contexts_ky_evaluable": int(sum(ky_eval.values())),
        "av": av_stats, "ky": ky_stats,
        "dep_genes_joint": len(dep_genes_joint),
        "directed_pairs": int(len(pdf)),
        "unordered_pairs": int(pdf.pair.nunique() if len(pdf) else 0)}
    receipt["outputs"] = {f"data/prep/{f}": C.sha(f"{OUT}/{f}")
                          for f in ["dep_av.npz", "dep_ky.npz", "ctx_paralog.npz",
                                    "pair_universe.csv", "ctx_group.json", "ky_pos.json",
                                    "lof_gene_models.json"]}
    json.dump(receipt, open(f"{OUT}/prep.receipt.json", "w"), indent=1)
    print(json.dumps({"universe": receipt["universe"], "pair_map": receipt["pair_map"]},
                     indent=1))


if __name__ == "__main__":
    main()
