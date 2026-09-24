# GEO metadata (metadata pages only; no data files downloaded)

All retrieved via https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=<ACC>&targ=self&form=text&view=full|brief
(WebFetch of the HTML GEO pages returned a reCAPTCHA interstitial; the plain-text SOFT metadata view was used.)

## GSE126459 — Bertero 2019 Hi-C subseries — retrieved 2026-09-24T17:51:22Z
- Title: "Gene expression and chromatin organization changes in lamin A/C haploinsufficient human induced pluripotent stem cell-derived cardiomyocytes [Hi-C]"
- Status: "Public on Feb 13 2019"; submitted Feb 12 2019; last update Mar 26 2019
- Overall design (verbatim): "Hi-C analyses of human induced pluripotent stem cell-derived cardiomyocytes (hiPSC-CM) with a heterozygous R225X mutation (mutant), and hiPSC-CM from two isogenic control lines where such mutation was reverted to the wild-type allele using CRISPR/Cas9 (corrected); two biological replicates from independent differentiations per cell line."
- Samples: GSM3602088–GSM3602093 (6 Hi-C libraries = 3 lines x 2 reps)
- SuperSeries GSE126460; RNA subseries GSE126458 ("three biological replicates from independent differentiations per cell line")

### GSM3602088 ("Hi-C library corrected 1 rep 1") data processing (verbatim)
- "validPair files were used as input for HOMER version 4.7 at 500KB resolution to generate PC1 values (A/B compartment calls)."
- "Genome_build: hg38"
- "PC1.bedGraph files are the ouput from HOMER on the processed Hi-C data, representing the A/B compartment calls, in bedGraph format (coordinates and score)"
- Supplementary file name pattern: `GSM3602088_HiC_corrected.1_rep1_500KB_Active.PC1.bedGraph.gz` (also `_500000_iced.matrix.gz`, `_allValidPairs.pairs.txt.gz`)
- Characteristics: "cell line: R225R LMNA corrected 1 hiPSCs"; "time point: Day 14 of cardiac differentiation"

→ Sign convention: the file is named "Active.PC1"; the paper states the eigenvector sign was oriented by constitutive gene expression "so that positive and negative values indicate A and B compartmentalization, respectively" (Bertero 2019 Methods; Fig. 6 A legend: "Positive and negative PC1 indicate A and B compartmentalization, respectively"). Note: HOMER's own `runHiCpca.pl` does not guarantee this sign; here the sign was set by the authors. Per-sample replicate-level PC1 bedGraphs exist (one per GSM), so mutant-minus-corrected can be computed at replicate level.

## GSE300197 — Shen 2026 — retrieved 2026-09-24T17:51:22Z
- Title: "The cytoskeleton drives abnormal chromatin-lamina interactions in LMNA-deficient cardiomyocytes."
- Status: "Public on Mar 26 2026"; submitted Jun 18 2025; last update Mar 30 2026; PubMed 41891953
- Overall design (verbatim, 3 lines): "RNA-seq profiling for human induced pluripotent stem cell-derived cardiomyocytes in siScr control and siLMNA knockdown samples after 48 hours of treatment." / "CUT&RUN sequencing for LMNB1 in human induced pluripotent stem cell-derived cardiomyocytes in siScr + mCherry control and siLMNA + mCherry and siLMNA + DNKASH samples after 48 hours of treatment." / "CUT&RUN sequencing for LMNB1 in human induced pluripotent stem cell-derived cardiomyocytes in siScr + DNKASH samples after 48 hours of treatment."
- 30 samples (GSM9055526–GSM9055551, GSM9437246–GSM9437249)
- Series supplementary files: GSE300197_RNA.counts.txt.gz; GSE300197_siLMNA.DNK.CR.zscore.bw; GSE300197_siLMNA.mCh.CR.zscore.bw; GSE300197_siScr.DNK.CR.zscore.bw; GSE300197_siScr.mCh.CR.zscore.bw (condition-level only — no per-replicate bigWigs at series level)
- Sample-level processing (GSM9055530, verbatim): "Assembly: hg38"; "zscore bws: bigwig signal files containing zscores called in 10kb window and smoothed using a rolling mean of the flanking 5 windows to each side"; "Supplementary_file_1 = NONE" (no per-sample supplementary files)

→ Confirms Study A's public processed lamina signal is condition-level, smoothed (effective autocorrelation ≈ ±5 x 10 kb windows) — relevant to the planned circular-shift null.

## Candidate additional outcome cohorts (metadata only)

- **GSE136252** — "Pathogenic LMNA variation disrupts a tissue-specific lamina-chromatin signature, resulting in loss of cellular identity" (Shah et al. 2021, Cell Stem Cell, PMC8106635). Design (verbatim): "Mapping of LB1 and H3K9me2 domains in control and LMNA T10I iPSC-derived cardiac myocytes at day 25 and 45 post-differentiation; mapping of LB1 and H3K9me2 domain in control and LMNA R541C iPSC-derived cardiac myocytes; mapping LB1 and H3K9me2 domains in control, LMNA T10I, and R541C iPSC-derived hepatocytes; … RNAseq of d25 control, T10I, and R541C iPSC-derived cardiac myocytes…". Human, chronic LMNA missense variants, lamina (LMNB1) side, replicate-level samples. Retrieved 2026-09-24T17:54:07Z.
- **GSE314556** — "Lamin A/C maintains genome topology and regulates transcriptional programs essential for virus-driven B cell activation. [Hi-C]" (PubMed 41648489). Design: "HiC of WT and LMNA/C depleted cells". Human LCL; *chronic-ish LMNA depletion WITH Hi-C in a human non-cardiac cell type* — the closest thing to an independent LMNA-loss compartment dataset. Retrieved 2026-09-24T17:53:48Z.
- **GSE41763 / GSE41764** — McCord et al. 2013 Genome Res, HGPS. GSE41763 summary (verbatim): "…HGPS cells experience genome-wide alterations in patterns of H3K27me3 deposition, changes in the associations of genomic loci with nuclear lamin A/C, and, at late passages, genome-wide loss of spatial compartmentalization of active and inactive chromatin domains…". Design: "Hi-C was performed on three primary fibroblast cell lines: an HGPS patient (passage 17 and 19; HGPS), normal cells from the father of the HGPS patient (passage 18; Father), and age-matched normal cells (passage 20; Age Control)." Hi-C + lamin A/C DamID in the same study. hg19-era. Retrieved 2026-09-24T17:53:49Z.
- **GSE312029 / GSE312031** — "Spatiotemporal remodeling of chromatin topology architecture and H3K27me3 redistribution underlies vascular pathology in Hutchinson-Gilford progeria syndrome" — in situ Hi-C + CUT&Tag in control vs HGPS iPSC-derived vascular smooth muscle cells (no lamin CUT&Tag listed among CTCF/SMC1A/H3K27me3/H3K27ac/H3K36me3). Retrieved 2026-09-24T17:53:49Z.
- **GSE206704 / GSE206707** — HGPS fibroblast Hi-C + transcriptome (eLife 2023).
- **GSE120836 / GSE120837** — "Genomic Reorganization of Lamin-Associated Domains in Cardiac Myocytes is Associated with Differential Gene Expression…" (lamina side, cardiac; mouse/human — check organism before use).
- **GSE221288** — "Gene regulatory loops at lamina-associated domains" (human ASC; lamin A/C ChIP-seq + public enhancer-capture Hi-C) — useful as a LAD-vs-contact reference, not an LMNA-perturbation cohort.
- **GSE89520** — Zheng et al. 2018 Mol Cell lamin TKO mESC Hi-C/LAD (mouse; cross-species, class-level prior art only).
