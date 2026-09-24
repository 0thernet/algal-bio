# Caruso et al. 2026 — prior-art read (GSE314556 within SuperSeries GSE314558)

"Lamin A/C maintains genome topology and regulates transcriptional programs essential for
virus-driven B cell activation." bioRxiv, 2026-01-12/13. DOI 10.64898/2026.01.12.699161.
PMID 41648489. PMC12871105. Wistar Institute (Caruso, Tempera et al.).

Read via the PMC full text and the Europe PMC REST full-text XML. bioRxiv HTML returned HTTP 429
twice and the GEO series page was CAPTCHA-blocked, so sample-level metadata could not be read
from GEO. All quotes are verbatim.

## 1. Perturbation, control, cell line

Stable lentiviral **CRISPR/Cas9 knockout** — not RNAi, not a degron. Methods (CRISPR/Cas9):
"B cells were transduced with lentiviruses expressing sgRNAs as previously described" and
"sgRNA sequences used were as follows: Control: ATTTCGCAGATCATCGACAT, LMNA:
AGTTTAAGGAGCTGAAAGCG."

No single-cell cloning and **no clone identifiers** are described, so the KO is a transduced pool,
not a validated clone. The control is the same LCL transduced with a control (non-targeting)
sgRNA — isogenic in background but sgRNA-matched, not untransduced parental. Cell line: EBV-positive lymphoblastoid line **GM12878**. Results also
note: "These cells show no differences compared to WT cells in terms of lamin B1 expression or
the number of EBV genomes per cell (Fig. S1A and S1B)."

## 2. Hi-C design and processing

Methods (Hi-C assay): "5 × 10⁶ cells per condition were collected for *in-situ* Hi-C"; libraries
built with "Ultralow Library Systems V2"; "Libraries were sequenced using the Illumina HiSeq
2500 sequencing platform with paired-end 75 bp read length." The protocol itself is by
reference — "Hi-C assay was performed as previously described."

- **Biological replicates per condition:** not stated (no "n =" for Hi-C anywhere).
- **Depth / valid pairs:** not stated.
- **Restriction enzyme:** not named (no MboI/DpnII/HindIII/Arima in the text).
- **Pipeline:** "HiC data were preprocessed using HiC-Pro v2.10.0 pipeline with default settings
  using the human genome at 1 kb resolution."
- **Differential contacts:** "DESeq2 was used to estimate the significance of differential contact
  based on raw count matrix files," then loops were "further filtered ... by CTCF binding."
- **Compartment method:** no tool named — no cooltools, HOMER, Juicer, FAN-C or dcHiC; no
  compartment-specific bin size; no PC1 orientation rule (GC content or gene density) given. The
  only methodological trace is a figure legend: "Eigenvector in WT versus lamin A/C KO cells from
  Hi-C data sets showing significant (p < 0.01) changes in open (A) and closed chromatin (B)
  compartments."

## 3. What is reported about A/B compartments

Essentially one sentence in Results: "the depletion of lamin A/C had a significant effect on
global genome organization, with 39 compartments switching from B (inactive chromatin) to A
(active chromatin) compartments and 23 from A to B in lamin A/C KO cells."

That is the whole compartment quantification: **counts of regions, net A-ward (39 B→A vs 23
A→B)**. No genome fraction or percentage, no compartment-strength or segregation metric, and
no saddle plot — "saddle" does not appear. Compartment changes are never related to LADs or
lamin B1; that link is made for CTCF only.

Loops: "increased frequency of smaller chromatin loops (occurring between nearby regions) and
a decreased occurrence of larger loops."

CTCF/periphery claim (Abstract): "lamin A/C influences the nuclear positioning and transcription
of CTCF-bound loci by preventing their relocation to the periphery and their association with
lamin B1." Supporting Results: "In absence of lamin A/C, CTCF became repositioned towards the
nuclear periphery" and "We observed increased interaction of CTCF with both lamin B1 and
H3K9me2 in the absence of lamin A/C (Fig. 4A)." The evidence is **proximity ligation / imaging,
not a genomic lamin B1 map**.

## 4. Global structural effect (confounder for a tile-level test)

Reported explicitly. Results: "significant effect on global genome organization." Abstract:
"significant three-dimensional reorganization of the genome, evidenced by the loss of
long-range chromatin loops, an increase in short-range contacts, and redistribution of
H3K9me2-marked heterochromatin." Discussion: "loss of lamin A/C causes the heterochromatin to
be untethered to the nuclear periphery, disrupting its supporting role."

A genome-wide shift in contact scaling (short-range up, long-range down) can inflate tile-level
compartment comparisons unless distance-matched or quantile-normalized.

## 5. Lamin B1 genomic data in the same cells

**No.** ChIP-seq in this study profiled **CTCF and H3K9me2 only**; lamin B1 appears only as a
western blot and as a PLA partner. Data availability: "The RNA-seq, the ChIP-seq and Hi-C
datasets generate during this study are available in the Gene Expression Omnibus (GEO)
repository, under accession number GSE314558." No LMNB1 ChIP-seq, CUT&RUN or DamID track
exists for these cells, so any LAD/LMNB1 axis must come from an external reference dataset.

## 6. Prior statement comparing lamina-sensitivity to compartment shift

**Not found.** Nothing in the paper resembles "regions that lose LMNB1 fastest after lamin loss
move toward B." The only lamina framing is generic: "Lamin A/C is associated with maintaining
nuclear structure and organizing chromatin by forming lamina-associated domains (LADs)." The
specific hypothesis appears unclaimed by this paper.

## Implications for a re-analysis

- Compartment analysis here is thin (region counts only; no tool, bin size, orientation,
  strength or saddle), so a PC1 re-analysis is additive, not duplicative.
- Replicate structure and depth are absent from the paper; read them off GEO metadata.
- The reported global contact-scaling shift requires distance-matched comparison.
- No matched LMNB1 map exists in these cells; an external LAD reference is needed and its
  cell-type mismatch must be declared.
