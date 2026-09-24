# Acute lamina change versus compartment change in LMNA-knockout lymphoblastoid cells: a pre-registered replication

Date: 2026-09-24. Campaign `lmna-acute-lamina-vs-lmna-ko-lymphoblastoid-compartment-2026-09-24`.
Registered outcome: **not passed** (label `NOT_PASSED`; seven of eight tier-A components failed: no effect floor was met and the replicate pairs disagree in sign). Not the opposite direction either: the correlations are near zero.

## Question

The compartment campaign (`lmna-acute-lamina-vs-chronic-compartment-2026-09-24`, not
passed) asked whether 500 kb regions whose LMNB1 association rises most after 48 h acute
*LMNA* siRNA in hiPSC-cardiomyocytes (Shen et al. 2026, GSE300197) sit further toward
compartment B under chronic *LMNA* haploinsufficiency in cardiomyocytes (Bertero et al.
2019, GSE126459). Both contrasts there were negative with p at the permutation floor, but
one raw effect (−0.080) missed the frozen −0.10 floor. This campaign asks the same question
in an outcome cohort this program had never opened: GM12878 B-lymphoblastoid cells with a
stable pooled CRISPR/Cas9 *LMNA* knockout versus a control-sgRNA pool (Caruso et al. 2026
preprint, GSE314556; two Hi-C replicates per condition; HiC-Pro valid pairs on hg19; no
compartment track deposited). Different lineage, different perturbation class, different
genome build, and PC1 computed by this program's own pipeline rather than taken from the
depositors.

Primary statistic (registered): rank-partial Spearman ρ between the acute lamina change
(siLMNA − siScr LMNB1 z-score, mCherry arm) and ΔPC1 = mean(KO) − mean(WT), adjusted for
baseline PC1 (WT mean) and baseline lamina (siScr). Hypothesised sign: negative.

## Design (frozen before outcome access)

- **Predictor:** rebuilt on hg19 500 kb tiles before freeze (`lift_predictor.py`): each
  10 kb interval of the four condition-merged GSE300197 LMNB1 z-score bigWigs (hg38) is
  lifted by its midpoint with the UCSC hg38→hg19 chain, dropped if it fails to lift or
  changes chromosome, and averaged into the hg19 tile containing the lifted midpoint; tiles
  with fewer than half of their 50 intervals are NaN. 5,776 tiles, 5,225 with a finite
  predictor; same columns as the compartment campaign's predictor; hash-bound.
- **Outcome pipeline (`pc1.py`, frozen and validated):** valid pairs → cis autosomal 500 kb
  matrices → ICE → observed/expected → Pearson → leading eigenvector → per-chromosome
  orientation on RefSeq Select TSS density. Validated before freeze on two GSE126459
  samples against the depositors' HOMER PC1: per-sample Spearman 0.923 and 0.880 (floor
  0.80), and 0.547 (floor 0.50) for the mutant − corrected difference. Every validation
  attempt is retained, including a failed first attempt (input layout) and a second whose
  script carried a personal path and was re-run bound.
- **Pipeline QC (mechanical):** per sample and chromosome, orientation must succeed and
  the sample's PC1 must correlate ≥ 0.5 with a leave-one-out WT reference; failing
  chromosomes are excluded genome-wide; more than three excluded autosomes is
  `PIPELINE_FAILURE`.
- **Statistics (the compartment campaign's frozen `compartment.py`, byte-identical):**
  unadjusted Spearman; rank-partial ρ adjusted for baseline PC1 and baseline lamina; both
  on per-chromosome variance-standardised PC1; within-chromosome circular-shift null of
  the predictor, 5,000 shifts, seed 20260925; four KO−WT replicate-pair signs.
- **Pass rule, tier A (all required):** orientation ok (genome ρ ≥ 0.3); ≥ 3,000 tiles;
  unadjusted, adjusted and standardised-unadjusted ρ each ≤ −0.05 with p ≤ 0.01;
  |adjusted| ≥ 0.5 |unadjusted|; all four replicate pairs negative. **Tier B:** tier A and
  adjusted ρ ≤ −0.10 (effect in the cardiomyocyte range). **Opposite:** unadjusted
  ρ ≥ +0.05 with one-sided positive p ≤ 0.01. Six mutually exclusive mechanical labels
  (`PIPELINE_FAILURE`, `TIER_B_PASS`, `TIER_A_PASS`, `OPPOSITE`,
  `NOT_PASSED_DIRECTION_CONSISTENT`, `NOT_PASSED`) with pre-committed interpretations and
  a no-spin rule.
- **Confound flag (reported only):** KO/WT ratio of the PC1 eigenvalue share outside
  [0.7, 1.4] adds "global compartment-strength change present" to the claim ceiling. The
  preprint reports global loop loss, so this flag was anticipated.
- **Operating characteristics (pre-registered):** null SD ≈ 0.019; single-arm power at the
  −0.05 floor ≈ 50% at true −0.05, 94% at −0.08; tier B ≈ 50% at true −0.10. Reviewer's
  full-rule simulation: tier A type I 0/12, power 5/12 at −0.048 and 12/12 at −0.085.
- **Review:** two independent pre-outcome rounds (PASS_WITH_REPAIRS, then PASS) plus
  verification of the round-2 minor repairs; skeptical review items 1–12. Freeze
  2026-09-24T21:14:10Z with every outcome file absent; intake streamed the four pairs files
  (≈ 7.4 GB) without inspection; the run refuses on any hash or byte-count mismatch.

## Outcome

Verdict label (mechanical, `replicate.verdict`): **`NOT_PASSED`**. Pre-committed interpretation:
"not passed; no evidence of generalisation to this lineage; ambiguous between refutation and
cardiac specificity." Not `OPPOSITE` (unadjusted ρ is not ≥ +0.05). Not
`NOT_PASSED_DIRECTION_CONSISTENT` (two of the four replicate pairs are positive and no
arm reaches p ≤ 0.01). Not `PIPELINE_FAILURE` (no chromosome excluded).

Pipeline: all four samples oriented on all 22 autosomes with no flip needed by the evaluator
(genome-wide orientation ρ = 0.637 on the WT mean); leave-one-out concordance with the WT
reference ≥ 0.965 on every chromosome and sample; eligible tiles 5,225 of 5,776 (every
tile with a finite predictor). Cis pairs kept: WT.1 53.5 M, WT.2 52.8 M, KO.1 63.0 M,
KO.2 26.2 M (the half-depth replicate, as disclosed before freeze). Compartment-strength
ratio KO/WT (PC1 eigenvalue share) 0.902, inside [0.7, 1.4]:
confound flag not raised (KO.2's share alone is 0.250 against ≈ 0.315 for the other three,
consistent with its depth). Replicate-concordance SD ratio 0.9999 (reported only).

| Statistic (KO − WT, n = 5,225) | Value | Tier-A floor | Met |
|---|---|---|---|
| Unadjusted ρ | -0.006 | ≤ −0.05 | no |
| Unadjusted p (one-sided, 5,000 shifts) | 0.184 | ≤ 0.01 | no |
| Adjusted ρ (baseline PC1 + baseline lamina) — **primary** | -0.018 | ≤ −0.05 | no |
| Adjusted p | 0.058 | ≤ 0.01 | no |
| Adjusted / unadjusted ratio | both negative, ratio ≥ 0.5 | ≥ 0.5 | yes |
| Standardised unadjusted ρ | -0.017 | ≤ −0.05 | no |
| Standardised unadjusted p | 0.187 | ≤ 0.01 | no |
| Standardised adjusted ρ / p (reported) | -0.031 / 0.034 | — | — |
| Replicate pairs KO.1−WT.1, KO.1−WT.2, KO.2−WT.1, KO.2−WT.2 | +0.017, +0.020, -0.027, -0.028 | all < 0 | no |
| Tier B (adjusted ρ ≤ −0.10) | — | requires tier A | no |

The compartment campaign's registered floors were −0.10 (raw) and −0.05 (adjusted) and its
observed adjusted values were −0.150 and −0.112; every correlation here is within two null
standard deviations (≈ 0.019 each) of zero.

### Pre-registered secondaries (exploratory; no p-values)

| Secondary | Value |
|---|---|
| Baseline-A tiles (n = 2,334) unadjusted ρ | +0.005 |
| Baseline-B tiles (n = 2,891) unadjusted ρ | -0.041 |
| DNKASH-arm predictor unadjusted ρ | -0.004 |
| Mean ΔPC1, top decile of lamina gain (n = 523) | -0.014 |
| Mean ΔPC1, bottom decile of lamina gain | -0.016 |
| Orientation floor 0.0 vs 0.3 | identical (no chromosome near the floor) |
| Baseline lamina vs baseline PC1 ρ (sanity; was −0.56/−0.55 in cardiomyocytes) | -0.488 |

Per-chromosome table (registered at report time; `results/per-chromosome-validation-vs-outcome.json`):
the unadjusted ρ per chromosome ranges from -0.244 (chr19, 105 tiles) to +0.124 (chr5) with both signs common;
the three chromosomes where `pc1.py` agreed least with the deposited GSE126459 PC1 during
validation (chr22 0.21, chr4 0.40 in one sample, chr9 0.68–0.73; chr21 has no validation
value because the deposited GSE126459 tracks contain no chr21 rows) contribute +0.073, +0.056
and -0.031 (together 650 of 5,225 tiles). The
registration's wording "the evaluator's per-chromosome output" was imprecise: the evaluator
records per-chromosome orientation ρ only, so the outcome column was computed from
`core/tiles.tsv` by `per_chromosome_table.py` after the outcome was known. It is a
secondary with no threshold and is disclosed as such.


## Interpretation

- The registered claim is not established, and the registered rule was not close to
  passing: no effect floor, no p-value floor and not the replicate-sign requirement.
  Under the pre-committed interpretation this is "no evidence of generalisation to this
  lineage; ambiguous between refutation and cardiac specificity". No threshold was changed
  after outcome access.
- What the data show, within the frozen analysis: the acute cardiomyocyte lamina-sensitivity
  map has essentially no rank relationship with compartment change in *LMNA*-KO GM12878
  cells (|ρ| ≤ 0.032 in every arm). The sanity correlation between baseline lamina (siScr
  LMNB1 in cardiomyocytes) and baseline PC1 (WT lymphoblastoid) is −0.49 (an exploratory
  secondary with no threshold), consistent with the predictor and outcome grids being
  aligned; what is absent is any relationship between *change* in one and *change* in the
  other.
- Power: the registered rule had ≈ 94% single-arm power at a true effect of −0.08 and
  12/12 in the reviewer's full-rule simulation at −0.085, and the pipeline reproduced the
  depositors' PC1 in the validation cohort at 0.88–0.92 per sample. A cardiomyocyte-sized
  effect (−0.11 to −0.15 adjusted) would have been detected here; a much smaller one
  (|ρ| < 0.05) would not, and the observed values are compatible with zero or with such a
  small effect.
- Why the two campaigns can differ without either being wrong: lineage (cardiomyocyte vs
  B-lymphoblastoid; LAD landscapes are largely cell-type specific), perturbation class
  (48 h siRNA and R225X haploinsufficiency vs a stable pooled CRISPR knockout selected over
  weeks), and the outcome caller (this program's ICE/PC1 on valid pairs vs HOMER). The
  registration named lineage ambiguity in advance and it cannot be resolved by these data.
- The two registered tests together therefore read: a weak, consistent, floor-missing
  association in the cardiomyocyte pair, and its absence in lymphoblastoid cells. Neither
  supports a discovery claim. Whether the cardiomyocyte association is lineage-specific or
  was itself noise near the ≈ 50% power point is the open question, and it is a wet-lab
  question (LMNB1 profiling in the R225X line itself), not another reanalysis.


## Claim ceiling

Nothing here should be described as a discovery. The defensible sentence is: "In a
pre-registered replication in *LMNA*-knockout GM12878 lymphoblastoid Hi-C, the acute
cardiomyocyte lamina-sensitivity map showed no correlation with compartment change
(adjusted ρ −0.018, p 0.06 against a 5,000-shift null; replicate pairs of mixed sign), so
the cardiomyocyte association did not generalise to this lineage." Correlational,
cross-study, cross-lineage, cross-perturbation, one condition-merged predictor track, two
Hi-C replicates per condition with one at half depth, PC1 computed by this program
(validated at 0.88–0.92 against the depositors' caller in a different cohort).


## Prior art

Read before freeze (`prior-art/caruso-2026.md`). The GSE314556 preprint reports 39 B→A and
23 A→B compartment switches and a global loss of long-range loops in the KO; it has no
lamin B1 genomic data and does not compare against any lamina-sensitivity measure. Shen
2026 never uses Hi-C. The class of result (lamina detachment coupled to A/B change) is known
from lamin-null mESCs (Zheng et al. 2018) and progeria fibroblasts. No third party was found
to have made this cross-study comparison. A passed result would therefore be a new instance
of a known class across three independent human studies, not a new mechanism.

## Execution record

- Pre-outcome review: round 1 PASS_WITH_REPAIRS (six blocking items, all repaired),
  round 2 PASS (no blocking items; eight minor items applied before freeze and verified
  by the reviewer as `round_2_repairs_verified`); `design/independent-review.json`,
  `design/skeptical-review.md` items 1–12.
- Method validation of `pc1.py` on GSE126459 (already-observed cohort): attempt 1 failed
  on the 4DN column layout with no PC1 produced; attempt 2 passed but its script carried a
  personal path; attempt 3 (bound script, identical pipeline bytes) passed at 21:02:48Z.
  All three retained in `design/method-validation-attempts.md`.
- Freeze-001 2026-09-24T21:14:10Z with `data/GSE314556` empty; 21 hashes bound, 20 files
  archived in `archive-001/` (the RefSeq table and chain are bound by hash only).
- Intake: a first download attempt was stopped by the operator after ≈ 0.8 GB of the first
  file to move it out of a shell with a 10-minute cap; its partial file was deleted and no
  receipt was written. The second attempt (21:17:09Z–21:36:37Z) streamed all four files
  to `.part` names, renamed on completion, and every byte count matched GEO metadata
  (`intake.json`). No file was opened.
- Run: a first launch failed at argument parsing (`replicate.py` has no `run` subcommand;
  the recipe in the working notes was wrong) before any binding check or data access
  (`results/run-001-argv-error.log`). The second launch verified every hash and byte
  count, computed PC1 for the four samples (≈ 16 min, ≈ 110 MB resident) and finished
  the evaluator at 21:53:25Z. One benign `Mean of empty slice` warning from the
  leave-one-out reference at tiles masked in every reference sample.
- Spend: $0 new provider or compute spend; ≈ 7.4 GB downloaded from GEO. Cumulative
  program spend remains $0.019722 of the $25 authorised.

