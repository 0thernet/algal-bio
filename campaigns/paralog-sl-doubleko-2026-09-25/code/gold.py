#!/usr/bin/env python3
"""Gold controls: canonical paralog synthetic-lethal pairs.

These serve two roles: sensitivity controls (the holdout MUST detect these
where it screened them) and calibration. Fixed list, fixed denominators.
Direction field records which partner is the lost-context gene in the
canonical biology; where the loss context is genomic (deletion) both
directions are listed.
"""
import json, os, sys
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import campaign as C

# (lost gene, dependent partner, context kind tried in order, basis)
GOLD = [
    ("STAG2", "STAG1", ("LOF", "DEL", "EXPR_LOW"), "van der Lelij 2017; widely replicated"),
    ("STAG1", "STAG2", ("DEL", "EXPR_LOW", "LOF"), "bidirectional coherence"),
    ("SMARCA4", "SMARCA2", ("LOF", "DEL", "EXPR_LOW"), "Hoffman 2014"),
    ("ARID1A", "ARID1B", ("LOF", "DEL", "EXPR_LOW"), "Helming 2014"),
    ("MAP2K1", "MAP2K2", ("EXPR_LOW", "DEL"), "pgPEN gold standard"),
    ("MAP2K2", "MAP2K1", ("EXPR_LOW", "DEL"), "pgPEN gold standard"),
    ("CDK4", "CDK6", ("EXPR_LOW", "DEL"), "pgPEN gold standard"),
    ("CDK6", "CDK4", ("EXPR_LOW", "DEL"), "pgPEN gold standard"),
    ("CCNL1", "CCNL2", ("EXPR_LOW", "DEL"), "Parrish 2021 top hit"),
    ("CCNL2", "CCNL1", ("EXPR_LOW", "DEL"), "Parrish 2021 top hit"),
    ("FAM50B", "FAM50A", ("EXPR_LOW", "DEL"), "Thompson 2021: FAM50B silencing -> FAM50A dep"),
    ("ENO1", "ENO2", ("DEL", "EXPR_LOW"), "Muller 2012 collateral lethality (1p36)"),
    ("GSK3A", "GSK3B", ("EXPR_LOW", "DEL"), "pgPEN PC9/HeLa SL"),
    ("GSK3B", "GSK3A", ("EXPR_LOW", "DEL"), "pgPEN PC9/HeLa SL"),
    ("CNOT7", "CNOT8", ("EXPR_LOW", "DEL"), "pgPEN SL"),
    ("ASF1A", "ASF1B", ("EXPR_LOW", "DEL"), "De Kegel wet-validated, HAP1"),
    ("ASF1B", "ASF1A", ("EXPR_LOW", "DEL"), "De Kegel wet-validated, HAP1"),
    ("COPS7A", "COPS7B", ("EXPR_LOW", "DEL"), "De Kegel wet-validated, HAP1"),
    ("COPS7B", "COPS7A", ("EXPR_LOW", "DEL"), "De Kegel wet-validated, HAP1"),
    ("PA2G4", "PA2G4P4", ("EXPR_LOW", "DEL"), "reported SL (paralog pseudogene edge - only if map covers)"),
]


def main():
    uni = pd.read_csv(f"{C.PREP}/pair_universe.csv")
    ky_pos = json.load(open(f"{C.PREP}/ky_pos.json"))
    in_uni = set(zip(uni.context, uni.dep_gene))
    sel_path = f"{C.OUT}/selection.real.csv"
    sel = pd.read_csv(sel_path) if os.path.exists(sel_path) else pd.DataFrame()
    sel_keys = set(zip(sel.context, sel.dep_gene)) if len(sel) else set()

    pairs = []
    for a, b, kinds, basis in GOLD:
        # The gold pair's registered context is the first kind whose context
        # gene is computable; gold controls exercise the HOLDOUT's ability to
        # detect published SLs, so they need not be in the discovery universe.
        hit = None
        for kd in kinds:
            cn = f"{kd}:{a}"
            if (cn, b) in in_uni:
                hit = cn
                break
        if hit is None:
            hit = f"{kinds[0]}:{a}"   # evaluable in the holdout regardless
        pairs.append({"context_gene": a, "dep_gene": b,
                      "context": hit, "available": True,
                      "in_universe": (hit, b) in in_uni,
                      "pair": "|".join(sorted((a, b))),
                      "ky_pos": ky_pos.get(hit, 0),
                      "basis": basis,
                      "nominated_by_screen": (hit, b) in sel_keys})
    df = pd.DataFrame(pairs)
    denoms = {"registered_pairs": len(df),
              "in_universe": int(df.in_universe.sum()),
              "nominated_by_screen": int(df.nominated_by_screen.sum()),
              "independent_controls": int((~df.nominated_by_screen).sum())}
    os.makedirs(f"{C.ROOT}/registration", exist_ok=True)
    json.dump({"pairs": pairs, "denominators_fixed_here": denoms},
              open(f"{C.ROOT}/registration/gold_controls.json", "w"), indent=1)
    print(json.dumps(denoms, indent=1))


if __name__ == "__main__":
    main()
