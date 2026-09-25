# Wide screen and fresh-cohort replication: GC content predicts lamina-contact change after lamin A/C loss (2026-09-24)

## Status (2026-09-25): provisional candidate, not a finding
- The GC-lamina association below was found in a registered screen and replicated in a registered K562 test. A later registered test in another pA-DamID cohort (lbr/, GSE277503) showed that two same-genotype wild-type libraries can differ by a GC gradient of rho +0.61, larger than the effect claimed here. The K562 placebos were small, but they came from only three wild-type libraries, so between-library GC variation could explain the LMNA result. Until a test bounds that variation inside the same data, the association is a candidate, not a finding.
- The registered LBR sign-reversal test was not supported (DIRECTION_ONLY). An exploratory fine-scale diagnostic meant to separate technical from domain-level GC gradients was uninformative (both sections below).
- The decisive test is registered and frozen: mef/, a third cohort (GSE124205, mouse primary MEFs, DamID-seq, lamin A/C knockdown) with three wild-type embryos, so between-embryo GC variation bounds the knockdown effect inside the same data. Its data had not been downloaded when this record was published.

## Summary at PR #7 (2026-09-24; kept as published, qualified by the status above)
- Positive, pre-registered: after loss of lamin A/C, regions richer in GC lose lamin B1 contact relative to AT-rich regions, beyond baseline lamina contact and gene density. Found in a registered 47-pair screen on public data (acute siLMNA in hiPSC-derived cardiomyocytes, GSE300197; held-out even-autosome rho -0.236) and REPLICATED in a registered test in a cohort this program had never opened (chronic LMNA-knockout K562, LMNB1 pA-DamID, GSE263012; rho -0.249 batch-matched and -0.272 all replicates, both p 0.0002 against 5,000 within-chromosome circular shifts; scale-free arm -0.253 / -0.266; WT-vs-WT placebos -0.061 and +0.035). Robust to CpG-island-count adjustment (-0.25 / -0.30) and amplicon exclusion; a cubic baseline also holds (-0.30 / -0.28) though its placebo rises to -0.091; 18 of 22 autosomes negative.
- Prior art: PARTIALLY_KNOWN. Shen et al. 2026 report that LMNA-sensitive LADs have higher CpG density (categorical, discovery dataset). New here: the continuous GC gradient beyond baseline contact, gene density and CpG-island count (CpG dinucleotide density itself not tested), and its replication in a second cell type, assay and perturbation class, in a dataset whose authors describe the LMNA KO as showing little change in lamina DamID (we did not quantify the absolute size of the KO effect; the gradient concerns its relative pattern). Prior-art gaps: Solovei 2013 and one 2025 paper were paywalled, and the T1/T2 LAD primary source was not quote-verified.
- Limits: one LMNA KO clone against one WT clone in the replication, and the two primaries share a KO replicate; GC-versus-change is sensitive to GC-dependent dynamic-range differences, which the scale-free arm does not remove; association only, no mechanism.
- Everything else tested here did not become a finding and is kept on record: 2 of 7 screen confirmations failed an artifact control; the two expression pairs were never artifact-controlled; the leading compartment candidate (R225X cardiomyocyte compartments drifting toward a lymphoblastoid configuration) failed its own registered panel test with LEAK_PATTERN; the LBR-knockout sign reversal is not claimed.

## Record, in the order it happened

### Registered screen result
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

## Current reading (superseded: see the panel shape test below, LEAK_PATTERN)
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
Hashes, timing (data files created 2-7 s after the freeze, local timestamps only), mechanical label and byte-identical re-run all check out. Exploratory probes (1,000 shifts; P_batch / P_all): excluding K562 amplicons -0.253 / -0.277; adding CpG-island count as covariate -0.251 / -0.300 (so the gradient is not explained by CpG-island count; CpG dinucleotide density, the measure Shen et al. used, was not tested as a covariate); median GC split -0.237 / -0.250; cubic baseline -0.303 / -0.281 (its WT-vs-WT placebo also rose to -0.091, p 0.001, still within the 0.13 bound); 18 of 22 autosomes negative for P_all (14 with p <= 0.05); LMNA loss on an LBR-null background (DKO minus LBR KO, same batch) -0.145. Caveats: the two primaries share one KO clone (14) against one WT clone (17) and one KO replicate, so they are not independent evidence; the shift null is off-centre for the placebos (null means -0.038 and +0.042), so placebo p-values should not be read against zero; GC-versus-change is sensitive to GC-dependent dynamic-range differences, which z-scoring does not remove.

## Registered test of the LBR sign reversal (lbr/, frozen before download): DIRECTION_ONLY — not supported

The LBR-loss result is not supported. The registered label is DIRECTION_ONLY in both arms: the primaries passed and placebos failed the size bound. In the linear arm both failed (PL_batch +0.130 and PL_st +0.610 against a bound of 0.071); in the flexible arm PL_st alone failed (+0.597 against 0.073).

Origin: in the damid/ campaign, K562 LBR KO gave gc ~ lamina change rho +0.32. That was a secondary readout, seen after outcome and opposite in sign to LMNA loss. This test used a fresh cohort, GSE277503 (van Schaik et al. 2025, NAR; RPE1 LMNB2 pA-DamID, WT vs LBR KO in two experiments, r13 and r14). The protocol, code, tests and pre-freeze review (design/lbr-review.json, PASS_WITH_REPAIRS, repairs applied) were frozen before any data file was downloaded.

| test | linear rho (p+) | flexible rho (p+) |
|---|---|---|
| P_r13 LBRKO − WT | +0.149 (0.0002) | +0.159 (0.0002) |
| P_r14 LBRKO − WT | +0.136 (0.0002) | +0.132 (0.0002) |
| PL_batch WT r13 − WT r14 | +0.130 (0.021) | +0.045 (0.50) |
| PL_st ST_r6 − ST_r7 (SunTag WT, two experiments) | **+0.610** (0.0002) | **+0.597** (0.0002) |
| FL_r13 / FL_r14 (pure flattening) | −0.056 / +0.029 | −0.112 / −0.086 |
| FLn_r13 / FLn_r14 (noise-matched, reported only) | −0.021 / +0.013 | −0.043 / −0.026 |
| T2B WT TOP2B siRNA − WT (reported only) | +0.189 / +0.139 | +0.209 / +0.175 |
| LBRKO + TOP2B siRNA − WT (reported only) | +0.110 / +0.116 | +0.105 / +0.099 |

What the numbers say, without the label:
- The within-experiment LBR KO deltas are positive in both experiments and both arms, the same sign as K562.
- The flattening controls sit at or below zero. Flattening of the lamina profile does not produce the positive association.
- The placebo failure is decisive, and informative in its own right. Two wild-type SunTag control libraries from different experiments differ by a GC gradient of rho +0.61, four times the primary effect.
- The iCUT WT cross-experiment placebo is +0.13 (linear).
- GC-graded differences between DamID libraries of the same genotype can therefore be far larger than the effects under test. A within-experiment contrast removes an experiment-level bias, but it cannot exclude a library-level one.
- TOP2B knockdown gives the same positive sign. The source paper reports that it phenocopies LBR loss; this is reported only.

Consequence for the earlier LMNA result: the K562 placebos were small (−0.061, +0.035), but they come from three WT libraries of one lab and cell line. The size of GC-graded between-library variation in pA-DamID is now the open question for every result in this report. It is the next thing to measure.

Limits as registered: one LBR KO line vs one WT line; LMNB2 in RPE1, not LMNB1 in K562; B shares experiments with the primaries; the paper's findings were read before registration.

## Exploratory fine-scale diagnostic (explore/, not registered): uninformative
Question: is a delta's GC association domain-level (between 500 kb tiles) or fine-scale (between the 20-25 kb bins inside a tile)? The reading rule was written into explore/fine_scale.py before its first run. Technical library GC bias should act at bin level, giving a fine-scale partial rho comparable to the coarse one. A domain-level lamina change should give a much smaller fine-scale rho. The first run was stopped after 3 of 10 contrasts because its per-tile loops were slow. A vectorized copy (explore/fine_scale_fast.py; same statistics, seed and draw order) reproduced those three rows exactly and completed the rest (explore/fine_scale.json, logs/fine_scale_fast.log).

| contrast | coarse rho | fine rho |
|---|---|---|
| K562 LMNA KO r8 − WT r8 | −0.241 | −0.030 |
| K562 LMNA KO r7 − WT r1 | −0.240 | +0.013 |
| K562 WT r1 − WT r2 | −0.073 | −0.033 |
| K562 WT r8 − WT r1 | +0.036 | +0.013 |
| K562 LBR KO r8 − WT r8 | +0.300 | +0.051 |
| RPE1 LBR KO − WT, r13 | +0.244 | +0.087 |
| RPE1 LBR KO − WT, r14 | +0.247 | +0.145 |
| RPE1 WT r13 − WT r14 | +0.113 | −0.007 |
| RPE1 SunTag WT r6 − r7 (PL_st) | +0.706 | +0.078 |
| RPE1 TOP2B siRNA − WT, r13 | +0.245 | +0.094 |

Reading: every contrast is coarse-dominated, including the same-genotype placebo PL_st (fine +0.078 against coarse +0.706). The premise that library GC bias would show at bin level does not hold for PL_st. This diagnostic therefore cannot separate a technical GC gradient from a domain-level lamina change. It is recorded as uninformative and carries no weight for or against the LMNA result. The coarse values here are tile means of 20-25 kb bins, partialled on baseline only (no gene-density covariate), so they differ slightly from the registered values. K562 rows use the GEO batch labels, so 'WT r8' is the WT_r3 track of the damid/ table. The docstring of explore/fine_scale.py says 500 null shifts; its code, and the vectorized copy, use 200. The docstring is left as written.

## Record note: working-copy overwrite, restored (2026-09-25)
The mef/ synthetic tests were first run at about 00:38 UTC on 2026-09-25. A module-name collision made `import build_features` resolve to code/build_features.py, the hg38 builder, which runs at import. It rewrote features/tiles.tsv and features/manifest.json in the private working directory with their versions from before the external features were added. No analysis ran on the overwritten files. Both files were restored from the PR #7 published copies, whose hashes equal the frozen originals. All five freeze receipts that bind them verify again: registration/freeze-pre-discovery.json, control/, panel/, damid/ and lbr/. The mouse builder was renamed mef/build_mm9_features.py so the collision cannot recur.

## Registered third-cohort test (mef/, GSE124205): frozen 2026-09-25T00:50:52Z, data not yet downloaded
Why this test: the lbr/ placebo showed that GC gradients between same-genotype libraries can exceed the claimed effect, and the fine-scale diagnostic could not tell them apart. A decisive test needs a cohort whose own wild-type replicates bound between-library GC variation, in data this program has never opened.

Cohort: GSE124205 (Reddy lab), primary mouse embryonic fibroblasts from three e13.5 embryos, Dam-LaminB1 DamID-seq, deposited log2(Dam-LaminB1/Dam) bigWigs on mm9. It is a third species, lab, assay pipeline and perturbation class (shRNA knockdown) relative to GSE300197 and GSE263012.

Design (mef/protocol.json):
- Prediction: negative. GC-rich tiles lose lamina contact after lamin A/C knockdown, beyond baseline contact and gene density.
- Primaries, one per embryo: knockdown minus wild type of the same embryo, for embryos 1.5 and x17. Each baseline is the mean of the other two wild-type embryos.
- Placebos: all three wild-type embryo pairs, each adjusted for the remaining embryo. Each must satisfy |rho| < half of the mean primary effect.
- Range controls: a wild-type track quantile-mapped onto each knockdown track's distribution. They catch a dynamic-range difference leaking through the baseline in the registered direction.
- Arms: raw, a flexible baseline spline and scale-free (z-scored tracks). The final label is REPLICATED only if all three arms are REPLICATED.
- Statistic: 5,000 within-chromosome circular shifts, one-sided p <= 0.01.
- Secondary: specificity against three drug perturbations of the same embryos (TSA, BIX01294, DZNep), labelled SPECIFIC, GENERIC or MIXED.
- Features: mm9 500 kb tiles built from UCSC annotation before any outcome file existed (mef/build_mm9_features.py).

Review: an independent pre-freeze review (design/mef-review.json) returned PASS_WITH_REPAIRS with no blocking items; all six minor repairs were applied before the freeze.

Known before registration (design/prior-art-mef.md):
- The source lab reports that lamin A/C knockdown leaves the MEF LAD profile unchanged by DamID.
- TSA disrupts mainly weakly bound LADs.
- Shah et al. 2021 (Cell Stem Cell) report that LADs lost with pathogenic LMNA variants are gene-rich and weakly bound. That is categorical and unadjusted, and it adds to the PARTIALLY_KNOWN prior-art verdict.

The hypothesis concerns the GC pattern of whatever change exists, not its size. If the change is near null, the placebo bound decides the label.

Known limits:
- Wild-type samples are untreated. The knockdown contrast therefore also carries viral transduction, puromycin selection and about four more days in culture.
- There are only two knockdown embryos.
- A systematic GC artifact confined to the knockdown libraries could not be separated from a real effect inside this cohort. Only agreement across cohorts addresses that.

This registration was published before the data download. The outcome will be recorded under the no-spin rule whatever it is.
