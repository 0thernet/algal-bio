# Shen et al. 2026, J Cell Biol — "The cytoskeleton contributes to abnormal genome-lamina interactions in LMNA-deficient cardiomyocytes"

- Source of excerpts: local retained capture <retained local capture of Shen 2026 full text (Ghostget capture, not tracked)>
  (capture.json: sourceUrl https://pmc.ncbi.nlm.nih.gov/articles/PMC13040498/ , capturedAt 2026-09-24T15:03:34.528Z, document sha256 35ffd2afbaca2ea7b4f34cd487574776103358b2cbe0ecad79ba10460bf8d3a3)
- DOI 10.1083/jcb.202506137 ; J Cell Biol 2026 Mar 27;225(5):e202506137 ; PMID 41891953 ; GEO GSE300197
- Excerpts read (UTC): 2026-09-24T17:49Z

## Whether Hi-C / compartments are compared anywhere: NO

Exhaustive case-insensitive search of the full captured text:
- "Hi-C" / "HiC": 0 occurrences anywhere (title, abstract, results, discussion, methods, figure legends, references).
- "compartment" (as a chromatin term): 0 occurrences in body text. The only string match is inside the URL of reference 25 (Gholamalamdari et al. 2025 eLife title "… beyond A and B compartments").
- "PC1", "eigenvector", "A/B": 0 occurrences in body text.
- "Bertero": 3 occurrences — all citation mentions (Introduction, Discussion, reference list), none comparing data.

The three Bertero mentions (verbatim):
1. Intro: "…are associated with loss of chromatin organization, impaired signal transduction, and aberrant mechanotransduction (Sullivan et al., 1999, …, Bertero et al., 2019, Shah et al., 2021)."
2. Intro: "Multiple models of human induced pluripotent stem cell-derived cardiomyocytes (hiPSC-CMs) expressing pathogenic *LMNA* mutation variants exhibit altered genome organization (Bertero et al., 2019, Lee et al., 2019, Salvarani et al., 2019, Shah et al., 2021). However, interpretation of changes observed in these models can be confounded by heterogeneous differentiation kinetics, as *LMNA* mutations are engineered into pluripotent hiPSCs and then differentiated into cells of interest (Ohno et al., 2013)."
3. Discussion: "Multiple models of patient-derived *LMNA* variants leveraging hiPSCs have established that *LMNA* mutations affect genome organization (Briand et al., 2018, Bertero et al., 2019, Lee et al., 2019, Shah et al., 2021). Our findings extends this by suggesting that peripheral chromatin organization can be affected at multiple stages of differentiation, including after cellular identity has been established."

## Vulnerable ("LMNA-sensitive") LADs — verbatim

Abstract: "Genome-wide mapping and locus-specific imaging reveal that LADs with a distinct molecular signature are preferentially vulnerable to LMNA reduction."

Results: "From the merged datasets, we identified 641 and 727 LADs occupying approximately 27% (median size 836 kb) and 28.5% (median size 744 kb) of the genome in siScr and siLMNA hiPSC-CMs, respectively. Approximately 82% of siScr LAD coverage was shared with siLMNA, with 18% of siScr LAD coverage lost and 13% of siLMNA LAD coverage gained upon *LMNA*-knockdown (Fig. S1 H). Given the established role of the nuclear lamina in scaffolding peripheral heterochromatin, subsequent analyses focused on LAD regions that lost LMNB1 occupancy upon *LMNA*-knockdown (Guelen et al., 2008)."

"Of the 641 siScr LADs, 138 (~20%) were entirely retained and classified as *LMNA*-insensitive… The remaining siScr LADs exhibited variable degrees of loss, with the top ~30% (n = 204 LADs) showing substantial reduction in LMNB1 occupancy (mean loss 55%; range 15 - 100%). These 204 LADs were classified as *LMNA*-sensitive".

"*LMNA*-sensitive LADs exhibited lower baseline LMNB1 enrichment in siScr hiPSC-CMs compared to *LMNA*-insensitive LADs (Fig. 1 G, S1 J) and were smaller in size (median size, 622 kb vs. 822 kb). Analysis of publicly available hiPSC-CMs datasets revealed that *LMNA*-sensitive LADs were less enriched for chromatin modified by H3K9me3, typically associated with transcriptional repression, demonstrated higher CpG density, and were flanked by regions of higher transcriptional activity compared to *LMNA*-insensitive LADs".

"Therefore, LADs with lower LMNB1 occupancy, reduced heterochromatin enrichment, and higher gene density are preferentially vulnerable to LMNA reduction, whereas the spatial positioning of strongly lamina-associated LADs is generally resistant to LMNA reduction."

→ Regions that GAIN LMNB1: the only quantitative statement is the "13% of siLMNA LAD coverage gained upon LMNA-knockdown" above; the paper explicitly de-scopes gained regions ("subsequent analyses focused on LAD regions that lost LMNB1 occupancy"). No further analysis of gained regions appears.

## Signal processing (Methods) — relevant to the planned test

"The resulting reads were mapped to the hg38 assembly with bowtie2… LADs were called using the Enriched Domain Detector (Lund et al., 2014) with parameters *required_fraction_of_informative_bins=0.98, p_hat_CI_method=agresti_coull, log_ratio_bin_size=10, fdr=0.05, and gap parameter 4*, using LMNB1 as the signal file and matched IgG file as background. Genome-wide LMNB1 signal was calculated for visualization and downstream analysis by counting reads detected in each 1kb or 10kb genomic bin using deeptools multiBigwigSummary…, z-scores were calculated excluding any bin with no reads from any sample mapped, and then were smoothed using a rolling mean of the flanking 5 windows to each side."

"LADs were considered sensitive if 15% or more of the LAD was lost in siLMNA cells. Insensitive LADs were defined as LADs that lost 0% of their area, while minimally-sensitive LADs had >0% and <15% of lost area."

Replicates: "n = 3 replicates/condition… Replicate samples were highly concordant by LMNB1 z-score and were merged within each condition for subsequent analyses (LMNB1 z-score Spearman correlation > 0.86, Fig. S1 F)."
