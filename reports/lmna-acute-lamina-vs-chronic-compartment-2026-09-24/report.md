# Acute lamina change versus chronic compartment change in LMNA-deficient hiPSC-cardiomyocytes: a registered cross-study test

Date: 2026-09-24. Campaign `lmna-acute-lamina-vs-chronic-compartment-2026-09-24`.
Registered outcome: **not passed** (conjunctive rule; two of sixteen components
failed: clone 2 raw and standardised raw effect). Direction as hypothesised in every arm of both contrasts.

## Question

Across autosomal 500 kb tiles of hg38, is the change in LMNB1 CUT&RUN
z-score after 48 h acute *LMNA* siRNA in day-35 hiPSC-cardiomyocytes (Shen et
al. 2026, GSE300197; condition-merged tracks; exposed predictor) negatively
correlated with the change in Hi-C compartment score (HOMER 500 kb
Active.PC1) in day-14 *LMNA* R225X hiPSC-cardiomyocytes relative to each of two
isogenic corrected clones (Bertero et al. 2019, GSE126459; untouched outcome)?
In words: do regions that gain relative lamina association when lamin A/C is
acutely lost sit further toward compartment B under chronic lamin A/C
haploinsufficiency?

## Design (frozen before outcome access)

- **Predictor:** per tile, coverage-weighted mean LMNB1 z-score in siLMNA.mCh
  minus siScr.mCh; baseline lamina = siScr.mCh mean. Built from exposed
  inputs only and hash-bound at freeze (5,236 finite tiles of 5,760).
- **Outcome:** per replicate, coverage-weighted mean PC1 over the same tiles;
  ΔPC1 = mean(mutant rep1, rep2) − mean(corrected clone rep1, rep2), separately
  for corrected clone 1 (GSM3602088/89) and clone 2 (GSM3602090/91).
- **Orientation:** per chromosome, PC1 must correlate positively with RefSeq
  Select TSS density on the corrected baselines (flip if negative; exclude
  below 0.2). Genome-wide ρ must be ≥ 0.3.
- **Statistics:** Spearman ρ (unadjusted); rank-partial ρ adjusted for
  baseline PC1 and baseline lamina; both again on per-chromosome
  variance-standardised PC1; within-chromosome circular-shift null of the
  predictor block, 5,000 shifts, seed 20260924; four replicate-pair signs.
- **Pass rule (all required):** orientation ok; ≥ 3,000 tiles; per clone:
  unadjusted ρ ≤ −0.10 and p ≤ 0.01; adjusted ρ ≤ −0.05 and p ≤ 0.01;
  |adjusted| ≥ 0.5 |unadjusted|; standardised unadjusted ρ ≤ −0.10 and
  p ≤ 0.01; all replicate pairs negative.
- **Pre-registered operating characteristics** (independent review): type I
  0/12 at zero effect; power ≈ 50% at true ρ ≈ −0.11, ≈ 75% at −0.14, 100% at
  −0.19. The binding constraint is the per-clone effect floor, not p.

## Outcome

Eligible tiles: 5,121 (chr22 excluded by the orientation rule, ρ = 0.13;
no chromosome flipped; genome-wide orientation ρ = 0.49). PC1 amplitude ratio
mutant/corrected 1.006 and 1.004 (no scale artefact).

| Statistic | Clone 1 (corrected 1) | Clone 2 (corrected 2) | Floor |
|---|---|---|---|
| Unadjusted ρ | **−0.122** | **−0.080** ✗ | ≤ −0.10 |
| Unadjusted p (shift null) | 0.0002 | 0.0002 | ≤ 0.01 |
| Adjusted ρ (baseline PC1 + lamina) | **−0.150** | **−0.112** | ≤ −0.05 |
| Adjusted p | 0.0002 | 0.0002 | ≤ 0.01 |
| Adjusted / unadjusted ratio | 1.23 | 1.41 | ≥ 0.5 |
| Standardised unadjusted ρ | −0.117 | −0.076 ✗ | ≤ −0.10 |
| Standardised p | 0.0002 | 0.0002 | ≤ 0.01 |
| Replicate pairs (rep1, rep2) | −0.096, −0.101 | −0.090, −0.052 | all < 0 |
| Clone pass | yes | **no** | |

p = 0.0002 is the floor 1/(5,000 + 1): no circular shift of the predictor
reached the observed correlation in any arm of either clone.

Registered pass: **false**. Registered opposite direction: false.

### Pre-registered secondaries (exploratory; no p-values)

| Secondary | Clone 1 | Clone 2 |
|---|---|---|
| Baseline-A tiles (n ≈ 2,510) unadjusted ρ | −0.081 | −0.077 |
| Baseline-B tiles (n ≈ 2,610) unadjusted ρ | −0.178 | −0.108 |
| DNKASH-arm predictor ρ | −0.126 | −0.075 |
| Mean ΔPC1, top decile of lamina gain | −0.061 | −0.045 |
| Mean ΔPC1, bottom decile of lamina gain | +0.039 | +0.028 |
| Orientation floor 0.0 (5,187 tiles): unadjusted / adjusted | −0.120 / −0.147 | −0.078 / −0.110 |
| Baseline lamina vs baseline PC1 ρ (sanity) | −0.558 | −0.550 |

## Interpretation

- The registered claim is not established. The rule was written to require
  the raw effect to clear −0.10 in both clones, and clone 2 did not
  (−0.080). No threshold was changed after outcome access.
- What the data show, within the frozen analysis: in both contrasts the
  correlation is negative, is more negative once baseline compartment and
  baseline lamina are controlled (−0.150, −0.112), survives per-chromosome
  standardisation, has the same sign in all four replicate pairs, and no
  within-chromosome circular shift of the predictor reproduces it (p at the
  floor in all eight permutation arms, six of which are in the pass rule). The effect is stronger in tiles that
  start in compartment B and is reproduced with the DNKASH-arm predictor.
  Tiles in the top decile of acute lamina gain sit about 0.1 PC1 units lower
  in the mutant than tiles in the bottom decile (clone 1).
- Size: |ρ| ≈ 0.08–0.15 at 500 kb is a modest genome-wide coupling, in line
  with Bertero et al.'s own report that compartment change in this model is
  restricted (∼1.2% of the genome switching) and with the pre-registered
  expectation of a weak effect.
- The result sits inside the ≈ 50% power regime the reviewer measured at the
  registered minimum: a true effect near −0.10 in clone 2 would fail the floor
  half the time. This is the reason the claim is "not passed" rather than
  "refuted"; the registration says so in advance.
- Prior art (`prior-art/report.md`): the exact comparison was not found in
  either source paper or any third party; Shen 2026 never uses Hi-C, and
  Bertero 2019 checked lamina association only by imaging at three loci. The
  class of result (lamina detachment coupled to A/B change) is known from mESC
  lamin knockouts and progeria fibroblasts. So a passed version of this claim
  would be a new instance of a known class across two independent human
  cardiomyocyte studies, not a new mechanism.

## Claim ceiling

Nothing here should be described as a discovery. The defensible sentence is:
"In a registered cross-study test, regions whose lamina association is most
sensitive to acute lamin A/C loss tended to sit further toward compartment B
in chronic LMNA R225X cardiomyocytes, consistently across two isogenic
contrasts, but the pre-registered effect floor was not met in one contrast."
Correlational, cross-study, cross-stage (day 35 vs day 14), cross-perturbation,
one condition-merged predictor track, two Hi-C replicates per line.

## What would move this to a shareable positive result

A pre-registered replication in an outcome cohort never opened by this
program, with the adjusted statistic as primary and an effect floor set from
the operating characteristics rather than from these observed values. The only
other human LMNA-loss Hi-C series found is GSE314556 (B-lymphoblastoid); a
metadata audit of it and of HGPS Hi-C series is in
`data-audit/replication-cohorts/` (metadata only; no outcome file was
retrieved). Its main findings: GSE314556 deposits only HiC-Pro valid-pair
files on hg19, so PC1 would have to be computed and the tile grid lifted over,
and its lineage is lymphoblastoid, so a null would be ambiguous between
refutation and cardiac specificity. Any such registration will be frozen and
independently reviewed before the files are downloaded, as here.

## Execution record

- Pre-outcome review: three rounds (PASS_WITH_REPAIRS → PASS →
  PASS_WITH_REPAIRS on the amendment), all repairs applied before the relevant
  freeze; `design/independent-review.json`, `design/skeptical-review.md`.
- Freeze-001 2026-09-24T20:13:55Z; intake-001 downloaded; **run-001 failed
  with zero eligible tiles** because the HOMER bedGraphs name chromosomes
  without the `chr` prefix; the crash occurred on empty arrays before any
  correlation or per-tile value was produced (`results/run-001-FAILED.md`, the registration's `results/run-001/FAILED.md`).
  Only coordinate columns and chromosome-name counts were inspected.
- Amendment amend-001: a two-line name adapter and one test. Byte-exact
  copies of the freeze-001 code and tests were reconstructed and hash-match,
  proving nothing else changed (`archive-001/`). Disclosed: the freeze-001
  code bytes differed from the round-2-reviewed bytes by the round-2 minor
  repair applied in between.
- Freeze-002 2026-09-24T20:19:49Z (registration differs from freeze-001 only
  in `amendments`, `code.tests` count and `frozen_utc`); intake-002
  re-downloaded all six files, byte-identical to intake-001; run-002 executed
  under the mandatory freeze and intake guards (all hashes verified).
- Spend: $0 new provider or compute spend; six downloads of ≈ 74 kB each.
  Cumulative program spend remains $0.019722 of the $25 authorised.
