#!/usr/bin/env python3
"""Prep for the GDSC2->PRISM campaign.

1. GDSC2 fitted dose-response -> models x drugs LN_IC50 matrix
   (SANGER_MODEL_ID -> DepMap ModelID via Model.csv; drop fits the GDSC
   release itself flags unusable).
2. Drug crosswalk: GDSC DRUG_NAME (+SYNONYMS) -> PubChem canonical SMILES
   -> InChIKey connectivity layer; PRISM treatment metadata SMILES ->
   InChIKey via RDKit. Drug identity = inchikey1 match only.
3. Contexts come from the depmap omics at confirm time; prep just pins
   the model set.
"""
import json, os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import campaign as C

DEPMAP = C.DEPMAP
MIN_SENSITIVE = 8         # drug needs >= 8 in-range sensitive lines
MIN_MODELS = 30


def main():
    os.makedirs(C.PREP, exist_ok=True)
    receipt = {"inputs": {}, "outputs": {}}
    ds = f"{C.ROOT}/data/discovery/GDSC2_fitted_dose_response_27Oct23.csv"
    receipt["inputs"]["data/discovery/GDSC2_fitted_dose_response_27Oct23.csv"] \
        = C.sha(ds)
    g = pd.read_csv(ds)
    g = g[g.DATASET == "GDSC2"]

    # SANGER_MODEL_ID -> ModelID
    m = pd.read_csv(f"{C.DD}/Model.csv", index_col=0)
    smap = {str(r.SangerModelID): i for i, r in m.iterrows()
            if isinstance(r.SangerModelID, str)}
    g["model"] = g.SANGER_MODEL_ID.astype(str).map(smap)
    g = g[g.model.notna() & g.LN_IC50.notna()]

    # per (drug, model): median of repeated curves
    piv = g.groupby(["DRUG_NAME", "model"]).LN_IC50.median().unstack(0)
    # drug eligibility: in-range sensitive fraction + nonzero spread
    mx = g.groupby(["DRUG_NAME", "model"]).MAX_CONC.median().unstack(0)
    sens = (piv < np.log(mx.clip(lower=1e-6))).sum(0)   # LN_IC50 < ln(MAX_CONC)
    keep_drugs = piv.columns[(sens >= MIN_SENSITIVE)
                             & (piv.std(0, skipna=True) > 0.05)]
    piv = piv[keep_drugs]
    # drop models with < MIN_MODELS drug values
    piv = piv[piv.notna().sum(1) >= MIN_MODELS]
    np.savez_compressed(f"{C.PREP}/gdsc2.npz", ic50=piv.to_numpy(dtype=float),
                        models=piv.index.to_numpy().astype(str),
                        drugs=piv.columns.to_numpy().astype(str))

    # GDSC name -> inchikey1 (PubChem reference, pre-resolved)
    comp = pd.read_csv(f"{C.ROOT}/data/refs/screened_compounds_rel_8.5.csv")
    g_names = comp.DRUG_NAME.dropna().unique()
    keys = {}
    if os.path.exists(f"{C.PREP}/gdsc_inchikey.json"):
        keys = json.load(open(f"{C.PREP}/gdsc_inchikey.json"))
    missing = [n for n in g_names if n not in keys]
    if missing:
        sys.exit(f"refusing: run fetch_drug_keys.py first for {len(missing)} "
                 f"GDSC names (writes data/refs/gdsc_inchikey.json)")
    # PRISM smiles -> inchikey1 via RDKit
    from rdkit import Chem
    from rdkit.Chem import inchi
    ti = pd.read_csv(f"{C.ROOT}/data/refs/prism19q4_sec_treatment_info.csv")
    ti = ti.drop_duplicates("broad_id")      # all secondary-screen batches
    pm = {}
    for _, r in ti.iterrows():
        # the SMILES field can carry comma-space-separated duplicates
        # (formulation variants); try each part
        parts = [p.strip() for p in str(r.smiles).split(", ") if p.strip()]
        parts += [str(r.smiles).strip().rstrip(",")]
        for smi in parts:
            mol = Chem.MolFromSmiles(smi)
            if mol is not None:
                pm[str(r.broad_id)] = inchi.MolToInchiKey(mol)[:14]
                break
    json.dump(pm, open(f"{C.PREP}/prism_inchikey.json", "w"), indent=1)

    # crosswalk: for each GDSC drug in the matrix, the PRISM broad_ids that
    # share its inchikey1
    p_inv = {}
    for bid, ik in pm.items():
        p_inv.setdefault(ik, []).append(bid)
    cross = {}
    for drug in piv.columns:
        ik = (keys.get(drug) or {}).get("inchikey")
        if ik:
            cross[drug] = {"inchikey1": ik[:14],
                           "prism_broad_ids": p_inv.get(ik[:14], [])}
    matched = [d for d, v in cross.items() if v["prism_broad_ids"]]
    json.dump(cross, open(f"{C.PREP}/drug_crosswalk.json", "w"), indent=1)
    receipt["inputs"]["data/refs/screened_compounds_rel_8.5.csv"] = C.sha(
        f"{C.ROOT}/data/refs/screened_compounds_rel_8.5.csv")
    receipt["inputs"]["data/refs/prism19q4_sec_treatment_info.csv"] = C.sha(
        f"{C.ROOT}/data/refs/prism19q4_sec_treatment_info.csv")
    receipt["inputs"]["data/prep/gdsc_inchikey.json"] = C.sha(
        f"{C.PREP}/gdsc_inchikey.json")
    for f in ("data/prep/gdsc2.npz", "data/prep/prism_inchikey.json",
              "data/prep/drug_crosswalk.json"):
        receipt["outputs"][f] = C.sha(f"{C.ROOT}/{f}")
    receipt["matrix"] = {"models": int(piv.shape[0]),
                         "drugs": int(piv.shape[1]),
                         "matched_to_prism": len(matched)}
    json.dump(receipt, open(f"{C.PREP}/prep.receipt.json", "w"), indent=1)
    print(json.dumps(receipt["matrix"], indent=1))


if __name__ == "__main__":
    main()
