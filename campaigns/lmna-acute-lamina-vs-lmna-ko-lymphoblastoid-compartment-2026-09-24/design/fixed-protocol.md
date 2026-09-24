# Fixed protocol (draft for independent review): replication of the acute-lamina → chronic-compartment association in an untouched cohort

Campaign `lmna-acute-lamina-vs-lmna-ko-lymphoblastoid-compartment-2026-09-24`. Status: DRAFT, not frozen. No GSE314556 file has been downloaded or opened.

## Why this test
The compartment campaign (registered, not passed) found, in both R225X-vs-corrected clone contrasts of GSE126459, a negative Spearman correlation between the acute siLMNA change in LMNB1 z-score (GSE300197) and the chronic PC1 shift, with adjusted ρ −0.150 / −0.112 at the circular-shift floor, but a raw ρ of −0.080 in clone 2 below the frozen −0.10 floor. The registered path forward was a pre-registered replication in an outcome cohort never opened by this program, with the adjusted statistic primary and a floor set from operating characteristics, not from the observed values.

## Cohort
GSE314556 (Caruso et al. 2026 preprint): GM12878 B-lymphoblastoid, LMNA/C KO vs WT, 2 vs 2 biological replicates, Hi-C, HiC-Pro v2.10.0 allValidPairs only, hg19. Preprint facts (prior-art/caruso-2026.md, read before freeze): the KO is a stable lentiviral CRISPR/Cas9 transduced pool, the "WT" samples are the same LCL with a control sgRNA; replicate number, depth and enzyme are unreported in the text; HiC-Pro v2.10.0 at 1 kb; no compartment caller or bin size is named; the paper reports only "39 compartments switching from B to A and 23 from A to B" (net A-ward, no strength metric, no saddle plots) and a global loss of long-range loops with gain of short-range contacts. No lamin B1 genomic data in these cells; no prior statement of the lamina-sensitivity → compartment-shift hypothesis. This is a different lineage (B-cell, not cardiomyocyte) and a different perturbation class (stable pooled KO, not haploinsufficient missense or acute siRNA), and the reported global contact-scaling change is exactly the confound the standardised arm and the compartment-strength (eigenvalue-share) flag were designed for. Interpretation is pre-committed below.

## Predictor (exposed; built before freeze)
GSE300197 mCh-arm z-score bigWigs lifted to hg19 by 10 kb-interval midpoint (pyliftover, UCSC hg38ToHg19 chain), averaged into 500 kb tiles, tiles with <50% lifted intervals NaN. `results/predictor/predictor_hg19.tsv` sha256 1670a3c9…; 5,225 finite tiles; distribution matches the hg38 predictor (SD 0.1947 vs 0.1943). dlam_mCh = siLMNA − siScr (mCh arm). DNK arm secondary.

## Outcome (untouched)
Per sample: valid pairs → 500 kb cis matrices (autosomes) → ICE → observed/expected → Pearson correlation → leading eigenvector (eigh) → per-chromosome sign orientation by TSS density (hg19 RefSeq Select). Implemented in `code/pc1.py` (hash-bound at freeze). Bins with < 10 nonzero entries masked; ICE tolerance 1e-5, ≤ 200 iterations; no MAPQ filter beyond HiC-Pro's own; per-chromosome orientation |ρ| ≥ 0.2 in pc1.py. All passed to pc1.py from the registration by `replicate.run_pc1`. Input layout (HiC-Pro or 4DN-style pairs) is auto-detected and recorded; the GSE126459 validation files use the 4DN layout and the first validation attempt failed on this (design/method-validation-attempts.md).

### Method validation gate (before freeze, pre-stated thresholds)
Run the identical pipeline on two GSE126459 valid-pairs files (mutant rep1 GSM3602092, corrected.1 rep1 GSM3602088; hg38 pipeline inputs) and compare with the deposited HOMER PC1 of the same samples:
- V1: genome-wide Spearman(pipeline PC1, deposited PC1) ≥ 0.80 for each sample, after the evaluator's per-chromosome orientation on both.
- V2: Spearman of per-tile deltas (mutant − corrected.1) ≥ 0.50.
If V1 or V2 fails, the pipeline is repaired and re-validated before freeze; every attempt is recorded. Result (attempt 2, pc1.py 137b18c8…): V1 0.923 (mutant rep1) and 0.880 (corrected.1 rep1); V2 0.547; passed. Per-chromosome agreement is in design/method-validation.json (attempt 3, same pipeline bytes). The validation uses outcome data already observed in the compartment campaign; it informs only the pipeline, never a threshold.

## Statistics (identical to the compartment campaign's frozen evaluator, `code/compartment.py` sha 776ccede…, reused unchanged)
Tiles: 500 kb, chr1–22, coverage ≥ 0.5. Contrast: mean(KO) − mean(WT). Baseline PC1 = mean(WT). Unadjusted Spearman; rank-partial Spearman adjusted for baseline PC1 and baseline lamina (siScr_mCh); per-chromosome variance-standardised arm; within-chromosome circular-shift null, 5,000 shifts, seed 20260925 (+1 adjusted, +2/+3 standardised), one-sided negative p. Orientation: per-chromosome flip if ρ(TSS) < 0, exclude if < 0.2, genome ρ ≥ 0.3 required. Replicate-concordance SD ratio reported only (not a strength measure; see Confound flag).

## Pass rule (conjunctive, frozen before download)
Tier A (direction replicates with a non-trivial effect): orientation ok; ≥ 3,000 eligible tiles; unadjusted ρ ≤ −0.05 with p ≤ 0.01; adjusted ρ ≤ −0.05 with p ≤ 0.01; standardised unadjusted ρ ≤ −0.05 with p ≤ 0.01; |adjusted| ≥ 0.5 |unadjusted|; all four KO−WT replicate-pair Spearman correlations negative.
Tier B (effect size comparable to the cardiomyocyte cohort): Tier A and adjusted ρ ≤ −0.10. Anchoring disclosed: −0.10 is the prior campaign's raw floor and lies inside its observed adjusted range; it is an effect-size replication claim, and it is the only place the adjusted statistic is operative beyond tier A's −0.05.
Opposite direction: unadjusted ρ ≥ +0.05 with positive-side p ≤ 0.01.
Confound flag (reported, does not change pass/fail): compartment-strength ratio KO/WT outside [0.7, 1.4], where strength = mean over oriented chromosomes of the PC1 eigenvalue share of the O/E Pearson matrix (scale-invariant; the evaluator's SD ratio cannot measure strength because pc1.py unit-scales each chromosome's eigenvector, so it is reported only as a replicate-concordance diagnostic). If flagged, the claim ceiling carries "global compartment-strength change present".

Pipeline QC (frozen, mechanical): per sample and chromosome, orientation must succeed and Spearman with the WT-reference PC1 must be ≥ 0.5 over finite tiles, where the reference is the mean of the WT samples other than the sample itself (leave-one-out for WT; KO samples use the full WT mean); a failing chromosome is excluded genome-wide with its reason recorded; more than 3 excluded autosomes gives the verdict PIPELINE_FAILURE (all statistics still reported; no claim either way). The cap counts only chromosomes dropped by this QC; chromosomes the evaluator later drops by its own orientation rule are reported separately.

Verdict labels are assigned mechanically by `replicate.verdict`: TIER_B_PASS, TIER_A_PASS, OPPOSITE, NOT_PASSED_DIRECTION_CONSISTENT (orientation ok, all three arms negative with p ≤ 0.01 and all four pairs negative, but a floor, the ratio or the tile minimum fails), NOT_PASSED, PIPELINE_FAILURE. No-spin rule: any NOT_PASSED* result is reported as "not passed" in the first sentence of every summary.

## Operating characteristics (design/null-sd-estimate.json)
Circular-shift null SD ≈ 0.019 for both arms on 5,121 tiles (2,000 shifts, compartment cohort geometry); null 1st percentile ≈ −0.042. Power of a single arm at floor −0.05 with p ≤ 0.01: ≈ 50% at true ρ −0.05, 94% at −0.08, 99.6% at −0.10. Tier B at −0.10: 50% at true −0.10. Full-rule simulation by the round-1 reviewer (unit-scaled synthetic PC1 on the real predictor, noisier KO rep2, 12 seeds): tier A type I 0/12; tier A power 5/12 at −0.048 and 12/12 at −0.085; tier B 5/12 at −0.10. The conjunctive rule over three correlated arms plus four pairs is somewhat below the single-arm figure; the compartment cohort's own arms were within 0.03 of each other.

## Pre-committed interpretation
- Tier A pass: the acute-lamina-sensitivity → chronic-B-shift association generalises across lineage and perturbation class; still a computational association, not mechanism.
- Tier B pass: as above with effect size in the range seen in cardiomyocytes.
- NOT_PASSED_DIRECTION_CONSISTENT (orientation ok, unadjusted/adjusted/standardised all < 0 with p ≤ 0.01, all four KO−WT pairs negative, but some tier-A floor or ratio missed): direction consistent, effect below floor; reported with that label only; no threshold change.
- Not passed otherwise: no evidence of generalisation to this lineage; ambiguous between refutation and cardiac specificity; stated as such.
- Opposite: reported as evidence against generalisation.
- KO rep2 is ~half depth; its depth is disclosed regardless. Chromosomes it fails to orient or that fall below the 0.5 concordance floor are excluded genome-wide by the pipeline QC; more than 3 excluded autosomes is PIPELINE_FAILURE (statistics still computed and reported, neither pass nor refutation).

## Freeze/intake
freeze.py refuses if any GSE314556 file exists or a freeze already exists; run refuses if any pairs file's byte count differs from the registered bytes_expected; archives bytes of every bound file; intake.py streams the four pairs files (~7.4 GB), hashing without inspection; run refuses on any mismatch. Prior spend $0.019722; this campaign costs $0 (local compute).
