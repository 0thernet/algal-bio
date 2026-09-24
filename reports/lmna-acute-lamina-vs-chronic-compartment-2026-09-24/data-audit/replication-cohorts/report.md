# Replication-cohort audit: human LMNA-loss compartment datasets

Metadata-only audit, 2026-09-24 (UTC 20:22-20:25). No data files were downloaded:
only GEO SOFT metadata, GEO FTP directory indexes, GEO `filelist.txt` manifests, and
NCBI E-utilities text. Raw metadata captures are under `raw/`; every request is logged
in `query-ledger.json`; structured per-dataset fields are in `cohorts.json`.

## Decision

**Best outcome-replication cohort: GSE314556** (Hi-C of WT and LMNA/C-depleted GM12878
human B-lymphoblastoid cells, 2 vs 2 biological replicates, hg19).

**Its processed compartment calls do not exist.** The deposit contains exactly four files,
one HiC-Pro `allValidPairs` text file per sample. There are no PC1/eigenvector bedGraphs,
no `.hic`/`.cool`/`.mcool` matrices, and no binned contact matrices of any kind. PC1 would
have to be computed from the valid pairs (~7.4 GB compressed across the four samples).

It is recommended because it is the only unobserved human dataset found that pairs a
genuine **LMNA loss-of-function** perturbation with an isogenic control, has true
within-condition biological replication (n=2 vs n=2). It is on **hg19** (per-sample
`Assembly: hg19`). Correction 2026-09-24 (session lead, after checking the SOFT captures):
the registered predictor of the compartment campaign is GSE300197 (hg38), and the discovery
PC1 GSE126459 is hg38 (`Genome_build: hg38`, six samples), so an hg38 tile grid would need a
liftover to hg19 for this cohort. Only the GSE136252 predictor option below shares hg19 with
GSE314556. The original audit text claimed no liftover anywhere in the chain; that was wrong.

Its principal weakness is lineage: GM12878 is an EBV-transformed lymphoblastoid line, not a
cardiomyocyte, and lamina-chromatin association is strongly lineage-specific (that is the
central claim of the very paper the predictor comes from). A positive result would therefore
be a strong, conservative generalization test; a null result would be ambiguous between
"the effect is false" and "the effect is cardiac-specific". This should be stated in the
pre-registration before the data are touched, not after.

Runner-up: **GSE312031** (HGPS iPSC-VSMC Hi-C, GRCh38, 5 kb HiCExplorer `.h5`). Independent,
modern, and well-processed, but progerin is a gain-of-function/dominant-negative perturbation
class rather than LMNA loss, its replicates were merged before deposit, it needs an
hg19↔hg38 liftover, and the study itself reports a *global* loss of A/B segregation at late
passage, which can manufacture a non-specific B-ward drift in any tile set.

A defensible design is to pre-register GSE314556 as the primary replication and GSE312031
(P7, the earlier passage) as a secondary, direction-only supporting analysis with its
different perturbation class declared up front.

---

## 1. GSE314556 — LMNA/C-depleted human B-lymphoblastoid Hi-C

- **Organism / cell line**: *Homo sapiens*, GM12878 (EBV-transformed B-lymphoblastoid).
- **Perturbation**: LMNA/C knockout. Sample characteristics read `lmnac genotype: WT` or
  `lmnac genotype: KO` — a stable genotype, not an acute siRNA knockdown. Series title says
  "depleted"; the sample-level field says KO. **The KO-vs-knockdown distinction is stated
  inconsistently between the title and the sample characteristics and should be resolved from
  the preprint before registration.**
- **Samples / replicates**: 4 total — GSM9401860 (WT rep1), GSM9401861 (WT rep2),
  GSM9401862 (KO rep1), GSM9401863 (KO rep2). Two biological replicates per condition.
- **Genome build**: hg19.
- **Pipeline**: HiC-Pro v2.10.0, default settings.
- **Processed files per sample** (from `filelist.txt`):
  | GSM | file | bytes |
  |---|---|---|
  | GSM9401860 | `GSM9401860_HIC.WT.1_allValidPairs.txt.gz` | 2,033,547,121 |
  | GSM9401861 | `GSM9401861_HIC.WT.2_allValidPairs.txt.gz` | 1,997,529,377 |
  | GSM9401862 | `GSM9401862_HIC.KO.1_allValidPairs.txt.gz` | 2,321,735,949 |
  | GSM9401863 | `GSM9401863_HIC.KO.2_allValidPairs.txt.gz` | 1,018,354,190 |
  Series-level: `GSE314556_RAW.tar`, 7,371,171,840 bytes (6.9 G). Nothing else.
- **Resolutions**: none fixed — valid pairs are fragment-level, so any bin size can be built.
  The processing note only says "at various resolutions".
- **Compartment calls present**: no. Matrices present: no.
- **Publication**: Caruso LB, Maestri D, Kossenkov A, Goldman AR, Cassel J, Soldan S,
  Lieberman PM, Tempera I. "Lamin A/C maintains genome topology and regulates transcriptional
  programs essential for virus-driven B cell activation." bioRxiv, 2026-01-13.
  DOI 10.64898/2026.01.12.699161; PMID 41648489; PMC12871105.
- **Dates**: submitted 2025-12-19, released public 2026-02-11, last updated 2026-02-12.
- **Relations**: SubSeries of GSE314558 (siblings GSE314537, GSE314543); BioProject PRJNA1391507.

**Verbatim GEO summary**

> Lamin A/C is a crucial structural component of the nuclear lamina that influences chromatin organization and gene regulation. In this study, we demonstrate that lamin A/C is vital for maintaining higher-order genome organization and transcriptional programs that support EBV-driven B-cell activation. Loss of lamin A/C in a B-lymphoblastoid cell line caused significant three-dimensional reorganization of the genome, evidenced by the loss of long-range chromatin loops, an increase in short-range contacts, and redistribution of H3K9me2- marked heterochromatin. These structural disruptions were linked to widespread changes in gene expression affecting metabolic, signaling, and differentiation pathways. Mechanistically, lamin A/C influences the nuclear positioning and transcription of CTCF-bound loci by preventing their relocation to the periphery and their association with lamin B1. Blocking H3K9me2 deposition mimicked the transcriptional effects of lamin A/C depletion and revealed increased sensitivity to PI3K inhibitors. Overall, our results identify lamin A/C as a key organizer of genome structure and epigenetic regulation in EBV-infected B cells, uncovering a lamin-dependent pathway that connects nuclear architecture, metabolism, and viral disease processes.

**Verbatim GEO overall design**

> HiC of WT and LMNA/C depleted cells

**Role**: outcome replication (primary). **Required work**: download ~7.4 GB of valid pairs;
`cooler cload pairs` (or `hicpro2juicebox`) to build 500 kb bins; ICE or KR balance;
PC1 via HOMER `runHiCpca.pl` at 500 kb to match the HOMER convention used for the
GSE126459 PC1, or `cooltools eigs-cis` with GC/gene-density sign orientation. No liftover.
Watch that KO rep2 is roughly half the compressed size of the other three libraries —
check cis valid-pair counts before trusting per-replicate eigenvectors.

Note on independence: this is the same laboratory (Tempera) and the same LCL/EBV system as
GSE198412 ("Nuclear lamina binds the EBV genome during latency", 4 Hi-C samples). Confirm
from the preprint that GSE314556 libraries are not reused from that study before calling
this an independent cohort.

---

## 2. GSE312029 / GSE312031 — HGPS iPSC-VSMC (progerin: a different perturbation class)

Both series share one preprint: "Spatiotemporal remodeling of chromatin topology architecture
and H3K27me3 redistribution underlies vascular pathology in Hutchinson-Gilford progeria
syndrome", biorxiv.org/content/10.64898/2025.12.11.693713 (Ngubo, Ahuja, Karimpour, Shrestha,
Hendzel, Perkins, Stanford). Submitted 2025-12-01, released 2025-12-04, last updated 2026-03-06.

**GSE312031 [Hi-C]** — 8 samples, GSM9336625–GSM9336632. Four iPSC-VSMC lines — BJ1C (male
control), 0901C (female control), AG1B (female HGPS), 0031C (male HGPS) — each at passage P7
and P14. GRCh38 primary assembly (GENCODE); BWA-MEM 0.7.17 then HiCExplorer
(`hicBuildMatrix` at 5 kb, replicates merged with `hicSumMatrix`). Per sample, one
`*_merged_5kb.h5` HiCExplorer HDF5 matrix, 410–454 MB each; `GSE312031_RAW.tar` is
3,442,053,120 bytes. Series-level processed files are TAD calls
(`GSE312031_{ctrl,hgps}_p{7,14}_100kb_VC_TADs.bed.gz`, 11 K each) and Mustache loop calls
(`GSE312031_{CTRL,HGPS}_P{7,14}_KR_mustache_loops.bedpe.gz`, 80–123 K). **No compartment/PC1
files.** Because replicates were merged before deposit, the effective n is 2 control lines
vs 2 HGPS lines per passage, with no within-condition replicate variance.

**GSE312029 [CUT&Tag]** — 84 samples, CTCF, SMC1A, H3K27me3, H3K27ac, H3K36me3 in the same
VSMCs; series supplementary is `GSE312029_RAW.tar` only. **No lamin antibody in the panel**,
so it cannot serve as an LMNB1 predictor.

**Verbatim GEO summary** (identical text in both series)

> Hutchinson-Gilford progeria syndrome (HGPS) is a devastating premature aging disorder driven by the accumulation of progerin, leading to severe vascular pathology. While epigenetic alterations are implicated, the spatiotemporal reorganization of the higher-order chromatin and its functional impact on vascular smooth muscle cell (VSMC) transcription remain poorly defined. Through an integrated multi-omics approach combining in situ high-throughput chromosome conformation capture (Hi-C) and Cleavage Under Targets and Tagmentation (CUT&Tag) profiling of CTCF, SMC1A, H3K27me3, H3K27ac, and H3K36me3 with transcriptomic analyses from control and HGPS iPSC-derived VSMCs, we reveal that global topologically associating domain (TAD) architecture remains largely intact in HGPS. However, the internal chromatin states of TADs undergo dynamic, passage-specific remodeling, characterized by a progressive accumulation of broad H3K27me3-repressed domains. This is accompanied by a loss of A/B compartment segregation, as confirmed by DNA-FISH, indicating a collapse of higher-order chromatin organization in late passage. Crucially, we uncover widespread rewiring of enhancer-promoter (E-P) loops, which is linked to the dysregulation of genes critical for vascular development, extracellular matrix organization, and atherosclerosis. Our study demonstrates that spatiotemporal redistribution of repressive histone marks and reorganization of E-P interactions within a structurally resilient TAD framework underpin widespread transcriptional dysregulation in HGPS vascular pathogenesis. This uncovers a critical dissociation    between higher-order chromatin architecture and epigenetic statehistone modification landscape, providing a mechanistic basis for the failure of vascular homeostasis in progeria.

**Verbatim GEO overall design** (identical text in both series — note that the Hi-C series
carries the CUT&Tag design string, which appears to be a submission error)

> Cleavage Under Targets and Tagmentation (CUT&Tag) profiling of CTCF, SMC1A, H3K27me3, H3K27ac, and H3K36me3 in vascular smooth muscle cell differentiated from patient-derived induced pluripotent stem cells

**Role**: GSE312031 = outcome replication (secondary, direction-only). GSE312029 = not usable.
**Required work** for GSE312031: ~3.4 GB; `hicMergeMatrixBins` 5 kb → 500 kb,
`hicCorrectMatrix` (KR/ICE), `hicPCA` for PC1 — or `hicConvertFormat` to `.cool` and use
cooltools. **Liftover required** (hg19 tile set ↔ GRCh38). Prefer P7 over P14: the reported
global collapse of A/B segregation at late passage is exactly the kind of non-specific
B-ward drift that would produce a spurious "confirmation".

---

## 3. GSE41763 / GSE41764 — McCord 2013 HGPS Hi-C + lamin A/C ChIP

**GSE41764** is the SuperSeries (28 samples, PMID 23152449, submitted 2012-10-22, released
2012-10-30, last updated 2019-05-15) over three SubSeries: GSE41751 (expression array,
Affymetrix U133 Plus 2.0), GSE41757 (ChIP-seq: H3K27me3 and lamin A/C), GSE41763 (Hi-C).

**GSE41763 [Hi-C]** — 4 samples: GSM1023732 Father p18, GSM1023733 Age-Control p20,
GSM1023734 HGPS p17, GSM1023735 HGPS p19. Primary dermal fibroblasts.
**Genome build hg18** — a liftover would be needed (hg18→hg19, or hg18→hg38).
Processing: Bowtie2 iterative mapping, reads binned to **200 kb**, iteratively corrected
(Imakaev 2012). Per sample two files, an `IntMatrix.txt.gz` (200 kb corrected matrix,
70–118 MB) and a `validPair.txt.gz` (185–368 MB); `GSE41763_RAW.tar` is 1,492,633,600 bytes.
**No compartment/PC1 files.**

Replication structure is the real problem: the two "HGPS" samples are two passages of a
single patient line, and the two controls are two different donors (the patient's father and
an unrelated age-matched control). There is no within-genotype biological replication.

**Verbatim GEO summary (GSE41763)**

> Hutchinson-Gilford progeria syndrome (HGPS) is a premature aging disease that is frequently caused by a de novo point mutation at position 1824 in LMNA. This mutation activates a cryptic splice donor site in exon 11, and leads to an in-frame deletion within the prelamin A mRNA and the production of a dominant negative lamin A protein, known as progerin. Here we show that HGPS cells experience genome-wide alterations in patterns of H3K27me3 deposition, changes in the associations of genomic loci with nuclear lamin A/C, and, at late passage, genome-wide loss of spatial compartmentalization of active and inactive chromatin domains that characterizes chromosome folding in normal cells. We further demonstrate that the H3K27me3 changes associate with gene expression alterations in HGPS cells. Our results support a model that the accumulation of progerin in the nuclear lamina leads to altered H3K27me3 marks in heterochromatin, possibly through the down-regulation of EZH2, and disrupts heterochromatin-lamina interactions. These changes may then lead to the genomic disorganization and changes in transcriptional regulation we observe in HGPS fibroblasts.

**Verbatim GEO overall design (GSE41763)**

> Hi-C was performed on three primary fibroblast cell lines: an HGPS patient (passage 17 and 19; HGPS), normal cells from the father of the HGPS patient (passage 18; Father), and age-matched normal cells (passage 20; Age Control).

**Verbatim GEO summary (GSE41764, SuperSeries)**

> This SuperSeries is composed of the SubSeries listed below.

**Verbatim GEO overall design (GSE41764)**

> Refer to individual Series

**GSE41757 [ChIP-seq]** — overall design, verbatim:

> ChIP-Seq was performed for H3K27me3 and lamin A/C in the human genome in three primary fibroblast cell lines: an HGPS patient (HGPS), normal cells from the father of the HGPS patient (Father), and age-matched normal cells (Age Control). Two biological replicates were performed.

Per-sample files are raw aligned-read BEDs with matched inputs — `GSM1023620_LaminA-Father-R1.bed.gz`
(79.5 MB), `GSM1023622_LaminA-Father-R2.bed.gz` (369 MB), `GSM1023624_LaminA-HGPS-R1.bed.gz`
(201 MB), `GSM1023626_LaminA-HGPS-R2.bed.gz` (388 MB), plus `*-INPUT.bed.gz` for each, and
ten H3K27me3 BEDs; `GSE41757_RAW.tar` is 6,743,982,080 bytes. No normalized signal tracks,
no domain calls.

**Role**: GSE41763 = outcome replication, weak supporting only. GSE41757 = not recommended
as a predictor (lamin A/C not LMNB1, fibroblast not cardiomyocyte, hg18, read-level BED only).
**Required work**: liftOver hg18→hg19 chain; 200 kb native bins do not nest into 500 kb tiles,
so either re-bin from `validPair` files or accept attenuation from a 200 kb→500 kb regrid;
PC1 by per-chromosome correlation-matrix eigendecomposition on the supplied `IntMatrix`,
or rebuild to `.cool` and use cooltools.

---

## 4. Full GEO search results — human LMNA/lamin + conformation/compartment

Query A (11 hits): `(LMNA[All Fields] OR "lamin A"[All Fields]) AND ("Hi-C"[All Fields] OR
"chromosome conformation"[All Fields] OR compartment[All Fields]) AND "Homo sapiens"[Organism]
AND "gse"[Entry Type]` — GSE305237, GSE314556, GSE306294, GSE221288, GSE198412, GSE124409,
GSE126460, GSE126459, GSE126458, GSE81671, GSE41763.

Query B (18 hits): same structure with `(progeria OR HGPS OR laminopathy OR progerin OR LMNB1)`
— GSE305237, GSE306294, GSE312031, GSE312029, GSE206707, GSE206704, GSE165303, GSE192739,
GSE186206, GSE163641, GSE124409, GSE124197, GSE126459, GSE126458, GSE80795, GSE81671,
GSE41764, GSE41763.

Note that GSE312029/GSE312031 do **not** appear under Query A — they never use the token
"LMNA" — which is a reminder that a single keyword query under-recovers this literature.

| GSE | title (short) | n samples | processed-file types | role |
|---|---|---|---|---|
| GSE314556 | Lamin A/C maintains genome topology … [Hi-C] | 4 | HiC-Pro allValidPairs only | **outcome replication, primary** |
| GSE312031 | HGPS iPSC-VSMC [Hi-C] | 8 | HiCExplorer 5 kb `.h5`; 100 kb TAD BED; Mustache loop BEDPE | outcome replication, secondary |
| GSE312029 | HGPS iPSC-VSMC [CUT&Tag] | 84 | RAW.tar only | not usable (no lamin target, no Hi-C) |
| GSE41763 | McCord HGPS Hi-C | 4 | 200 kb IntMatrix + validPair (hg18) | weak supporting |
| GSE41764 | McCord SuperSeries | 28 | see SubSeries | container |
| GSE41757 | McCord ChIP-seq (H3K27me3, lamin A/C) | 18 | read-level BED + INPUT (hg18) | predictor, not recommended |
| GSE41751 | McCord expression array | 6 | array | not usable |
| GSE124409 | LMNB1-KO MDA-MB-231 | 20 | 500 kb ICED whole-genome matrices, 40 kb per-chr matrices, ATAC bigWig | specificity control |
| GSE221288 | Gene regulatory loops at LADs (ASC) | 13 | per-replicate lamin A/C 1 kb log-ratio bedGraph + peak BED; histone bigWig | predictor alternative, wrong lineage |
| GSE81671 | Laminopathy lamin mutations, genome models | 25 | RAW.tar 5.6 M (no new Hi-C) | context only |
| GSE198412 | Nuclear lamina binds the EBV genome [Hi-C] | 4 | not assessed | not usable / independence flag |
| GSE165303 | 3D chromatin in human dilated cardiomyopathy | 177 | in situ Hi-C, HiChIP, ChIP, ATAC, RNA | cardiac context, no LMNA contrast |
| GSE126459 | LMNA R225X hiPSC-CM [Hi-C] | 6 | **500 kb PC1 bedGraph per sample**, 500 kb ICED matrix, allValidPairs | already observed (discovery cohort) |
| GSE126458 / GSE126460 | same study, companion assays | 9 / 15 | expression and other | not independent |
| GSE305237 | Base editing rescues HGPS | 3 | expression | not usable |
| GSE306294 | Pol III tissue/tumor atlas | 24 | occupancy | not usable |
| GSE206704 / GSE206707 | HGPS fibroblast transcriptional profiling | 11 / 22 | expression | not usable |
| GSE192739 / GSE186206 / GSE163641 / GSE124197 / GSE80795 | APEX-seq; Ki67; tree-of-life 3D; KAT7 screen; CpG partitioning | various | various | incidental keyword matches |

**Key structural finding**: across every human dataset located, **GSE126459 — the discovery
cohort — is the only one that ships per-sample 500 kb PC1 bedGraphs.** Every candidate
replication cohort requires PC1 to be computed from matrices or valid pairs. That is not a
blocker, but it means the replication cannot be "read off" a deposit and the PC1 method
(tool, bin size, balancing, sign convention) must be fixed in the pre-registration in advance,
ideally by re-deriving PC1 for GSE126459 with the same pipeline and confirming it reproduces
the deposited HOMER PC1 before touching the replication data.

---

## 5. Human LMNB1 / lamin A/C signal datasets in cardiomyocytes — predictor cohort

**GSE136252 (Shah 2021) — recommended predictor, with one hard caveat.**

- Title: "Pathogenic LMNA variation disrupts a tissue-specific lamina-chromatin signature,
  resulting in loss of cellular identity". Submitted 2019-08-23, released 2021-02-01,
  processed files last revised 2020-07-23. BioProject PRJNA561761, SRA SRP219155.
- 112 samples; LB1 and H3K9me2 ChIP-seq with matched inputs, plus RNA-seq, in hiPSC-derived
  cardiac myocytes (d25, d45), hepatocytes (d23) and adipocytes (d25), for control,
  LMNA T10I and LMNA R541C.
- Genome build **hg19**. Tracks are deeptools `bamCoverage --normalizeUsing RPGC` then
  `bigWigCompare --operation subtract` against input; LADs/KDDs called with EDD 1.1.18;
  differential peaks with epic2 + DiffBind.

**Caveat, and it is the decisive one: there are no per-sample processed files.** Every GSM in
GSE136252 carries `!Sample_supplementary_file_1 = NONE`. All tracks live at the series level
and were made from BAMs merged across replicates within a condition. So a predictor built
here is a fixed region/condition-level signal, with no replicate-level variance available.

Cardiomyocyte LMNB1 (LB) tracks, series-level, with listed sizes:

| file | size | condition |
|---|---|---|
| `GSE136252_d25_control_LB.bigWig` | 866 M | control CM, day 25 |
| `GSE136252_d45_control_LB.bigWig` | 1.0 G | control CM, day 45 |
| `GSE136252_d25_T10I_LB.bigWig` | 1.0 G | LMNA T10I CM, day 25 |
| `GSE136252_d45_T10I_LB.bigWig` | 1.0 G | LMNA T10I CM, day 45 |
| `GSE136252_R541C_LB_CM.RPGC.inputsubtract.bigWig` | 679 M | LMNA R541C CM |

Matching CM peak files: `GSE136252_d25_control_LB_peaks.clipped.bed.gz` (9.6 K),
`GSE136252_d25_T10I_LB_peaks.clipped.bed.gz` (7.7 K),
`GSE136252_d45_control_LB_peaks.clipped.bed.gz` (11 K),
`GSE136252_d45_T10I_LB_peaks.clipped.bed.gz` (11 K),
`GSE136252_R541C_LB_CM_peaks.clipped.bed.gz` (7.6 K).

Ready-made differential sets, which are the directly usable part:
`GSE136252_d25_LB_gained_peaks.bed.gz` (5.5 K), `GSE136252_d25_LB_lost_peaks.bed.gz` (7.4 K),
`GSE136252_d45_LB_gained_peaks.bed.gz` (5.8 K), `GSE136252_d45_LB_lost_peaks.bed.gz` (4.0 K).
Also present: matching H3K9me2 CM bigWigs/peaks, hepatocyte and adipocyte LB/H3K9me2 tracks,
and RNA-seq matrices (`GSE136252_RNAseq.log2cpmmatrix.filtered.txt.gz`,
`GSE136252_differential_expression_output.csv.gz`, `GSE136252_raw_count_matrix.csv.gz`).

**Role**: predictor replication — recommended. Same lineage (hiPSC-CM) and same build (hg19)
as the registered predictor, but derived from a *chronic* LMNA missense mutation rather than
acute siRNA, which makes it a genuinely independent way to define "tiles that gain LMNB1 when
LMNA function is lost". **Required work**: no liftover; bin the input-subtracted RPGC bigWigs
to 500 kb (`bigWigAverageOverBed` or pyBigWig) and take T10I-minus-control and
R541C-minus-control deltas, or simply intersect the supplied `d25`/`d45` LB gained-peak BEDs
with the 500 kb tile set. Because there is one track per condition, register the predictor as
a fixed tile set and do not attempt replicate-level predictor inference.

**Other lamin signal datasets located, and why none replaces it**: GSE221288 has exactly the
per-replicate normalized lamin tracks that GSE136252 lacks
(`GSM6857883..GSM6857888_ASC_D{0,1,3}_LMNAC_Rep{1,2}_log_ratio_1KB.bedgraph.gz`, ~20–23 MB
each, plus `_peaks.bed.gz`), but it is lamin A/C in adipose stem cells with no LMNA
perturbation. GSE41757 is lamin A/C in fibroblasts on hg18, deposited as read-level BED.
GSE81671 is lamin A/C ChIP in FPLD2 fibroblasts and Flag-LMNA HeLa, with a 5.6 MB RAW archive
and no new Hi-C. **No human cardiac-tissue LMNB1 DamID or CUT&RUN dataset with per-sample
processed tracks was found**; GSE165303 is the only large human cardiac 3D-genome resource and
it profiles H3K27ac/HAND1/ATAC, not lamins.

Search-coverage limit worth recording: the two queries above were keyword searches on the
GDS database restricted to *Homo sapiens* GSE records. They would miss datasets that describe
lamin B1 profiling without the tokens searched (for example a DamID study labelled only
"LaminB1 DamID" in a tissue series title with no LMNA/HGPS/compartment keyword), and they miss
ArrayExpress/ENCODE-only deposits entirely. A dedicated `(LMNB1 OR "lamin B1") AND (DamID OR
CUT&RUN OR LAD) AND (heart OR cardiomyocyte)` sweep, plus an ENCODE/4DN check, is the obvious
next step if a per-replicate cardiac predictor is judged necessary.

---

## Recommended registration, in one paragraph

Pre-register GSE314556 as the outcome-replication cohort and the GSE136252 hiPSC-CM
LMNB1-gained tile set as the predictor, both on hg19 with no liftover. Fix the PC1 pipeline
in advance (HOMER `runHiCpca.pl` at 500 kb, sign oriented by gene density) and validate it by
reproducing the deposited GSE126459 PC1 bedGraphs before the replication data are processed.
Declare before analysis that (a) GSE314556 is lymphoblastoid, so a null is ambiguous between
refutation and cardiac specificity; (b) GSE314556 KO rep2 is roughly half-depth and may be
dropped only under a depth threshold set in advance; (c) GSE312031 P7 is a secondary
direction-only analysis in a different perturbation class; and (d) GSE124409 (LMNB1-KO) is a
pre-registered specificity control, not a confirmation cohort. Confirm from the GSE314556
preprint whether the perturbation is a true knockout or a depletion, and whether its libraries
are independent of GSE198412 from the same laboratory.
