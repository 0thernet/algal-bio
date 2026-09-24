# Wide screen: lamina, compartment and expression features across public LMNA datasets (2026-09-24)

## Registered result
Seven of 47 pre-registered cross-study pairs confirmed on held-out even autosomes (discovery on odd autosomes selected 10; Bonferroni k = 10, one-sided circular-shift p <= 0.005, |rho| >= 0.05 in the discovery sign). Registration frozen 2026-09-24T22:54:12Z (registration/freeze-pre-discovery.json, 19 files) after two independent reviews (design/pre-discovery-review.json PASS_WITH_REPAIRS, blocker fixed; design/repair-review.json PASS). Survivors frozen 2026-09-24T22:54:53Z before confirmation.

| Pair (predictor ~ outcome) | Discovery rho | Confirmation rho | Confirmed |
|---|---|---|---|
| gc ~ dlam_mCh | -0.251 | -0.236 | yes |
| siScr_mCh ~ dpc1_cm_r225x | -0.093 | -0.202 | yes |
| tss_count ~ dpc1_cm_r225x | +0.084 | +0.116 | yes |
| pc1_lcl_base ~ dpc1_cm_r225x | +0.174 | +0.111 | yes |
| arm_pos ~ dpc1_cm_r225x | +0.130 | +0.030 | no |
| gc ~ dpc1_cm_r225x | +0.205 | +0.245 | yes |
| siScr_mCh ~ dpc1_lcl_ko | +0.087 | -0.014 | no |
| tss_count ~ lfc_ipsc_silmna | +0.162 | +0.137 | yes |
| tss_count ~ lfc_cm_h222p | +0.098 | +0.084 | no (p 0.009 > 0.005) |
| gc ~ lfc_cm_h222p | +0.160 | +0.273 | yes |

A confirmed pair is a pre-registered cross-study association. It is not by itself a finding: the registered design did not anticipate the artifact below.

## Exploratory artifact control (designed after confirmation, frozen before computing: control/protocol.json, control/freeze.json)
Every confirmed pair whose outcome is a delta adjusted for its own baseline has the sign that regression to the mean predicts when the baseline is noisy. Each was re-tested with a baseline covariate whose noise is independent of the delta (lamina: the DNK arm baseline; cardiomyocyte: mutant minus one corrected clone, adjusted for the other clone, both swaps) plus a clone-vs-clone placebo.

| Pair | Label |
|---|---|
| H1 gc ~ dlam_mCh | SURVIVES_ARTIFACT_CONTROL |
| H2 siScr_mCh ~ dpc1_cm | FAILS_ARTIFACT_CONTROL (odd half swap A rho -0.029; placebo +0.08) |
| H3 tss_count ~ dpc1_cm | FAILS_ARTIFACT_CONTROL (placebo +0.060 > half the mutant effect) |
| H4 pc1_lcl_base ~ dpc1_cm | SURVIVES_ARTIFACT_CONTROL (swaps +0.075 to +0.148; placebo +0.026 / +0.007) |
| H5 gc ~ dpc1_cm | SURVIVES_ARTIFACT_CONTROL (swaps +0.138 to +0.211; placebo +0.002 / +0.028) |

The two expression pairs were not covered; they remain susceptible to RNA-seq GC and pseudocount bias and carry no claim.

## Exploratory robustness (descriptive, control/robust_explore.json)
H4 holds in each mutant replicate against each corrected clone (+0.097 to +0.118), with a cubic baseline (+0.136), jointly with GC (+0.128), and in every baseline tertile (+0.096 to +0.160); the within-mutant placebo is +0.009. H5 is similar (+0.146 to +0.186) but its within-mutant placebo is +0.035 (p 0.019), a hint of technical GC sensitivity. Both mutant samples' genome-wide PC1 resembles the GM12878 PC1 more (0.704, 0.698) than all four corrected samples do (0.654 to 0.679); mutant libraries are the two smallest files, so depth does not explain it. The slope of the mutant delta on an independent baseline is about -0.01, which argues against a global compartment-strength gain leaking through proxies.

## Current reading
Candidate (exploratory, single cohort): in LMNA R225X haploinsufficient iPSC cardiomyocytes, compartments shift toward the configuration of an unrelated lineage (GM12878) beyond the cardiac baseline, GC and gene density; i.e. cell-type-specific compartmentalisation erodes. Status: not a finding until a registered test in data this program has never opened. Discriminating prediction: shifts should correlate positively with non-cardiac reference PC1s and not with cardiac-tissue PC1s, beyond the baseline; a residual-true-compartment leak would predict the opposite ordering.
