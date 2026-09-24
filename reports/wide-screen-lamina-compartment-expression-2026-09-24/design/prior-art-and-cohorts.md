# LMNA / lamin A/C compartment screen: prior art, fresh cohorts, reference PC1 sources

Compiled 2026-09-24. Web search + full-text reading only; nothing large was downloaded.
Claim status is marked **[verified]** (I read the sentence or the record myself),
**[record-verified]** (GEO/4DN/ENCODE metadata read directly via eutils / portal API, but no paper text),
or **[unverified]** (found only in secondary text or not checked).

Screen being contextualised: mutant-minus-corrected ΔPC1 (HOMER, 500 kb) in LMNA R225X hiPSC-CMs
vs two corrected isogenic clones; after adjusting for CM baseline PC1, GC, gene density, baseline
lamin B1, the predictors are (a) GM12878 PC1 (+) and (b) GC (+); and GC predicts Δlamin-B1 z-score
after acute siLMNA in iPSCs (−).

---

## 0. Accession housekeeping

* The Bertero 2019 JCB data-availability sentence is: *"Hi-C and RNA-seq data are available in GEO
  under accession no. GSE126460."* **[verified,** full text PMC6719452**]**. GSE126460 is the
  SuperSeries; **GSE126459** is the Hi-C SubSeries (6 samples) and GSE126458 the RNA-seq SubSeries
  (9 samples) **[record-verified]**. So the cohort you used is the right one; cite GSE126460 as the
  parent.
* GSE314556 (excluded) is only the **Hi-C SubSeries** of the 2026 lamin A/C LCL study. Its siblings
  are *not* excluded and are directly usable as covariates for that cohort:
  **GSE314543** (ChIP-seq, H3K9me2 + CTCF, 16 samples) and **GSE314537** (RNA-seq, 8 samples);
  parent SuperSeries **GSE314558** **[record-verified]**.

---

## 1. PRIOR ART

### 1.1 What Bertero 2019 (J Cell Biol) itself says

DOI 10.1083/jcb.201902117, PMID 31395619, PMC6719452.

Abstract, verbatim **[verified]**:

> "While large-scale changes in chromosomal topology are evident, differences in chromatin
> compartmentalization are limited to a few hotspots that escape segregation to the nuclear lamina
> and inactivation during cardiogenesis. These regions exhibit up-regulation of multiple noncardiac
> genes including *CACNA1A*, encoding for neuronal P/Q-type calcium channels. … Thus, global errors
> in chromosomal compartmentation are not the primary pathogenic mechanism in heart failure due to
> lamin A/C haploinsufficiency."

Results, verbatim **[verified]**:

> "…lamin A/C haploinsufficiency in developing hiPSC-CMs results in highly selective dysregulation
> of chromatin compartmentalization, particularly for a handful of genomic hotspots that fail to
> transition from the active compartment in the nuclear interior to the inactive compartment
> associated to the nuclear lamina. We will refer to these as lamin A/C–sensitive B domains."

> "These findings confirmed that impaired transition to the B compartment of selected lamin
> A/C–sensitive domains leads to up-regulation of multiple noncardiac genes that would otherwise be
> transcriptionally repressed during cardiomyocyte differentiation."

> "We previously showed that transition from the B to A compartment during cardiogenesis often
> reflects relocalization of loci from the nuclear periphery to the nuclear interior (Bertero et
> al., 2019) … Thus, we speculated that the opposite could also be true, and that lack of transition
> from the A to B compartment in mutant hiPSC-CMs might reflect impairment of translocation to
> peripheral LADs."

The up-regulated hotspot genes were "significantly enriched for three chromosome locations … two of
which corresponded to the lamin A/C–sensitive hotspots 5q31.3 and 19q13.33 … and were associated
with neuronal development" (protocadherin clusters, LRRC4B, SYT3, CACNA1A) **[verified]**.

**What Bertero 2019 does NOT contain [verified by exhaustive string search of the PMC full text]:**
the strings "GC content", "GM12878", "lymphoblast" do not occur anywhere; there is no nucleotide
composition analysis, no comparison with any non-cardiac cell type's compartment track, and no
genome-wide regression. Their only external comparator is their own hESC/hESC-CM cardiogenesis
time course (Bertero et al. 2019 *Nat Commun* 10:1538, DOI 10.1038/s41467-019-09483-5, GEO
GSE106687/GSE106690). Their analysis is hotspot/threshold-based, not a continuous genome-wide model,
and they explicitly argue *against* a global compartment phenotype.

**Relation to your result.** The direction is prior art in a weak, qualitative form: the regions that
fail to inactivate are exactly regions that are A in non-cardiac states and normally go B during
cardiogenesis, so "shift toward the GM12878 state" is a genome-wide, quantitative restatement of
Bertero's hotspot claim — *except* that Bertero frames it as an arrested developmental transition
(retention of the progenitor/iPSC state), not as convergence on an unrelated lineage, and explicitly
denies that it is global. A continuous "other-cell-type PC1 predicts ΔPC1 after covariate
adjustment" statement appears to be new **[verified as absent from Bertero; not found elsewhere in
this search]**.

### 1.2 Closest prior art on "LMNA loss erodes cell-type-specific genome organisation"

1. **Shah et al. 2021, *Cell Stem Cell* 28:938–954** — DOI 10.1016/j.stem.2020.12.016, PMID
   33529599, PMC8106635. LMNA T10I and R541C introduced into hiPSCs; LAMIN B1 and H3K9me2 ChIP-seq +
   RNA-seq in hiPSC-CMs vs hepatocytes vs adipocytes. Title and abstract, verbatim **[verified]**:
   *"Pathogenic LMNA variants disrupt cardiac lamina-chromatin interactions and de-repress
   alternative fate genes"*; *"Disrupted regions were enriched for transcriptionally active genes and
   regions with lower LAMIN B1 contact frequency. The lamina-chromatin interactions disrupted in
   mutant cardiomyocytes were enriched for genes associated with non-myocyte lineages and correlated
   with higher expression of those genes."* Data: **GSE136252** **[verified, quoted availability
   sentence]**. They ranked LADs by **gene density** deciles **[verified via full-text read]**; I
   found no GC-content analysis **[unverified — not an exhaustive string search of that paper]**.
   *This is the strongest existing statement of the "lamina safeguards cell identity / alternative
   fate genes get de-repressed" idea, but it is about LADs and expression, not about Hi-C
   compartments, and not about resemblance to a specific other cell type's compartment profile.*
2. **Lee et al. 2019, *Nature* 572:335–340** (LMNA K117fs, PDGF) — DOI 10.1038/s41586-019-1406-x,
   PMC6779479. I could not confirm that this paper contains Hi-C or any compartment analysis; the
   phenotype is arrhythmia/calcium and PDGF pathway activation, and secondary sources describe only
   RNA-seq/ATAC-type genomics **[unverified — PMC fetch was blocked by a redirect; treat "no Hi-C"
   as likely but unconfirmed]**.
3. **Zheng et al. 2018, *Mol Cell* 71:802–815** — DOI 10.1016/j.molcel.2018.05.017, PMID 30201095,
   PMC6886264. Abstract, verbatim **[verified]**: *"Using Hi-C, we show that lamins maintain proper
   interactions among the topologically associated chromatin domains (TADs) but not their overall
   architecture. … lamin loss causes expansion or detachment of specific LADs in mouse ESCs. The
   detached LADs disrupt 3D interactions of both LADs and interior chromatin."* i.e. the published
   position is that lamin loss perturbs domain-domain interactions and LAD anchoring, **not** that it
   reassigns compartments toward another lineage. Data: **GSE89520** **[record-verified]**.
4. **Bhattacharjee / Nature Communications 2022, "Lamin A/C-dependent chromatin architecture
   safeguards naïve pluripotency to prevent aberrant cardiovascular cell fate and function"** —
   DOI 10.1038/s41467-022-34366-7, GEO **GSE164068** (Hi-C, mESC LMNA KO vs control, 3+3) /
   GSE164069 (SuperSeries). Summary, verbatim **[record-verified from the GEO record]**: *"We find
   major changes in chromatin compaction and localization of cardiac genes already in Lmna−/− ESCs
   resulting in precocious activation of a transcriptional program promoting cardiomyocyte versus
   endothelial cell fate…"* This is "lamin A/C loss releases a *different* lineage's program", in ESCs.
5. **"Lamin A/C maintains genome topology and regulates transcriptional programs essential for
   virus-driven B cell activation", bioRxiv 2026**, DOI 10.64898/2026.01.12.699161, PMID 41648489;
   LMNA CRISPR KO in GM12878 LCL; Hi-C (hg19), H3K9me2/CTCF ChIP, RNA-seq. Reported **[verified via
   full-text fetch]**: *"39 compartments switching from B (inactive chromatin) to A (active
   chromatin) compartments and 23 from A to B in lamin A/C KO cells compared with the WT sample"*
   and *"WT cells predominantly displayed the phenotype of memory B cells, while KO cells exhibited
   characteristics akin to naïve B cells"* — again an identity-regression claim, but transcriptional,
   and B→A biased. Note the coincidence that your reference cell type (GM12878) is this paper's
   *perturbed* cell type: GSE314556's Hi-C is a direct, independent test of the same hypothesis in
   the reference line itself.
6. **McCord et al. 2013, *Genome Res* 23:260–269** (HGPS, progerin) — PMID 23152449,
   DOI 10.1101/gr.138032.112 **[DOI unverified; PMID verified]**, GEO GSE41763 (Hi-C) / GSE41764
   (SuperSeries). Reported findings **[verified only via the journal/secondary summary, not by
   reading the paper's own sentences]**: late-passage HGPS fibroblasts show *genome-wide loss of
   spatial compartmentalization*, preceded by *loss of H3K27me3 in gene-poor regions and gain of
   H3K27me3 in gene-rich regions*, plus chromatin detachment from the lamina. **This is the closest
   published statement to a composition-dependent (gene-density, and by proxy GC) response to a
   lamin A/C lesion**, and it is a *loss of contrast* (compartment erosion), which is what a positive
   coefficient on another cell type's PC1 plus a positive GC coefficient would look like if the
   erosion were toward a generic GC-driven compartment profile.
7. **Falk et al. 2019, *Nature* 570:395–399** — DOI 10.1038/s41586-019-1275-3, PMID 31168090, GEO
   **GSE111032** (WT vs LBR-KO thymocytes, rods vs non-rod neurons; 8 Hi-C samples)
   **[record-verified]**. Conclusion: heterochromatin–heterochromatin attraction drives
   compartmentalisation; lamina interactions position, rather than create, the compartments. Useful
   as the mechanistic null: removing a tether should *reposition* without re-identifying compartments.
8. **Chang et al. (lamin B1 depletion), GSE124409, "Nuclear peripheral chromatin-lamin B1
   interaction is required for global integrity of chromatin architecture and dynamics in human
   cells"** **[record-verified from the GEO record]**; lamin B1 depletion → LAD detachment, increased
   inter-chromosomal interaction, decompaction. Published version (*Protein & Cell*, 2022) not
   fetched **[unverified]**. Nothing about GC dependence found.
9. **Cell Reports 2025, "Nuclear-lamin-guided plastic positioning and folding of the human genome"**
   (S2211-1247(25)01300-2) — surfaced in search, not read **[unverified]**; worth a look as the most
   recent systematic lamin-vs-folding paper.
10. Also surfaced and not read **[unverified]**: GSE268924/268923/268922 *"The molecular basis of
    lamin-chromatin interactions"* (2025, lamin A/C depletion, SAMMY-seq + cryo-ET) and
    GSE330298/330103 *"Lamins gate nuclear and chromatin structures for cardiomyocyte maturation
    genes"* (bioRxiv 2026, PMC13228526) — the latter is the only other *cardiomyocyte* lamin Hi-C
    dataset I found, and its Hi-C arm is lamin **B1** cKO, not Lmna.

**Bottom line for Q1a:** no one has published the specific claim that LMNA loss shifts compartments
*toward another cell type's PC1 profile* as a genome-wide, covariate-adjusted quantity. The
neighbouring claims that do exist are: (i) failure to complete lineage-specific A→B inactivation
(Bertero 2019); (ii) LAD disruption enriched for other-lineage genes (Shah 2021); (iii) an
identity-regression phenotype in Lmna−/− ESCs and in LMNA-KO LCLs; (iv) global compartment erosion
in progerin-expressing cells (McCord 2013). Your framing is a synthesis of (i)+(iv) with a
quantitative test none of them ran.

### 1.3 Is a GC dependence of lamin-linked compartment change known?

* **Meuleman et al. 2013, *Genome Res* 23:270–280**, PMID 23124521 — *"Constitutive nuclear
  lamina–genome interactions are highly conserved and associated with A/T-rich sequence."*
  Reported **[verified at the level of title/abstract summary, exact sentence not quoted from the
  PDF]**: constitutive LADs are "universally characterized by long stretches of DNA with high A/T
  content", and "changes in A/T content have driven gene relocation to and from the nuclear lamina
  during evolution". This is the foundational result that *baseline* lamina association is
  GC-anticorrelated — so a GC-dependent *response* to LMNA perturbation is mechanistically plausible
  and partly expected.
* **McCord 2013** (above): gene-poor vs gene-rich asymmetry in the H3K27me3 change; gene density is a
  strong GC proxy at 500 kb.
* **Lieberman-Aiden et al. 2009** (DOI 10.1126/science.1181369): A compartment is the GC-rich,
  gene-rich, DNase-accessible one — the reason PC1 and GC are collinear at all **[unverified quote]**.
* I found **no** paper reporting GC content as a *continuous predictor of the change* in compartment
  score or in lamin B1 signal under lamin perturbation. Treat that as an unclaimed result, with the
  circularity caveat in §3.4.

### 1.4 Compartment convergence toward a "generic"/other state in other contexts

* **Senescence.** *"The loss of heterochromatin is associated with multiscale three-dimensional
  genome reorganization and aberrant transcription during cellular senescence"*, *Genome Res* 2021,
  DOI 10.1101/gr.275235.121, PMID 34140314 **[abstract verified]**; Criscione et al. 2016,
  *Sci Adv* 2:e1500882 (replicative senescence) and Sati et al. 2020, *Mol Cell* (OIS) **[unverified]**.
  Consensus in secondary summaries: a subset of TADs switches compartment, facultative heterochromatin
  tends to move B→A, and RS shows *dampened* A–A interactions / weaker compartmentalisation while OIS
  shows stronger B–B **[unverified]**. So "compartment contrast erodes" is described; "compartments
  converge on another lineage's profile" is not, as far as I found.
* **Aging.** *"Multiscale 3D genome reorganization during skeletal muscle stem cell lineage
  progression and aging"*, *Sci Adv* 2023, DOI 10.1126/sciadv.abo1360, PMID 36800432
  **[abstract verified]**; "geriatric SC displays a prominent loss of local chromatin connectivity".
  Also GSE334821 *"Aging is associated with enhanced chromatin compaction…"* **[record-verified]**.
* **Cancer.** GSE246599 *"Deterioration of multi-level 3D genome organization during breast cancer
  progression"* **[record-verified title only]**; the standard reference for cancer compartment
  change is Johnstone et al. 2020 *Cell* **[unverified]**.
* A useful framing precedent: eLife 2025, *"Major nuclear locales define nuclear genome organization
  and function beyond A and B compartments"*, PMID 40279158, PMC12029212 — includes the K562
  LMNA/LBR knockout series (GSE263012) and reports **[verified via secondary summary of the paper]**
  that *"whereas LMNA knockout alone showed little change in lamina DamID, the LBR knockout and
  LMNA/LBR double knockout lines showed partial reduction in lamina DamID for most LADs"*. That is a
  direct, quotable counterweight to a strong single-gene LMNA effect on lamina association in K562,
  and worth reconciling with your siLMNA lamin-B1 result.

---

## 2. FRESH COHORTS (excluding GSE126459, GSE314556, GSE300197)

All rows **[record-verified]** from GEO eutils summaries and the GEO FTP supplementary listings
(sizes are the FTP-reported supplementary sizes; raw FASTQ in SRA is extra). Genome build is marked
unverified unless a processed file name or the paper states it.

### 2.1 Hi-C / in situ Hi-C with a lamin perturbation

| Accession | System | Perturbation | n (Hi-C) | Build | Processed deposited? | Suppl. size |
|---|---|---|---|---|---|---|
| **GSE164068** (parent GSE164069) | mouse ESC | *Lmna*−/− vs control | 3 vs 3 | mm10 (from file names) | **Yes — `*_merge_mm10.PC1.bedGraph.gz`, 1.4 MB per condition** + WashU near-contact beds | 1.4 MB PC1 files; 1.8–1.9 GB validPairs |
| **GSE339018** (parent GSE339045) | mouse cerebellar granule neurons, d8 | *lmna* KD vs ctrl (plus brd4/etv1/top1/top2b/wapl/nup153/med1/p300 KDs) | 3 lmnaKD GSMs (GSM9886538-40) | mm10 **[unverified]** | **Yes — `.hic` per condition** (`GSE339018_d8_lmnaKD.allValidPairs.hic` 1.3 GB; `d8_ctrl_m6` 2.0 GB) | ~1.3 GB (KD) + ~2.0 GB (ctrl) |
| **GSE89520** | mouse ESC | lamin single/double/triple KO (Zheng 2018) | 40 samples total, subset Hi-C | mm9/mm10 **[unverified]** | RAW tar only | 6.5 GB |
| **GSE330103** (parent GSE330298) | mouse P0.5 heart, cardiomyocyte-specific | **Nkx2-5Cre;Lmnb1^Flox/−** vs `Flox/+` (lamin **B1**, not LMNA) | 2 vs 2 | mm10 **[unverified]** | **Yes — `*_modified_cscore.bedgraph.gz`, 1.7 MB per genotype** | 1.7 MB ×2; 2.9 GB RAW |
| **GSE41763** (parent GSE41764) | human skin fibroblasts | HGPS (progerin) vs father/age-control, p17–p20 | 2 HGPS + 2 control | hg18/hg19 **[unverified]** | RAW tar | 1.4 GB |
| **GSE206704** | human fibroblasts | HGPS, 2 patient + 2 healthy lines, early vs late passage (AG03257, AG11513, HGADFN167/168, GM08398) | 11 | hg19/hg38 **[unverified]** | RAW tar only | 4.6 GB |
| **GSE312031** (CUT&Tag sibling GSE312029) | human VSMC | HGPS vs control, P7 and P14, M and F | 8 | hg38 **[unverified]** | **Yes — TAD beds (100 kb) and mustache loop bedpe** | 3.2 GB RAW + ~0.4 MB calls |
| **GSE193694** | human iPSC-derived hMSC/VSMC/VEC | **LMNA c.1579C>T p.R527C** (MAD type A) patient iPSC vs corrected | Hi-C GSM5818750/51 (2) | hg38 **[unverified]** | RAW tar only | 8.0 GB (whole SuperSeries) |
| **GSE111032** | mouse thymocytes / rods / neurons | **LBR**-KO vs WT thymocytes (Falk 2019) | 2 vs 2 (+rods, neurons) | mm9/mm10 **[unverified]** | RAW tar | 1.1 GB |
| **GSE124409** | human cells | **LMNB1** depletion | subset of 20 | hg19 **[unverified]** | peaks + counts only | 846 MB |
| **GSE81671** | human fibroblasts, laminopathy mutations | Chrom3D genome models integrating Hi-C + LAD | 25 samples | hg19 **[unverified]** | models | 5.6 MB |
| **GSE314543 / GSE314537** | GM12878 LCL | LMNA CRISPR KO (siblings of the excluded GSE314556) | 16 ChIP / 8 RNA | hg19 **[verified from the preprint]** | — | not checked |

Best value for a cheap replication: **GSE164068** (PC1 bedGraphs already deposited, 1.4 MB, mm10;
you can lift the same model straight onto it with a mouse reference cell type) and **GSE330103**
(cscore bedGraphs, 1.7 MB, but the perturbation is lamin B1).

Best value for a *human, disease-relevant, compartment-erosion* test: **GSE206704** (5 lines ×
passage, HGPS) and **GSE312031** (HGPS VSMC, P7 vs P14 — a built-in "progression" axis).

Not found, despite searching: any public **Micro-C** dataset with an LMNA perturbation
**[verified absent from a GEO gds search for lamin + Hi-C/HiC; not an exhaustive ENA search]**.

### 2.2 Lamin B1 DamID / ChIP under LMNA perturbation (other than GSE300197)

| Accession | System | Perturbation | Assay | Deposited processed | Size |
|---|---|---|---|---|---|
| **GSE263012** | K562 | **LMNA KO, LBR KO, LMNA/LBR DKO** vs WT | **LMNB1 DamID-seq** (+ Dam controls, RNA-seq, Repli-seq) | **Yes — `*_LMNB1-25kb-combined.bw` per genotype, 1.1–1.7 MB** | 796 MB RAW; bigWigs ~1.7 MB |
| **GSE136252** | hiPSC-CM, hepatocyte, adipocyte | **LMNA T10I and R541C** vs isogenic control | **LAMIN B1 ChIP-seq** + H3K9me2 ChIP + RNA-seq | **Yes — RPGC input-subtracted bigWigs per cell type/genotype** | ~0.5–0.7 GB per bigWig |
| **GSE97095** (SuperSeries) / **GSE153919** | mouse MEFs | shLmnA, shLmnC, shLmnA+C, shLmnb1 vs shLacZ/shLuc | **Dam–lamin B1 DamID-seq** | RAW tar | 155 MB each |
| **GSE190197** | HeLa | Dam-WT vs **Dam-LMNA R527C** | **lamin A DamID-seq** (not lamin B1) | RAW tar | 603 MB |
| **GSE98675** | hESC→endothelial | **lamin A R482W** (FPLD2) | lamin A/C ChIP + RNA-seq **[unverified assay detail]** | not checked | not checked |
| **GSE247771 / GSE247774** | mouse myoblasts | LAP2α loss (redistributes nucleoplasmic lamin A/C) | lamin A/C ChIP-seq | not checked | not checked |
| **GSE268924/268923/268922** | mouse | lamin A/C depletion | SAMMY-seq, ChIP, RNA | not checked | not checked |

**GSE263012 is the single best external replication target for your siLMNA lamin-B1 GC result**: it
is an LMNA *knockout* (not knockdown), human, with ready-made 25 kb LMNB1 bigWigs, and the associated
eLife paper already claims LMNA KO alone barely changes lamina DamID — a sharp, falsifiable contrast
with a GC-graded effect.

---

## 3. REFERENCE PC1 SOURCES (non-cardiac, easily downloadable)

### 3.1 ENCODE "genome compartments" bigWigs (GRCh38) — recommended

1068 released GRCh38 files with `output_type=genome compartments`, 1.3–2.7 MB each
**[record-verified via the ENCODE search API; a ranged GET of one file returned HTTP 206, so the
URLs are open]**. Query template:

```
https://www.encodeproject.org/search/?type=File&output_type=genome+compartments&assembly=GRCh38&limit=all&format=json
```

| Cell type | File | URL |
|---|---|---|
| GM12878 | ENCFF661LPK (2.6 MB, preferred_default) | https://www.encodeproject.org/files/ENCFF661LPK/@@download/ENCFF661LPK.bigWig |
| GM12878 (2nd res.) | ENCFF259AAM (1.4 MB) | https://www.encodeproject.org/files/ENCFF259AAM/@@download/ENCFF259AAM.bigWig |
| IMR-90 | ENCFF547NRM (1.3 MB) | https://www.encodeproject.org/files/ENCFF547NRM/@@download/ENCFF547NRM.bigWig |
| IMR-90 (2nd expt) | ENCFF755CEZ (1.4 MB) | https://www.encodeproject.org/files/ENCFF755CEZ/@@download/ENCFF755CEZ.bigWig |
| K562 | ENCFF456BBV (1.4 MB) | https://www.encodeproject.org/files/ENCFF456BBV/@@download/ENCFF456BBV.bigWig |
| HepG2 | ENCFF545CMV (2.5 MB, *archived*) / ENCFF299NFD (1.4 MB) | https://www.encodeproject.org/files/ENCFF299NFD/@@download/ENCFF299NFD.bigWig |
| HCT116 | ENCFF442FIA (2.5 MB) | https://www.encodeproject.org/files/ENCFF442FIA/@@download/ENCFF442FIA.bigWig |
| A549 | ENCFF575RNT (1.3 MB) | https://www.encodeproject.org/files/ENCFF575RNT/@@download/ENCFF575RNT.bigWig |
| MCF-7 | ENCFF922MKI (2.4 MB) | https://www.encodeproject.org/files/ENCFF922MKI/@@download/ENCFF922MKI.bigWig |
| **heart left ventricle** (tissue; cardiac positive control) | ENCFF835JWK / ENCFF560GQH (1.4 MB) | https://www.encodeproject.org/files/ENCFF835JWK/@@download/ENCFF835JWK.bigWig |

Also available with ≥8 files each: heart right ventricle, right/left cardiac atrium, motor neuron,
HL-60/S4, transverse colon, mammary epithelial cell, ovary, hTERT RPE-1, pancreas, CD4/CD8 T cells,
CD14 monocyte, aorta, dorsolateral prefrontal cortex, psoas muscle, adrenal gland, right lobe of
liver, keratinocyte, Jurkat, Ramos, HAP-1, KBM-7, SK-N-DZ, Panc1, PC-3, GM23248 **[record-verified]**.
Note ENCODE has **no H1 or HFF** GRCh38 compartment file in this set **[verified in the same listing]**.
Bin size is not exposed in the file metadata **[unverified]** — check the bigWig header; the two size
tiers (≈1.35 MB vs ≈2.55 MB) almost certainly correspond to two resolutions.

### 3.2 4DN compartment bigWigs (GRCh38) — for H1 and HFFc6

4DN has 802 `file_type=compartments` files. **The portal `@@download` endpoint returned HTTP 403 for
anonymous requests**, but the public open-data S3 mirror works (ranged GET → HTTP 206)
**[both verified]**:

```
https://4dn-open-data-public.s3.amazonaws.com/fourfront-webprod/wfoutput/<uuid>/<accession>.bw
```

| Cell type | Accession | uuid | Size | Track |
|---|---|---|---|---|
| IMR-90 | 4DNFIHM89EGL | e35d39b7-e5b5-4d29-a510-b10ab91dd7dc | 212 KB | in situ Hi-C MboI, merged reps |
| HepG2 | 4DNFIZ2TEYL4 | f9c766d1-3537-4f1c-9bf2-fa6809a2d5d0 | 212 KB | in situ Hi-C DpnII, merged reps |
| H1-hESC (Tier 1) | 4DNFI8E6IFSN | b35d27b4-0387-4941-aa0c-265b6c6af68b | 322 KB | in situ Hi-C DpnII, Dekker lab |
| HFFc6 (Tier 1) | 4DNFI1YXFNRW | b260c265-da1f-4a53-af32-31f904e3292f | 321 KB | in situ Hi-C DpnII, Dekker lab |
| GM12878 | 4DNFI45JB4MU | 8c217955-9d39-4ec9-8be9-3db9be6c190e | 215 KB | in situ Hi-C NcoI, merged reps |
| K562 (Tier 2) | 4DNFI3OPG4RB | 4d1f3a26-c850-442f-8ad7-2977f99a3689 | 213 KB | in situ Hi-C DpnII, merged reps |

Other 4DN biosources with compartment tracks, useful as lineage comparators: HeLa-S3 (116 files),
HUVEC, **WTC-11 iPSC→cardiogenic mesoderm→primitive cardiac myocyte→cardiac muscle cell** (a full
human cardiac differentiation series, GRCh38), heart left ventricle / left atrium, RUES2,
H1→definitive endoderm, olfactory receptor cell, plus mouse (GRCm38) ESC, cardiac muscle cell,
cerebellar granule neuron d8/d14/d28, thymocyte, Treg **[record-verified]**. The WTC-11 cardiac
series and the mouse CGN series are the natural "matched-lineage" controls for your GM12878 term.
Get any uuid with:
`curl -H 'Accept: application/json' https://data.4dnucleome.org/files-processed/<ACC>/ | jq -r .uuid`.

### 3.3 hg19 options

* **GSE63525 (Rao 2014)**: `GSE63525_GM12878_subcompartments.bed.gz` (31 KB, hg19, A1/A2/B1–B4) at
  https://ftp.ncbi.nlm.nih.gov/geo/series/GSE63nnn/GSE63525/suppl/ **[record-verified]**. Per-cell-type
  PC1 eigenvectors exist only inside the `*_intrachromosomal_contact_matrices.tar.gz` bundles
  (6.5 GB–23 GB) — impractical; prefer the GRCh38 tracks above and lift over, or recompute.
* 3D Genome Browser bulk download page (http://3dgenome.fsm.northwestern.edu/download.html) is listed
  as carrying per-cell-type compartment calls **[unverified — page not opened]**.
* Cardiac baseline for the Bertero cohort itself: GSE106687/GSE106690 (hESC→CM Hi-C time course)
  **[record-verified]**.

### 3.4 Two caveats that bear directly on the screen

1. **Eigenvector sign convention.** PC1 sign is arbitrary per chromosome and is conventionally
   oriented using GC content or gene density. If the ENCODE/4DN compartment tracks were sign-oriented
   by GC (their convention is **unverified**), then "GM12878 PC1" carries a GC-derived sign and your
   two predictors — other-cell-type PC1 and GC — are structurally entangled, over and above their
   genuine biological collinearity. Check the orientation procedure per track, or re-derive PC1
   yourself with a fixed orientation rule and repeat the model with the orientation anchored to gene
   density instead of GC.
2. **Reference choice should be falsifiable.** The prediction "cell-type-specific compartmentalisation
   erodes" implies the coefficient should be similar for *any* sufficiently distant reference cell
   type (K562, HepG2, IMR-90, H1) and should shrink toward zero for a cardiac reference (heart left
   ventricle ENCFF835JWK, or 4DN WTC-11 cardiac muscle cell). Running the same model across the
   ENCODE panel converts a single suggestive coefficient into a shape test, and distinguishes
   "erosion toward a generic GC-driven profile" from "shift toward lymphoblastoid identity
   specifically".

---

## 4. One-line answers

1. **Prior art:** partially, in weaker forms. Bertero 2019 reports the same *direction* as hotspots
   (failure to complete the cardiogenic A→B inactivation) but no GC and no other-cell-type analysis,
   and explicitly denies a global effect; Shah 2021 reports lamina-chromatin disruption enriched for
   non-myocyte lineage genes; McCord 2013 reports genome-wide compartment erosion in progerin cells
   with a gene-poor/gene-rich asymmetry; Lmna−/− ESCs and LMNA-KO LCLs show identity regression
   transcriptionally. The specific continuous claim — other-cell-type PC1 and GC predicting ΔPC1
   after covariate adjustment — was not found in the literature.
2. **Fresh cohorts:** 12 Hi-C series and 7 lamin B1/lamin A ChIP-DamID series listed above; best
   picks GSE164068 (PC1 already deposited), GSE206704 + GSE312031 (HGPS, human, passage axis),
   GSE339018 `d8_lmnaKD`, GSE263012 (LMNB1 DamID in LMNA-KO K562) and GSE136252 (LAMIN B1 ChIP in
   LMNA-mutant hiPSC-CMs).
3. **Reference PC1:** ENCODE `genome compartments` bigWigs (GRCh38, ~1.3–2.7 MB, open) for GM12878,
   IMR-90, K562, HepG2, HCT116, A549, MCF-7 and heart left ventricle; 4DN open-data S3 bigWigs for
   H1-hESC, HFFc6 and the WTC-11 cardiac differentiation series.
