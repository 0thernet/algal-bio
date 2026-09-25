#!/usr/bin/env python3
"""Compute discovery effects for the frozen positive-control pairs.

These pairs are not chosen by the screen. They are published dependency
relationships plus four self-dependencies, and their replication rate in the
holdout is the sensitivity floor of the confirmation test itself: if a tier
cannot recover them, that tier cannot be read as evidence about anything else.

The set is deliberately mixed in strength. The self-dependencies are an upper
bound on what any tier can detect. The classical controls are large effects in
common contexts. The MATCHED controls were added so that the floor is measured
at something like the effect size and prevalence of the primary selection
rather than well above it, which is the only way a floor licenses reading a low
primary rate as evidence about the pairs rather than about the test.

A control is UNAVAILABLE, and belongs to no denominator, if its dependency gene
is outside the discovery dependency universe or its context holds in fewer
discovery models than the prevalence floor every screened context had to clear.
Both reasons are recorded here, before the freeze. Note that excluding common
essentials from the dependency universe removes some genuine published
relationships (PRMT5, SHOC2): a pan-lethal gene cannot show a context-specific
dependency in this design, and saying so in advance is better than reporting it
afterwards as a non-replication.
"""
import json, os, sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import stats as ST
import contexts as CX
import prep as PR
import screen as SC

ROOT = os.path.dirname(HERE)
LB_Z = 1.96
MIN_POS = PR.MIN_POS     # a control must clear the same prevalence floor as any
                         # context in the screen, or it is not a control here

CLASSICAL = [
    ("MUT_DAM:SMARCA4", "SMARCA2", "SMARCA4-mutant lines depend on the paralogue SMARCA2 (Hoffman 2014 PNAS 10.1073/pnas.1316793111; Wilson 2014 Mol Cell Biol 10.1128/MCB.01372-13)"),
    ("MUT_DAM:APC", "CTNNB1", "APC-mutant colorectal lines depend on beta-catenin (Wnt addiction; Rosenbluh 2012 Cell 10.1016/j.cell.2012.11.026)"),
    ("MUT_DAM:RB1", "CCND1", "RB1 loss removes the cyclin D1 requirement, so RB1-mutant lines are LESS dependent (positive beta) (Dean 2010 Cell Cycle 10.4161/cc.9.9.11545)"),
    ("MUT_HOT:RB1", "CCND1", "the same relationship read from hotspot calls (Dean 2010 Cell Cycle 10.4161/cc.9.9.11545)"),
    ("EXPR_LOW:MLH1", "WRN", "mismatch-repair loss creates WRN dependency (Chan 2019 Nature 10.1038/s41586-019-1102-x; Behan 2019 Nature 10.1038/s41586-019-1103-9; Kategaya 2019 iScience 10.1016/j.isci.2019.02.006)"),
    ("SIG:MSI_HIGH", "WRN", "microsatellite instability creates WRN dependency (Chan 2019 Nature 10.1038/s41586-019-1102-x; Behan 2019 Nature 10.1038/s41586-019-1103-9; Kategaya 2019 iScience 10.1016/j.isci.2019.02.006)"),
    ("EXPR_LOW:RPP25", "RPP25L", "paralogue synthetic lethality (De Kegel 2021 Cell Syst 10.1016/j.cels.2021.08.006)"),
    ("EXPR_LOW:TTC7B", "TTC7A", "paralogue synthetic lethality (De Kegel 2021 Cell Syst 10.1016/j.cels.2021.08.006)"),
    ("EXPR_LOW:CYB5A", "CYB5B", "paralogue synthetic lethality (De Kegel 2021 Cell Syst 10.1016/j.cels.2021.08.006)"),
    ("MUT_HOT:BRAF", "MAPK1", "BRAF-mutant lines depend on ERK2/MAPK1 (Yao 2017 Nature 10.1038/nature23291)"),
    ("MUT_HOT:NRAS", "SHOC2", "RAS-mutant lines depend on the SHOC2 scaffold (Sulahian 2019 Cell Rep 10.1016/j.celrep.2019.09.025)"),
]
# Each matched control carries the context MODALITY ITS PUBLICATION REPORTS:
# deletion for the collateral-lethality pairs, mutation for the loss-of-function
# drivers, loss of expression only where the paper measures expression. An
# earlier draft filed the deletion pairs under EXPR_LOW, which contradicted its
# own citations; that is corrected here, before the freeze.
MATCHED = [
    ("MUT_DAM:ARID1A", "ARID1B", "ARID1A-mutant lines depend on the paralogue ARID1B (Helming 2014 Nat Med 10.1038/nm.3480)"),
    ("DEL:VPS4A", "VPS4B", "VPS4A deletion creates VPS4B dependency (Neggers 2020 Cell Rep 10.1016/j.celrep.2020.108493; Szymanska 2020 EMBO Mol Med 10.15252/emmm.202013125)"),
    ("MUT_DAM:STAG2", "STAG1", "STAG2 loss-of-function creates STAG1 dependency (van der Lelij 2017 eLife 10.7554/eLife.26980; Benedetti 2017 Oncotarget 10.18632/oncotarget.16391)"),
    ("MUT_DAM:CREBBP", "EP300", "CREBBP-mutant lines depend on the paralogue EP300 (Ogiwara 2016 Cancer Discov 10.1158/2159-8290.CD-15-0754)"),
    ("MUT_DAM:SMARCB1", "EZH2", "SMARCB1 loss creates EZH2 dependency (Wilson 2010 Cancer Cell 10.1016/j.ccr.2010.09.006; Knutson 2013 PNAS 10.1073/pnas.1303800110)"),
    ("EXPR_LOW:NAPRT", "NAMPT", "NAPRT silencing creates NAMPT dependency (Chowdhry 2019 Nature 10.1038/s41586-019-1150-2; Tateishi 2016 Cancer Cell 10.1016/j.ccell.2015.12.009)"),
    ("DEL:ENO1", "ENO2", "1p36 ENO1 deletion creates ENO2 dependency, collateral lethality (Muller 2012 Nature 10.1038/nature11331)"),
    ("DEL:ME2", "ME3", "ME2 deletion creates ME3 dependency, collateral lethality (Dey 2017 Nature 10.1038/nature21052)"),
    ("DEL:MTAP", "PRMT5", "MTAP deletion creates PRMT5 dependency (Mavrakis 2016 Science 10.1126/science.aad5944; Kryukov 2016 Science 10.1126/science.aad5214)"),
]
SELF = [
    ("MUT_HOT:BRAF", "BRAF", "self-dependency: the strongest detectable signal, an upper bound on tier sensitivity"),
    ("MUT_HOT:NRAS", "NRAS", "self-dependency"),
    ("MUT_HOT:PIK3CA", "PIK3CA", "self-dependency"),
    ("MUT_HOT:KRAS", "KRAS", "self-dependency"),
]
GOLD = ([(c, d, n, "classical") for c, d, n in CLASSICAL]
        + [(c, d, n, "matched") for c, d, n in MATCHED]
        + [(c, d, n, "self") for c, d, n in SELF])


def main():
    dep = np.load(f"{ROOT}/data/prep/dep.npz", allow_pickle=False)
    Y = dep["dep"]
    models = list(dep["models"])
    genes = list(dep["genes"])
    gi = {g: i for i, g in enumerate(genes)}
    X = CX.build([c for c, _, _, _ in GOLD], models)
    Z = CX.covariates_for(models)
    ess = set(CX.strip_entrez(pd.read_csv(
        f"{ROOT}/data/depmap24q4/AchillesCommonEssentialControls.csv").Gene))
    out = []
    for ctx, dg, note, cls in GOLD:
        rec = {"context": ctx, "dep_gene": dg, "class": cls, "note": note}
        if dg not in gi:
            why = ("the dependency gene is a reference common essential, so it is outside the "
                   "discovery dependency universe by design: a pan-lethal gene cannot show a "
                   "context-specific dependency here") if dg in ess else \
                  ("the dependency gene is outside the discovery dependency universe: its gene "
                   "effect does not vary enough across discovery models to be tested")
            out.append({**rec, "available": False, "why": why})
            continue
        x = X[ctx].to_numpy(dtype=float)
        y = Y[:, gi[dg]].astype(float)
        ok = np.isfinite(x) & np.isfinite(y)
        n_pos = int((x[ok] == 1).sum())
        if n_pos < MIN_POS:
            out.append({**rec, "available": False, "n_pos": n_pos,
                        "why": f"the context holds in {n_pos} discovery models, below the "
                               f"prevalence floor of {MIN_POS} that every screened context cleared"})
            continue
        b, r, p, se, df = ST.associate(y[ok][:, None], x[ok][:, None], Z[ok])
        beta, lb = float(b[0, 0]), float(abs(b[0, 0]) - LB_Z * se[0, 0])
        out.append({**rec, "available": True,
                    # A replication rule needs a discovery effect to replicate. A
                    # control the discovery screen itself does not detect at the
                    # threshold every primary pair had to clear carries no sign and
                    # no magnitude to carry forward, so it is reported but is not a
                    # member of the sensitivity-floor denominator. This makes the
                    # floor easier to pass, and both rates are reported.
                    "meets_discovery_floor": bool(abs(beta) >= SC.MIN_ABS_BETA
                                                  and lb >= SC.MIN_BETA_LB),
                    "beta": beta, "se": float(se[0, 0]), "p": float(p[0, 0]),
                    "beta_lb": lb,
                    "dep_sd_discovery": float(np.std(y[ok])),
                    "n": int(ok.sum()), "n_pos": n_pos})
    avail = [o for o in out if o.get("available")]
    floor = [o for o in avail if o["meets_discovery_floor"]]
    payload = {"schema": "bio.gold-controls.v2",
               "purpose": "sensitivity floor for the holdout confirmation test",
               "selection": "fixed by published prior evidence before the confirmation run; not produced by the screen",
               "floor_rule": ("a control enters the sensitivity-floor denominator only if the "
                              "discovery screen itself detects it at the same threshold every "
                              "primary pair had to clear: |beta| >= "
                              f"{SC.MIN_ABS_BETA} and 95 percent lower bound >= {SC.MIN_BETA_LB}. "
                              "A published relationship the discovery panel does not show is "
                              "reported as such and predicts nothing about the holdout."),
               "denominators_fixed_here": {
                   "all_available": len(avail),
                   "floor_denominator": len(floor),
                   "self_dependencies": sum(1 for o in floor if o["class"] == "self"),
                   "classical": sum(1 for o in floor if o["class"] == "classical"),
                   "matched": sum(1 for o in floor if o["class"] == "matched"),
                   "available_but_not_detected_in_discovery": [
                       f"{o['context']}->{o['dep_gene']}" for o in avail
                       if not o["meets_discovery_floor"]],
                   "unavailable": [f"{o['context']}->{o['dep_gene']}" for o in out
                                   if not o.get("available")],
                   "unavailable_why": {f"{o['context']}->{o['dep_gene']}": o["why"]
                                       for o in out if not o.get("available")}},
               "pairs": out}
    os.makedirs(f"{ROOT}/registration", exist_ok=True)
    json.dump(payload, open(f"{ROOT}/registration/gold_controls.json", "w"), indent=1)
    print(json.dumps({k: v for k, v in payload.items() if k != "pairs"}, indent=1))
    for o in out:
        print(f"{o['class']:9s} {o['context']:22s} -> {o['dep_gene']:8s} "
              + (f"beta {o['beta']:+.3f} lb {o['beta_lb']:+.3f} n_pos {o['n_pos']}"
                 + ("" if o["meets_discovery_floor"] else "  [below the discovery floor]")
                 if o.get("available") else f"UNAVAILABLE ({o['why']})"))


if __name__ == "__main__":
    main()
