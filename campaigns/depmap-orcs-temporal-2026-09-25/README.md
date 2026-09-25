# Campaign D — ORCS independent-screen replication

**Question:** do the 77 context->dependency associations frozen by the
DepMap campaign replicate in BioGRID ORCS 2.0.18 human CRISPR screens —
hundreds of independently published genome-scale screens the 24Q4
discovery pipeline never ingested?

**Registered design**

- Pair set: verbatim copy of the depmap campaign's frozen selection +
  placebos + gold controls (hash-pinned at prep).
- Holdout: `BIOGRID-ORCS-ALL-homo_sapiens-2.0.18.screens.tar.gz`
  (Release-Archive, compiled 2025-09-09), fetched sealed post-freeze;
  `confirm.py` verifies hash + registered URL + post-freeze timestamp.
- Usable screens: human, knockout, negative selection, viability-family
  phenotype, genome-scale (>= 5,000 scored genes); DepMap-ingested
  PMIDs excluded (29083409 Meyers, 30971826 Behan, 38215750 Pacini).
- Cell lines map to DepMap models via normalized name matching; context
  status recomputed from 24Q4 omics.
- Replication per pair: dep_gene's within-screen lethal rank (rank
  fraction, 0 = most lethal) is smaller in context-positive than
  context-negative screens — one-sided Mann-Whitney, BH q <= 0.10, each
  arm >= 3 usable mapped screens.
- Predictions and labels: `registration/protocol.json`.

**Provenance:** `registration/freeze.json` seals code + registration +
placebo set before the sealed fetch; `code/confirm.py` is the only code
path that opens the tarball.
