# Campaign C — RNAi transfer of the registered context->dependency pairs

**Question:** do the 77 context->dependency associations selected and frozen
by the DepMap campaign (sealed-holdout campaign, PRs #12/#13 in the public
repository) replicate under a different perturbation chemistry — RNAi
knockdown — in the DEMETER2 v6 combined matrix?

**Why it matters:** CRISPR-specific artifacts (cut-site toxicity, guide
cross-targeting) cannot replicate under RNAi, which shares neither
mechanism. Transfer here would argue the associations are
perturbation-independent biology; failure is ambiguous between artifact
and incomplete knockdown, and per-context-kind rates are reported.

**Registered design**

- Pair set: verbatim copy of the DepMap campaign's frozen selection
  (`registration/depmap_pairs.csv`, hash-pinned at prep time), its placebo
  selections, and its gold controls. DEMETER2 has never influenced the set.
- Holdout: DEMETER2 v6 (`D2_combined_gene_dep_scores.csv`, figshare
  10.6084/m9.figshare.6025238), fetched sealed only after the freeze;
  `confirm.py` verifies hash + registered URL + post-freeze timestamp.
- Replication: same sign as the discovery beta, one-sided p < 0.05, and a
  standardized holdout effect >= 0.5x the standardized shrunken discovery
  effect.
- Contexts recomputed from DepMap 24Q4 omics on D2-mapped models
  (704/712 lines mapped pre-freeze).
- Predictions P1/P2/P4/P5 and labels: `registration/protocol.json`.

**Provenance:** `data/prep/prep.receipt.json` pins the copied pair set and
the sample map; `registration/freeze.json` seals code + registration
before any sealed fetch; `code/confirm.py` is the only code path that
opens the D2 matrix.
