# LYSMD3 prior-art follow-up, 24 September 2026

**Decision: retire the broad claim that LYSMD3 is newly connected to lamin A or progerin.** Keep the human cardiomyocyte result as an exploratory, context-specific observation only. This follow-up found a decisive exact-gene result in the 2012 paper's main Table 1; no supplement is needed to establish that prior connection.

## Exact primary result

[Kubben et al., *Mapping of lamin A- and progerin-interacting genome regions* (2012), Table 1](https://pmc.ncbi.nlm.nih.gov/articles/PMC3443488/#Tab1), DOI [10.1007/s00412-012-0376-7](https://doi.org/10.1007/s00412-012-0376-7), contains the row below. These are the paper's values, not a new analysis.

| Field | Published value |
| --- | --- |
| Mouse Entrez gene ID | 80289 |
| Gene abbreviation | Lysmd3 |
| Target type | MEF A&P Common |
| Expression WT+Ctrl / WT+OST-A / WT+OST-P | 2.24 / 2.37 / 2.41 |
| Linear FC A/Ctrl | 1.09, no significance mark |
| Linear FC P/Ctrl | 1.13, significance mark a |
| Linear FC P/A | 1.03, no significance mark |
| Expression-change labels | A- / P↑ |
| Regulator of transcription? / HGPS candidate? | No / No |

The paper's methods define the common A&P set as promoters enriched in both lamin-A and progerin ChIP compared with control, with comparable A/P signals. The footnote defines mark a as ANOVA p < 0.05 without a fold-change threshold. It therefore reports a modest progerin/control expression increase at a previously mapped lamina-associated locus. The authors did **not** select Lysmd3 as an HGPS candidate. The row is from mouse embryonic fibroblasts. The article also studies mouse cardiac myocytes, but that does not turn this row into a Lysmd3-specific cardiac experiment. These distinctions matter: promoter association does not show binding between the LYSMD3 protein and lamins, causation of cardiomyopathy, or replication of the new human LMNA-depletion observation.

Machine-readable cells, column mapping, source offsets, and hashes are in `pmc3443488-lysmd3-table1-row.json`. The retained DOM evidence (`pmc3443488-table1-source-fragment.html`, with a compact row/header/footnote in `pmc3443488-lysmd3-row.html`) is hash-bound in `provenance.manifest.json` but not tracked in Git because it is raw article HTML.

## Correction to the earlier audit

The new Ghostget capture has the **same Markdown SHA-256** as the earlier capture: `f3365bdaa00bc580ae72bcd0d1bc25c026ab79b57ffb67f3c39cd279d091fb26`. A case-insensitive scan finds one exact `Lysmd3` occurrence in its Table 1. The earlier statement that this gene did not occur in the retained main text is wrong and should be corrected in the public audit and report. The capture did not omit the table. A case-sensitive scan for uppercase `LYSMD3` would miss the mouse-style symbol, but the exact cause of the earlier error was not proven.

## Gene identity and bounded additional searches

[NCBI human Gene 116068](https://www.ncbi.nlm.nih.gov/gene/116068) fixes the human symbol as LYSMD3, HGNC:26969, Ensembl ENSG00000176018, and lists clone names FLJ13542 and DKFZp686F0735. [NCBI mouse Gene 80289](https://www.ncbi.nlm.nih.gov/gene/80289) fixes Lysmd3, MGI:1915906, Ensembl ENSMUSG00000035840, alias 1110030H10Rik, and explicitly identifies the human ortholog. Searches used these strings and case-insensitive symbols; species were not collapsed into one biological experiment. The NCBI entries were readable through the web tool. The separate local Ghostget captures returned challenge pages and are rejected as identity evidence, despite their technical capture status saying complete.

[Guo et al. (2017), a tetralogy-of-Fallot modifier study](https://pmc.ncbi.nlm.nih.gov/articles/PMC5647121/), examined Lysmd3 by in situ hybridization in E9.5/E10.5 mouse embryos and described its expression as ubiquitous. LYSMD3 was one of the genes in the 5q14.3 contact domain considered in that study. This is developmental expression evidence; it does not establish an LYSMD3-specific congenital-heart-disease mechanism or an LMNA effect.

[The 2025 DeepGCFS hypertension biomarker study](https://pmc.ncbi.nlm.nih.gov/articles/PMC11761172/) selected both LYSMD3 and CMTM5 among ten computational biomarkers and reported LYSMD3 differential expression in pulmonary-hypertension dataset GSE113439. Its training and validation disease contexts differ. This is prior cardiovascular transcriptomic evidence, not a validated molecular mechanism or evidence about LMNA cardiomyopathy.

A [2024 cardiac-fibroblast PKNOX2 paper](https://www.nature.com/articles/s41392-024-01804-5) has an indexed PDF search hit naming Lysmd3 among heatmap rows. The figure bytes were not verified; this remains a reading-queue item and is **not admitted as primary figure evidence**.

The search did not establish a prior exact human cardiomyocyte LMNA-depletion/relative-LMNB1-gain/LYSMD3-downregulation result. That is a bounded search outcome, not proof of novelty. No claim should be based on absence of a search result.

## Recommendation

Correct the public claim now, retain the computational observation and all failures, and prioritize stronger independently reproduced effects for the next campaign. If LYSMD3 remains under study, frame it as a known lamina-linked locus with a potentially context-dependent response, not a newly discovered lamin target. The remaining supplement gap concerns details such as whether Lysmd3 appears in the cardiac target lists; it no longer creates uncertainty about whether lamin/progerin prior art exists.

This investigation used no paid inference, no hosted Sponge writes, and no contact with collaborators. All artifacts are local research records, not authenticated Sponge attestations.
