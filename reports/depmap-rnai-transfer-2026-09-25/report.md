# depmap-rnai-transfer-2026-09-25 — RNAi transfer outcome

**Label: `RNAI_REPLICATED`** — the depmap campaign's 77 registered
context->dependency pairs replicate under RNAi knockdown (DEMETER2 v6),
a perturbation chemistry sharing neither Cas9 cutting nor guide
cross-targeting.

## Numbers

| set | tested | replicated | rate |
|-----|--------|------------|------|
| primary | 72 | 41 | **0.569** (P1 >= 0.30 PASS) |
| novel (is_novel subset) | 31 | 18 | 0.581 (P4 >= 0.25 & >=3 PASS) |
| placebo | 3 | 0 | 0.000 (P2 <= 0.15 PASS; 1 seed's CSV was empty — recorded) |
| gold (floor subset) | 15 | 11 | **0.733** (P5 >= 0.5 PASS) |

5 of 77 primary pairs untested (dep gene absent from the D2 combined
matrix or under the MIN_N/MIN_POS floors on the 704 D2-mapped models).

## Context-kind stratification (registered priors)

| context kind | tested | replicated | rate |
|---|---|---|---|
| DEL | 4 | 0 | **0.000** |
| EXPR_LOW | 47 | 26 | 0.553 |
| MUT_DAM | 16 | 10 | 0.625 |
| MUT_HOT | 4 | 4 | 1.000 |
| SIG | 1 | 1 | 1.000 |

The registered prior — amplification/aneuploidy and copy-number contexts
are expected NOT to transfer under RNAi (they are the classic CRISPR
cut-site-toxicity class) — holds: **all four DEL-context pairs fail**,
including the FOCAD->PELO deletion association, while mutation- and
expression-silencing contexts transfer at ~0.55-0.63. This is the
artifact-adjudication result the campaign was built for: the non-CNV
associations are perturbation-independent biology; the CNV associations
were not.

## Provenance & errata

- Pre-freeze independent review: initial FAIL (3 blockers: empty-placebo
  crash, missing results dir, unbound sibling machinery; + majors:
  requirement-driven sealed checks, placebo injection guard, gold floor
  restricted to the controls file's own 16-pair denominator, fail-closed
  discovery sd). All repaired; `registration/prefreeze-review.json`.
- Frozen 2026-09-25T20:34:53Z (top_digest f9cf08fb); preregistration
  public as PR #17 before any sealed fetch.
- Run 1 (20:34:04Z, digest c524f5a6) read the holdout and produced
  `NOT_EVALUABLE` with zero pairs tested: `load_d2` read the
  D2_combined matrix in the wrong orientation (genes are rows
  'NAME (entrez)', CCLE columns) *and* stripped entrez suffixes from the
  wrong axis. Fixed in `load_d2`; the run and its artifacts are preserved
  (`results/confirmation.run1-bad-orientation.*`, runs ledger).
- Run 2 (20:41:26Z, this report): correct orientation; all numbers above.

## Honest reading

- Strength: a calibrated, mechanistically coherent transfer result —
  0.57 overall, 0.58 among reference-novel pairs, CNV contexts correctly
  predicted to fail.
- Caveats: D2 lines substantially overlap discovery models (assay-level,
  not cohort-level, independence); non-replication is ambiguous between
  artifact and incomplete knockdown; only 3 tested placebo pairs is a
  thin P2 denominator; this is an association-level transfer claim, not
  mechanism.
