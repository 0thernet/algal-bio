#!/usr/bin/env python3
"""Everything about the holdout test that can be known WITHOUT the holdout.

Fixes, before the freeze, every denominator the predictions are stated over,
and records the facts a reader would otherwise have to take on trust after the
fact: how many models carry each context in each tier, whether the KY library
even targets each dependency gene, and how the holdout-only panel differs in
composition from the discovery panel.

Reads shared omics, the screen map, the KY guide map and the tier model lists.
Never reads any dependency matrix from data/sealed/ or data/other/.
"""
import json, os, re, sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import contexts as CX

ROOT = os.path.dirname(HERE)
D = f"{ROOT}/data/depmap24q4"
MIN_TIER_POS = 3        # a tier needs this many context-positive models to test a pair
KY_ONLY_POWERED = 6     # ... and this many for the primary tier B denominator


def tiers():
    smap = pd.read_csv(f"{D}/CRISPRScreenMap.csv")
    smap["lib"] = smap.ScreenID.str.extract(r"\.([A-Z]+)\d+$")
    libs = smap.groupby("ModelID").lib.agg(lambda s: set(s))
    return {"A": [m for m, v in libs.items() if "KY" in v],
            "A_shared": [m for m, v in libs.items() if "KY" in v and "AV" in v],
            "B": [m for m, v in libs.items() if v == {"KY"}],
            "C": [m for m, v in libs.items() if "CD" in v]}


def ky_targets():
    """Genes the Kosuke Yusa library actually targets. A pair whose dependency
    gene is not in the library is unconfirmable, and saying so in advance costs
    nothing and prevents reading an absence as a non-replication."""
    g = pd.read_csv(f"{D}/KYGuideMap.csv")
    col = next(c for c in g.columns if c.lower() in ("gene", "genesymbol", "symbol"))
    return set(CX.strip_entrez(g[col].dropna().astype(str).unique()))


def counts(pairs, tier_models):
    keys = sorted(set(pairs["context"]))
    out = {}
    for tier, models in tier_models.items():
        X = CX.build(keys, models)
        npos = {k: int(np.nansum(X[k].to_numpy(dtype=float) == 1)) for k in keys}
        nneg = {k: int(np.nansum(X[k].to_numpy(dtype=float) == 0)) for k in keys}
        out[tier] = {"n_models": len(models), "n_pos": npos, "n_neg": nneg}
    return out


def composition(tier_models):
    mod = CX.model_table()
    sig = CX.signatures()
    out = {}
    for tier, models in tier_models.items():
        m = mod.reindex(models)
        s = sig.reindex(models)
        out[tier] = {
            "n": len(models),
            "lineage_share": {k: round(v, 4) for k, v in
                              m.OncotreeLineage.fillna("UNKNOWN").value_counts(normalize=True)
                              .head(10).items()},
            "msi_high_share": round(float((s.MSIScore > CX.MSI_HI).mean()), 4),
            "wgd_share": round(float((s.WGD > 0).mean()), 4),
            "median_aneuploidy": (None if s.Aneuploidy.isna().all()
                                  else float(s.Aneuploidy.median())),
        }
    return out


def main():
    tm = tiers()
    sel = pd.read_csv(f"{ROOT}/results/selection.real.csv")
    gold = pd.DataFrame([p for p in json.load(
        open(f"{ROOT}/registration/gold_controls.json"))["pairs"] if p.get("available")])
    placebo = []
    for f in sorted(os.listdir(f"{ROOT}/results")):
        if f.startswith("selection.placebo") and f.endswith(".csv"):
            try:
                p = pd.read_csv(f"{ROOT}/results/{f}")
            except pd.errors.EmptyDataError:
                continue
            if len(p):
                placebo.append(p)
    placebo = (pd.concat(placebo, ignore_index=True) if placebo
               else pd.DataFrame({"context": [], "dep_gene": []}))

    ky = ky_targets()
    res = {"schema": "bio.tier-testability.v2",
           "meaning": ("computed from shared omics and library maps only, before the freeze. "
                       "These are the denominators the registered predictions are stated over."),
           "tier_models": {k: len(v) for k, v in tm.items()},
           "tier_composition": composition(tm),
           "ky_library_gene_coverage": {},
           "counts": {}, "denominators": {}}

    for name, pairs in [("primary", sel), ("gold", gold), ("placebo_pooled", placebo)]:
        if not len(pairs):
            res["counts"][name] = {}
            res["denominators"][name] = {t: 0 for t in tm}
            continue
        c = counts(pairs, tm)
        res["counts"][name] = c
        res["denominators"][name] = {}
        for tier in tm:
            ok = sum(1 for _, r in pairs.iterrows()
                     if c[tier]["n_pos"].get(r["context"], 0) >= MIN_TIER_POS
                     and c[tier]["n_neg"].get(r["context"], 0) >= MIN_TIER_POS
                     and r["dep_gene"] in ky)
            res["denominators"][name][tier] = int(ok)
        res["denominators"][name]["B_powered"] = int(sum(
            1 for _, r in pairs.iterrows()
            if c["B"]["n_pos"].get(r["context"], 0) >= KY_ONLY_POWERED
            and c["B"]["n_neg"].get(r["context"], 0) >= MIN_TIER_POS
            and r["dep_gene"] in ky))
        genes = sorted(set(pairs["dep_gene"]))
        res["ky_library_gene_coverage"][name] = {
            "dependency_genes": len(genes),
            "targeted_by_the_ky_library": sum(1 for g in genes if g in ky),
            "not_targeted": sorted(g for g in genes if g not in ky)}

    json.dump(res, open(f"{ROOT}/results/tier_testability.json", "w"), indent=1)
    print(json.dumps({"tier_models": res["tier_models"],
                      "denominators": res["denominators"],
                      "ky_coverage": {k: {kk: vv for kk, vv in v.items() if kk != "not_targeted"}
                                      for k, v in res["ky_library_gene_coverage"].items()}}, indent=1))


if __name__ == "__main__":
    main()
