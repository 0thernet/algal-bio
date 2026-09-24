# Outcome cohort audit — GSE126459 (metadata only)

Date: 2026-09-24. No PC1, contact-matrix, or valid-pair values were opened.
Source: GEO full SOFT export retained as `GSE126459-full.soft.txt`
(sha256 6258f93d8a340ab722c9c75901ae04f55eeb23794a88e436163b21d6e396e0be).

## What the cohort is

- Series GSE126459, Hi-C subseries of GSE126460 (Bertero et al. 2019, JCB,
  doi 10.1083/jcb.201902117). Day-14 hiPSC-cardiomyocytes; one heterozygous
  LMNA R225X patient line and two CRISPR-corrected isogenic lines
  ("corrected 1", "corrected 2"), two biological Hi-C replicates each.
- Six samples GSM3602088–GSM3602093. Sample titles, characteristics, and
  file names agree on line and replicate identity (checked programmatically in
  `GSE126459-outcome-audit.json`).
- Processing per sample: BWA-MEM 0.7.13 to hg38; HiC-Pro 2.7.6 (pairs >1 kb,
  MAPQ ≥30); HOMER 4.7 at 500 kb resolution for PC1 A/B compartment calls.
- Per-sample supplementary files: `*_500KB_Active.PC1.bedGraph.gz` (used),
  `*_500000_iced.matrix.gz` and `*_allValidPairs.pairs.txt.gz` (not used).

## Why this cohort qualifies as an untouched outcome

- Never downloaded or opened in this program before the freeze (the earlier
  campaigns used only the RNA subseries GSE126458).
- Same genome build (hg38) as the exposed predictor (GSE300197 CUT&RUN
  z-score bigWigs), so no liftover is needed.
- Replicate-level PC1 tracks allow replicate sign-agreement checks and two
  independent corrected-clone contrasts.

## Known limitations recorded before outcome access

- PC1 values are HOMER outputs at the authors' settings; the sign convention
  ("Active.PC1" implies positive = active/A) is verified after intake by a
  pre-registered orientation rule against gene density, not by the contrast.
- Sex is not stated in the GEO characteristics; chrX and chrY are excluded.
- Two replicates per line; the test is on ~5,000 autosomal 500 kb tiles
  with a within-chromosome circular-shift null, not on replicate variance.
- Different differentiation stage (day 14 vs day 35) and perturbation
  (chronic truncation vs 48 h siRNA) from the predictor study; that is the
  question, not a nuisance.

## Other candidate outcome cohorts considered

Handled in the prior-art lane; none are required for the registered test.
