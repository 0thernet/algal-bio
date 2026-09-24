#!/usr/bin/env python3
"""Report-time secondary (registered in secondary_reported_only; no threshold depends on it):
per chromosome, the method-validation agreement of pc1.py with the deposited GSE126459 PC1
(design/method-validation.json) beside the unadjusted Spearman between dlam_mCh and
dPC1 = mean(KO) - mean(WT) over that chromosome's eligible tiles (results/run-001/core/tiles.tsv).
Usage: per_chromosome_table.py <method-validation.json> <tiles.tsv> <registration.json> <out.json>
"""
import json, sys
import numpy as np
import compartment as C
mv = json.load(open(sys.argv[1])); reg = json.load(open(sys.argv[3]))
samples = reg["outcome"]["samples"]
ko = [g for g, m in samples.items() if m["condition"] == "KO"]; wt = [g for g, m in samples.items() if m["condition"] == "WT"]
rows = [l.rstrip("\n").split("\t") for l in open(sys.argv[2], encoding="utf-8")]
cols, rows = rows[0], rows[1:]
ci = {c: i for i, c in enumerate(cols)}
chrom = np.array([r[ci["chrom"]] for r in rows])
dlam = np.array([float(r[ci["dlam_mCh"]]) for r in rows])
pc1 = {g: np.array([float(r[ci[f"pc1_{g}"]]) for r in rows]) for g in samples}
dpc1 = np.mean([pc1[g] for g in ko], axis=0) - np.mean([pc1[g] for g in wt], axis=0)
table = {}
for c in reg["tiles"]["chromosomes"]:
    idx = chrom == c
    val = {gsm: mv["samples"][gsm]["per_chromosome_spearman"].get(c) for gsm in mv["samples"]}
    table[c] = {"n_eligible_tiles": int(idx.sum()),
                "validation_spearman_vs_deposited_pc1": val,
                "outcome_unadjusted_rho_dlam_vs_dpc1": float(C.spearman(dlam[idx], dpc1[idx])) if idx.sum() >= 10 else None}
out = {"schema": "bio.per-chromosome-validation-vs-outcome.v1", "note": "report-time join of two mechanically produced records; exploratory; no p-values; no threshold depends on it", "per_chromosome": table}
json.dump(out, open(sys.argv[4], "w"), indent=2); open(sys.argv[4], "a").write("\n")
for c, t in table.items():
    v = t["validation_spearman_vs_deposited_pc1"]
    print(c, t["n_eligible_tiles"], {k: (None if x is None else round(x, 2)) for k, x in v.items()}, None if t["outcome_unadjusted_rho_dlam_vs_dpc1"] is None else round(t["outcome_unadjusted_rho_dlam_vs_dpc1"], 3))
