# Prior art for libvar/ (GC-correlated same-condition library variation in DamID)

Review by an independent read-only Devin subagent (2026-09-25), literature only; no GEO data files opened.

## Verdict: PARTIALLY_KNOWN

The components are documented — GC/fragment-length bias in DamID counts, sample-specific GC
effects surviving global normalization, and placebo/replicate calibration in adjacent fields —
but **no published quantification of GC-correlated gradients between same-condition DamID
lamina-contact libraries** and **no published practice of same-condition-pair placebo
calibration for DamID differential-LAD claims** was found. The specific claim (|rho| ~0.1-0.7,
persistence after z-scoring, unidentifiability consequence) appears novel as a DamID result,
not as a general phenomenon.

## What is already known (bounds on the claim)

- Ashmore PhD thesis (U. Edinburgh 2018): fragment length and nucleotide content "generate
  systematic bias and technical variation" in DamID-seq — mechanism exists, not quantified
  between libraries.
- Tosti et al. Genome Research 2018 (Daim): conditional quantile normalization removes
  GATC-fragment-length and GC-content biases from DamID counts — correction methods exist;
  a GC-conditioned model is a published alternative to placebo calibration.
- Marshall & Brand Bioinformatics 2015 (damidseq_pipeline): KDE-based Dam-fusion/Dam
  normalization; no GC quantification.
- Hansen, Irizarry & Wu Biostatistics 2012 (CQN): GC content has a strong *sample-specific*
  effect in RNA-seq that plain quantile normalization does not remove — theoretical warrant
  for GC-correlated between-library differences surviving z-scoring/quantile norm.
- van Schaik et al. Genome Biology 2022 (pA-DamID): z-scoring of log2 LaminB1/Dam ratios is
  published practice "to account for differences in dynamic range" — our persistence-after-
  z-score observation extends this.
- Dam-only signal tracks accessible, gene-rich, GC-richer chromatin (CATaDa; Aughey 2018);
  GATC motif is 75% GC — fragment density and PCR efficiency are GC-coupled.
- damsel (Page et al. 2024), damidBind (Marshall lab bioRxiv 2026): differential DamID via
  limma/NOIseq on replicates; no GC-stratified placebo calibration.

## Precedent for same-condition placebo calibration (adjacent fields)

- RUV (Risso et al. Nat Biotechnol 2014): estimate unwanted variation from samples where the
  covariate of interest is constant — canonical precedent for the strategy.
- IDR (Li 2011; Landt ENCODE 2012): replicate rank-consistency required in ChIP-seq.
- Teng & Irizarry Genome Res 2017: GC effect is experiment-specific, strong enough to flip
  peak calls between labs on the same cell line, survives standard normalization.
- Teng et al. NAR Genom Bioinform 2021: mixed-effects model on 211 CTCF samples; between-
  replicate site variability is GC- and low-complexity-associated.
- "Systematic Regional Bias is Widespread in ChIP-seq" (bioRxiv 2026): 80% of 200+
  condition-matched dual-replicate ENCODE experiments contain systematic regional bias.
- Genomic-control lambda / Efron empirical null: calibrating observed associations against
  within-cohort nulls is standard.

## Holdout cohort metadata (GSE135834)

- Yattah C et al. "Dynamic Lamin B1-Gene Association During Oligodendrocyte Progenitor
  Differentiation." Neurochem Res 2020;45(3):606-619. PMID 32020491, PMCID PMC7060805.
  B. van Steensel is a GEO contributor.
- Mouse primary OPCs, Dam-only vs LMNB1-Dam lentivirus; PF (proliferating) and T3
  (differentiated) conditions, 3 LMNB1-Dam replicates each.
- Per GEO sample metadata (verified): trimmed reads aligned to **mm10** with BWA-MEM;
  counts cpm-normalized; log2 ratio of tethered DamID to untethered Dam; 400-bp windows,
  quantile normalized (per file names). Deposited files are bigWigs.
- Caveat: fixed 400-bp windows, not GATC fragments; the deposited tracks are already
  quantile-normalized (a stronger normalization than the other cohorts; disclosed in the
  protocol).

## Framing adopted for the registration

- Claim is "first DamID-specific quantification + unidentifiability consequence", citing the
  above so it cannot be read as claiming GC bias itself is new.
- "Not identifiable from a two-library contrast alone" rather than absolute
  "unidentifiable": GC-conditioned models (CQN/RUV-style) are a published alternative;
  placebo calibration is preferred here because it is model-free.
