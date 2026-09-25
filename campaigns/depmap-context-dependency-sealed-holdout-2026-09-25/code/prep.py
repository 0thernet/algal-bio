#!/usr/bin/env python3
"""Build model-level matrices for the context-dependency study.

Discovery arm only: Avana (AV) screens, collapsed to one row per ModelID.
Never touches data/sealed/ or data/sanger_holdout/.

Outputs (data/prep/):
  dep.npz        dependency matrix (models x dep genes), lineage vector, model ids
  ctx.npz        context matrices (models x context features), one block per context type
  *.json         feature name lists and a provenance receipt
"""
import hashlib, json, os, re, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import contexts as CX

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = f"{ROOT}/data/depmap24q4"
OUT = f"{ROOT}/data/prep"
os.makedirs(OUT, exist_ok=True)

# --- parameters (frozen by the protocol; see registration/protocol.json) ---
MIN_POS = 15            # minimum context-positive discovery models
MAX_POS_FRAC = 0.40     # context must not be the majority state
MIN_LINEAGES = 2        # context must be positive in at least this many lineages
MIN_POS_PER_LINEAGE = 3 # ... with at least this many positives in each of them
DEP_MIN_SD = 0.20       # dependency must vary across models
DEP_MIN_HIT = -0.50     # at least one model must be dependent
DEP_MIN_HITS = 3        # at least this many models below DEP_MIN_HIT
EXPR_ON = 3.0           # gene must be expressed above this in >=1/3 of models
DUP_R = 0.95            # context columns correlated above this share a diversity budget

# A-priori gene-universe exclusions, both generic classes rather than named
# genes: see gene_universe() for why each one produces cross-library
# reproducible artifacts rather than biology.
LOCUS_TYPE = "gene with protein product"
EXCLUDED_FAMILY = "Olfactory receptor"

# Covariates cannot also be contexts: a feature that is in the design is
# perfectly explained by the design, so its slope is not identified. These are
# excluded from the context universe in advance rather than silently zeroed.
COVARIATE_CONTEXTS = {"MUT_DAM:TP53", "MUT_HOT:TP53", "SIG:WGD"}


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 24), b""):
            h.update(c)
    return h.hexdigest()


def gene_universe():
    """Symbols admitted as a context gene or a dependency gene, and why.

    Two a-priori exclusions, both for classes that produce cross-library
    reproducible artifacts rather than biology:

      not a protein-coding locus   pseudogenes, immunoglobulin and T-cell
        receptor segments, non-coding RNA, readthrough and fragile-site
        entries. V(D)J recombination in a lymphoid line is read by the copy
        number pipeline as a deep deletion of IGH/IGK/IGL/TR segments, which is
        a lineage marker wearing a copy-number label; pericentromeric and
        acrocentric pseudogenes carry the same kind of mis-mapped call.
      olfactory receptor   a large, unexpressed, highly similar gene family in
        which multi-targeting guides produce gene-independent depletion.
    """
    g = pd.read_csv(f"{D}/Gene.csv", low_memory=False)
    ok = g.locus_type == LOCUS_TYPE
    olf = g.gene_group.fillna("").str.contains(EXCLUDED_FAMILY, case=False)
    keep = set(g.symbol[ok & ~olf].astype(str))
    return keep, {"gene_rows": int(len(g)),
                  "protein_product": int(ok.sum()),
                  "olfactory_receptors_excluded": int((ok & olf).sum()),
                  "admitted": len(keep)}


def collapse_duplicates(X, names):
    """Group context columns that carry (nearly) the same measurement.

    Exactly duplicated columns are collapsed to one representative: three copies
    of one copy-number segment are one measurement and must not each receive
    their own diversity budget. Columns that survive but correlate above DUP_R
    with a kept column share that column's budget, recorded as ctx_group.
    """
    keys = {}
    keep_idx, rep_of = [], {}
    for j, nm in enumerate(names):
        col = X[:, j]
        k = hashlib.sha256(np.nan_to_num(col, nan=-9.0).astype(np.float32).tobytes()).hexdigest()
        if k in keys:
            rep_of[nm] = names[keys[k]]
            continue
        keys[k] = j
        keep_idx.append(j)
        rep_of[nm] = nm
    Xk = X[:, keep_idx]
    kept = [names[j] for j in keep_idx]

    # correlation clustering among the survivors, within one pass
    A = np.nan_to_num(Xk, nan=0.0)
    A = A - A.mean(axis=0, keepdims=True)
    sd = np.sqrt((A ** 2).sum(axis=0))
    sd[sd == 0] = 1.0
    A = A / sd
    group = list(range(len(kept)))
    C = A.T @ A
    np.fill_diagonal(C, 0.0)
    for j in range(len(kept)):
        hit = np.where(np.abs(C[j, :j]) > DUP_R)[0]
        if hit.size:
            group[j] = group[int(hit[0])]
    ctx_group = {kept[j]: kept[group[j]] for j in range(len(kept))}
    return Xk, kept, ctx_group, rep_of


def main():
    receipt = {"inputs": {}, "outputs": {}, "params": {
        "MIN_POS": MIN_POS, "MAX_POS_FRAC": MAX_POS_FRAC, "MIN_LINEAGES": MIN_LINEAGES,
        "MIN_POS_PER_LINEAGE": MIN_POS_PER_LINEAGE, "DEP_MIN_SD": DEP_MIN_SD,
        "DEP_MIN_HIT": DEP_MIN_HIT, "DEP_MIN_HITS": DEP_MIN_HITS,
        "EXPR_LOW": CX.EXPR_LOW, "EXPR_ON": EXPR_ON, "DEEP_DEL_CN": CX.DEEP_DEL_CN,
        "MSI_HI": CX.MSI_HI, "DUP_R": DUP_R,
        "COVARIATE_CONTEXTS": sorted(COVARIATE_CONTEXTS)}}

    # ---- dependency matrix: AV screens only, QC-passing, collapsed per model ----
    av = f"{ROOT}/data/discovery/ScreenGeneEffect.AV.csv"
    receipt["inputs"]["ScreenGeneEffect.AV.csv"] = sha(av)
    dep = pd.read_csv(av, index_col=0)
    qc = pd.read_csv(f"{D}/AchillesScreenQCReport.csv")
    receipt["inputs"]["AchillesScreenQCReport.csv"] = sha(f"{D}/AchillesScreenQCReport.csv")
    good = set(qc.ScreenID[qc.PassesQC.fillna(False) & qc.CanInclude.fillna(False)])
    dropped_qc = [s for s in dep.index if s not in good]
    dep = dep.loc[[s for s in dep.index if s in good]]
    smap = pd.read_csv(f"{D}/CRISPRScreenMap.csv")
    receipt["inputs"]["CRISPRScreenMap.csv"] = sha(f"{D}/CRISPRScreenMap.csv")
    s2m = dict(zip(smap.ScreenID, smap.ModelID))
    missing = [s for s in dep.index if s not in s2m]
    if missing:
        sys.exit(f"refusing: screens absent from CRISPRScreenMap.csv: {missing[:5]}")
    dep.index = [s2m[s] for s in dep.index]
    dep.columns = CX.strip_entrez(dep.columns)
    dep = dep.groupby(level=0).mean()
    dep = dep.loc[:, ~dep.columns.duplicated()]

    # ---- lineage ----
    model = pd.read_csv(f"{D}/Model.csv", index_col=0)
    receipt["inputs"]["Model.csv"] = sha(f"{D}/Model.csv")
    lineage = model.OncotreeLineage.reindex(dep.index).fillna("UNKNOWN")

    # ---- dependency gene filter ----
    # The Hart n Blomen reference essentials, an external list. DepMap's own
    # CRISPRInferredCommonEssentials.csv is inferred from the JOINTLY fitted
    # CRISPRGeneEffect matrix, which includes the sealed holdout, so using it
    # would make the discovery gene universe a function of the holdout.
    ess = set(CX.strip_entrez(pd.read_csv(f"{D}/AchillesCommonEssentialControls.csv").Gene))
    receipt["inputs"]["AchillesCommonEssentialControls.csv"] = sha(f"{D}/AchillesCommonEssentialControls.csv")
    admitted, gene_stats = gene_universe()
    receipt["inputs"]["Gene.csv"] = sha(f"{D}/Gene.csv")
    A = dep.to_numpy(dtype=np.float64)
    frac_missing = np.isnan(A).mean(axis=0)
    sd = np.nanstd(A, axis=0)
    hits = np.nansum(A <= DEP_MIN_HIT, axis=0)
    keep = (frac_missing < 0.05) & (sd >= DEP_MIN_SD) & (hits >= DEP_MIN_HITS)
    keep &= np.array([g not in ess for g in dep.columns])
    keep &= np.array([g in admitted for g in dep.columns])
    dep_genes = list(np.array(dep.columns)[keep])
    A = A[:, keep]
    col_mean = np.nanmean(A, axis=0)
    miss = np.isnan(A)
    A[miss] = np.take(col_mean, np.where(miss)[1])
    receipt["dependency"] = {"screens_in": len(dropped_qc) + len(dep.index),
                             "screens_dropped_failing_qc": len(dropped_qc),
                             "models": len(dep.index), "genes_in": int(keep.size),
                             "genes_kept": len(dep_genes), "imputed_cells": int(miss.sum()),
                             "reference_essentials_excluded": len(ess),
                             "gene_universe": gene_stats}

    models = list(dep.index)
    np.savez_compressed(f"{OUT}/dep.npz", dep=A, models=np.array(models),
                        genes=np.array(dep_genes), lineage=np.array(lineage.to_numpy(dtype=str)))
    json.dump(dep_genes, open(f"{OUT}/dep_genes.json", "w"))
    del dep

    # ---- context blocks ----
    blocks, names, kinds = [], [], []
    n = len(models)
    max_pos = int(MAX_POS_FRAC * n)
    lin = lineage.to_numpy(dtype=str)

    def qualifies(X, cols):
        """The registered context-feature filter, applied identically to every block."""
        npos = np.nansum(X == 1, axis=0)
        nneg = np.nansum(X == 0, axis=0)
        ok = (npos >= MIN_POS) & (npos <= max_pos) & (nneg >= MIN_POS)
        # a context confined to one lineage is a lineage label, not a lesion
        spread = np.zeros(X.shape[1], dtype=int)
        for lv in np.unique(lin):
            spread += (np.nansum(X[lin == lv] == 1, axis=0) >= MIN_POS_PER_LINEAGE)
        ok &= spread >= MIN_LINEAGES
        ok &= np.array([c not in COVARIATE_CONTEXTS for c in cols])
        return ok, npos, spread

    def add_binary(mat_df, kind):
        m = mat_df.reindex(models)
        raw = m.to_numpy(dtype=float)
        X = np.column_stack([CX.binarise(raw[:, j], kind) for j in range(raw.shape[1])])
        syms = CX.strip_entrez(list(mat_df.columns))
        cols = [f"{kind}:{c}" for c in syms]
        in_universe = np.array([s in admitted for s in syms])
        ok, npos, spread = qualifies(X, cols)
        ok &= in_universe
        blocks.append(X[:, ok])
        names.extend(np.array(cols)[ok].tolist())
        kinds.extend([kind] * int(ok.sum()))
        return {"kind": kind, "features_in": int(ok.size),
                "outside_gene_universe": int((~in_universe).sum()),
                "features_kept": int(ok.sum())}

    stats = []
    for kind, fn in [("MUT_DAM", "OmicsSomaticMutationsMatrixDamaging.csv"),
                     ("MUT_HOT", "OmicsSomaticMutationsMatrixHotspot.csv"),
                     ("DEL", "OmicsAbsoluteCNGene.csv")]:
        receipt["inputs"][fn] = sha(f"{D}/{fn}")
        stats.append(add_binary(pd.read_csv(f"{D}/{fn}", index_col=0), kind))

    fn = "OmicsExpressionProteinCodingGenesTPMLogp1.csv"
    receipt["inputs"][fn] = sha(f"{D}/{fn}")
    ex = pd.read_csv(f"{D}/{fn}", index_col=0)
    on_frac = (ex.reindex(models) > EXPR_ON).mean(axis=0)
    ex = ex.loc[:, (on_frac >= 1 / 3).to_numpy()]
    stats.append(add_binary(ex, "EXPR_LOW"))
    del ex

    fn = "OmicsSignatures.csv"
    receipt["inputs"][fn] = sha(f"{D}/{fn}")
    sig_bin = CX.sig_binary(sorted(CX.SIG_DEF), models)
    Xs = sig_bin.to_numpy(dtype=float)
    ok, npos, _ = qualifies(Xs, list(sig_bin.columns))   # the same gate as every other block
    blocks.append(Xs[:, ok])
    names.extend(np.array(list(sig_bin.columns))[ok].tolist())
    kinds.extend(["SIG"] * int(ok.sum()))
    stats.append({"kind": "SIG", "features_in": int(Xs.shape[1]), "features_kept": int(ok.sum()),
                  "n_pos": {c: int(v) for c, v in zip(sig_bin.columns, npos)},
                  "rejected": [c for c, k in zip(sig_bin.columns, ok) if not k]})

    X = np.concatenate(blocks, axis=1)
    X, names, ctx_group, rep_of = collapse_duplicates(X, names)
    kind_of = {nm: nm.split(":", 1)[0] for nm in names}
    kinds = [kind_of[nm] for nm in names]
    np.savez_compressed(f"{OUT}/ctx.npz", ctx=X, names=np.array(names), kinds=np.array(kinds),
                        models=np.array(models))
    json.dump(names, open(f"{OUT}/ctx_names.json", "w"))
    json.dump(ctx_group, open(f"{OUT}/ctx_group.json", "w"))
    json.dump({k: v for k, v in rep_of.items() if k != v},
              open(f"{OUT}/ctx_duplicates.json", "w"))
    receipt["context"] = {"blocks": stats, "features_total": int(X.shape[1]),
                          "exact_duplicates_collapsed": int(sum(1 for k, v in rep_of.items() if k != v)),
                          "correlation_groups": len(set(ctx_group.values()))}
    receipt["pairs_nominal"] = int(X.shape[1]) * len(dep_genes)
    json.dump(receipt, open(f"{OUT}/prep.receipt.json", "w"), indent=1)
    # the two matrices every later step consumes are pinned here, so the freeze
    # can bind them without carrying 9 MB of array into the manifest by hand
    receipt["outputs"] = {f"data/prep/{f}": sha(f"{OUT}/{f}")
                          for f in ["dep.npz", "ctx.npz", "dep_genes.json", "ctx_names.json",
                                    "ctx_group.json", "ctx_duplicates.json"]}
    json.dump(receipt, open(f"{OUT}/prep.receipt.json", "w"), indent=1)
    print(json.dumps({k: v for k, v in receipt.items() if k != "inputs"}, indent=1))


if __name__ == "__main__":
    main()
