# Wide screen and fresh-cohort replication: GC content predicts lamina-contact change after lamin A/C loss (2026-09-24)

## Summary
- Positive, pre-registered: after loss of lamin A/C, regions richer in GC lose lamin B1 contact relative to AT-rich regions, beyond baseline lamina contact and gene density. Found in a registered 47-pair screen on public data (acute siLMNA in hiPSC-derived cardiomyocytes, GSE300197; held-out even-autosome rho -0.236) and REPLICATED in a registered test in a cohort this program had never opened (chronic LMNA-knockout K562, LMNB1 pA-DamID, GSE263012; rho -0.249 batch-matched and -0.272 all replicates, both p 0.0002 against 5,000 within-chromosome circular shifts; scale-free arm -0.253 / -0.266; WT-vs-WT placebos -0.061 and +0.035). Robust to CpG-island adjustment (-0.25 / -0.30), amplicon exclusion and a cubic baseline; 18 of 22 autosomes negative.
- Prior art: PARTIALLY_KNOWN. Shen et al. 2026 report that LMNA-sensitive LADs have higher CpG density (categorical, discovery dataset). New here: the continuous GC gradient beyond baseline contact, gene density and CpG islands, and its replication in a second cell type, assay and perturbation class, in a dataset whose authors describe the LMNA KO as showing little change.
- Limits: one LMNA KO clone against one WT clone in the replication; association only, no mechanism.
- Everything else tested here did not become a finding and is kept on record: 2 of 7 screen confirmations failed an artifact control; the two expression pairs were never artifact-controlled; the leading compartment candidate (R225X cardiomyocyte compartments drifting toward a lymphoblastoid configuration) failed its own registered panel test with LEAK_PATTERN; the LBR-knockout sign reversal is not claimed.

## Record, in the order it happened

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

## Registered panel shape test (panel/, frozen before reference download): LEAK_PATTERN
Not supported. The erosion reading of H4 is rejected by its own registered test. Heart left ventricle predicted the R225X shift (+0.109 / +0.112) at least as strongly as the non-cardiac median, and its cardiac-specific component was positive (+0.077 / +0.075, p <= 0.0004), the pattern registered in advance as the residual-leak alternative. P1 also failed (4 of 6 non-cardiac references passed; IMR-90 +0.004 / +0.015, A549 +0.046 / +0.059). The ENCODE GM12878 track reproduced the wide-screen predictor (+0.155 / +0.131).
Most parsimonious reading (post hoc, not tested): the two mutant libraries are more reproducible than the corrected ones (between-replicate Spearman 0.981 vs 0.968 to 0.977), and a less noisy PC1 resembles every reference compartment track and GC more, whatever the lineage. H4 and H5 are treated as probable data-quality artifacts and carry no claim.

## Registered fresh-cohort replication (damid/, frozen before download): REPLICATED
GC content predicts the change in lamin B1 contact after lamin A/C loss in a cohort this program had never opened: GSE263012, LMNA-knockout K562, LMNB1 pA-DamID (hg38). Rank-partial Spearman, adjusted for gene density and an independent-noise WT baseline, within-chromosome circular-shift null (5,000 shifts):

| Test | raw rho | scale-free rho |
|---|---|---|
| P_batch (KO r8 - WT r8, baseline WT r1+r2) | -0.249 (p 0.0002) | -0.253 |
| P_all (mean KO - WT r1+r2, baseline WT r3) | -0.272 (p 0.0002) | -0.266 |
| Placebo WT r1 - WT r2 | -0.061 (p 0.11) | -0.062 |
| Placebo WT r3 - WT r1 | +0.035 | +0.036 |
| LBR KO (secondary) | +0.316 | +0.326 |
| LMNA/LBR double KO (secondary) | +0.267 | +0.280 |

Placebo bound 0.13; both placebos within it. Delta slopes on the baseline are near zero for LMNA KO (+0.03 to +0.04 raw, -0.01 scale-free); KO and WT track SDs are similar (2.57-2.64 vs 2.45-2.51). Discovery-cohort effect -0.24; replication -0.25 to -0.27.
Limits: one LMNA KO clone against one WT clone; different cell type, assay and perturbation from discovery; mechanism not addressed. Secondary: LBR loss shows the opposite GC dependence (LBR KO has compressed dynamic range, SD 1.73, and a strong negative slope on baseline, so its sign is reported, not interpreted).

### Erratum and prior art (design/prior-art-gc-lamina.md)
- GSE300197 cells are hiPSC-derived cardiomyocytes (Shen et al. 2026 J Cell Biol, DOI 10.1083/jcb.202506137), not undifferentiated iPSCs. The frozen protocols say "iPSC"; they are left unchanged and this erratum governs.
- Prior-art verdict PARTIALLY_KNOWN. Shen et al. 2026 report, on the discovery dataset, that LMNA-sensitive LADs have higher CpG density (categorical comparison, alongside lower baseline LMNB1). The GSE263012 paper (Belmont lab, eLife 2025, DOI 10.7554/eLife.99116) reports that the LMNA KO "shows little change in lamina DamID" and has no GC, AT or gene-density analysis.
- What is new here: a continuous GC gradient of the lamina-contact change that holds beyond baseline LMNB1 and gene density, and its pre-registered replication in a second cell type, assay and perturbation class (K562 chronic LMNA KO, pA-DamID), where the dataset's own authors describe the KO as showing little change.
- The LBR KO / DKO sign reversal is not claimed: LBR KO compresses lamina contact (track SD 1.73 vs 2.45-2.51 WT; slope on baseline -0.40 raw, -0.17 scale-free), and a flattening leak through a noisy baseline predicts exactly a positive GC sign. It would need its own registered test with a flattening-robust design.

### Post-outcome review (design/damid-post-outcome-review.json): CONFIRMED_WITH_CAVEATS
Hashes, timing (data files created 2-7 s after the freeze, local timestamps only), mechanical label and byte-identical re-run all check out. Exploratory probes (1,000 shifts; P_batch / P_all): excluding K562 amplicons -0.253 / -0.277; adding CpG-island count as covariate -0.251 / -0.300 (so the gradient is not the CpG-density signal already reported); median GC split -0.237 / -0.250; cubic baseline -0.303 / -0.281; 18 of 22 autosomes negative for P_all (14 with p <= 0.05); LMNA loss on an LBR-null background (DKO minus LBR KO, same batch) -0.145. Caveats: the two primaries share one KO clone (14) against one WT clone (17) and one KO replicate, so they are not independent evidence; the shift null is off-centre for the placebos (null means -0.038 and +0.042), so placebo p-values should not be read against zero; GC-versus-change is sensitive to GC-dependent dynamic-range differences, which z-scoring does not remove.
