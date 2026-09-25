# Prior art: genome-wide mining of context-specific gene dependencies in DepMap

**Compiled** 2026-09-25. **Scope:** novelty assessment for a planned study that mines DepMap 24Q4
`ScreenGeneEffect.csv` (screen-level Chronos gene effects) for associations between a genomic context
feature (damaging mutation, hotspot mutation, deep CN deletion, very low expression, MSI/WGD/aneuploidy)
and dependency on another gene, with within-lineage centering, **discovery in Broad Avana screens
(n=1046)** and **confirmation in sealed Sanger Kosuke-Yusa (KY) screens (n=315, incl. 119 KY-only models)**.

Every claim below carries a citation. Quotations are verbatim from the cited full text (Europe PMC
full-text XML, bioRxiv full text, or the DepMap release README) unless marked "abstract only".

**Contents.** §0 what the release already contains · §1 who has already mined DepMap this way (§1.7 corrects two
citations in the planning brief; §1.10 is the related-work table) · §2 the Avana/KY split in the literature
(§2.4 the pre-registration search) · §3 published replication rates and thresholds (§3.6 puts them all on one
scale) · §4 verified login-free reference-set downloads · §5 the statistical traps · Appendix A access notes ·
**§6 Verdict — last section.**

**Answer in one line, per the six questions asked:** the discovery space is thoroughly worked (Q1), nobody has
used the Avana→KY boundary as a sealed pre-registered holdout (Q2), the only published cross-library replication
rate is 77%/61% on *shared* cell lines with pre-selected features (Q3), all five reference sets are downloadable
without login and three of the canonical URLs in circulation are dead or wrong (Q4), six trap classes are
documented with their published mechanism (Q5), verdict **PARTIALLY_KNOWN** (Q6).

---

## 0. What the planned dataset already is (read this before claiming novelty)

The DepMap Public 24Q4 `README.txt` (figshare `10.25452/figshare.plus.27993248`, file
`README.txt`, 43,103 bytes) documents the pipeline that produces `ScreenGeneEffect.csv`:

> "Run Chronos per library-screen type to generate screen-level gene effect scores, apply copy number
> correction, then scale such that median of common essentials is at -1.0 and median of nonessentials is
> at 0, and correct for screen quality. To correct proximity bias, the median gene effect of each
> chromosome arm is aligned to be the same across all screens. See Venceti et al. 2024
> (https://doi.org/10.1186/s13059-024-03336-1) for more details on this correction. This produces the
> integrated CRISPRGeneEffect matrix using Chronos's innate batch correction. Concatenate gene effects
> from all libraries into a single ScreenGeneEffect matrix."

> "### ScreenGeneEffect.csv … Gene effect estimates for all screens Chronos processed by library, copy
> number corrected, scaled, screen quality corrected then concatenated."

The same README states what the three libraries are:

> "This Achilles dataset contains the results of genome-scale CRISPR knockout screens for Achilles (using Avana
> Cas9 and Humagne-CD Cas12 libraries) and Achilles combined with Sanger's Project SCORE (KY Cas9 library)
> screens."

The project's own sealed split (`data/split.receipt.json`) matches: AV = 1046 screens, KY = 315 screens,
CD = 40 screens, 18,435 gene columns, with SHA-256 receipts for each part — i.e. the split is third-party
verifiable, and the **Humagne-CD screens are a different nuclease (Cas12a)**, which matters for §6.2 item 4.

Two consequences the design must state explicitly:

1. AV and KY screens in `ScreenGeneEffect.csv` are **Chronos-processed separately per library**, so the
   holdout is genuinely a separate inference run, not a re-slicing of one joint fit (good for the design).
   The joint-fit matrix is `CRISPRGeneEffect.csv`; using it would destroy the holdout.
2. 24Q4 **already applies arm-level proximity-bias correction** and CN correction. This substantially
   blunts (but does not eliminate — see §5) the strongest reviewer objection.

Feature definitions the planned study will use are also fixed by the same README:

> "### OmicsSomaticMutationsMatrixDamaging.csv … Genotyped matrix determining for each cell line whether
> each gene has at least one damaging mutation. A variant is considered a damaging mutation if
> LikelyLoF == True. (0 == no mutation; If there is one or more damaging mutations in the same gene for the
> same cell line, the allele frequencies are summed, and if the sum is greater than 0.95, a value of 2 is
> assigned and if not, a value of 1 is assigned.)"

> "### OmicsSomaticMutationsMatrixHotspot.csv … A variant is considered a hot spot if it's present in one
> of the following: Hess et al. 2019 paper, OncoKB hotspot, COSMIC mutation significance tier 1."

> "### OmicsSignatures.csv … Model-level genomic signatures extracted from WES and WGS data. Signatures
> include Ploidy, Chromosomal Instability (CIN), Whole Genome Doubling (WGD), Loss of Heterozygosity
> Fraction (LoH Fraction), and Microsatellite Instability (MSI Score). Ploidy, CIN, WGD, and LoH Fraction
> are generated using PureCN … MSI Score is generated by MSIsensor2".

A release asset that directly addresses the protospacer-variant trap of §5.4 also exists:

> "### OmicsGuideMutationsBinaryAvana.csv … Binary matrix indicating whether there are mutations in guide
> locations from the Avana library. Avana guide library can be accessed from AvanaGuideMap.csv."

(equivalent `OmicsGuideMutationsBinaryKY.csv`, `OmicsGuideMutationsBinaryHumagne.csv`).

---

## 1. Who has already systematically mined DepMap for context-specific dependencies

### 1.1 DepMap's own Predictability / biomarker pipeline — the closest prior art

DepMap publishes, per gene, a random-forest model of the Chronos dependency profile against the **exact
feature classes the planned study proposes**. The authoritative description (Gong 2025, bioRxiv
`10.1101/2025.02.07.637152`, full text):

> "The predictability of any given dependency is summarized by a random forest model trained to predict a
> continuous Chronos dependency score using a set of biomarkers including mRNA expression, damaging
> mutations, driver mutations, hotspot mutations, lineage annotation, fusion, copy number, and confounder
> experimental covariates."

> "In brief, the relative importance indicates the impact of the feature on prediction accuracy relative to
> other features in the model (mRNA expression, damaging mutations, driver mutations, hotspot mutations,
> lineage annotation, fusion, copy number, and confounder experimental covariates), is computed with Gini
> importance, and is normalized so that the sum of all feature importances add up to 100."

> "The advantage of the random forest approach is that it reduces co-linearity, nominating features that are
> most predictive amongst other highly correlated features."

The method reference for the DepMap Predictability tab is Dempster, Krill-Burger, McFarland, Warren, Boehm,
Vazquez, Hahn, Golub & Tsherniak, *"Gene expression has more power for predicting in vitro cancer cell
vulnerabilities than genomics"*, bioRxiv 2020, DOI `10.1101/2020.02.21.959627` (preprint only; no journal
version indexed in Europe PMC as of 2026-09). Abstract, verbatim:

> "In this work, we conduct the first rigorous comparison of DNA- and expression-based predictive models for
> viability across five datasets encompassing chemical and genetic perturbations. We find that expression
> consistently outperforms DNA for predicting vulnerabilities, including many currently stratified by
> canonical DNA markers. Contrary to their perception in the literature, the most accurate expression-based
> models depend on few features and are amenable to biological interpretation."

Code: `https://github.com/broadinstitute/cds-ensemble`. A **downloadable frozen output** of this pipeline
exists (see §4): figshare `10.6084/m9.figshare.26955886`, *DepMap Predictability with Subsampling*,
CC BY 4.0, whose description states:

> "These files contain a summary of predictability of CRISPRGeneEffect in Depmap 24Q2 with variable numbers
> of cell lines provided to the predictive model. Subsets of the CRISPR gene effect matrix were supplied to
> a random forest model and out of sample performance recorded. The prediction method is similar to that
> described in https://doi.org/10.1101/2020.02.21.959627, with equivalent code available at
> https://github.com/broadinstitute/cds-ensemble".

**Implication:** a per-gene, genome-wide ranked list of the top-10 predictive features (expression / damaging
mutation / hotspot / CN / lineage) with out-of-sample Pearson r already exists for 17,108 genes. Any
"novel" pair the planned study reports must be checked against this table, and the planned analysis must be
positioned as *hypothesis-testing with a sealed replication cohort*, not as *first-time feature discovery*.

### 1.2 Gong 2025 — a pan-cancer biomarker mining of DepMap with these same features

Dennis Gong, *"Pan-Cancer Biomarker Analysis from the Cancer Dependency Map: A Blueprint for Precision
Oncology"*, bioRxiv, DOI `10.1101/2025.02.07.637152`.

> "We conducted a multi-omic analysis of biomarker-dependency relationships across 1,150 cancer molecular
> profiles to identify novel biomarkers for patient stratification."

> "Finally, we screen for associations between hotspot mutations, damaging mutations, and protein abundance,
> providing insights for developing heterobifunctional small molecules for induced proximity and protein
> degradation."

> "Within damaging mutations, TP53 mutation strongly predicted MDM2, MDM4, and PPM1D dependency, and ARID1A
> mutation strongly predicted ARID1B dependency."

> "Highly predictive hotspot mutations were saturated with oncogenes (BRAF, HRAS, NRAS, KRAS)."

> "DepMap demonstrated an overall sensitivity of 40.8% (29 validated target–indication combinations out of 71
> with clinical proof of concept), significantly exceeding the pretest probability of 2.86% (12,090
> significant relationships out of 422,050 possible pairings)."

Thresholds used: `Chronos < -1` for "strong dependency"; `Chronos < -0.5` for "essential"; lineage
enrichment by "a two-sided t-test between gene dependency effect sizes in each lineage relative to all other
cell lines", "Genes with a negative t-statistic were considered to exhibit stronger dependencies in the
lineage (p < 0.01)"; selectivity by skewed-LRT > 100. **No Sanger/KY holdout is used anywhere.**

### 1.3 Behan et al. 2019 (Project Score, KY library) — Nature

Behan FM et al., *"Prioritization of cancer therapeutic targets using CRISPR-Cas9 screens"*, Nature 568:511–516,
DOI `10.1038/s41586-019-1103-9`, PMID 30971826. Abstract (Europe PMC, abstract only — full text paywalled):

> "Here we performed genome-scale CRISPR-Cas9 screens in 324 human cancer cell lines from 30 cancer types and
> developed a data-driven framework to prioritize candidates for cancer therapeutics. We integrated cell
> fitness effects with genomic biomarkers and target tractability for drug development to systematically
> prioritize new targets in defined tissues and genotypes. We verified one of our most promising
> dependencies, the Werner syndrome ATP-dependent helicase, as a synthetic lethal target in tumours from
> multiple cancer types with microsatellite instability."

**Critical for the planned design:** the flagship MSI-context dependency (MSI → WRN) was *discovered in the
KY/Project Score data that the plan proposes to use as its holdout*. If the pipeline recovers MSI→WRN it is a
positive control, not a finding, and it must be pre-listed as such.

### 1.4 Pacini et al. 2024 (2nd-generation DepMap) — Cancer Cell

Pacini C, Duncan E, Gonçalves E, Gilbert J, Bhosle S, Horswell S, Karakoc E, Lightfoot H, Curry E, Muyas F,
Bouaboula M, Pedamallu CS, Cortes-Ciriano I, Behan FM, Zalmas LP, Barthorpe A, Francies H, Rowley S, Pollard
J, Beltrao P, Parts L, Iorio F, Garnett MJ. *"A comprehensive clinically informed map of dependencies in
cancer cells and framework for target prioritization."* Cancer Cell 42(2):301–316, DOI
`10.1016/j.ccell.2023.12.016`, PMID 38215750. **Access note:** cell.com and sciencedirect returned HTTP 403
to automated fetches and the article is hybrid-OA with no repository copy (Unpaywall/OpenAlex: `"any_repository_has_fulltext": False`); quotes below are the Europe PMC abstract plus the Sanger DepMap portal documentation.

> "Here, we construct a second-generation map of cancer dependencies by annotating 930 cancer cell lines with
> multi-omic data and analyze relationships between molecular markers and cancer dependencies derived from
> CRISPR-Cas9 screens. We identify dependency-associated gene expression markers beyond driver genes, and
> observe many gene addiction relationships driven by gain of function rather than synthetic lethal effects.
> By combining clinically informed dependency-marker associations with protein-protein interaction networks,
> we identify 370 anti-cancer priority targets for 27 cancer types, many of which have network-based evidence
> of a functional link with a marker in a cancer type."

Sanger DepMap portal documentation (`https://depmap.sanger.ac.uk/documentation/datasets/wg-crispr-knockout/`)
on how the two institutes' data were combined for this release:

> "16 additional screens generated at Sanger were added to the Project Score data. The screens were combined
> using ComBat, and correction vectors were estimated from eight models in both datasets to correct for
> differences in assay lengths."

Open Targets release note (`https://www.opentargets.org/news/second-generation-depmap-11-january-2024.html`):

> "pooled together data from 930 cancer cell lines" … "370 candidate priority drug targets across 27 cancer types"

**Key point for novelty:** Pacini 2024 **pooled** Broad + Sanger into one 930-model map. It did not hold one
library out.

### 1.5 Vinceti et al. 2024 — bias-correction benchmark that also counts biomarker associations

Note the correct spelling: **Vinceti** A, Iannuzzi RM, Boyle I, Trastulla L, Campbell CD, Vazquez F, Dempster
JM, Iorio F. *"A benchmark of computational methods for correcting biases of established and unknown origin in
CRISPR-Cas9 screening data."* Genome Biology 25:192 (2024), DOI `10.1186/s13059-024-03336-1`, PMID 39030569,
PMC11264729. (The DepMap 24Q4 README itself spells it "Venceti et al. 2024" — cite the DOI, not the README
spelling.) Full detail in §5.

> "We also evaluated the capability of each method to preserve data quality and heterogeneity by assessing the
> extent to which the processed data allows accurate detection of true positive essential genes, established
> oncogenetic addictions, and known/novel biomarkers of cancer dependency."

> "Most of the tested correction methods increased the number of significant (< 5% FDR) CFE/SSD associations
> compared to those detectable in the unprocessed versions of both datasets."

### 1.6 Other genome-wide association / prediction efforts

| Work | Citation | What it did |
|---|---|---|
| Tsherniak et al. 2017, "Defining a Cancer Dependency Map" | Cell 170:564–576.e16, DOI `10.1016/j.cell.2017.06.010`, PMID 28753430, PMC5667678 | Founding genome-wide dependency/marker map (RNAi era) |
| Chronos | Dempster JM et al., Genome Biol 22:343 (2021), DOI `10.1186/s13059-021-02540-7`, PMID 34930405, PMC8686573 | The gene-effect model the plan consumes; see §5.3 |
| Krill-Burger et al. 2023 | Genome Biol 24:192, DOI `10.1186/s13059-023-03020-w`, PMID 37612728, PMC10464129 | CRISPR-vs-RNAi predictive-marker comparison; defines the "biomarker classes" taxonomy |
| SLIdR | Srivatsa S et al., Nat Commun 13:7748 (2022), DOI `10.1038/s41467-022-35378-z`, PMID 36517508, PMC9751287 | Rank-based statistical framework for mutation→dependency SL pairs from pan-cancer perturbation screens |
| TCGA-DepMap | Shi X et al., Nat Cancer 5:1176–1194 (2024), DOI `10.1038/s43018-024-00789-y`, PMID 39009815, PMC11358024 | ML translation of DepMap dependencies to TCGA tumours, incl. synthetic lethalities |
| De Kegel et al. 2021 | Cell Syst 12:1144–1159, DOI `10.1016/j.cels.2021.08.006`, PMID 34529928 | Paralog SL classifier from DepMap 20Q2 + molecular profiles of >700 lines |
| Breast-cancer DMA pipeline | Cancer Biol Med (2025), DOI `10.20892/j.issn.2095-3941.2025.0290`, PMID 41131861, PMC12724301 | "We established a dependency marker association (DMA) analytic pipeline by using linear regression modeling to assess associations between 3,874 representative gene dependencies and multi-omics markers" (47 breast lines only) |

Field-state review (useful to cite for "this is an active, crowded area"): Vinceti A / Iorio F et al.,
*"Genetic interactions, synthetic lethality and complexity in cancer vulnerability mapping — Insights and
perspectives from the 2nd EuroDepMap symposium."* FEBS Letters (2026), DOI `10.1002/1873-3468.70306`,
PMID 41725108. Abstract, verbatim:

> "Large-scale perturbational approaches have transformed cancer research, enabling systematic identification of
> tumour-specific dependencies and therapeutic vulnerabilities. However, many clinically relevant vulnerabilities
> arise from genetic interactions, including synthetic lethal and buffering relationships, and are shaped by
> cellular state, lineage and treatment history. Interpreting complex dependency landscapes increasingly relies
> on advanced computational and AI-based approaches integrating molecular, phenotypic and contextual
> information."

Verbatim from SLIdR (PMC9751287):

> "Here, we present SLIdR (Synthetic Lethal Identification in R), a statistical framework for identifying SL
> pairs from large-scale perturbation screens." … "SLIdR successfully predicts SL pairs even with small sample
> sizes while minimizing the number of false positive targets." … "The predicted SL pairs are validated by
> large-scale drug-response profiles and literature evidence."

Verbatim from Krill-Burger 2023 (PMC10464129) on the biomarker taxonomy the planned study's "already known"
annotation must mirror:

> "Several types of relationships between genetic dependencies and predictive features ("biomarker classes")
> have been commonly observed, including genetic driver, expression addiction, paralog, and CYCLOPS."

> "We found that more CRISPR models were classified as expression addiction (dependency predicted by
> expression of the target gene) or paralog (dependency predicted by omics features of the target gene's
> paralogs), and a greater number of models were classified as CYCLOPS models (stronger dependency associated
> with lower copy number of the target gene) using RNAi."

> "To test this hypothesis, we created a functional similarity network for each CRISPR and RNAi dataset and
> measured enrichment of previously established gene-gene relationships (CORUM, InWeb PPI, KEGG, Ensembl
> Paralog) among the top co-dependencies of each gene".

---

### 1.7 Two identifier corrections to the brief's own citations (verified)

The planning brief cites "Boruta-based SL networks (bioRxiv 2025.04.07.647559 / Bioinformatics btag337)".
Both halves resolve to the same paper, and **that paper does not use Boruta**:

* bioRxiv `10.1101/2025.04.07.647559` was published as **DepMine** — Pearl LH, Pearl FMG,
  *Bioinformatics* 2026;42(6):btag337, DOI `10.1093/bioinformatics/btag337`, PMID 42203685, PMC13281939.
  Beware a near-collision: `btaf337` is a different paper entirely (DicePlot, PMID 40574664). Cite `btag337`.
  DepMine is the **only all-genes DepMap context-dependency sweep found in this survey**, and it is also the
  weakest statistically: χ² on 2×2 tables plus Cohen's *d* and Pareto decision trees, with a dependency
  threshold of 0.65, **no FDR correction, no held-out cohort and no independent-screen confirmation**, yielding
  34,256 GeneA:GeneB pairs at raw *P* < 0.05 (DepMap 2023Q2, 16,825 genes; all-by-all run on 2022Q2). Its
  dissections of the VPS4A/18q21.33 and HBS1L/9p21.3 loci are the cleanest published statement of the
  **regional-deletion passenger confounder** that the planned study's "deep copy-number deletion" arm inherits
  (see §5.2).
* The genuine Boruta-based DepMap SL pipeline is **PARIS** — Benfatto S et al.,
  *Mol Cancer* 2021;20:111, DOI `10.1186/s12943-021-01405-8`, PMID 34454516, PMC8401190. DepMap 19Q3;
  FATHMM-MKL > 0.7 to call damaging mutations; Boruta run for 500 iterations; 549 DDR genes first, then
  genome-wide; 15 high-confidence DDR SL interactions; validation is **wet-lab only (12 cell lines)**, no
  independent screen. Its headline methodological result is directly relevant to the plan's feature mix:
  expression data is a better predictor of dependency than mutation data.

**Consequence for the plan:** neither paper is a novelty blocker for the *design*, but DepMine is the paper a
reviewer will cite to say "all-genes context mining has been done". The distinguishing answer must be
statistical rigour (FDR + sealed confirmation), not scope.

### 1.8 The SL databases and browsers that would serve as the frozen "already known" set

None of these mine DepMap single-knockout screens for context associations, which is the cleanest part of the
novelty argument.

| Resource | Citation | Content | Does it contain DepMap context associations? |
|---|---|---|---|
| **SynLethDB 2.0** | Wang J et al., *Database (Oxford)* 2022;2022:baac030, DOI `10.1093/database/baac030`, PMID 35562840, PMC9216587 | 50,868 SL pairs total, **35,943 human**; sources = literature curation + GenomeRNAi/BioGRID + GEMINI-processed dual-knockout screens | **No.** `grep -ci "DepMap\|Achilles\|Avana"` over the paper = **0** |
| **SLKB** | Gökbağ B et al., *Nucleic Acids Res* 2024;52(D1):D1418–D1428, DOI `10.1093/nar/gkad806`, PMID 37889037, PMC10767912 | 11 combinatorial dual-knockout (CDKO) experiments, 22 cell lines, 16,059 SL and 264,424 non-SL pairs, five scoring methods | **No** — CDKO screens only |
| **PICKLES v3** | Novak R, Lenoir WF, Hart T et al., *Nucleic Acids Res* 2023;51(D1):D1117–D1121, DOI `10.1093/nar/gkac982`, PMID 36350677, PMC9825567 | Browser over Avana, Project Score and TKOv3 plus Chronos for 1,162 screens / 18,959 genes; display thresholds "BF > 10, Z-score < –4, or Chronos score < –0.75" | **No** — a browser with **no association hypothesis test, no multiple-testing correction and no lineage centering** |
| **DeepDEP** | Chiu Y-C et al., *Sci Adv* 2021;7(34):eabh1275, DOI `10.1126/sciadv.abh1275`, PMID 34417181, PMC8378822 | Deep-learning prediction of CERES gene effect from multi-omics, TCGA autoencoder pretraining | Prediction, not association testing; see §2.4 for its validation design |

The SLKB paper also supplies the single most useful reproducibility statistic in this literature for calibrating
expectations, verbatim (PMC10767912):

> "Our analysis revealed that there is only 1.21% overlap among the top 10% of SL pairs identified by the five
> scoring methods"

and, on cell-line transferability, Jurkat yielded 374 SL pairs and K562 1,523 with only **82 overlapping**.
Companion benchmark: *NAR Genom Bioinform* 2025, DOI `10.1093/nargab/lqaf129`, PMC12464814. A recent
compendium reports 117 of 472 predicted pairs confirmed: *Genome Biol* 2025, DOI
`10.1186/s13059-025-03737-w`, PMC12445041.

### 1.9 Genome-wide context-association tools that already cover several of the plan's feature types

**Tsherniak et al. 2017 (Cell 170:564, PMC5667678)** — the founding marker–dependency map, and the quantitative
warning against going genome-wide. Verbatim:

> "769 genes were differentially required in subsets of these cell lines at a threshold of six standard
> deviations from the mean. We found predictive models for 426 dependencies (55%) by nonlinear regression
> modeling considering 66,646 molecular features. Many dependencies fall into a limited number of classes, and
> unexpectedly, in 82% of models, the top biomarkers were expression-based."

> "Having discovered MDPs for high-confidence 6σ dependencies, we next applied them to 5,536 candidate
> dependencies at lower confidence levels (between a threshold of 2σ and 6σ from the mean). These additional
> analyses netted significant MDPs for 741 additional genes, a rate (13.4%) much lower than observed for 6σ
> dependencies (51.8%), reflecting the lower signal in this candidate dependencies set"

> "Surprisingly, the vast majority of predictable differential dependencies (82%) were best predicted by RNA
> expression levels, whereas DNA mutation accounted for only 16% and DNA copy number only 2%"

The 51.8% → 13.4% collapse is the base rate the plan's all-genes sweep will run into, and the 82%/16%/2%
split predicts that the plan's *expression* arm will dominate its *mutation* and *deletion* arms.

**CEN-tools** — Sharma S, Dincer C, Weidemüller P, Wright GJ, Petsalaki E, *Mol Syst Biol* 2020;16:e9698,
DOI `10.15252/msb.20209698`, PMID 33073517, PMC7569414. This is the closest *feature-set* overlap with the
plan: it tests both Broad DepMap and Sanger Project Score, and covers tissue, mutation, expression and drug
context, including MSI. Verbatim:

> "users can interrogate the essentiality of a gene from large-scale genome-scale CRISPR screens in a number of
> biological contexts including tissue of origin, mutation profiles, expression levels and drug responses."

> "For discrete contexts, cell lines were separated into test and control groups depending on whether they
> fulfilled the criteria of the context or not. The groups were separated either from pancancer or within a
> specific tissue/cancer type. … For the statistical tests, Kruskal–Wallis and Mann–Whitney U (two-samples
> Wilcoxon) tests were used with default parameters"

> "Pre-annotated commonly occurring hotspot mutations in 75 genes were used in the analysis."

> "The association of microsatellite instability (MSI) with the essentiality of the WRN helicase in colorectal
> cell lines was investigated in the 'SANGER' project."

**Its gap is exactly the plan's opportunity: CEN-tools states no FDR correction anywhere in its statistics
section.** Its "confidence" mechanism is a minimum-group-size tier (Group A ≥ 6 samples per group vs Group B
3–5), not multiple-testing control.

**SynLeGG** — Wappett M, … Overton IM, *Nucleic Acids Res* 2021;49(W1):W613–W618, DOI `10.1093/nar/gkab338`,
PMID 33997893, PMC8265155. Verbatim:

> "SynLeGG (www.overton-lab.uk/synlegg) identifies and visualizes mutually exclusive loss signatures in 'omics
> data to enable discovery of genetic dependency relationships (GDRs) across 783 cancer cell lines and 30
> tissues."

> "A total of 24 CRISPR predictions from SynLeGG overlapped with a recently published screen (34), where 18/24
> (75%) had Bonferroni-corrected T-test P-value <10−5; corresponding to FDR = 0.25".

It also supplies a base-rate anchor the plan should use when setting its expected discovery count: "these
proportions correspond to the frequency of negative genetic dependencies observed in the 5416 genes tested by
Costanzo et al." — i.e. **3.75%**.

**Chiu et al. 2025 breast DMA pipeline** (already in §1.6; full text read). Its scope limits, verbatim
(PMC12724301):

> "The analysis included dependencies with the top 2,000 standard deviation values, excluding pan-cancer core
> essential genes13, thus resulting in a total of 1,839 gene dependencies. … This process yielded a final set of
> 3,874 gene dependencies for correlation analysis with molecular characteristics across multiple layers."

> "P values were adjusted for the false discovery rate with the Benjamini-Hochberg procedure in multiple
> comparisons."

> "We selected a total of 47 cell lines with available gene dependency data for analysis, 21 of which had all
> omics data available"

47 breast lines, DepMap 22Q2, pre-filtered dependencies, and confirmation by drug-sensitivity concordance
rather than an independent screen.

**Krill-Burger et al. 2023 (PMC10464129) — the pan-lethal problem the plan must pre-declare.** Verbatim:

> "the majority of each cell line's dependencies are part of a set of 1867 genes that are shared dependencies
> across the entire collection (pan-lethals)."

> "We refer to a gene that is deemed a dependency in at least 90% of cell lines, as a pan-dependency."

> "When performing hit calling per cell line (genes with greater than 50% probability of dependency,
> 'Methods'), the increase in CRISPR pan-dependencies translates to an average of 63% of dependencies detected
> per cell line being pan-dependencies using CRISPR as opposed to 30% using RNAi"

> "The second model is the Unbiased model where the top 1000 features according to Pearson correlation between
> feature and perturbation target are included without use of any other prior information. Random forest
> regression models (100 trees, max-depth of 8, and a minimum of 5 cell lines per leaf) from the Python
> scikit-learn package were trained using stratified 5-fold cross-validation."

An all-genes sweep will carry ~1,867 CRISPR pan-lethal genes that structurally cannot show context signal in
Chronos. Either declare them in scope and expect near-zero yield there, or exclude them by a pre-stated rule;
Krill-Burger is the citation for the rule.

**Chronos's own biomarker benchmark** (Dempster 2021, PMC8686573) is worth citing to justify the plan's use of
Chronos and its −0.5 threshold. Verbatim:

> "Chronos generally outperforms competitors in separation of controls and strength of biomarker associations,
> particularly when longitudinal data is available. Additionally, Chronos exhibits the lowest copy number and
> screen quality bias of evaluated methods."

> "For interpretability, we recommend users shift and scale the whole inferred gene matrix so the median of all
> nonessential gene scores is 0 and the median of all essential gene scores is -1 globally, not per cell line."

Note the asymmetry the plan inherits: Chronos's advantage over competitors was demonstrated in **Achilles/Avana**
and was *not* significant in Project Score — "BAGEL2 outperformed Chronos in Project Score by 13% according to
NNMD, while Chronos was first by 6.5% over MaGECK as measured by PR AUC; however, the differences between first
and second-best algorithms in Project Score were not statistically significant." A reviewer can argue the
confirmation set is scored by a method tuned on the discovery set's library.

For the plan's "very low expression" arm, Chronos's expression-addiction benchmark is the relevant precedent:

> "After subsetting to those present in all algorithms and datasets, and removing any common essential genes
> (identified from the DepMap releases [26, 32]), we had 106 putative expression addiction genes."

**Project Score's own prioritisation machinery** — Dwane L, Behan FM, Gonçalves E et al., *Nucleic Acids Res*
2021;49(D1):D1365–D1372, DOI `10.1093/nar/gkaa882`, PMID 33068406, PMC7778984 — is how Behan 2019's
biomarker classes are actually defined, and it is fetchable where the Behan body is not. Verbatim:

> "The Project Score database currently allows users to investigate the fitness effect of 18 009 genes tested
> across 323 cancer cell models."

> "The remaining 30% of the target priority score was based on evidence of a biomarker associated with a
> dependency on the target, and takes into account the frequency at which the target is somatically altered in
> patient tumours (genomic biomarker prevalence). The strength of the associated genomic biomarker ranges from
> class A to class C (strongest to weakest) and is based on statistical significance of the target association
> and effect size. Core fitness genes have by default an assigned priority score of 0 (or null), as these
> targets have an increased likelihood of non-selective toxic effects in tissues."

**SLIdR's cross-screen combination** (Srivatsa et al. 2022, PMC9751287) is the closest published analogue to
the plan's confirmation step, and its caveat is the plan's caveat. Verbatim:

> "Therefore, using Fisher's method to combine the corresponding p-values from both screens for each SL pair
> and retaining only the significant pairs, we identified 162 robust SL pairs across both screens (see
> Methods). These 162 pairs retained 62% (91 SL pairs) of the original DRIVE candidate SL pai[rs]"

> "This could partly be attributed to the reduced power in the CRISPR analysis, as the data had only 266 cell
> lines in common with the DRIVE data, i.e., 107 cell lines from the DRIVE screen were missing in the CRISPR
> screen. Another factor is the differences in pre-processing and normalization steps across the two screens."

> "SLIdR recovered a significant fraction of established SL interactions (hypergeometric p-values < 10−9) with
> sensitivities of 12.3% and 11.45%"

**Further tools in this family** (metadata verified, full texts not read — leads only): shinyDepMap, Shimada K
et al., *eLife* 2021;10:e67073, DOI `10.7554/eLife.67073`; "Dynamic rewiring of biological activity across
genotype and lineage revealed by context-dependent functional interactions", *Genome Biol* 2022, DOI
`10.1186/s13059-022-02712-z`, PMC9241233; SL-Miner, *Bioinformatics* 2024, DOI
`10.1093/bioinformatics/btae016`; the `depmap` R package, *F1000Research*, DOI
`10.12688/f1000research.52811.1`. Two 2025 results overlap the plan's feature list directly and should be read
before writing: "SKI complex loss renders 9p21.3-deleted or MSI-H cancers dependent on PELO", *Nature* 2025,
DOI `10.1038/s41586-024-08509-3`, PMC11864980 (**9p21.3 deletion and MSI-H — two of the plan's context
features already published as a dependency result**), and "A tumour-derived organoid biobank maps cancer gene
dependencies", *Nature* 2026, DOI `10.1038/s41586-026-10830-y`, PMC13581617.

### 1.10 Prior-art comparison table (the related-work table for the paper)

| Work | Data | Scope of association testing | Statistic / thresholds | Multiple testing | Independent-screen confirmation |
|---|---|---|---|---|---|
| **DepMine** (btag337) | DepMap 2023Q2 (all-by-all on 2022Q2) | 16,825 genes all-by-all; LoF and CN-deletion contexts | χ² on 2×2, dependency threshold 0.65, Cohen's *d* | **none** | **none** — 34,256 pairs at raw *P* < 0.05 |
| **PARIS** (Mol Cancer 2021) | DepMap 19Q3 | 549 DDR genes, then genome-wide | Boruta/RF importance, scaled importance 0.4 / 0.5 | n/a (RF selection) | wet-lab only (12 lines) |
| **SynLethDB 2.0** | literature + DBs + GEMINI on CDKO | curation; 35,943 human SL pairs | evidence-weighted confidence score | n/a | **no DepMap-derived pairs at all** |
| **SLKB** | 11 CDKO experiments, 22 lines | 280,483 pairs, 5 scoring methods | top-10% + ≥3/5 majority vote | n/a | **1.21% overlap across methods** |
| **PICKLES v3** | Avana, Score, TKOv3; BAGEL2/Z/Chronos | none — visualisation | BF > 10 / Z < −4 / Chronos < −0.75 (display only) | none | none |
| **DeepDEP** | DepMap 2018Q2, 278 lines, 1,298 DepOIs | prediction, not association | per-DepOI ρ; ρ = 0.87 on test set | n/a | Broad-new, Sanger/KY, RNAi — **post hoc** |
| **Dempster 2019** | Avana + KY, unprocessed | 578 CFEs × SSD genes = 29,350 tests | *t*-test, **FDR < 5%, ΔFC < −1** | **BH FDR** | **reciprocal: 71 Broad / 90 Sanger / 55 both** |
| **Tsherniak 2017** | 501 RNAi screens | 769 6σ deps × 66,646 features | ATLANTIS conditional-inference trees, FDR < 0.05 permutation | yes | none (RNAi only) |
| **Pacini 2021 / 2024** | integrated Broad+Sanger; 930 lines (2024) | CFE × dependency, per tissue | two-sided *t*-test, 5% FDR | yes | integration, not confirmation |
| **CEN-tools** | DepMap + Project Score | tissue / mutation / expression / drug, incl. MSI | Kruskal–Wallis, Mann–Whitney U, n ≥ 3 | **none stated** | both projects shown side by side |
| **SynLeGG** | 783 lines, CERES | GMM clusters × CRISPR/mutation | *t*-test q-values; χ² for mutation | q-values | 18/24 overlap with one screen, FDR 0.25 |
| **SLIdR** | DRIVE → DepMap CRISPR | driver × perturbed, pan-cancer and per-type | Irwin–Hall on ranks + matching | q ≤ 0.2 for drug arm | **Fisher's method → 162 robust pairs** |
| **Chiu 2025** | DepMap 22Q2, 47 breast lines | 3,874 pre-filtered deps × multi-omics | linear regression + subtype covariate | **BH FDR** | drug-sensitivity concordance only |
| **THE PLAN** | DepMap 24Q4 `ScreenGeneEffect`, screen-level Chronos | all ~18,400 genes × mut/hotspot/deep-del/low-expr/MSI/WGD/aneuploidy, lineage-centred | pre-declared, FDR + permutation placebos | yes | **sealed KY: 315 screens, 119 lines disjoint** |

**Three sentences for the Introduction, each defensible from the above:** (1) Systematic DepMap
context × dependency mining exists but is almost always restricted to a pre-selected set of *selective*
dependencies — 769 6σ genes (Tsherniak 2017), SSD genes only (Dempster 2019), 3,874 filtered genes (Chiu 2025),
549 DDR genes (PARIS) — and the one all-genes exception applies no multiple-testing correction at all (DepMine,
34,256 pairs at raw *P* < 0.05). (2) Cross-screen agreement of such associations has been measured once,
reciprocally rather than as discovery→confirmation, and it is imperfect: 55 of 71 Broad and 90 Sanger
associations replicated (Dempster 2019), while composite SL calls from the same combinatorial data agree only
1.21% across scoring methods (SLKB). (3) No published DepMap association study pre-registers its analysis or
reserves a sealed confirmation screen; existing "held-out" designs are within-dataset cross-validation folds
(§2.4).

## 2. Has anyone used the Avana-vs-KY library difference as a pre-registered train/holdout split?

**No.** Every use of the Broad/Sanger library difference found in this survey is either (a) a *concordance /
reproducibility* analysis on the **cell lines screened at both institutes**, or (b) *integration* of the two
datasets into one pooled matrix. No pre-registered discovery/holdout split, and no split that is disjoint in
cell lines as well as library, was found. Searches for `"pre-registered" DepMap`, `held-out cell lines
dependency biomarker validation`, and `replication cohort CRISPR dependency` returned no such design.

### 2.1 Dempster et al. 2019 — concordance, on the 147 shared cell lines

Dempster JM, Pacini C, Pantel S, Behan FM, Green T, Krill-Burger J, Beaver CM, Younger ST, Zhivich V, Najgebauer
H, et al. *"Agreement between two large pan-cancer CRISPR-Cas9 gene dependency data sets."* Nat Commun 10:5817
(2019), DOI `10.1038/s41467-019-13805-y`, PMID 31862961, PMC6925302.

What they actually did — verbatim:

> "We analyze data from recently published pan-cancer CRISPR-Cas9 screens performed at the Broad and Sanger
> Institutes. Despite significant differences in experimental protocols and reagents, we find that the screen
> results are highly concordant across multiple metrics with both common and specific dependencies jointly
> identified across the two studies. Furthermore, robust biomarkers of gene dependency found in one data set
> are recovered in the other. Through further analysis and replication experiments at each institute, we show
> that batch effects are driven principally by two key experimental parameters: the reagent library and the
> assay length."

The unit of analysis is the **overlap**, not a holdout:

> "considering 147 cell lines and 16,733 genes screened independently by both institutes"

> "We considered each of these features in turn and observed its status in the cell lines screened at both
> Sanger and Broad. Based on this, cell lines were split into two groups (respectively with negative/positive
> feature) and each of the SSD genes was t-tested for significant differences in gene scores across the
> obtained two groups of cell lines."

The nearest thing to a train/test framing is an ROC exercise using one study's hits as labels for the other's
p-values — still on the same 147 shared lines:

> "This was assessed by first considering the associations found significant (FDR < 5%) in one study as
> positive controls and calculating precision, recall, and sensitivity using a rank predictor based on the
> p-values obtained in the other study for all associations. We then tested how performance changed when
> considering increasingly stringent subsets of significant associations as positive controls and found that
> the most significant associations in one study were the most likely to be recovered in the other."

> "For the agreement assessment via ROC indicators (Recall, Precision and Specificity), for each of the two
> studies in turn we picked the most significant 20, 40, 60, 80, and 100% associations as true controls and
> evaluated the performance of a rank classifier based on the corresponding significance p-values obtained in
> the other study."

**This is the single most important sentence for the planned study's novelty claim:** Dempster's replication
test holds the *library/protocol* constant-free but holds the *cell lines* fixed. The planned design's
119 KY-only models make library **and** biological sample disjoint, which Dempster 2019 explicitly could not do.

### 2.2 Pacini et al. 2021 — integration, with the overlap used to *estimate batch effects*

Pacini C, Dempster JM, Boyle I, Gonçalves E, Najgebauer H, Karakoc E, van der Meer D, Barthorpe A, Lightfoot H,
Jaaks P, et al. *"Integrated cross-study datasets of genetic dependencies in cancer."* Nat Commun 12:1661
(2021), DOI `10.1038/s41467-021-21898-7`, PMID 33712601, PMC7955067.

> "Here, we integrated the two largest public independent CRISPR-Cas9 screens performed to date (at the Broad
> and Sanger institutes) by assessing, comparing, and selecting methods for correcting biases due to
> heterogeneous single-guide RNA efficiency, gene-independent responses to CRISPR-Cas9 targeting originated
> from copy number alterations, and experimental batch effects."

> "Between the two datasets, there was an overlap of 168 cell lines screened by both institutes, encompassing
> 16 different tissue types … The set of overlapping cell lines enabled the estimation of batch effects due to
> differences in the experimental protocols underlying the two datasets, without biasing the correction toward
> specific cell line lineages."

> "The ComBat estimates, pooled mean, variance and empirical Bayes adjustments (mean and standard deviation)
> for each batch based on the analysis of 168 cell lines common to both initial datasets were computed. The
> ComBat correction using these estimates was then applied to all screens, i.e., the union of the two initial
> datasets."

So the overlap is spent on **batch-effect estimation**, and the two libraries are then **merged**. This is the
opposite of a sealed holdout, and it is the standard practice the planned study departs from.

### 2.3 Pacini et al. 2024 and the DepMap "Broad–Sanger" page — integration again

`https://depmap.org/broad-sanger/`:

> "We analyzed the agreement between Achilles and Score dependency datasets along multiple axes and found good
> concordance."

> "Both studies not only identified consistent sets of biomarkers for selective dependencies, but also agreed
> on their predictive power."

> "The integrated datasets span over 900 cell lines, representing the largest integrative resource of genetic
> dependencies in cancer."

> "In our comparative analysis, we found good concordance but also clear batch effects between the Achilles and
> Score datasets."

> "Both studies identified similar sets of common essential genes (1,031 common essentials were identified by
> both institutes out of 1,688 identified by either)."

**Verdict on Q2:** the Avana/KY difference is used for *concordance* (Dempster 2019), *batch-effect estimation
and merging* (Pacini 2021, Pacini 2024), and *bias-correction benchmarking on both datasets in parallel*
(Vinceti 2024). Using it as a **sealed, pre-registered replication cohort — with 119 cell lines never screened
in the discovery library — appears to be unprecedented.** That is the methodological novelty; it is not a
biological novelty.

---

### 2.4 Systematic search for *any* pre-registered or sealed-holdout DepMap association study — zero hits

A dedicated set of queries was run against Europe PMC (which indexes abstracts **and** open-access full text),
so these counts cover bodies as well as abstracts:

| Query | Hits | Relevant |
|---|---|---|
| `"pre-registered" AND DepMap` | 3 | 0 — a stem-cell paper, a Chem Rev review, an AI-virtual-cell review |
| `"preregistered" AND "cancer dependency"` | 2 | 0 — a Perturb-seq paper, a meeting-abstract dump |
| `"prespecified analysis plan" AND DepMap` | 1 | 0 — an eLife survival-analysis paper |
| `"registered analysis plan" AND "cell line" AND CRISPR` | 1 | 0 — a neuroscience meeting abstract |
| `"replication cohort" AND "CRISPR dependency"` | **0** | — |
| `"held-out" AND DepMap AND biomarker` | 44 | 0 for this purpose — **all** are internal ML cross-validation splits |

**"Held-out" in this literature means a cross-validation split of cell lines within one dataset, never a sealed
independent screen reserved before analysis.** Concretely:

* **DeepDEP** (Chiu et al., *Sci Adv* 2021, PMC8378822) — 90/10 random cell-line split, then three post-hoc
  independent datasets. Verbatim: "We randomly partitioned CCLs into training/validation (90%) and testing
  (10%) sets, where eight-ninth of the samples in the former set were randomly selected for training and
  one-ninth for validation (Fig. 2C). No significant bias was observed between the training and testing sets in
  terms of tissue type, cell culture type, culture medium, or quality of CRISPR screen (table S6)." Its Sanger
  arm is the nearest thing in print to the plan's structure, and is explicitly *not* sealed: "We used three
  independent datasets to validate the model (table S5). … The other two datasets were collected from (i) a
  CRISPR-Cas9 screens conducted by the Sanger Institute using a different CRISPR library (7) and (ii) RNAi-based
  genome-wide dependency screens (25). … For CCLs unique to the validation sets, our predicted dependencies
  recapitulated their real screening results (89 and 211 CCLs; ρ = 0.61 and 0.47)." Note also that the Sanger
  score they validated against was not Chronos: "we used the fitness effect score that was calculated as the
  quantile-normalized depletion log fold change between targeting sgRNAs and plasmid library."
  **DeepDEP is nonetheless the one published precedent for scoring cell lines *unique to* the Sanger screen — the
  plan's 119 KY-only lines. It did so for prediction accuracy (ρ), not for confirming pre-selected associations.**
* **Krill-Burger 2023** (PMC10464129) — "stratified 5-fold cross-validation. Once predictions were made for each
  held-out set…" — within-dataset only.
* **Dempster 2019** (PMC6925302) — reciprocal recovery on the 147 lines screened at both institutes, not a
  discovery/confirmation split (§2.1).
* **SLIdR** (PMC9751287) — DRIVE discovery then DepMap-CRISPR as a second screen, combined by Fisher's method;
  not pre-registered and not sealed, and it re-used the same mutation calls after the DRIVE result was known.

**This is the plan's genuine novelty claim**, with two honesty constraints that must appear in the paper:
(a) absence from indexed literature is not proof of absence — OSF and AsPredicted registrations are indexed by
neither Europe PMC nor Crossref, so a targeted OSF search should be run before the claim is written down;
(b) the *spirit* of cross-screen confirmation is well established (Dempster 2019, SLIdR, DeepDEP), so the novelty
is the **pre-commitment and the sealing**, not the two-dataset structure. Do not over-claim the latter.

## 3. State of the art: how many context-specific associations replicate, and at what thresholds

All numbers verbatim.

### 3.1 Dempster 2019 (Nat Commun 10:5817) — the headline replication numbers

Genomic features (Cancer Functional Events; mutations in drivers, recurrent amplifications/deletions,
hypermethylated promoters, MSI status, tissue of origin):

> "These tests yielded 71 out of 29,350 possible significant associations (FDR < 5%, ΔFC < −1) between
> molecular features and gene dependency when using the Broad unprocessed data, and 90 when using the Sanger
> unprocessed data (Supplementary Data 6). Of these, 55 (77% of the Broad associations and 61% of the Sanger
> ones) were found in both data sets (FET p-value = 9.08 × 10–133, Fig. 3a and Supplementary Data 6)."

> "Further, the overall correlation between differences in gene depletion FCs between cell lines with and
> without a specified molecular feature was equal to 0.763, and 99.2% of associations had the same sign of
> differential dependency across the two studies (Fig. 3a). This indicates that the studies agree not only on
> the existence of specific biomarkers but also on their robustness."

Expression features:

> "we found significant overlap between gene expression biomarker associations identified in each data set with
> 4,459 (52% of Broad and 66% of Sanger gene expression biomarkers) found significant for both studies, out of
> 97,363 tested (Fisher's exact test p-value below machine precision), and strong overall agreement of
> correlation scores between gene expression markers and SSD genes dependency across data sets (Pearson's
> correlation 0.804, Fig. 3d)."

Exact statistical recipe and feature-frequency filters (this is the closest published template for the planned
analysis, and it is worth matching so the numbers are comparable):

> "We used cell lines' binary event matrices based on mutation data, copy number alterations, the tissue of
> origin and MSI status. The resulting set of 587 features were present in at least 3 different cell lines and
> fewer than 144. We performed a systematic two-sample unpaired Student's t-test (with the assumption of equal
> variance between compared populations) to assess the differential essentiality of each of the SSD genes
> across a dichotomy of cell lines defined by the status (present/absent) of each CFE in turn. SSD genes were
> those with NormLRT values greater than 100 in either institute. … P-values were corrected for multiple
> hypothesis testing using Benjamini–Hochberg. We also estimated the effect size of each tested association by
> means of Cohen's Delta (ΔFC), i.e. difference in population means divided by their pooled standard
> deviations."

Also worth reporting: **the "novel" yield is small and the "known" fraction dominates.**

> "Gene dependency associations identified with both data sets included expected as well as potentially novel
> hits. Examples of expected associations included increased dependency on ERBB2 in ERBB2-amplified cell lines,
> increased dependency on beta-catenin in APC mutant cell lines and increased dependency on MYCN in peripheral
> nervous system cell lines. A potentially novel association between FAM72B promoter hypermethylation and
> beta-catenin was also consistently identified across data sets (Fig. 3c)."

### 3.2 Pacini 2021 — scale of the test space, and marginal gain from merging

> "For each CFE and tissue type, we performed a Student's t-test for each selective gene dependency (SGD,
> Methods) contrasting two groups of cell lines based on the status of CFE under consideration
> (present/absent), for a total number of 2,142,162 biomarker/dependency pairs tested."
> (676 CFEs × 17 tissue types.)

> "Performing systematic biomarker analysis using CFEs on cell lines from individual tissue lineages unveiled
> 52 additional significant associations in the integrated dataset (when considering only CFE/gene-dependency
> pairs testable in the individual datasets at 1% FDR) with respect to those using the Sanger dataset alone,
> and 68 with respect to the Broad dataset (Supplementary Table 2)."

> "Furthermore, 19 tissue-specific significant associations identified in the integrated dataset were tested
> but not found significant in either the Broad or the Sanger dataset."

Selectivity gate used: `NormLRT > 200`.

> "We tested genes whose NormLRT values were greater than 200 in any integrated dataset."

Common-essential exclusion threshold (the same −0.5 the plan should adopt):

> "After filtering for genes that tend to be common essentials (mean dependency scores lower than −0.5 in the
> CRISPRcleanR-ComBat dataset, where −1 is the median of scores of known common essentials)"

### 3.3 Gene-effect magnitude conventions

Gong 2025 states the two conventions in use, verbatim:

> "Dependency scores are continuous values that range in magnitude but have empirically demonstrated that
> essential genes commonly have Chronos score < -1, and unexpressed genes commonly have Chronos score equal to 0."

> "the average dependency of essential genes; Chronos < -1"

> "These genes tended to also to be essential genes (Chronos < -0.5), such that knockout often had deleterious
> effects."

> "Across all targets showing preferential dependency (Chronos score 1.5 standard deviations below the mean) in
> a given cell line, 909 (79%) had at least one target with a dependency score < -1, with an average of 3.0
> targets per cell line (range: 1–13)."

### 3.4 The sobering base rate for SL reproducibility

Ku AA, Hu HM, Zhao X, Shah KN, Kongara S, Wu D, McCormick F, Balakrishnan S, Bandyopadhyay S. *"Integration of
multiple biological contexts reveals principles of synthetic lethality that affect reproducibility."* Nat Commun
11:2375 (2020), DOI `10.1038/s41467-020-16078-y`, PMID 32398776, PMC7217969.

> "We provide evidence for why most reported synthetic lethals are not reproducible which is addressable using a
> multi-faceted testing framework."

> "In the case of KRAS, we identify that published synthetic lethal screen hits significantly overlap at the
> pathway rather than gene level."

> "Lack of overlap likely stems from biological rather than technical limitations as most synthetic lethal
> phenotypes are strongly modulated by changes in cellular conditions or genetic context, the latter determined
> using a pairwise genetic interaction map that identifies numerous interactions that suppress synthetic lethal
> effects."

> "As a basis for comparison we selected the top 250 KRAS synthetic lethal genes reported in each study as hits
> (KSL genes, Supplementary Data 1), and found that there was marginal overlap between any pair of studies based
> on a hypergeometric test accounting for total number of tested genes in each study, consistent with previous
> reports"

> "In contrast, the gene level overlap between these two studies was not significant (p = 0.17)"

### 3.5 Lord & Ashworth: the field's own translational scorecard

Lord CJ, Ashworth A. *"PARP inhibitors: Synthetic lethality in the clinic."* Science 355:1152–1158 (2017), DOI
`10.1126/science.aam7344`, PMID 28302823, PMC6175050. Abstract first (Europe PMC `isOpenAccess: N`,
`fullTextXML` returns HTTP 500); the author manuscript was later retrieved in full via NCBI `efetch` — see below:

> "PARP inhibitors (PARPi), a cancer therapy targeting poly(ADP-ribose) polymerase, are the first clinically
> approved drugs designed to exploit synthetic lethality, a genetic concept proposed nearly a century ago."
> … "However, as with other targeted therapies, resistance to PARPi arises in advanced disease. In addition,
> determining the optimal use of PARPi within drug combination approaches has been challenging."

Lord CJ, Tutt ANJ, Ashworth A. *"Synthetic lethality and cancer therapy: lessons learned from the development of
PARP inhibitors."* Annu Rev Med 66:455–470 (2015), DOI `10.1146/annurev-med-050913-022545`, PMID 25341009.
**Abstract only** (no PMC record):

> "The genetic concept of synthetic lethality, in which the combination or synthesis of mutations in multiple
> genes results in cell death, provides a framework to design novel therapeutic approaches to cancer. Already
> there are promising indications, from clinical trials exploiting this concept by using poly(ADP-ribose)
> polymerase (PARP) inhibitors in patients with germline BRCA1 or BRCA2 gene mutations, that this approach could
> be beneficial."

Read together with Ku 2020: after ~two decades of SL screening, **one** SL relationship (BRCA–PARP) has produced
approved drugs, and the reviews frame everything else as promise. Any paper claiming new SL pairs from a
reanalysis is judged against that base rate.

**Planning consequence:** a *gene-level* replication requirement in a sealed cohort is a much harder bar than the
literature's own base rate; expect a low confirmation count, and pre-register a *pathway-level* secondary
endpoint so a null gene-level result is still interpretable.

**Full text of the Science 2017 paper was subsequently obtained** (via NCBI `efetch` on PMC6175050; Europe PMC's
`fullTextXML` endpoint returns HTTP 500 for it). Its explicit criteria for a therapeutically useful SL are the
standard the plan's confirmed hits will be judged against, verbatim:

> "For example, SL interactions with therapeutic value are ideally: (i) associated with a therapeutic window
> defined by a biomarker that can be used to stratify patients for therapy; (ii) capable of highly penetrant
> effects, where the presence of the biomarker predicts profound sensitivity to inhibition of the SL target in
> the majority of cases; (iii) robust in the face of the molecular diversity and plasticity seen in human
> tumors; (iv) pharmacologically tractable; and (v) well understood in terms of molecular mechanism, as this can
> inform the development of biomarkers and an understanding of drug resistance mechanisms."

> "Critical to these efforts will be a greater understanding of the underlying principles of what triggers an SL
> interaction, the factors determining the robustness of such interactions (i.e. how easily are SL interactions
> reversed by other molecular changes) and how robust SL interactions can be predicted, rather than only
> empirically identified through large-scale genetic screens. For example, it has been suggested that robust SL
> interactions are enriched for pairs of genes that are closely connected on protein-protein interaction
> networks; i.e., those that directly interact or interact via one or two additional proteins or nodes, rather
> than being distantly connected via a larger number of intervening nodes (71)."

**The single most on-point statement of the reproducibility problem in the Lord/Ashworth corpus** is Ryan CJ,
Bajrami I, Lord CJ. *"Synthetic Lethality and Cancer — Penetrance as the Major Barrier."* Trends Cancer
4(10):671–683 (2018), DOI `10.1016/j.trecan.2018.08.003`, PMID 30292351. **No PMC record, not open access;
abstract only**, verbatim:

> "Synthetic lethality has long been proposed as an approach for targeting genetic defects in tumours. Despite a
> decade of screening efforts, relatively few robust synthetic lethal targets have been identified. Improved
> genetic perturbation techniques, including CRISPR/Cas9 gene editing, have resulted in renewed enthusiasm for
> searching for synthetic lethal effects in cancer. An implicit assumption behind this enthusiasm is that the
> lack of reproducibly identified targets can be attributed to limitations of RNAi technologies. We argue here
> that a bigger hurdle is that most synthetic lethal interactions (SLIs) are not highly penetrant, in other
> words they are not robust to the extensive molecular heterogeneity seen in tumours. We outline strategies for
> identifying and prioritising SLIs that are most likely to be highly penetrant."

Ryan CJ, Devakumar LPS, Pettitt SJ, Lord CJ. *"Complex synthetic lethality in cancer."* Nat Genet 55:2039–2048
(2023), DOI `10.1038/s41588-023-01557-x`, PMID 38036785. **No PMC record; abstract only:**

> "The standard approach normally involves identifying genetic interactions between two genes, a driver and a
> target. In reality, however, most cancer synthetic lethal effects are likely complex and also polygenic, being
> influenced by the environment in addition to involving contributions from multiple genes."

Two further entries in this line, metadata-verified but unreadable (no abstract in Crossref or Europe PMC), listed
so the plan's related-work section is current rather than as support for any claim: Lord CJ, Tutt ANJ, Ashworth A,
*"Two decades of PARP inhibitor synthetic lethality in cancer"*, Nature, published 2026-05-06, DOI
`10.1038/s41586-026-10404-y`, PMID 42092061; and Gonçalves E, Ryan CJ, Adams DJ, *"Synthetic lethality in cancer
drug discovery: challenges and opportunities"*, Nat Rev Drug Discov, published 2025-09-11, DOI
`10.1038/s41573-025-01273-7`. **Do not** cite Lord & Ashworth, Nature 481:287 (2012), DOI
`10.1038/nature10760`, for a reproducibility claim — its abstract contains no such statement and the body was
not readable here.

### 3.6 All published replication/agreement rates found, on one scale

Everything below is a *different* quantity, and the plan should pick the one it is actually claiming to beat.

| Quantity | Value | Source |
|---|---|---|
| CFE×dependency associations significant in both Broad and Sanger, of those significant in one | 55 of 71 Broad (77%) and of 90 Sanger (61%) | Dempster 2019, PMC6925302 |
| Sign agreement of differential dependency across the two studies | **99.2%**; correlation of ΔFC = 0.763 | Dempster 2019 |
| Expression-biomarker associations significant in both | 4,459 of 97,363 tested — 52% of Broad, 66% of Sanger | Dempster 2019 |
| Marker–dependency models recovered for strongly selective vs weakly selective dependencies | **51.8% → 13.4%** | Tsherniak 2017, PMC5667678 |
| SL pairs retained when two independent screens are combined by Fisher's method | 162 robust pairs; **62%** of the original candidates | SLIdR, PMC9751287 |
| Overlap among top-10% SL pairs across five scoring methods on the *same* data | **1.21%** | SLKB, PMC10767912 |
| SL pairs shared between two cell lines in one CDKO study | 82, of 374 (Jurkat) and 1,523 (K562) | SLKB |
| Predicted pairs confirmed in a 2025 compendium | 117 of 472 | Genome Biol 2025, PMC12445041 |
| Background frequency of negative genetic dependencies (the prior on any random pair) | **3.75%** | SynLeGG, PMC8265155, citing Costanzo et al. |
| Interactions shared across eight combinatorial CRISPR screens | **4** | SLIdR, PMC9751287 |

**Reading:** the two numbers a reviewer will hold the plan to are Dempster's **77% / 61%** (what cross-library
replication looks like when it is done on *shared cell lines* with pre-selected strong features) and SLKB's
**1.21%** (what agreement looks like when anything about the analysis changes). The plan's design — different
library **and** disjoint cell lines **and** all genes — sits closer to the second condition than the first, so a
confirmation rate well below 77% is the honest expectation and must be pre-stated as such rather than treated as
failure.


---
## 4. Verified downloadable "already known" reference sets

Every row below was fetched from this machine on **2026-09-25** with
`curl -sL -o <file> <URL> -w "%{http_code} %{size_download} %{content_type}"` — **no login, no cookies, no
browser**. Byte counts and first lines are what actually came back, not what the site advertises. Working copies
are in this session's scratchpad (`…/scratchpad/refs/`); nothing was written into the project outside
`prior-art/`.

### 4.1 Verification table

| # | Item | Exact URL (verified) | Filename | HTTP | Bytes | First line (verbatim) | Rows | Login? | Licence |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **SynLethDB human SL pairs** (v3.0 archive) | `https://zenodo.org/records/22843223/files/Human.SL.detailed.tsv?download=1` | `Human.SL.detailed.tsv` | 200 | 3,742,521 | `x:START_ID	x_type	x_name	x_source	y:END_ID	y_type	y_name	y_source	relation	:TYPE	rel_source	edge_index	cell_line	pubmed_id	cancer` | 37,944 lines = **37,943 data rows**; 37,536 unique unordered symbol pairs | No | CC BY 4.0 (Zenodo record metadata `{"id":"cc-by-4.0"}`) |
| 1b | SynLethDB human **non**-SL (negative controls) | `https://zenodo.org/records/22843223/files/Human.non.SL.detailed.tsv?download=1` | `Human.non.SL.detailed.tsv` | 200 | 12,587,566 | same header as row 1 | 112,247 lines = **112,246 data rows** | No | CC BY 4.0 |
| 2 | **SLKB** SL calls per study × cell line | `https://slkb.osubmi.org/SLKB_predictions.xlsx` | `SLKB_predictions.xlsx` | 200 | 2,258,555 | (xlsx) sheet 1 `26864203_OVCAR8`, header `GEMINI-Score	HORLBECK-Score	MAGECK-Score	MEDIAN-B/NB Score	sgRNA-Derived B/NB Score	total_count	gene_pair` | 32 sheets named `PMID_CELLLINE`; 78,835 rows incl. 32 headers ⇒ **78,803 gene-pair rows** | No | GPL-3.0+ (figshare deposit) |
| 2b | SLKB full database (SQL dump) | `https://ndownloader.figshare.com/files/41055392` (article `https://figshare.com/articles/dataset/SLKB_-_Deposited_Data/22902839`) | `SQL_Dumps.zip` → `SLKB-sqlite3_dump.sql` + `schemas/` | 206 on a `-r 0-2047` range probe; `application/zip`, magic `PK\x03\x04` | 240,825,452 (figshare-reported; not fully downloaded) | binary zip | n/a | No | GPL-3.0+ |
| 3 | **DepMap-published biomarker / top-feature table** | `https://ndownloader.figshare.com/files/49052758` (article `https://figshare.com/articles/dataset/DepMap_Predictability_with_Subsampling/26955886`) | `predictions_with_1021_lines_summary.csv` | 200 | 7,654,522 | `gene,model,pearson,best,feature0,feature0_importance,feature1,feature1_importance,…,feature9,feature9_importance` | 17,109 lines = **17,108 data rows** | No | CC BY 4.0 |
| 3b | DepMap 24Q4 Public release file (proof the release route works without depmap.org) | `https://ndownloader.figshare.com/files/51064916` (article `https://plus.figshare.com/articles/dataset/DepMap_24Q4_Public/27993248`) | `CRISPRInferredCommonEssentials.csv` | 200 | 20,795 | `Essentials` | 1,524 lines = **1,523 genes** | No | CC BY 4.0 |
| 4 | **CORUM human core complexes**, release 5.3 (2026-04-14) | `https://mips.helmholtz-muenchen.de/fastapi-corum/public/file/download_current_file?file_id=human&file_format=txt` | served as `humanComplexes` txt | 200 | 6,268,940 (`text/plain`) | `complex_id	complex_name	synonyms	organism	cell_line	pmid	comment_complex	comment_members	comment_disease	comment_drug	comment_drug_formal	subunits_uniprot_id	subunits_gene_name	subunits_gene_name_synonyms	subunits_protein_name	…	fcgs_category_name` (28 cols) | 7,813 physical lines, but comment fields contain embedded newlines ⇒ **5,628 complexes** (lines with a numeric `complex_id`) | No | **CC BY-NC 4.0** — verbatim from the site bundle: "We have chosen to apply the Creative Commons Attribution (CC BY-NC 4.0) License to all copyrightable parts of…" |
| 4b | CORUM all-organism complexes | `https://mips.helmholtz-muenchen.de/fastapi-corum/public/file/download_current_file?file_id=complete&file_format=txt` | `allComplexes` txt | 200 | 8,893,038 | same header | 10,884 lines ⇒ **8,132 complexes** | No | CC BY-NC 4.0 |
| 5 | **Human paralog table** (Ensembl BioMart, protein-coding) | `https://www.ensembl.org/biomart/martservice` with the XML of §4.2 URL-encoded as `query=` (byte-identical from `https://useast.ensembl.org/biomart/martservice`) | streamed TSV | 200 | 16,022,513 (`text/plain`) | `Gene stable ID	Gene name	Human paralogue gene stable ID	Human paralogue associated gene name	Paralogue %id. target Human gene identical to query gene	Paralogue %id. query gene identical to target Human gene` | 264,052 lines = **264,051 directed paralog pairs**, all unique | No | Ensembl data: no restrictions / EMBL-EBI terms of use |
| 6 | **Reactome** pathway membership, all levels | `https://reactome.org/download/current/Ensembl2Reactome_All_Levels.txt` | `Ensembl2Reactome_All_Levels.txt` | 200 | 504,035,190 (`text/plain`) | **no header**; first line is data: `2RSSE.1b.1	R-CEL-162582	https://reactome.org/PathwayBrowser/#/R-CEL-162582	Signal Transduction	IEA	Caenorhabditis elegans` | **3,767,604 rows**, of which **1,126,408** are `Homo sapiens` | No | Open-access (CC0 per reactome.org licence page — licence page not itself re-fetched) |
| 6b | MSigDB C2:CP canonical pathways | `https://data.broadinstitute.org/gsea-msigdb/msigdb/release/2025.1.Hs/c2.cp.v2025.1.Hs.symbols.gmt` | `c2.cp.v2025.1.Hs.symbols.gmt` | 200 | 1,626,547 | `SA_B_CELL_RECEPTOR_COMPLEXES	https://www.gsea-msigdb.org/gsea/msigdb/human/geneset/SA_B_CELL_RECEPTOR_COMPLEXES	ATF2	BCR	BLNK	ELK1	FOS	GRB2	HRAS	JUN	LYN	MAP2K1	…` | **4,023 gene sets** (GMT, one set per line) | No on this `data.broadinstitute.org` path (the `gsea-msigdb.org/.../download_file.jsp` route *does* ask for registration) | CC BY 4.0 for MSigDB overall; sub-collections carry their source's terms |
| 6c | BioGRID multi-validated physical interactions | `https://downloads.thebiogrid.org/Download/BioGRID/Latest-Release/BIOGRID-MV-Physical-LATEST.tab3.zip` | zip → `BIOGRID-MV-Physical-5.0.261.tab3.txt` (261,191,696 B uncompressed) | 200 | 34,843,705 (`application/download`) | `#BioGRID Interaction ID	Entrez Gene Interactor A	Entrez Gene Interactor B	BioGRID ID Interactor A	BioGRID ID Interactor B	Systematic Name Interactor A	Systematic Name Interactor B	Official Symbol Interactor A	Official Symbol Interactor B	…` (37 cols) | 558,811 lines = **558,810 interactions** | No | MIT Licence (per BioGRID terms; terms page not re-fetched) |
| 6d | HuRI (Human Reference Interactome) | `http://www.interactome-atlas.org/data/HuRI.tsv` — **needs `curl -k` or plain HTTP**: the 301 to `https://www.interactome-atlas.org/…` fails TLS ("no alternative certificate subject name matches target host name") | `HuRI.tsv` | 200 (with `-k`) | 1,681,536 (`text/tab-separated-values`) | **no header**; first line is data: `ENSG00000000005	ENSG00000061656` | **52,548 interaction rows** (Ensembl gene-ID pairs) | No, but the broken certificate forces `-k`/http | CC BY 4.0 (terms page not re-fetched) |

### 4.2 Exact BioMart query for the paralog table (row 5)

URL-encode this as the `query` parameter:

```xml
<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE Query><Query virtualSchemaName="default" formatter="TSV" header="1" uniqueRows="1" count="" datasetConfigVersion="0.6"><Dataset name="hsapiens_gene_ensembl" interface="default"><Filter name="biotype" value="protein_coding"/><Filter name="with_hsapiens_paralog" excluded="0"/><Attribute name="ensembl_gene_id"/><Attribute name="external_gene_name"/><Attribute name="hsapiens_paralog_ensembl_gene"/><Attribute name="hsapiens_paralog_associated_gene_name"/><Attribute name="hsapiens_paralog_perc_id"/><Attribute name="hsapiens_paralog_perc_id_r1"/></Dataset></Query>
```

Invocation that returned the verified bytes:
`curl -sL -o out.tsv --get --data-urlencode "query=$Q" https://www.ensembl.org/biomart/martservice`.
For a **frozen** set, replace the host with a dated archive (De Kegel et al. 2021 used Ensembl 93 =
`http://jul2018.archive.ensembl.org`). Dropping the `biotype` filter runs but balloons past 180 MB, dominated by
Y_RNA/miRNA families — that request was deliberately aborted.

### 4.3 Corrections and dead routes (each one will otherwise cost a day)

* **The SynLethDB DOI in circulation is wrong.** `10.1093/nar/gkab1107` resolves (Crossref) to *"VFDB 2022: a
  general classification scheme for bacterial virulence factors"*. SynLethDB 2.0 is **Database (Oxford)
  2022;2022:baac030, DOI `10.1093/database/baac030`, PMID 35562840**; the original is **NAR 2016;44(D1):D1011,
  DOI `10.1093/nar/gkv1108`, PMID 26516187**.
* **SynLethDB has moved and is now v3.0.** `https://synlethdb.sist.shanghaitech.edu.cn/` 301s to
  `https://www.synlethdb.com/`, a Vue SPA whose HTML shell is 1,198 bytes — there is no file there. The real
  download table is hard-coded in the JS chunk
  `https://www.synlethdb.com/assets/DownloadPage-BSWs5n-U.js`, which points every file at **Zenodo record
  22843223** (concept DOI `10.5281/zenodo.22843222`). The v3.0 web-server paper is stated as "in preparation",
  so cite the 2.0 paper plus the Zenodo version DOI.
* **SLKB has no static SL-pair CSV.** `rawSL` (`SLKB_original_scores.csv`) and `calcSL`
  (`SLKB_calculated_scores.csv`) are R Shiny `downloadHandler` outputs generated per session
  (`session/<token>/download/…`), so they cannot be curl'd without driving the app. `predSL` is the one static
  asset under the app's `www/` and is fetchable (row 2). `https://slkb.osubmi.org/` itself returns 46 KB of
  Shiny HTML; guessed paths like `/SLKB.sql` return 404. For the whole database use the figshare SQL dump (row 2b).
  There is also **no** `SLKB` Bioconductor package — `https://bioconductor.org/packages/release/bioc/html/SLKB.html`
  is a 404.
* **depmap.org blocks automation.** `https://depmap.org/portal/api/download/files` returns HTTP 200 but with a
  5,175-byte HTML "DepMap — Verification" cookie/bot gate, as does
  `https://depmap.org/portal/data_page/?tab=allData`. Use the figshare mirrors above; they are login-free.
* **No `Predictability_*.csv` ships in any DepMap Public quarterly release.** Full figshare file manifests were
  enumerated for 24Q4 (73 files), 24Q2 (66), 23Q4 (56), 23Q2 (52), 22Q4 (47) and 22Q2 (42): **zero** filenames
  contain "predict", "biomarker", "feature" or "model_". The DepMap-published predictability tables live in
  *separate* figshare items — `DepMap Predictability with Subsampling` (26955886, row 3, whose
  `predictions_with_*_lines_summary.csv` files are exactly gene × model × Pearson × top-10 features with
  importances) and `Expression vs genomics for predicting dependencies` (25843450, CC BY 4.0, 47 files including
  `AchillesAllFeaturePredictions.hdf5`, `AchillesSummary.csv`, `AchillesFeatureDropScore.csv`, plus RNAi /
  PRISM / Project Score / GDSC17 equivalents). **This matters for §6.2 item 3: the "is it already in DepMap's own
  top features?" check must be run against figshare 26955886, not against anything in the 24Q4 release the plan
  already has on disk.**
* **CORUM's classic `coreComplexes.txt.zip` path is dead.**
  `https://mips.helmholtz-munich.de/corum/download/coreComplexes.txt.zip` and its `helmholtz-muenchen.de`
  equivalent both return HTTP 200 with the 423-byte SPA `index.html` — not a file. The working route is the
  FastAPI backend found in the site bundle: base `https://mips.helmholtz-muenchen.de/fastapi-corum`, with
  `GET /public/releases/current` → `{"version":"5.3","date":"2026-04-14","is_current":true}`,
  `GET /public/file/info` → the eight datasets (`complete`, `human`, `drugs`, `formal_drugs`, `splice`,
  `partial`, `fcg`, `uniprot`; txt/json/xml), and
  `GET /public/file/download_current_file?file_id=…&file_format=…` for the bytes. Archived releases are at
  `/public/releases/archived` + `/public/file/download_archived_file`. The OpenAPI spec
  (`/fastapi-corum/openapi.json`, 53,797 B) marks these `public` endpoints with an OAuth2 security scheme, yet
  they answer anonymously. The response is `text/plain` despite the `txt` "format" name — it is not zipped.
* `https://ftp.ensembl.org/pub/current_tsv/ensembl-compara/homologies/` → **404**; that path no longer exists, so
  Compara-file paralogs could not be verified. BioMart is the working route.
* **De Kegel's repository does not ship a paralog-pair table.** `cancergenetics/paralog_SL_prediction` (and the
  `DeKegel/` fork) contain only `local_data/feature_table.xlsx`, `feature_list.txt`, `validated_SLs.txt` and
  `RF_model.pickle`; the pair universe is regenerated from Ensembl 93 BioMart in
  `1_data_processing/02_process_ensembl_paralogs.ipynb`. `http://www.cancergd.org/static/paralogs/` is only a
  meta-refresh to `SHAP_charts.html`.
* **Bonus, metadata verified but not downloaded** (228–301 MB zips): *"A predicted cancer dependency map for
  paralog pairs"*, figshare 31058182, DOI `10.6084/m9.figshare.31058182.v3`, CC BY 4.0 — files
  `full_SLprediction_matrix.csv.zip` (301,001,525 B), `full_SLprediction_matrix_GIMAP.csv.zip` (228,818,438 B),
  `excluded_pairs.csv` (163,473 B); description states **33,419 paralog pairs**, from "Systematic prioritisation
  of context-specific paralog pair vulnerabilities in cancer", Daldal et al. 2026 (paper DOI not verified). If
  this is what it claims, it is a direct competitor for the paralog arm of the plan and must be read.

### 4.4 Citations for the reference sets (all DOI↔PMID pairs confirmed via Crossref / NCBI eutils)

| Resource | Paper | DOI | PMID |
|---|---|---|---|
| SynLethDB 2.0 | Wang J, Wu M, Huang X, et al. *Database (Oxford)* 2022;2022:baac030 | `10.1093/database/baac030` | 35562840 |
| SynLethDB (original) | Guo J, Liu H, Zheng J. *Nucleic Acids Res* 2016;44(D1):D1011 | `10.1093/nar/gkv1108` | 26516187 |
| SynLethDB 3.0 data | Feng Y, Zhang R, Zheng J. Zenodo 2026 | `10.5281/zenodo.22843222` (version `10.5281/zenodo.22843223`) | – |
| SLKB | Gökbağ B, Tang K, et al. *Nucleic Acids Res* 2024;52(D1):D1418 | `10.1093/nar/gkad806` | 37889037 |
| DepMap 24Q4 Public | figshare+ dataset | `10.25452/figshare.plus.27993248.v1` | – |
| DepMap Predictability with Subsampling | figshare dataset | `10.6084/m9.figshare.26955886.v1` | – |
| DepMap programme review | Boehm JS, et al. *Nat Rev Cancer* 2024 | `10.1038/s41568-024-00763-x` | 39468210 |
| Expression-vs-genomics predictability | Dempster JM, et al. preprint + data | `10.1101/2020.02.21.959627`; data `10.6084/m9.figshare.25843450.v1` | – |
| CORUM (current) | Tsitsiridis G, et al. *Nucleic Acids Res* 2025 | `10.1093/nar/gkae1033` | 39526397 |
| Paralog SL prediction / pair universe | De Kegel B, Quinn N, Thompson NA, Adams DJ, Ryan CJ. *Cell Syst* 2021;12(12):1144 | `10.1016/j.cels.2021.08.006` | 34529928 |
| Reactome | Milacic M, et al. *Nucleic Acids Res* 2024;52(D1):D672 | `10.1093/nar/gkad1025` | 37941124 |
| MSigDB | Liberzon A, et al. *Cell Syst* 2015;1(6):417 | `10.1016/j.cels.2015.12.004` | 26771021 |
| BioGRID | Oughtred R, et al. *Protein Sci* 2021;30(1):187 | `10.1002/pro.3978` | 33070389 |
| HuRI | Luck K, et al. *Nature* 2020;580:402 | `10.1038/s41586-020-2188-x` | 32296183 |

### 4.5 Recommended freeze set

Four targets, all login-free with stable versioned identifiers:

1. **SynLethDB 3.0** `Human.SL.detailed.tsv` + `Human.non.SL.detailed.tsv`, pinned to Zenodo version DOI
   `10.5281/zenodo.22843223` — gives positives *and* negatives with cell line, PMID and assay provenance, so a
   confirmed pair can be annotated "known, and known from which assay in which line".
2. **CORUM 5.3 human complexes**, pinned by `/public/releases/current` = `5.3 / 2026-04-14`. **Caveat: CC BY-NC
   4.0**, which matters if any downstream artefact is commercial.
3. **The BioMart paralog TSV**, pinned to a dated `*.archive.ensembl.org` host rather than `www`. `www` is a
   moving release and was briefly serving a 503 "Service unavailable" page **with HTTP 200** during this
   session — so the pipeline must sniff the first line, not just the status code.
4. **`predictions_with_1021_lines_summary.csv`** from figshare 26955886 as the DepMap biomarker/top-feature
   baseline, since no DepMap Public quarterly release ships a Predictability file.

All four must be downloaded, hashed and committed **before** unsealing the KY holdout, with the hashes recorded
alongside `data/split.receipt.json` (§6.2 item 6).


---

## 5. Known statistical traps a reviewer will raise — with the published mechanism

### 5.1 Lineage / tissue-of-origin confounding

Every published version of this analysis either stratifies by tissue or tests lineage as a feature, because
lineage dominates the dependency signal. Dempster 2019 (PMC6925302) includes *tissue of origin* as one of the
tested features and reports lineage associations as top hits:

> "Examples of expected associations included increased dependency on ERBB2 in ERBB2-amplified cell lines,
> increased dependency on beta-catenin in APC mutant cell lines and increased dependency on MYCN in peripheral
> nervous system cell lines."

Pacini 2021 (PMC7955067) stratifies *within* lineage rather than adjusting:

> "We investigated each of the integrated datasets' ability to reveal tissue-specific biomarkers of
> dependencies." … "For each CFE and tissue type, we performed a Student's t-test for each selective gene
> dependency (SGD, Methods) contrasting two groups of cell lines based on the status of CFE under consideration
> (present/absent)"

> "Many dependencies are context specific, reducing cellular fitness in a subset of lineages, that can be used
> to elucidate gene function and identify cancer type-specific vulnerabilities."

Gong 2025 (`10.1101/2025.02.07.637152`) shows how much of the "context-specific dependency" signal is simply
lineage:

> "Selective dependencies were enriched for protein kinases, but most strongly by lineage defining gene sets
> including specific terms for mesenchymal, digestive tract, gland, and lymphoid differentiation and
> development"

> "Many TF dependencies are lineage-specific and strongly correlated with the expression of the oncogenic TF
> itself."

**Mechanism.** Almost every genomic context feature is itself lineage-enriched (APC/MSI in bowel, TP53 almost
everywhere, VHL in kidney, SMARCB1 in rhabdoid, EWSR1 fusions in bone). Any test that pools lineages recovers
"lineage → lineage-specific dependency" and mislabels it as "mutation → dependency".
**What the plan must survive:** within-lineage centering of both sides removes the *mean* lineage offset but not
(a) lineage-specific *variance* differences, (b) features that are perfectly nested within one lineage (which
become untestable after centering and must be dropped, not silently kept), or (c) residual confounding by
sub-lineage (e.g. MSI vs MSS colorectal, PAM50 subtype within breast — Pacini 2021 explicitly notes subtypes:
"clinical subtypes such as PAM50 classifications are available for the breast cancer cell lines"). Pre-register
a minimum number of feature-positive and feature-negative lines *per lineage* and report the per-lineage
contribution of every confirmed pair.

### 5.2 Copy-number and proximity bias in CRISPR screens

Vinceti A, Iannuzzi RM, Boyle I, Trastulla L, Campbell CD, Vazquez F, Dempster JM, Iorio F. Genome Biology
25:192 (2024), DOI `10.1186/s13059-024-03336-1`, PMC11264729.

CN-amplification mechanism, verbatim:

> "The activity of Cas9 is influenced by structural features of the target site, including copy number
> amplifications (CN bias)."

> "A Copy number amplification bias in CRISPR screening data: when the Cas9 enzyme targets a copy number
> amplified gene it induces multiple double-strand breaks (DSBs) resulting in a high cytotoxic effect
> independent of the gene's function or expression."

> "In a typical (uncorrected) CRISPR-Cas9 screen, CN amplifications generate gene-independent detrimental
> effects on cellular fitness, leading to highly CN-amplified genes being detected as strongly essential,
> regardless of their function or expression"

Proximity-bias mechanism, verbatim:

> "More worryingly, proximal targeted loci tend to generate similar gene-independent responses to CRISPR-Cas9
> targeting (proximity bias), possibly due to Cas9-induced whole chromosome-arm truncations or other genomic
> structural features and different chromatin accessibility levels."

> "These truncations are responsible for the deletion of entire chromosomal regions that contain multiple genes,
> resulting in a mixed viability reduction profile given by the sum of the individual gene death phenotypes."

> "E Proximity bias in CRISPR screening data: when a functional p53 or other DNA-repairing factors are present,
> DSBs cause cell cycle arrest (until the genetic damage is fixed) or apoptosis." … "However, in the absence or
> reduced levels of functional p53, a DSB may not be repaired before mitosis."

Quantified in both target datasets:

> "As expected, we observed probability values larger than 0.5, indicative of larger intra-arm similarity over
> inter-arm ones, thus the presence of a proximity bias, in Project Achilles and Project Score datasets
> (unprocessed versions) both (average BMP across chromosome arms = 0.628 and 0.646, respectively for Project
> Achilles and Project Score, Fig. 2)."

**The Chronos-specific warning that applies directly to `ScreenGeneEffect.csv`:**

> "We observed very mild, not significant reductions for the other methods and a significant increase of the
> proximity bias consistently across both Project Achilles or Project Score when processing them with Chronos
> only (average BMP across chromosome arms = 0.716 and 0.726, with t-test p = 5.59 × 10−11 and 2.1 × 10−5,
> respectively"

**And the TP53-dependent residual, which is a mutation-context confounder by construction:**

> "Consistently, we observed an increased intra-arm similarity in screening data derived from cell lines with
> loss-of-function TP53 mutations compared to TP53 wild-type ones, when considering the uncorrected version of
> each dataset as well as post-processing them with each tested method (Fig. 2d)."

> "Notably, we observed a larger residual difference in the proximity bias between TP53 mutant and TP53
> wild-type cell lines in the Chronos, Crispy, and GAM post-corrected version of Project Achilles and Project
> Score (AR = 1.029, 1.053, 1.051 respectively, for Project Achilles and 1.043, 1.062, 1.056 respectively, for
> Project Score)."

> "TP53 expression has been suggested to reduce chromosomal loss in CRISPR-Cas9 editing [52–54] due to its
> involvement in the DNA repair mechanism."

The mitigation the 24Q4 release applies (and which the plan inherits) is AC-Chronos arm alignment:

> "Arm-corrected Chronos — To correct the proximity bias post-Chronos processing, the median gene effect of each
> chromosome arm is aligned to be the same across all screens."

> "AC-Chronos outperforms other methods in correcting both CN and proximity biases when jointly processing
> multiple screens of models with available CN information"

Primary source for proximity bias: Lazar NH, Celik S, Chen L, Fay MM, Irish JC, Jensen J, et al.
*"High-resolution genome-wide mapping of chromosome-arm-scale truncations induced by CRISPR-Cas9 editing."*
Nature Genetics 56:1482–1493 (2024), DOI `10.1038/s41588-024-01758-y`, PMID 38811841, PMC11250378.

> "Here we performed a phenotypic CRISPR–Cas9 scan targeting 17,065 genes in primary human cells, revealing a
> 'proximity bias' in which CRISPR knockouts show unexpected similarities to unrelated genes on the same
> chromosome arm."

> "Multiple lines of evidence suggest that this proximity bias is caused by telomeric truncations of chromosome
> arms and is consistent across cell types, labs and Cas9 delivery methods."

> "Additionally, we reanalyzed the Cancer Dependency Map (DepMap) genome-wide CRISPR–Cas9 screens in cancer cell
> lines to confirm the impact of proximity bias on target discovery, propose potential mediators and show that
> this effect persists even when controlling for cell-line specific CNVs."

> "Proximity bias confounds therapeutic target identification"

> "Visual examination and quantification of the DepMap CRISPR map confirms the presence of arm-scale proximity
> bias (Fig. 3b,c), and the proximity bias effect is maintained in a newer version of these data (22Q4), which
> controls for CNVs."

> "Also, patterns of proximity bias reflect differences between reference genomes and true chromosomal
> structure, including large-scale structural variants."

**Why this bites this specific design.** Two of the planned context features are copy-number/structural:
"deep copy-number deletion" and "WGD/aneuploidy". A deep deletion of gene A is an arm-scale event in most cases;
if gene B is on the same arm, an apparent "deletion of A → altered dependency on B" is a proximity artefact, not
a genetic interaction. **Mandatory guard:** annotate every pair with same-chromosome / same-chromosome-arm status
and genomic distance, report the confirmed-pair rate separately for same-arm and different-arm pairs, and
pre-register exclusion (or separate reporting) of same-arm pairs. Aneuploidy/WGD as a feature is even worse: it
is a genome-wide structural covariate that modulates the bias itself.

### 5.3 Screen quality, Cas9 activity and growth-rate confounding

Dempster JM, Rossen J, Kazachkova M, Pan JH, Kugener G, Root DE, Tsherniak A. *"Chronos: a cell population
dynamics model of CRISPR experiments that improves inference of gene fitness effects."* Genome Biology 22:343
(2021), DOI `10.1186/s13059-021-02540-7`, PMID 34930405, PMC8686573.

> "CRISPR loss of function screens are powerful tools to interrogate biology but exhibit a number of biases and
> artifacts that can confound the results."

> "For analyses that compare gene essentiality estimates across screens, variation in screen quality can lead to
> significant biases [4, 18, 19]."

> "Additionally, we have observed in Project Achilles that screen quality (determined by separation of positive
> and negative control gene fitness effects) varies substantially across cell lines, due to variable Cas9
> activity or other factors [4]."

> "Chronos addresses sgRNA efficacy, variable screen quality and cell growth rate, and heterogeneous DNA cutting
> outcomes through a mechanistic model of the experiment."

> "For Chronos, we define gene fitness effect as the fractional change in growth rate rcg = Rcg∗/Rc − 1."

> "Additionally, CRISPR screens are confounded by incomplete penetrance of the gene knockout phenotype."

**Mechanism.** Because the Chronos gene effect is a *fractional* change in growth rate, screens of slow-growing
lines have less dynamic range and noisier estimates; and Cas9 activity varies by line. Any context feature
correlated with proliferation rate (TP53 status, CDKN2A deletion, MYC amplification, WGD) will therefore
correlate with the *magnitude* of gene effects genome-wide, producing an apparent context-specific dependency
for hundreds of genes simultaneously. **Mandatory guards:** (a) join `CRISPRInferredModelGrowthRate.csv` and
`CRISPRInferredModelEfficacy.csv` (both in the 24Q4 release) and show that confirmed associations are not
explained by them; (b) report, for each context feature, whether the feature-positive group has a different
mean *genome-wide* gene effect (a simple immediate red flag); (c) use `AchillesScreenQCReport.csv` /
`ScreenSequenceMap.csv` to exclude low-quality screens before, not after, looking at results.

Library representation is an additional, and possibly *dominant*, screen-level covariate. Metz P,
Alves-Vasconcelos S, Wallbank R, Riepsaame J, Brown S, Hassan AB. *"Variation in guide RNA library
representation results in gene effect score bias in genome-wide CRISPR screens."* BMC Genomics (2026), DOI
`10.1186/s12864-026-12658-2`, PMC13023172.

> "We demonstrate that the choice of CRISPR library is often the most significant factor that influences genetic
> perturbation results, outweighing other variables such as either target cell lines or culture media
> conditions."

> "A potential contributor to this effect is gRNA representation within a given CRISPR library, where lower gRNA
> representation can lead to variable and more pronounced gene effect scores using either log fold change or
> Chronos analysis."

> "CRISPR library gRNA representation dependent bias remains a major challenge in the interpretation of gene
> essentiality in perturbation screens."

**Double-edged for this design.** If library is the largest single variance component, then (i) an AV→KY
replication is a genuinely stringent specificity filter — this is the design's real strength; but (ii) the
false-negative rate will be high, so a low confirmation count is *expected* and must not be reported as
"associations are mostly artefacts". Pre-register an explicit power/sensitivity analysis: for a known-true
positive-control set (e.g. Dempster 2019's 55 cross-replicated CFE associations, ERBB2-amp→ERBB2,
APC-mut→CTNNB1, MSI→WRN, ARID1A-mut→ARID1B, TP53-mut→MDM2/MDM4/PPM1D), what fraction does the KY cohort
recover at the chosen threshold? That number is the ceiling on the study's sensitivity and must be reported
*before* the novel-pair count.

### 5.4 Multi-target guides, mismatch tolerance, seed effects, and variants in the protospacer

Fortin J-P, Tan J, Gascoigne KE, Haverty PM, Forrest WF, Costa MR, Martin SE. *"Multiple-gene targeting and
mismatch tolerance can confound analysis of genome-wide pooled CRISPR screens."* Genome Biology 20:21 (2019),
DOI `10.1186/s13059-019-1621-7`, PMID 30683138, PMC6346559. **This paper is specifically about the Avana
library** — i.e. exactly the discovery half of the planned split.

> "In this work, we analyze CRISPR essentiality screen data from 391 cancer cell lines to characterize biases
> induced by multi-target sgRNAs."

> "We find that the number of on-targets and off-targets both increase sgRNA activity in a cell line-specific
> manner and that existing additive models of gene knockout effects fail at capturing genetic interactions that
> may occur between co-targeted genes."

> "In the Avana library, a number of sgRNAs are annotated to target multiple genes through perfect sequence
> complementarity between the sgRNA's spacer sequence and genomic DNA—we refer to such guides as 'multi-target'
> guides." … "68,742 guides align uniquely to one target only, and 3959 guides align to more than one target
> (multi-target guides), resulting in 2023 genes that are targeted by at least one multi-target guide."

> "This significant enrichment for paralog genes (exact binomial test, p < 2.2×10−16) confirms that co-targeted
> genes often share high homology."

> "We further show that single-mismatch tolerant sgRNAs can confound the analysis of gene essentiality and lead
> to incorrect co-essentiality functional networks."

> "We also show that off-target effects caused by single-mismatch sgRNA-DNA alignments can cause spurious
> associations between cell lineage and gene knockout."

Seed-region mechanism, verbatim:

> "The effect of a single mismatch is more pronounced for mismatches far away from the PAM site (PAM-distal
> region) as opposed to PAM-proximal nucleotides, sometimes referred to as the seed region."

> "In addition, among those 224 guides, 77 guides (34%) have their on-target and off-target genes annotated as
> paralogs in the PANTHER database."

**The trap that is lethal for a mutation → dependency screen** — genotype in the protospacer changes cutting
efficiency, so a mutation *is* an assay covariate:

> "Genetic variation, such a single nucleotide polymophisms (SNPs) and small indels, can have a profound effect
> on sgRNA specificity and on-target efficiency [20–23]."

> "In addition, canonical NGG PAM sites can be either destroyed or created through SNP variation."

> "We found that 473 guides are targeting a protospacer sequence containing a SNP targeted by the array."

> "A large proportion of SNP-guide pairs has a genotype-LFC positive correlation greater than by chance (262
> pairs, 56%), confirming the hypothesis that an alternative allele within the protospacer region results in a
> decrease of cleavage efficiency as observed by a less negative log-fold change."

> "The genotype-LFC correlations are significantly higher for SNPs located in the PAM-proximal region of the
> protospacer in comparison to SNPs located in the PAM-distal region (Wilcoxon rank sum test, p=2.54×10−6)."

> "Overall, this shows how the presence of a common SNP within the protospacer region can alter guide activity
> and result in spurious log-fold changes for a subset of cell lines."

**Mandatory guard (and it is cheap):** DepMap 24Q4 ships `OmicsGuideMutationsBinaryAvana.csv` and
`OmicsGuideMutationsBinaryKY.csv` — "Binary matrix indicating whether there are mutations in guide locations
from the Avana library" (README). Flag, per screen, any dependency gene whose guides overlap a mutation in that
model, and exclude or separately report those observations. Also join `AvanaGuideMap.csv` / `KYGuideMap.csv` to
flag multi-target guides and paralog co-targeting, and `CRISPRInferredGuideEfficacy.csv`. Note that this trap is
*library-specific*, so it is one of the artefact classes the KY holdout genuinely filters — but only if you do
not pre-filter it away inconsistently between the two halves.

### 5.5 Mutation calls are correlated with mutational burden, MSI and ploidy

**Mechanism (mechanical, not subtle).** `OmicsSomaticMutationsMatrixDamaging.csv` is a per-gene
"has ≥1 LikelyLoF variant" indicator. The probability that any given gene carries such a variant scales with the
model's total mutation count. Therefore:

1. Every "damaging mutation in gene A" feature is positively correlated with TMB, and with each other. A
   hypermutator (MSI, POLE, MMR-deficient) is feature-positive for thousands of genes at once.
2. Because the planned study *also* tests MSI as a feature, the mutation features and the MSI feature are not
   independent tests — the multiple-testing correction is anti-conservative if computed as if they were, and the
   permutation null must permute *models*, not feature labels within a gene, to preserve the burden structure.
3. Any genome-wide shift in gene effect that tracks TMB (through proliferation, aneuploidy, p53 status, or the
   proximity-bias mediator of §5.2) will generate thousands of apparent "damaging mutation → dependency"
   associations with the same sign.

Published anchor for the burden/MSI coupling: Campbell BB, Light N, Fabrizio D, Zatzman M, Fuligni F, de Borja R,
et al. *"Comprehensive Analysis of Hypermutation in Human Cancer."* Cell 171:1042–1056.e10 (2017), DOI
`10.1016/j.cell.2017.09.048`, PMID 29056344, PMC5849393. Verbatim (abstract):

> "We present an extensive assessment of mutation burden through sequencing analysis of >81,000 tumors from
> pediatric and adult patients, including tumors with hypermutation caused by chemotherapy, carcinogens, or
> germline alterations." … "Replication repair deficiency was a major contributing factor. We uncovered new
> driver mutations in the replication-repair-associated DNA polymerases and a distinct impact of microsatellite
> instability and replication repair deficiency on the scale of mutation load."

i.e. MSI status and mutation load are not separable covariates: the planned MSI feature and the planned
damaging-mutation features are measuring overlapping things.

**Mandatory guards:** (a) regress out (or stratify on) log10 total mutation count / TMB on the feature side;
(b) drop genes whose damaging-mutation frequency is explained by gene length × TMB (a length-and-burden null);
(c) restrict damaging-mutation features to genes with a plausible LoF interpretation (e.g. tumour suppressors,
OncoKB-annotated) as a pre-registered primary analysis, with the unrestricted genome-wide version as secondary;
(d) permute at the model level within lineage.

### 5.6 Trivial / already-explained association classes that will dominate the top of the list

These are not artefacts of your pipeline; they are known biology that will swamp the ranking, and each already
has a name in the literature. Krill-Burger 2023 (PMC10464129):

> "Several types of relationships between genetic dependencies and predictive features ('biomarker classes')
> have been commonly observed, including genetic driver, expression addiction, paralog, and CYCLOPS."

- **Self-expression / expression addiction.** "very low expression of gene A" → "no dependency on gene A" is
  definitional: DepMap's own dependency-probability model uses unexpressed genes as the null distribution
  (README: "The null distribution is determined from unexpressed gene scores in those cell lines that have
  expression data available"), and Gong 2025 states "unexpressed genes commonly have Chronos score equal to 0."
  Self-pairs (A==B) and expression-of-A → dependency-on-A must be excluded a priori, not discovered.
- **Deep deletion of gene A → loss of dependency on gene A.** If the gene is absent there is nothing to cut;
  this is a measurement tautology plus CN bias, not a genetic interaction.
- **CYCLOPS.** Krill-Burger 2023: "CYCLOPS genes have a positive correlation (r > 0.5) between RNAi gene effects
  and copy number"; "a greater number of models were classified as CYCLOPS models (stronger dependency
  associated with lower copy number of the target gene)". Partial CN loss of A → dependency on A is a known
  class.
- **Paralog buffering.** Krill-Burger 2023: "CRISPR knockout of RAB6A has a more negative viability effect on
  cells lacking expression of paralog gene RAB6B (Wilcoxon p-value: CRISPR = 6.2 × 10−24, RNAi = 6.1 × 10−7)";
  "RNAi gene effect of RBBP4 is more correlated with expression of paralog gene RBBP7." Dempster 2019: "ATP6V0E1
  showed significant dependency when its paralog ATP6V0E2 had a low expression". Low expression of A →
  dependency on paralog B is the single most common "novel-looking" class and is systematically catalogued by
  De Kegel et al. 2021 (`10.1016/j.cels.2021.08.006`), who analysed "genome-wide CRISPR screens and molecular
  profiles of over 700 cancer cell lines" for exactly this.
- **Known driver/oncogene addiction.** Gong 2025: "Highly predictive hotspot mutations were saturated with
  oncogenes (BRAF, HRAS, NRAS, KRAS)"; "Within damaging mutations, TP53 mutation strongly predicted MDM2, MDM4,
  and PPM1D dependency, and ARID1A mutation strongly predicted ARID1B dependency."
- **Same-complex / same-pathway co-dependency.** Pacini 2021 used exactly these three annotations as a
  known-relationship benchmark: "We assembled a set of functionally related gene pairs using paralogs identified
  by EnsemblCompara, protein-protein interactions identified by Li et al., and CORUM complex comemberships."

### 5.7 Selection-then-confirmation statistics

- **Winner's curse / regression to the mean.** Effect sizes for top-ranked discovery pairs are upward-biased;
  the confirmation cohort will show systematically smaller effects even for true positives. Pre-register that
  the holdout estimates the effect size and the discovery only ranks.
- **Scale non-comparability across libraries.** `ScreenGeneEffect` is scaled per library run ("scale such that
  median of common essentials is at -1.0 and median of nonessentials is at 0"), so an absolute gene-effect
  difference threshold is not automatically transferable from AV to KY. Either use a standardised effect size
  (Cohen's d, as Dempster and Pacini both do with ΔFC) or re-derive the threshold within KY.
- **Gene coverage differs between libraries.** Avana and KY target overlapping but non-identical gene sets
  (KY: "90,709 sgRNAs targeting 18,009 genes (~5 sgRNAs/gene)", Sanger DepMap documentation). Pairs where either
  gene is untested in KY must be declared unconfirmable in advance, not counted as failures.
- **The 119 KY-only models are not a random sample.** They are the Sanger-specific panel; their lineage
  composition, MSI/WGD prevalence and per-lineage counts must be tabulated *before* unsealing, and features that
  are absent or near-monomorphic in them declared out of scope.

---

---

## Appendix A. Access and reproducibility notes for this survey

- Full texts were retrieved as Europe PMC full-text XML (`https://www.ebi.ac.uk/europepmc/webservices/rest/<PMCID>/fullTextXML`)
  for PMC6925302, PMC7955067, PMC11264729, PMC11250378, PMC8686573, PMC10464129, PMC6346559, PMC9751287,
  PMC7217969, PMC13023172, PMC5849393 (abstract). All quotations above come from those documents or from the
  cited web page / README.
- **Could not access full text:** Pacini et al. 2024 Cancer Cell (`10.1016/j.ccell.2023.12.016`) — cell.com and
  sciencedirect return HTTP 403 to automated requests; hybrid OA with no repository copy
  (OpenAlex `any_repository_has_fulltext: false`). Behan et al. 2019 Nature
  (`10.1038/s41586-019-1103-9`) — paywalled; the Unpaywall repository link (hdl.handle.net/2318/1714058)
  returned HTML, not a PDF. For both, only the Europe PMC abstract plus portal documentation was used, and this
  is flagged at each quotation. **If exact Methods wording from Pacini 2024 matters for the registration
  (specifically its ANOVA/effect-size thresholds), obtain the PDF manually.**
- Lord & Ashworth's own reviews were not retrievable in full text via this route (Science
  `10.1126/science.aam7344` PMC6175050 returned no full-text XML; Annu Rev Med `10.1146/annurev-med-050913-022545`
  has no PMC record). The reproducibility argument is therefore anchored on Ku et al. 2020, which is open access
  and states the point more quantitatively.
- Additional full texts read for §§1.7–1.10, 2.4, 3.5 and 3.6: PMC13281939 (DepMine), PMC8401190 (PARIS),
  PMC9216587 (SynLethDB 2.0), PMC10767912 (SLKB), PMC9825567 (PICKLES v3), PMC8378822 (DeepDEP), PMC7778984
  (Project Score database), PMC7569414 (CEN-tools), PMC8265155 (SynLeGG), PMC12724301 (Chiu 2025 breast DMA),
  PMC5667678 (Tsherniak 2017) and PMC6175050 (Lord & Ashworth Science 2017). Two of these — PMC5667678 and
  PMC6175050 — return HTTP 500 from Europe PMC's `fullTextXML` endpoint and were obtained instead via NCBI
  `efetch?db=pmc`. Publisher sites (cell.com, sciencedirect, nature.com) and `pmc.ncbi.nlm.nih.gov` block
  automated requests with 403 / redirect-to-IdP / reCAPTCHA, so **Europe PMC REST plus NCBI `efetch` is the only
  reliable retrieval path from this machine** and should be used for any follow-up reading.
- Papers deliberately left at abstract-or-metadata level, each labelled as such at the point of use, so no body
  text is quoted that was not read: Behan 2019, Pacini 2024, Ryan 2018 (Trends Cancer, PMID 30292351), Ryan 2023
  (Nat Genet, PMID 38036785), Ashworth & Lord 2018 (PMID 29955114), Lord/Tutt/Ashworth 2026 Nature (PMID
  42092061, no abstract available anywhere), Gonçalves/Ryan/Adams 2025 Nat Rev Drug Discov.
- Three citation errors were found and corrected, two of them in the planning brief itself
  (see §1.7 and §4.3): (a) bioRxiv 2025.04.07.647559 / Bioinformatics `btag337` is **DepMine**, which does not
  use Boruta — the Boruta pipeline is **PARIS**, `10.1186/s12943-021-01405-8`; (b) `btaf337` is a different paper
  (DicePlot, PMID 40574664) — the digits are not interchangeable; (c) `10.1093/nar/gkab1107` is *not* SynLethDB
  2.0, it is VFDB 2022 — SynLethDB 2.0 is `10.1093/database/baac030`.
- Note the author-name discrepancy: the DepMap 24Q4 README cites the bias-correction benchmark as
  "Venceti et al. 2024"; the paper's author is **Vinceti** A. Cite the DOI `10.1186/s13059-024-03336-1`.
- Every URL in §4 was fetched on 2026-09-25 from this machine with `curl -sL`, no login and no browser; HTTP
  status, byte count and verbatim first line in that table are observed values. Two download traps are recorded
  there because they return misleading success codes: `www.ensembl.org/biomart` served a 503 "Service
  unavailable" page **with HTTP 200**, and CORUM's legacy `coreComplexes.txt.zip` path returns HTTP 200 carrying
  a 423-byte SPA `index.html`. Any freeze script must validate the first line, not the status code.
- **Not done in this survey, and required before the novelty claim is written down:** a targeted search of OSF and
  AsPredicted for an existing pre-registered DepMap dependency-association plan. Neither registry is indexed by
  Europe PMC or Crossref, so §2.4's zero-hit result covers the literature only (§2.4 caveat (a)).

---

## 6. Verdict

### 6.1 Classification: **PARTIALLY_KNOWN**

Split the claim in two, because the two halves get different verdicts.

**The discovery space is KNOWN — decisively so.**
Genome-wide association of mutation / copy-number / expression / MSI context features against Chronos gene
effects in DepMap is not merely done, it is *published as a standing product*. DepMap's own Predictability
pipeline fits, for every one of ~17,100 genes, a random forest against "mRNA expression, damaging mutations,
driver mutations, hotspot mutations, lineage annotation, fusion, copy number, and confounder experimental
covariates" (Gong 2025, `10.1101/2025.02.07.637152`; method: Dempster et al. `10.1101/2020.02.21.959627`; code
`broadinstitute/cds-ensemble`), and a frozen genome-wide output table is downloadable under CC BY 4.0
(figshare `10.6084/m9.figshare.26955886`). Dempster 2019 (`10.1038/s41467-019-13805-y`) already ran the
t-test version on both institutes' data (29,350 genomic and 97,363 expression tests). Pacini 2021
(`10.1038/s41467-021-21898-7`) ran 2,142,162 tissue-stratified biomarker/dependency tests. Pacini 2024
(`10.1016/j.ccell.2023.12.016`) built the 930-model clinically-informed version and shipped 370 priority
targets. Gong 2025 ran the pan-cancer version with exactly the planned feature classes. If the deliverable is
"a list of context-specific dependencies from DepMap", it is a reimplementation.

Three further findings close off the escape routes a plan like this usually takes:
* **"All genes rather than only selective genes" is not a novelty.** DepMine (Pearl & Pearl,
  `10.1093/bioinformatics/btag337`, §1.7) already ran an all-by-all sweep over 16,825 genes with LoF and
  copy-number-deletion contexts and published 34,256 pairs. Its weakness is statistical (no FDR, no holdout),
  not one of scope — so the plan's advantage over it is rigour, and rigour alone.
* **"These particular context features" is not a novelty.** CEN-tools (`10.15252/msb.20209698`, §1.9) already
  serves tissue, mutation (including a 75-gene hotspot list), expression-level and MSI contexts across *both*
  Broad DepMap and Sanger Project Score. Its gap is also statistical: no FDR correction anywhere.
* **Two of the plan's flagship context features already have a published dependency result.** MSI→WRN was
  discovered in KY (Behan 2019) and 9p21.3 deletion / MSI-H→PELO was published in Nature in 2025
  (`10.1038/s41586-024-08509-3`, PMC11864980). Both are positive controls for this design, not findings.

**The validation design is NOVEL — and it is the only thing that is.**
No paper found in this survey uses the Avana/KY library boundary as a *pre-registered, sealed discovery →
confirmation split*. The literature uses that boundary in exactly three ways:
(i) **concordance on the shared lines** — Dempster 2019, "147 cell lines and 16,733 genes screened
independently by both institutes", with the replication test run on those same shared lines;
(ii) **batch-effect estimation and merging** — Pacini 2021, "the ComBat estimates … based on the analysis of 168
cell lines common to both initial datasets were computed. The ComBat correction using these estimates was then
applied to all screens, i.e., the union of the two initial datasets"; Pacini 2024 and the DepMap Broad–Sanger
page likewise pool into "over 900 cell lines";
(iii) **parallel bias-correction benchmarking** — Vinceti 2024, which corrects and evaluates Project Achilles
and Project Score side by side.
Nobody has held KY out. Nobody has used the 119 KY-only models to make the confirmation cohort disjoint in
*both* reagent and biological sample. Searches for pre-registration in this literature returned nothing.

So: the biology is KNOWN; the epistemics are NOVEL. That is a publishable contribution — as a
**reproducibility/benchmark paper**, not as a discovery paper — provided the requirements in §6.2 are met.

### 6.2 What specifically must be added to make the result publishable as new

Blunt list, in order of how badly a reviewer will hurt you without it.

1. **A sensitivity floor from positive controls, computed in KY before any novel claim.**
   Without this, "X of K discovery pairs confirmed" is an uninterpretable number. Pre-specify a positive-control
   set — ERBB2-amp→ERBB2, APC-mut→CTNNB1, MSI→WRN (note: *discovered in KY*, Behan 2019, so it is a control and
   must be declared as such), TP53-mut→MDM2/MDM4/PPM1D, ARID1A-mut→ARID1B, STAG2-mut→STAG1, and the 55
   cross-replicated CFE associations of Dempster 2019 — and report what fraction the 315 KY screens / 119
   KY-only models recover at your threshold. Report the minimum detectable standardised effect at n=119.
   Metz 2026 (`10.1186/s12864-026-12658-2`) makes this non-negotiable: "the choice of CRISPR library is often the
   most significant factor that influences genetic perturbation results, outweighing other variables such as
   either target cell lines or culture media conditions." Your holdout is a *hard* test; quantify how hard.

2. **Bias stratification, pre-registered, with results reported whether or not they are flattering.**
   - Same-chromosome and same-chromosome-arm annotation on every pair, with confirmed-pair rates reported
     separately (Lazar 2024 `10.1038/s41588-024-01758-y`: proximity bias "persists even when controlling for
     cell-line specific CNVs"; Vinceti 2024: Chronos-only processing *increases* arm-level bias, BMP 0.716/0.726).
   - Guide-overlapping-mutation exclusion using `OmicsGuideMutationsBinaryAvana.csv` / `…KY.csv`
     (Fortin 2019 `10.1186/s13059-019-1621-7`: 56% of SNP-in-protospacer guide pairs show genotype-correlated
     log-fold change).
   - Multi-target / paralog co-targeting guide flags from `AvanaGuideMap.csv` / `KYGuideMap.csv`.
   - TMB adjustment or stratification on the feature side (Campbell 2017 `10.1016/j.cell.2017.09.048`).
   - Screen-quality and growth-rate covariates (`AchillesScreenQCReport.csv`,
     `CRISPRInferredModelGrowthRate.csv`, `CRISPRInferredModelEfficacy.csv`), plus the simple
     genome-wide-mean-shift check per feature.
   - A same-arm-only and a shuffled-arm permutation placebo, in addition to the label permutation.

3. **A frozen, versioned, timestamped "already known" reference set, fixed before unsealing** — paralogs,
   complexes, pathways, SL databases, *and* the DepMap Predictability table (§4). "Novel" must mean "not in
   DepMap's own top-10 features for that gene either", otherwise the first reviewer will paste your top hit into
   depmap.org and find it on the Predictability tab. Pacini 2021 already used exactly the paralog/PPI/CORUM
   triple as the known-relationship benchmark, so this is the expected standard.

4. **At least one orthogonal axis of evidence for the headline novel pair(s).** Confirmation in a second
   *library* is not the same as confirmation by a second *modality*. Options available without new experiments:
   the Humagne-CD screens in the same release (`ScreenGeneEffect.CD.csv`, n=40 — small, but a *different
   nuclease*, Cas12a rather than Cas9, per the 24Q4 README, so it is modality-independent in a way KY is not), DEMETER2 RNAi gene effects (Krill-Burger 2023 `10.1186/s13059-023-03020-w` shows RNAi recovers
   paralog buffering that CRISPR saturates), PRISM/GDSC drug sensitivity, or CRISPR combinatorial paralog screens.
   Without this, the paper is a reanalysis; with it, it is a discovery with a clean replication.

5. **A pathway-level secondary endpoint, pre-registered.** Ku 2020 (`10.1038/s41467-020-16078-y`): "We provide
   evidence for why most reported synthetic lethals are not reproducible"; "published synthetic lethal screen hits
   significantly overlap at the pathway rather than gene level"; "the gene level overlap between these two studies
   was not significant (p = 0.17)". If gene-level confirmation is near zero — a realistic outcome — a
   pre-registered pathway-level endpoint is what keeps the study interpretable rather than null-and-void.

6. **Publish the seal, not just the claim.** The design's entire value is that the holdout was untouched. Deposit
   the registration with a timestamp, the SHA-256 of the sealed KY file, the discovery-only code, and the frozen
   reference sets, *before* unsealing. The existing `data/split.receipt.json` already records
   `ScreenGeneEffect.csv` sha256 `71cb5b34…`, AV 1046 rows sha256 `7c4e5a19…`, KY 315 rows sha256 `97eb783b…`,
   CD 40 rows, 18,435 columns — that receipt plus a timestamped registration *is* the paper's novelty claim, so
   it must be public and third-party verifiable (OSF / Zenodo DOI), not a local file.

7. **A pre-declared rule for pan-lethal genes.** Krill-Burger 2023 (`10.1186/s13059-023-03020-w`) shows that
   "the majority of each cell line's dependencies are part of a set of 1867 genes that are shared dependencies
   across the entire collection (pan-lethals)" and that 63% of per-line CRISPR hits are pan-dependencies. An
   all-genes sweep carries those ~1,867 genes, which structurally cannot show context signal in Chronos; they
   inflate the denominator and dilute FDR. Either declare them in scope and pre-state the expected near-zero
   yield, or exclude them by a rule fixed before discovery, citing Krill-Burger. Do not decide after seeing the
   results.

8. **Pre-empt the "your confirmation set is scored by a method tuned on your discovery library" objection.**
   Chronos's published superiority is an Achilles/Avana result and is explicitly *not* significant in Project
   Score: "BAGEL2 outperformed Chronos in Project Score by 13% according to NNMD, while Chronos was first by
   6.5% over MaGECK as measured by PR AUC; however, the differences between first and second-best algorithms in
   Project Score were not statistically significant" (Dempster 2021, `10.1186/s13059-021-02540-7`). Either
   pre-register a sensitivity analysis of the KY confirmation using a second scorer (BAGEL2 Bayes factors or
   CRISPRcleanR-corrected log-fold changes, both published for Project Score), or state in the limitations that
   the confirmation rate is conditional on Chronos. Pacini 2021 is the citation that this choice moves the
   answer: the *number* of significant biomarker/dependency associations differed significantly between
   CRISPRcleanR, CCR-JACKS and CERES pipelines on the same data.

9. **Report the whole funnel, including the embarrassing numbers**: pairs tested, pairs passing discovery,
   pairs testable in KY (gene coverage differs — KY targets 18,009 genes vs Avana's set), pairs confirmed,
   pairs confirmed *and* not already known, and pairs confirmed but same-arm / guide-mutation-flagged /
   TMB-explained. A reviewer who cannot see the denominator will assume you chose it after unsealing.

### 6.3 What to claim, in one sentence

> "Using a pre-registered, hash-sealed split of DepMap 24Q4 screen-level Chronos gene effects by CRISPR library,
> we estimate — for the first time in a cohort disjoint from discovery in both reagent and cell line — the
> replication rate of genome-wide context-specific dependency associations, and we report the fraction of
> replicated associations that are not already captured by paralogy, complex/pathway co-membership, existing
> synthetic-lethality databases, or DepMap's own predictability models."

That claim is defensible and new. The claim "we discovered N novel context-specific dependencies in DepMap" is
neither.

---
