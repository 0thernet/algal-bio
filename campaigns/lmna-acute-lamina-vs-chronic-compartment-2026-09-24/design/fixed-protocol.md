# Fixed-protocol design: acute lamina change vs chronic compartment change

Working directory is private; the public record is assembled after the run.

## Question
Do 500 kb autosomal tiles whose LMNB1 CUT&RUN z-score rises after 48 h
siLMNA in day-35 hiPSC-CMs (Shen 2026, GSE300197; exposed predictor) show a
lower Hi-C PC1 in chronic LMNA R225X day-14 hiPSC-CMs than in each isogenic
corrected clone (Bertero 2019, GSE126459; untouched outcome)?

## Why this test
- Predictor and outcome come from different labs, assays, differentiation
  stages and perturbations, and are both hg38 at compatible resolution.
- The outcome has replicate-level tracks and two independent corrected-clone
  contrasts, so replicate sign agreement and clone concordance are testable.
- Prior art (`../prior-art/report.md`): Shen 2026 never compares with Hi-C;
  Bertero 2019 compared lamina association only by imaging at three loci; no
  third party pairs these data. The class of result (LAD loss ↔ A shift) is
  known from mESC and HGPS work, so a pass would be a cross-context
  concordance, not a new mechanism.

## Pre-outcome sequence
1. Metadata-only audit of GSE126459 (`../data-audit/`).
2. Prior-art lane (`../prior-art/`).
3. Registration draft (`../registration/protocol.draft.json`), code and 20
   synthetic tests (`../code/`).
4. Predictor table built from exposed inputs only
   (`../results/predictor/predictor.tsv`, sha bound at freeze).
5. Independent pre-outcome review; repairs; freeze receipt binding
   registration, code, tests, predictor table and requirements.
6. Intake receipt for the six PC1 bedGraphs; run; record everything.

## Statistics (see registration for exact values)
- Unadjusted Spearman and rank-partial correlation adjusted for baseline PC1
  and baseline lamina, per corrected clone.
- Within-chromosome circular-shift null of the predictor block (5,000 shifts,
  seed 20260924). The whole predictor vector is rolled per chromosome, so its
  autocorrelation (10 kb bins smoothed over ±5 windows, then 500 kb tiles) is
  preserved under the null.
- Pass is conjunctive: orientation ok, ≥3,000 tiles, and for each clone (raw and per-chromosome variance-standardised PC1; adjusted magnitude at least half the unadjusted)
  ρ ≤ −0.10 (unadjusted) and ρ ≤ −0.05 (adjusted) with p ≤ 0.01 each, and
  all four replicate-pair correlations negative.

## Known threats and how they are handled
| Threat | Handling |
|---|---|
| PC1 sign per chromosome | per-chromosome orientation against TSS density on corrected baselines; flips and exclusions recorded |
| Baseline confounding (lamina-rich B tiles regress to the mean) | adjusted statistic controls baseline PC1 and baseline lamina; both must pass |
| Spatial autocorrelation | circular-shift null preserves it |
| Sex chromosomes / unknown sex | chrX, chrY excluded |
| Single condition-merged predictor track | stated in claim ceiling; DNK arm reported as a consistency secondary |
| Compositional z-scores | claim is about relative lamina change |
| Weak expected effect | minimum effect registered; a non-pass retires the claim only for |ρ| ≳ 0.14 (≈75–80% power), smaller effects stay undetermined |

## Pre-outcome review round 1 (2026-09-24)
Verdict PASS_WITH_REPAIRS. Repairs applied before freeze: mandatory freeze and
intake receipts with full hash guards (registration, code, tests, requirements
lock, predictor, six outcome files); PC1 amplitude-artefact control (scale
diagnostic, per-chromosome standardised sensitivity arm as a pass component,
adjusted/unadjusted ratio rule); measured operating characteristics recorded
in the registration (≈50% power at the registered minimum, ≈75–80% at |ρ| 0.14 on re-measurement);
orientation-floor sensitivity at 0.0 and 0.3; every implicit parameter written
into `fixed_parameters_explicit`; replicate-pair criterion labelled weak.

## Pre-outcome review round 2 (2026-09-24)
Verdict PASS. Three minor items applied before freeze: threshold parameters
now read fail-closed by subscript; the standardised arm is described as
centring as well as scaling; power wording corrected to the re-measured rate.
