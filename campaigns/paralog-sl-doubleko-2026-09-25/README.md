# Campaign A — paralog synthetic lethality, combinatorial-KO holdout

**Question:** do paralog-loss events (deep deletion, expression silencing,
loss-of-function mutation) in cancer cell lines predict increased dependency
on the retained paralog partner, at rates that transfer into combinatorial
double-knockout CRISPR screens?

**Why it differs from the earlier campaign:** the discovery-side association
is now *conjunctive* — a pair must pass the registered filters on BOTH the
Avana and the KY single-KO libraries (KY is seen data for this campaign and
correctly sits inside discovery). The sealed holdout is a different assay
class entirely: combinatorial double-KO interaction tables.

**Registered design**

- Pair universe: Ensembl paralog pairs, max %id >= 40; directed
  context -> dependency edges where the context is a paralog-loss event on A
  and the dependency gene is A's paralog partner B.
- Contexts: `DEL` / `EXPR_LOW` / `LOF` (the last built from
  OmicsSomaticMutations' own LikelyLoF calls — the damaging-mutation matrix
  was rejected because it is not LoF-specific).
- Pairs excluded when the dep gene carries any multi-aligning Chronos-used
  guide in either library (paralog cross-targeting confound, Fortin 2019).
- Discovery: AV beta <= -0.30 with shrunken LB and BH q <= 0.01 over the
  universe, AND KY beta <= -0.15 with one-sided p < 0.05, dep gene expressed
  among context-positive AV models; diversity caps; strata by context kind.
- Holdout predictions are asymmetric by line context (see protocol): a
  context-positive line predicts the partner's single-KO is lethal; a
  context-negative line predicts a synthetic-lethal pair call.
- Holdout corpus: in4mer unified re-scoring (six studies, ~20 lines),
  Parrish Table S4, Flister 2025 Table S2 if fetchable.
- Predictions P1–P5, labels and caveats: `registration/protocol.json`.

**Provenance:** every input and output is hash-pinned in
`data/prep/prep.receipt.json`; `registration/freeze.json` seals code +
registration before `code/fetch_holdout.py` may run; `code/confirm.py` is the
only code path that opens holdout score data.

**Novelty claim:** PARTIALLY_KNOWN method (De Kegel & Ryan 2021, Köferle 2022,
Kebabci 2026), novel rigor axis — see `prior-art/prior-art-paralog-sl.md`.

**Registered selection** (results/selection.annotated.csv, frozen): 10 pairs —
3 documented SLs (STAG2→STAG1, SMARCA4→SMARCA2, EP300→CREBBP, doubling as
calibration), 2 pairs absent from both reference classes, and 5 pairs the
literature records as tested non-SL negatives — replication of the last class
would contradict a prior screen and is scored as its own class, never as
novelty. All five placebo seeds nominated zero pairs; P2 therefore passes by
the disclosed zero-nomination convention and its evidence is thin.
