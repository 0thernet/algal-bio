# Outcome: context-specific dependencies against a sealed cross-library holdout (2026-09-25)

**Registered label: CROSS_PLATFORM_REPLICATED.** All five pre-registered predictions passed. The headline independent-cell-line estimate is **18 of 35 powered pairs (0.51, Wilson 95% CI 0.36 to 0.67)** replicating in 119 Sanger KY cell lines that the Broad Avana discovery screen never saw. Across all 315 KY lines, which include 196 lines shared with discovery, 66 of 77 replicate (0.86, CI 0.76 to 0.92).

## Order of events after the freeze (UTC, 2026-09-25)

The campaign README is bound by the freeze and ends before it, so the rest of the order of events is recorded here.

- 07:39:48 `registration/freeze.json`: 54 files bound, top digest `688981057cb7...`; four sealed resources hashed, none read.
- 07:44:54 pre-registration published: algal-bio PR #12 merged as `91c349c`.
- 07:52:14 `code/confirm.py`, the only code that reads the seal, verified the freeze (54 frozen files, 4 sealed resources, 33 receipted inputs) and then opened the KY matrix once. `results/confirmation.runs.jsonl` holds exactly one run, with `rerun: false`.

## Registered predictions

| prediction | registered rule | observed | result |
|---|---|---|---|
| P1 | tier A rate >= 0.40 and placebo <= 1/3 of it | 66/77 = 0.857; placebo 0/3 | pass |
| P2 | tier A placebo rate <= 0.15 | 0/3 = 0.0 | pass |
| P3 | tier B powered rate >= 0.25 | 18/35 = 0.514 | pass |
| P4 | novel tier A rate >= 0.30 and >= 5 pairs | 27/34 = 0.794 | pass |
| P5 | all 4 self-dependencies, and >= 0.5 of the uncorrelated floor (fixed denominator 3) | 4/4; 2/3 | pass |

Every denominator equals the value fixed before the freeze, except the placebo arm: 4 placebo pairs were context-testable in tier A beforehand, and 3 met the model-count requirement once the sealed matrix was read. Under the registered convention the fourth is NOT TESTED rather than failed. Either way, one placebo replication would have made the rate 1/3 and labelled the run PLACEBO_BREACH.

## Reported without prediction

- Tier A_shared (196 shared lines): 63/77 = 0.82. Tier B, all testable pairs: 27/63 = 0.43. Tier C (Cas12a, a different nuclease): 18/42 = 0.43.
- Already known vs novel: tier A 39/43 vs 27/34; tier B 16/37 vs 11/26. Being novel does not reduce transfer to independent lines.
- Sign agreement, discovery vs holdout beta: tier A 0.97 (beta correlation 0.75); tier B 0.78 (0.57).
- Calibration over all 141 selectable candidates: 113/141 replicate in tier A. By decile of shrunken discovery effect the rate rises from 6/15 to 13-14 of 14, so replication tracks discovery effect size.
- Positive controls: 15/17 overall in tier A; classical 9/10, matched 2/3, self 4/4.
- Placebo in tier A_shared: 1/3 replicated. When cell lines are shared, the pipeline can manufacture a replication.

## Candidate findings: novel pairs that replicate in independent cell lines (tier B)

These are associations (a low-expression or lesion context in one gene predicts stronger dependency on another), not mechanisms. "Novel" means absent from the reference classes in `registration/protocol.json` (paralogues, CORUM complexes, MSigDB pathways, SynLethDB); it does not mean previously unknown to science. Most have 4 to 7 context-positive holdout lines.

| context -> dependency | discovery beta | holdout beta (tier B) | holdout-only context-positive lines |
|---|---|---|---|
| EXPR_LOW:ZEB1 -> ITGAV | +0.30 | +0.28 | 30 (lineage-heavy, bowel-dominated) |
| EXPR_LOW:SEPTIN5 -> RAB6A | -0.32 | -0.22 | 13 |
| EXPR_LOW:GPX8 -> IRS2 | -0.36 | -0.34 | 7 |
| EXPR_LOW:MICALL2 -> FDPS | -0.36 | -0.93 | 4 |
| EXPR_LOW:KATNAL1 -> STX4 | -0.37 | -0.75 | 4 |
| EXPR_LOW:KATNAL1 -> STXBP3 | -0.30 | -0.38 | 4 (same context as STX4) |
| EXPR_LOW:AJUBA -> KTI12 | +0.41 | +0.55 | 4 |
| EXPR_LOW:LDAH -> HSD17B12 | -0.52 | -0.29 | 4 |
| MUT_DAM:KDM2B -> WRN | -0.51 | -0.68 | 4 (2 lineages; possibly an MSI-adjacent signal) |

**Not three findings:** DEL:FOCAD, DEL:HACD4 and DEL:IFNB1 -> PELO are all chr9p21 neighbours with near-identical holdout effects. They are one locus, and FOCAD/9p21-PELO collateral lethality is arguably published biology. Removing the whole cluster leaves P3 at 15/35 = 0.43, so the label does not depend on it.

## What may and may not be claimed

- **May claim:** under a design fixed and published in advance, most context-dependency associations nominated from the public Avana screens replicate when the CRISPR library and laboratory change (0.86). About half replicate in cell lines the discovery screen never saw (0.51, CI 0.36 to 0.67). Reference-absent pairs transfer at the same rate as known ones. The test was sensitive, recovering 4/4 self-dependencies and 15/17 controls.
- **May not claim:** mechanism or causality; independent cell lines in tier A; that "novel" means unknown to science; transfer to other screen collections (one holdout); or specificity beyond what 3 placebo pairs allow. The 0/3 placebo result excludes only placebo rates above about 0.56. The better-powered discovery-side placebo ratio was 0.051, marginally over its 0.05 ceiling, and was disclosed before the freeze.

## Reviews

- Pre-freeze: three independent reviews. The third is `registration/prefreeze-review-3.json` (PASS_WITH_REPAIRS, no blocker).
- Pre-registration PR #12: `review/pr12-review.json`.
- Post-outcome: `review/post-outcome-review.json` (PASS). It recomputed P1 to P5 and the label from `results/confirmation.csv`, and confirmed one run and freeze verification before the seal was read.

Paid spend: $0.
