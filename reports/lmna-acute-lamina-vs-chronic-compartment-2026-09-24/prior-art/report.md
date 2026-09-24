# Prior-art audit — acute LMNB1 change (Shen 2026) vs chronic Hi-C PC1 change (Bertero 2019)

Auditor: bounded prior-art pass, read-only, 2026-09-24 (UTC). Outputs: this report, `findings.json`, `query-ledger.json`, `sources/`.

## Decision

**Exact comparison previously reported: NO** (searched; not found). Confidence: medium-high — high that neither source study did it, medium that no third party did.

Strongest evidence, in order:

1. **Study A did not do it.** The full retained text of Shen et al. 2026 contains **zero** occurrences of "Hi-C", "compartment" (as a chromatin term), "PC1", "eigenvector" or "A/B" in body text, figure legends or methods. The only "compartment" string is inside a reference URL (Gholamalamdari 2025 eLife title). Bertero 2019 appears three times, all as background citations, e.g. Discussion: *"Multiple models of patient-derived LMNA variants leveraging hiPSCs have established that LMNA mutations affect genome organization (Briand et al., 2018, Bertero et al., 2019, Lee et al., 2019, Shah et al., 2021). Our findings extends this by suggesting that peripheral chromatin organization can be affected at multiple stages of differentiation, including after cellular identity has been established."* ([PMC13040498](https://pmc.ncbi.nlm.nih.gov/articles/PMC13040498/); local capture sha256 `35ffd2ab…f8d3a3`). **The planned test is therefore not a replication of an analysis in Study A.**
2. **Study B did not do it genome-wide.** Bertero 2019's only lamina comparison is 3D immunoFISH at five loci: *"We tested this by combined immunofluorescence for the nuclear lamina and 3D-DNA FISH for three loci contained within genomic locations showing aberrant compartmentalization in mutant hiPSC-CMs: CACNA1A, LRRC4B, and PCDHGB4 (Fig. 6 E)."* No DamID/ChIP/CUT&RUN lamina dataset is generated or reanalyzed anywhere in the paper.
3. **No third party found.** Europe PMC full-text search for the accessions (`GSE126459 OR GSE126460 OR GSE300197`) returns **1** hit — Bertero 2019 itself. `CITES:41891953_MED` (works citing Shen 2026) returns **1** hit, a nuclear-mechanobiology review with no reanalysis. Twelve further Europe PMC queries (incl. preprints via `SRC:PPR`) and five GEO queries surfaced no study pairing acute lamin-A/C-depletion lamina data with chronic LMNA-mutant compartment data in any human cell type.

**Caveat, stated plainly:** absence of a search hit is not proof of novelty. Blind spots: Europe PMC full-text indexing lags for very recent articles; an analysis buried in a supplementary figure or a reviewer response is not text-indexed; theses, conference abstracts and non-Europe-PMC preprint servers were not searched; and I did not search Google Scholar citation graphs beyond the Europe PMC `CITES:` index.

**What is *not* novel:** the *class* of result. Lamin loss causing LAD detachment coupled to altered active/inactive domain interactions is established (Zheng 2018 Mol Cell, mESC, GSE89520), as is correlated lamina-association and compartmentalization change in an LMNA disease model (McCord 2013, HGPS fibroblasts). Bertero 2019 even states the expectation of a *small* effect. A positive result would be a new instance of a known class; a strong negative correlation across the genome would run against Bertero's own conclusion that compartment change in this model is "highly restricted".

---

## Item 1 — Bertero 2019 (Study B)

Source file: `sources/bertero-2019-jcb.md` (sha256 `4e4bdea637f1804d985a2c0ef44eb43a09e7e51438a6f89e0c626693da027c22`). Full text retrieved from Europe PMC JATS XML at 2026-09-24T17:50:29Z (the PMC HTML page returns a reCAPTCHA interstitial to automated fetches).

**Compartment changes reported.**
> "To further assess the effect of lamin A/C haploinsufficiency on chromatin compartmentalization, we identified genomic bins with significantly different A/B compartment scores and switching from active to inactive or vice versa between at least two conditions (Table S5). We noticed that the vast majority of compartment transitions were observed for mutant hiPSC-CMs versus each corrected control (Fig. 6 A), and that B to A inversions were more common than A to B ones (42 and 27, respectively; Table S5). We observed that 63% of A to B transitions in mutant cells involved the X chromosome, while B to A changes showed a notable concentration on chromosome 19 but were otherwise evenly spread across 13 additional chromosomes (Fig. 6 B, Fig. S5 A, and Table S5). Overall, compartment changes involved ∼1.2% of the genome, indicating that chromatin compartment dysregulation in mutant cells is not widespread but is actually highly restricted."

> (Discussion) "Analysis of A/B compartment changes revealed that only ∼1.2% of the genome changed compartments in LMNA mutants, and these aberrations were concentrated in hotspots on chromosomes 5 and 19. Surprisingly, the overlap between strong dysregulation in gene expression and compartment aberrations was minimal (<2%; Fig. S5 B)."

So: 69 switching 500 kb bins (42 B→A, 27 A→B), ~1.2% of the genome, X-enriched for A→B and chr19-enriched for B→A.

**Replicate handling and significance rule.**
> "Changes in A/B compartmentalization were determined by a one-way ANOVA of PC1 scores across the two replicates for the three cell lines, using a significance cutoff of P < 0.05 combined by the need for the average PC1 to change sign across at least one pair of condition. Consistent changes in A/B compartmentalization were further selected if the average PC1 score for mutant hiPSC-CMs changed sign compared with the average PC1 score of each corrected hiPSC-CMs."

> (Methods, In situ DNase Hi-C) "The assay was performed on ∼2 × 10^6 hiPSC-CMs at day 14 of differentiation on **two biological replicates (independent differentiations) per cell line**."

(RNA-seq used three biological replicates per line — GSE126458.)

**Comparison to lamina data.** Only imaging, only at CACNA1A, LRRC4B, PCDHGB4 (+ VAV1, LGALS14 controls):
> "We previously showed that transition from the B to A compartment during cardiogenesis often reflects relocalization of loci from the nuclear periphery to the nuclear interior (Bertero et al., 2019), in agreement with the notion that the B compartment contains the vast majority of LADs (Luperchio et al., 2017). Thus, we speculated that the opposite could also be true, and that lack of transition from the A to B compartment in mutant hiPSC-CMs might reflect impairment of translocation to peripheral LADs."

> "Interestingly, PCDHGB4 did not change localization either during differentiation or in mutant hiPSC-CMs (Fig. 7 B), indicating that aberrant compartmentalization of this chromatin region does not result from changes in association to the nuclear lamina, and thus it must reflect some other mechanism."

No LAD/DamID/LMNB1 genome-wide dataset is used. This is exactly the hypothesis the registered test would take genome-wide — and Bertero already reports one locus out of three where the coupling fails.

**Sign convention, build, resolution, tool.**
> "A/B compartmentalization was computed by eigenvalue decomposition of the contact maps using HOMER (Heinz et al., 2010) with 500-kb resolution and no additional windowing (super-resolution was also set at 500 kb). The sign of the first eigenvector (PC1) was selected based on the expression of ∼5,000 genes constitutively expressed across hESC-CM differentiation (Bertero et al., 2019), so that positive and negative values indicate A and B compartmentalization, respectively."

> (Fig. 6 A legend) "Heatmap of all significantly different A/B compartment scores (Hi-C matrix PC1; P < 0.05 by one-way ANOVA; n = 2 differentiations; Table S5) in 500-kb bins that changed PC1 sign between two or more conditions. **Positive and negative PC1 indicate A and B compartmentalization, respectively.**"

> (Methods, Hi-C data analysis) "Fastq files were mapped to the **hg38** genome using Burrows-Wheeler Aligner (BWA-MEM)… ICE–balanced matrices at **500-kb resolution**."

GEO corroborates at sample level (GSM3602088): *"validPair files were used as input for HOMER version 4.7 at 500KB resolution to generate PC1 values (A/B compartment calls)"*, *"Genome_build: hg38"*, file `GSM3602088_HiC_corrected.1_rep1_500KB_Active.PC1.bedGraph.gz`. **Positive Active.PC1 = A/active is confirmed, and it was set deliberately by the authors — it is not a HOMER guarantee, so the registered analysis should still sanity-check sign per chromosome against gene density before differencing.**

## Item 2 — Shen 2026 (Study A)

Source file: `sources/shen-2026-jcb.md` (sha256 `9707e74908b93c7dc5986878e13d90c1b0f94f6c6b0e73d1938b07f42f6df041`), excerpted from the local retained capture (capture.json `capturedAt` 2026-09-24T15:03:34.528Z, document sha256 `35ffd2afbaca2ea7b4f34cd487574776103358b2cbe0ecad79ba10460bf8d3a3`, sourceUrl https://pmc.ncbi.nlm.nih.gov/articles/PMC13040498/).

**Comparison to Hi-C / compartments / Bertero: none.** Zero body-text occurrences of "Hi-C", "compartment", "PC1", "A/B" (verified by case-insensitive grep over the whole capture). No R225X or other chronic LMNA-mutant dataset is reanalyzed. **This planned test is therefore not a replication.**

**Vulnerable LADs (which LADs lose lamina association).**
> (Abstract) "Genome-wide mapping and locus-specific imaging reveal that LADs with a distinct molecular signature are preferentially vulnerable to LMNA reduction."

> "Of the 641 siScr LADs, 138 (~20%) were entirely retained and classified as LMNA-insensitive… The remaining siScr LADs exhibited variable degrees of loss, with the top ~30% (n = 204 LADs) showing substantial reduction in LMNB1 occupancy (mean loss 55%; range 15 - 100%). These 204 LADs were classified as LMNA-sensitive"

> "Therefore, LADs with lower LMNB1 occupancy, reduced heterochromatin enrichment, and higher gene density are preferentially vulnerable to LMNA reduction, whereas the spatial positioning of strongly lamina-associated LADs is generally resistant to LMNA reduction."

**Regions gaining LMNB1: quantified once, then excluded.**
> "Approximately 82% of siScr LAD coverage was shared with siLMNA, with 18% of siScr LAD coverage lost and **13% of siLMNA LAD coverage gained** upon LMNA-knockdown (Fig. S1 H). Given the established role of the nuclear lamina in scaffolding peripheral heterochromatin, **subsequent analyses focused on LAD regions that lost LMNB1 occupancy** upon LMNA-knockdown (Guelen et al., 2008)."

This is a real novelty margin: the gain arm of the registered hypothesis is unstudied in Study A. Note the corollary risk — gained-LMNB1 regions are, per the paper's own framing, the least characterized part of the dataset, and the condition-level z-score construction means a genome-wide z-score is compositional (a decrease somewhere forces an apparent increase elsewhere). "Relative LMNB1 signal" deltas must be interpreted with that constraint, which no published analysis of these tracks has yet had to confront.

**Processing relevant to the null model** (Methods, corroborated by GSE300197 sample metadata): hg38, bowtie2, EDD LADs (fdr=0.05, gap 4), *"Genome-wide LMNB1 signal was calculated … by counting reads detected in each 1kb or 10kb genomic bin … z-scores were calculated excluding any bin with no reads from any sample mapped, and then were smoothed using a rolling mean of the flanking 5 windows to each side."* Three replicates per condition, *"merged within each condition"* (Spearman > 0.86); the public bigWigs are condition-level only (`GSE300197_siScr.mCh.CR.zscore.bw` etc., `Sample_supplementary_file_1 = NONE` at sample level). The exposure side is thus effectively n=1 per condition with ~110 kb induced autocorrelation — the within-chromosome circular-shift null is the right call, and the shift block must exceed the smoothing width.

## Item 3 — Other publications comparing acute depletion lamina change with chronic LMNA-mutant compartment change

**Direct comparison: none found** (2012–2026, incl. preprints). Evidence: `GSE126459 OR GSE126460 OR GSE300197` in Europe PMC full text → 1 hit (Bertero 2019 itself); `CITES:41891953_MED` → 1 hit ([Nuclear mechanobiology: a brief history and five unresolved questions](https://europepmc.org/article/MED/42635001), a review); `CITES:31395619_MED AND (LAD OR "lamina-associated" OR LMNB1 OR DamID)` → 28 hits, all reviews or unrelated primary work (the only primary cardiomyocyte lamina papers among them are Shen 2026 itself and Shah-lab work, neither of which reanalyses Bertero's Hi-C); `ABSTRACT:"cardiac laminopathy" AND ("Hi-C" OR compartment) AND ("LAD" OR lamina)` → 0.

**Class-level prior art (established; see `sources/prior-art-class.md`):**

- **Zheng et al. 2018, Mol Cell** (PMID 30201095, GSE89520, mESC lamin triple-KO): *"Combining Hi-C with fluorescence in situ hybridization (FISH) and analyses of lamina-associated domains (LADs), we reveal that lamin loss causes expansion or detachment of specific LADs in mouse ESCs. The detached LADs disrupt 3D interactions of both LADs and interior chromatin."* Detachment coupled to compartment behavior is known — in mouse, with all lamins removed.
- **McCord et al. 2013, Genome Res** (HGPS; GSE41763/GSE41764): *"HGPS cells experience genome-wide alterations in patterns of H3K27me3 deposition, changes in the associations of genomic loci with nuclear lamin A/C, and, at late passages, genome-wide loss of spatial compartmentalization of active and inactive chromatin domains"* — a within-study correlation of lamina association and compartmentalization in a chronic LMNA disease model.
- **"Differential contributions of nuclear lamina association and genome compartmentalization to gene regulation"** (2023 Nucleus, PMID 37017584): cross-dataset comparison of lamin association vs Hi-C compartment across cell types is established method; *"In general, we observed an additive rather than redundant effect of lamin association and compartment status."*
- **Bertero 2019's own prior expectation:** *"our results agree with previous findings from mouse embryonic stem cells, in which depletion of B-type nuclear lamins results in minimal changes in A/B compartmentalization (Amendola and van Steensel, 2015; Zheng et al., 2015, 2018)."*

**Distinction, stated explicitly:** the *class* ("LAD gain/loss tracks B/A compartment switching; lamin loss perturbs both") is known and repeatedly published. The *exact comparison* (Shen 2026 acute siLMNA LMNB1 delta vs Bertero 2019 R225X-minus-corrected PC1 delta, 500 kb, hg38, human cardiomyocytes, acute vs chronic, across studies) has not been reported in anything I could find.

## Item 4 — Other public datasets usable as an additional untouched outcome cohort

Metadata only; no data files retrieved. Verbatim design strings in `sources/geo-metadata.md`.

| Accession | What it is | Fit for this question |
|---|---|---|
| **GSE314556** | "Lamin A/C maintains genome topology… [Hi-C]"; "HiC of WT and LMNA/C depleted cells", human B-lymphoblastoid (PubMed 41648489) | **Best compartment-outcome cohort.** Same exposure (LMNA loss), Hi-C outcome, independent lab. Non-cardiac, EBV-transformed → generality check, not strict replication |
| **GSE136252** | Shah et al. 2021 Cell Stem Cell: LMNB1 + H3K9me2 domains and RNA-seq in LMNA T10I / R541C iPSC-CMs, hepatocytes, adipocytes | **Best lamina-outcome cohort.** Chronic human LMNA variants, replicate-level, cardiomyocyte. No Hi-C → tests exposure reproducibility (acute vs chronic lamina delta), not the compartment outcome |
| **GSE41763 / GSE41764** | McCord 2013 HGPS fibroblasts: Hi-C + lamin A/C DamID + H3K27me3 | Chronic progerin (dominant-negative, not haploinsufficiency), fibroblast, hg19-era build → weak replication, useful directional check |
| **GSE312029 / GSE312031** | HGPS iPSC-derived VSMC: in situ Hi-C + CUT&Tag (CTCF, SMC1A, H3K27me3/ac, H3K36me3) | Recent Hi-C in an LMNA-disease iPSC derivative; no lamin CUT&Tag listed |
| **GSE206704 / GSE206707** | HGPS fibroblast Hi-C + transcriptome (eLife 2023) | Additional chronic progerin compartment data |
| **GSE120836 / GSE120837** | "Genomic Reorganization of Lamin-Associated Domains in Cardiac Myocytes…" | Cardiac LAD reorganization; confirm organism and perturbation before use |
| **GSE221288** | "Gene regulatory loops at lamina-associated domains" (human ASC; lamin A/C ChIP-seq + public enhancer-capture Hi-C) | LAD-vs-contact reference, not an LMNA-perturbation cohort |
| **GSE89520** | Zheng 2018 lamin TKO mESC Hi-C/LADs | Mouse; class-level cross-species check only |

Notable negative: `LMNA AND (knockdown OR siRNA OR degron OR knockout) AND Homo sapiens AND (hi-c OR compartment)` in GEO returned **0** series, and the human LMNA+Hi-C query returned only 13 records (Bertero's series/samples, GSE314556, GSE221288, GSE81671, GSE41763). There is no second human *acute* LMNA-depletion Hi-C dataset to pair against — which is why the registered test must borrow across studies, and why a second cohort for the *exposure* side (GSE136252) is more attainable than one for the outcome side.

## Search coverage

Databases: Europe PMC REST (MED + PMC + PPR preprints) — 12 structured queries plus 3 abstract lookups and 2 full-text retrievals; NCBI GEO DataSets via E-utilities — 5 queries; GEO SOFT accession metadata — 11 accessions; general WebSearch — 4 queries; local retained capture of Study A — full-text grep. All timestamps, query strings and hit counts are in `query-ledger.json`. All searches 2026-09-24, 17:48–17:55 UTC.

Retained sources (`prior-art/sources/`, SHA-256 of retained text):

| File | SHA-256 |
|---|---|
| `bertero-2019-jcb.md` | `4e4bdea637f1804d985a2c0ef44eb43a09e7e51438a6f89e0c626693da027c22` |
| `shen-2026-jcb.md` | `9707e74908b93c7dc5986878e13d90c1b0f94f6c6b0e73d1938b07f42f6df041` |
| `geo-metadata.md` | `3b593b02d99319c0895626335211d99829b4a35aa87c27556413370979847d3c` |
| `prior-art-class.md` | `95937af869c04d23e5b86e2366f11e23666563c9192ecff948561e14454b5804` |

Upstream capture already on disk: `jcb-2026-lmna.md`, sha256 `35ffd2afbaca2ea7b4f34cd487574776103358b2cbe0ecad79ba10460bf8d3a3` (captured 2026-09-24T15:03:34Z).

## Gaps and limits

1. **Not proof of novelty.** The negative searches establish that nothing surfaced, not that nothing exists. Supplementary-only analyses, theses, non-indexed preprints and very recent papers are invisible to these queries.
2. **Shah 2021 full text unread.** PMC8106635 is not open access on Europe PMC (fullTextXML returned 150 bytes) and PMC HTML is reCAPTCHA-gated to automated fetches. I could not verify from its text whether it compares its LMNB1 data to Bertero's Hi-C. Its GEO design lists no Hi-C, so a compartment comparison there is unlikely but unconfirmed — **the single largest residual risk to the "no" decision**; worth one manual browser read.
3. **Bertero Table S5 not opened.** The per-bin PC1 table (the object the planned test would correlate against) was not inspected; 42/27/1.2% are from the text. Bin count, chromosome coverage and NA handling are unverified.
4. **PMC and GEO HTML are reCAPTCHA-gated** for automated fetches; all evidence came from Europe PMC XML, GEO SOFT text views and E-utilities. No GEO data files were downloaded, per scope.
5. **Directionality prior is against a large effect.** Both Bertero's conclusion (~1.2% of genome) and the mESC literature it cites predict minimal compartment change under lamin loss. The registered analysis should pre-specify what magnitude of negative correlation counts as a finding rather than noise, and pre-commit to how condition-level z-score compositionality is handled on the Study A side.


## Addendum (main session, 2026-09-24)

Gap 1 partially closed: the Europe PMC core record for Shah 2021 (PMC8106635) carries no mention of Hi-C, chromosome conformation, compartments or PC1 in its abstract or keywords. Full text still unread; recorded as `shah-2021-abstract-no-hic` in findings.json.
