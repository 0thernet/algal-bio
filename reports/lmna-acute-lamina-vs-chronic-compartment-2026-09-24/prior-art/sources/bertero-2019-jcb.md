# Bertero et al. 2019, J Cell Biol — "Chromatin compartment dynamics in a haploinsufficient model of cardiac laminopathy"

- URL (full text retrieved): https://www.ebi.ac.uk/europepmc/webservices/rest/PMC6719452/fullTextXML
- Canonical: https://pmc.ncbi.nlm.nih.gov/articles/PMC6719452/ ; DOI 10.1083/jcb.201902117 ; PMID 31395619
- Retrieved (UTC): 2026-09-24T17:50:29Z
- Note: pmc.ncbi.nlm.nih.gov returned a reCAPTCHA interstitial to WebFetch; the open-access JATS XML from Europe PMC was used instead. Excerpts only.

## Abstract (verbatim)

"Mutations in A-type nuclear lamins cause dilated cardiomyopathy, which is postulated to result from dysregulated gene expression due to changes in chromatin organization into active and inactive compartments. To test this, we performed genome-wide chromosome conformation analyses in human induced pluripotent stem cell–derived cardiomyocytes (hiPSC-CMs) with a haploinsufficient mutation for lamin A/C. Compared with gene-corrected cells, mutant hiPSC-CMs have marked electrophysiological and contractile alterations, with modest gene expression changes. While large-scale changes in chromosomal topology are evident, differences in chromatin compartmentalization are limited to a few hotspots that escape segregation to the nuclear lamina and inactivation during cardiogenesis. … Thus, global errors in chromosomal compartmentation are not the primary pathogenic mechanism in heart failure due to lamin A/C haploinsufficiency."

## Compartment changes: counts and effect size (Results, "Incomplete transitions from the active to inactive chromatin compartment…")

"To further assess the effect of lamin A/C haploinsufficiency on chromatin compartmentalization, we identified genomic bins with significantly different A/B compartment scores and switching from active to inactive or vice versa between at least two conditions (Table S5). We noticed that the vast majority of compartment transitions were observed for mutant hiPSC-CMs versus each corrected control (Fig. 6 A), and that B to A inversions were more common than A to B ones (42 and 27, respectively; Table S5). We observed that 63% of A to B transitions in mutant cells involved the X chromosome, while B to A changes showed a notable concentration on chromosome 19 but were otherwise evenly spread across 13 additional chromosomes (Fig. 6 B, Fig. S5 A, and Table S5). Overall, compartment changes involved ∼1.2% of the genome, indicating that chromatin compartment dysregulation in mutant cells is not widespread but is actually highly restricted."

Discussion: "Analysis of A/B compartment changes revealed that only ∼1.2% of the genome changed compartments in LMNA mutants, and these aberrations were concentrated in hotspots on chromosomes 5 and 19. Surprisingly, the overlap between strong dysregulation in gene expression and compartment aberrations was minimal (<2%; Fig. S5 B)."

Figure 6A legend: "Heatmap of all significantly different A/B compartment scores (Hi-C matrix PC1; P < 0.05 by one-way ANOVA; n = 2 differentiations; Table S5) in 500-kb bins that changed PC1 sign between two or more conditions. Positive and negative PC1 indicate A and B compartmentalization, respectively."

## Resolution, build, replicates, PC1 sign convention, statistics (Methods, "Hi-C data analysis")

"Fastq files were mapped to the hg38 genome using Burrows-Wheeler Aligner (BWA-MEM) with default parameters… The mapped files were processed through HiC-Pro (Servant et al., 2015), filtering for mapping quality (MAPQ) score >30 and excluding pairs <1 kb apart, to generate valid pairs and iterative correction of Hi-C data (ICE)–balanced matrices at 500-kb resolution."

"A/B compartmentalization was computed by eigenvalue decomposition of the contact maps using HOMER (Heinz et al., 2010) with 500-kb resolution and no additional windowing (super-resolution was also set at 500 kb). The sign of the first eigenvector (PC1) was selected based on the expression of ∼5,000 genes constitutively expressed across hESC-CM differentiation (Bertero et al., 2019), so that positive and negative values indicate A and B compartmentalization, respectively."

"Changes in A/B compartmentalization were determined by a one-way ANOVA of PC1 scores across the two replicates for the three cell lines, using a significance cutoff of P < 0.05 combined by the need for the average PC1 to change sign across at least one pair of condition. Consistent changes in A/B compartmentalization were further selected if the average PC1 score for mutant hiPSC-CMs changed sign compared with the average PC1 score of each corrected hiPSC-CMs."

Methods, "In situ DNase Hi-C": "The assay was performed on ∼2 × 10^6 hiPSC-CMs at day 14 of differentiation on two biological replicates (independent differentiations) per cell line."

Methods, RNA-seq: "RNA-seq was performed on 2–3 × 10^6 hiPSC-CMs at day 14 of differentiation on three biological replicates (independent differentiations) per cell line… Reads were mapped to hg38 using STAR".

## Relation to the lamina (Results) — the only lamina comparison performed

"We previously showed that transition from the B to A compartment during cardiogenesis often reflects relocalization of loci from the nuclear periphery to the nuclear interior (Bertero et al., 2019), in agreement with the notion that the B compartment contains the vast majority of LADs (Luperchio et al., 2017). Thus, we speculated that the opposite could also be true, and that lack of transition from the A to B compartment in mutant hiPSC-CMs might reflect impairment of translocation to peripheral LADs. We tested this by combined immunofluorescence for the nuclear lamina and 3D-DNA FISH for three loci contained within genomic locations showing aberrant compartmentalization in mutant hiPSC-CMs: CACNA1A, LRRC4B, and PCDHGB4 (Fig. 6 E). … Interestingly, PCDHGB4 did not change localization either during differentiation or in mutant hiPSC-CMs (Fig. 7 B), indicating that aberrant compartmentalization of this chromatin region does not result from changes in association to the nuclear lamina, and thus it must reflect some other mechanism."

→ The lamina comparison in Bertero 2019 is imaging-based (immunoFISH at 3 loci + 2 control loci). No genome-wide LAD/DamID/LMNB1 dataset is compared to the PC1 changes anywhere in the paper (no DamID or ChIP/CUT&RUN lamina data were generated or reanalyzed).

## Prior-art-relevant framing statement (Discussion)

"On the other hand, our results agree with previous findings from mouse embryonic stem cells, in which depletion of B-type nuclear lamins results in minimal changes in A/B compartmentalization (Amendola and van Steensel, 2015; Zheng et al., 2015, 2018)."
