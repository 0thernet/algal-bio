# Campaign B — GDSC2 → PRISM drug-biomarker transfer

**Question:** do biomarker→drug-sensitivity associations discovered in
GDSC2 (fitted LN_IC50, covariate-adjusted) replicate at the association
level in the sealed PRISM 19Q4 Repurposing matrix? The GDSC↔PRISM
consistency debate is a decade old; this is a registered, sealed-holdout
association-level test.

**Registered design**

- Discovery: GDSC2 27Oct23 fitted dose-response; contexts are DepMap
  24Q4 omics on Sanger-mapped models; sensitizing associations
  (beta <= -0.35, q <= 0.01) with >=8 ctx+ and >=40 fitted models.
- Drug matching by InChIKey connectivity layer only: GDSC names resolved
  via PubChem (pinned reference), PRISM SMILES resolved via RDKit.
- Floor-effect compounds excluded a priori (>=8 in-range sensitive
  lines); they can never enter the denominator.
- Holdout: sealed PRISM secondary-screen replicate-collapsed log2FC,
  fetched post-freeze; the same association reruns with the depmap
  covariate design; replication = same sign + one-sided p<0.05 +
  |z| >= 0.5x discovery.
- Predictions/labels in `registration/protocol.json`; gold anchors in
  `registration/gold_controls.json`.

**Provenance:** freeze binds code + registration + the drug crosswalk +
discovery matrix receipt; `confirm.py` is the only path opening PRISM.
