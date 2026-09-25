# Paralog synthetic lethality — combinatorial double-KO holdout outcome

**Registered label: DOUBLEKO_REPLICATED** (run 2026-09-25T19:31:20Z under freeze `f875b1ef`)

## Question

Do paralog-loss events (deep deletion, expression silencing, loss-of-function
mutation) in cancer cell lines predict increased dependency on the retained
paralog partner, at rates that transfer into combinatorial double-knockout
CRISPR screens?

## Design recap

- Discovery: conjunctive — a pair must pass registered filters on BOTH the
  Avana and KY single-KO libraries (KY is seen data in this campaign).
- Holdout: published combinatorial double-KO tables, opened once after the
  freeze; only in4mer's unified re-scoring table parsed (pgPEN supplements
  were retrievable only as HTML error pages from PMC — recorded as
  UNPARSEABLE; Flister 2025 has no open deposit — ABSENT).
- Asymmetric prediction per holdout line: context-positive -> the partner's
  single-KO score in the line's bottom 5%; context-negative -> the dataset's
  own synthetic-lethal pair call.
- Universe: 160 directed paralog pairs (Ensembl, %id >= 40, multi-targeting
  guide exclusion); selection: 10 pairs (4 LOF, 6 EXPR_LOW).

## Result against the registered predictions

| prediction | observed | threshold | verdict |
|---|---|---|---|
| P1 replication rate | 4/9 tested pairs = 0.44 | >= 0.30 | pass |
| P2 placebo rate | no placebo pair was ever nominated (5 seeds) | <= 0.15 | pass by zero-nomination convention (disclosed, thin) |
| P3 enrichment over base rate | 3.13x (9.4% vs 3.0% in the same dataset-lines) | >= 1.5 | pass |
| P4 novel pairs | 1/1 tested, replicated; only 2 novel pairs exist -> below the 5-pair evaluability floor | >= 0.25 & >=5 | not evaluable (registered convention: reported, not gated) |
| P5 gold controls | 13/19 tested = 0.68 | >= 0.5 | pass |

## The replications

- `LOF:SMARCA4 -> SMARCA2`: partner single-KO lethal (sko -1.6) in A549, a
  SMARCA4-deficient line — the canonical SWI/SNF paralog-buffering mechanism
  on a context-positive line.
- `EXPR_LOW:TTC7B -> TTC7A`: synthetic-lethal pair calls in A375 and MeWo.
  This pair is a *documented non-SL negative* in the reference tables —
  replication here contradicts a prior screen.
- `EXPR_LOW:FERMT1 -> FERMT2`: partner single-KO lethal in Meljuso and MeWo.
- `EXPR_LOW:SLC16A3 -> SLC16A1`: synthetic-lethal pair call in HAP1 — one of
  the two novel (reference-absent) pairs.

Gold controls replicate bidirectionally where buffering is reciprocal
(CCNL1/2, GSK3A/B, ASF1A/B, COPS7A/B) — as biology predicts.

## Provenance and the disclosed erratum

The registration was cut four times before any holdout score was read —
each re-cut repaired parse/registration bugs found by the header-only
inspection path (wrong PMC URL form, pair-separator, empty placebo CSVs,
refs-receipt path resolution). One substantive erratum is recorded in
`registration/holdout_map.json`: the in4mer hit rule was initially
registered as `dLFC <= -0.5 AND Cohen's d <= -1.0`, which misstates the
published convention both in threshold and direction. The frozen rule is
the paper's literal one — `dLFC < -1 AND Cohen's D > 0.8`
(Esmaeili Anvar et al. 2024, Methods). An evaluation under the
misregistered rule ran first and produced UNDERPOWERED (P5 1/19); the runs
ledger and this note disclose that outcome.

## Honest limits

- Single parsed holdout dataset (in4mer): 63,784 rows, 7,011 pairs, ~22
  study-lines; only 9/10 selected pairs were holdout-covered.
- 4/9 replication rests on 6 events; three are partner-single-KO calls — a
  weakly pair-specific test (a variably-essential partner passes for
  unrelated reasons).
- Three documented-nonSL negatives and the three known SLs are the
  "calibration" signal; only 2 pairs were strictly novel and only 1 was
  holdout-tested.
- Placebo P2 passes by the disclosed zero-nomination convention — the
  selection pipeline simply nominated no placebo pairs across 5 seeds;
  this is thin evidence, not a measured holdout rate.
- pgPEN direct tables never parsed (PMC serves HTML to non-browser
  clients); Flister 2025 has no public deposit. Both are recorded as
  unavailable rather than silently dropped.
- Associations, not mechanisms. The context-conditional claim (line
  context predicts which outcome resolves) is the distinguishing
  contribution; the headline is a rate, not a new biology fact.
