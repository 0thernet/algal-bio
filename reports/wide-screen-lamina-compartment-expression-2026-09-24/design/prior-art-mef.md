# Prior art before the mef/ registration (GSE124205), 2026-09-25

Independent read-only literature lane (Devin subagent, background; literature, GEO text and preprints only; no GSE124205, GSE97095, GSE153919 or GSE97092 data file was opened). Recorded before the mef/ freeze. Verbatim report below; citations and quotes are the subagent's and were not re-verified line by line unless marked in the protocol.

## Verdict: PARTIALLY_KNOWN

No source found states a *continuous* GC gradient of lamina-contact change after lamin A/C loss with adjustment for baseline contact and gene density. However, the categorical shadow is now documented in a second, independent prior paper beyond Shen 2026: **Shah et al. 2021, Cell Stem Cell** (same Jain lab lineage as the GSE300197 discovery paper) reports that LADs lost in LMNA-mutant cardiomyocytes are gene-rich, transcriptionally active, and low in baseline LMNB1 contact — i.e., the same covariate bundle the proposed test adjusts for. Separately, the two Reddy-lab papers covering GSE124205/GSE153919 report **no detectable change at all** in Dam-LaminB1 DamID after lamin A/C knockdown in MEFs — an important framing/threat result, not prior art for the gradient itself.

**Correction to the registration metadata:** PMID 34775987 is **Wong et al. 2021, Genome Biology 22:305** ("Lamin C is required to establish genome organization after mitosis," DOI 10.1186/s13059-021-02516-7), which is the **GSE153919** paper (shA/shC/shAC/shB1 MEFs). The GSE124205 series is associated with the Luperchio/Reddy bioRxiv preprints 10.1101/481598 ("The repressive genome compartment…", 2018) and 10.1101/122226 ("Chromosome Conformation Paints…", 2017); I found no peer-reviewed version of 481598.

## Q1 — Luperchio/Reddy (GSE124205): lamin A/C KD and drug effects on DamID

- Lamin A/C KD: *"Surprisingly, even complete knockdown of Lamin A/C does not result in an altered LAD profile by DamID (Figure 4A), in agreement with previous studies on ES cells."* Single-cell conformation paints revealed disorganization invisible to ensemble DamID. (bioRxiv 10.1101/122226, Luperchio, Sauria, Wong, Gaillard, Yamada, Taylor, Reddy 2017; same shAC MEF DamID libraries as GSE124205 [unverified that identical text appears in 481598]).
- Drugs: *"Disruptions using DZNep and BIX01294 displayed 93% to 96% overlap of LAD organization with non-treated cells. TSA treatment showed modestly more derangement, with 86% overlap… LAD disruption in TSA conditions appears to occur over regions that displayed low lamina signal in untreated cells, suggesting that these regions are more susceptible to disruption."* — a **LAD-strength (weak-LAD) dependence** for TSA, not a GC analysis.
- No GC content, AT content, CpG density, or gene-density analysis of the DamID *changes* appears in the retrievable text; analysis axes are chromatin state (H3K9me2/3, H3K27me3) and LAD-vs-non-LAD organization.

## Q2 — Harr et al. 2015 JCB and GSE153919 (Wong et al. 2021)

- Harr et al. 2015 (DOI 10.1083/jcb.201405110, PMID 25559185): *"Knockdown of YY1 or lamin A/C, but not lamin A, led to a loss of lamina association"* for TCIS-inserted lamina-associating sequences (LASs) from **fibroblast-specific variable LAD (vLAD) borders**, and endogenous vLAD loci depended on lamin A/C, YY1, H3K27me3, H3K9me2/3. This is a **LAD-subtype dependence** (variable LAD borders, YY1-motif-rich, GC-rich motifs — though the paper never analyzes GC/AT content itself). [unverified: no GC/CpG statement found; none seen in available full-text excerpts]
- Wong et al. 2021 (GSE153919): Dam-LMNB1 DamID-seq in shA/shC/shAC/shB1 MEFs — *"these analyses revealed no significant differences in cells depleted of both lamin A and lamin C compared to wild-type cells… LAD boundaries also remained intact under all four conditions; genome-wide comparisons between log2 ratios of DamID-seq signals were virtually ind[istinguishable]."* Effects were only visible by FISH/lacO assays (lamin C, not lamin A, required). No GC/AT analysis found.

## Q3 — Other prior art

- **Shah et al. 2021, Cell Stem Cell 28:938 (DOI 10.1016/j.stem.2020.12.016, PMID 33529599)** — strongest new prior art. Pathogenic LMNA variants (T10I, R541C) in hiPSC-CMs: *"Disrupted regions were enriched for transcriptionally active genes and regions with lower LAMIN B1 contact frequency"*; *"deciles of LADs with the highest gene density were enriched for control-only LADs [lost in mutant], whereas deciles with low-gene-density LADs were enriched for shared LADs."* Gene-rich, weakly-lamina-bound LADs preferentially lose contact — a categorical, unadjusted version of the claim, by the same institute group as Shen 2026.
- **Amendola & van Steensel 2015, EMBO Rep (10.15252/embr.201439789)**: lamin triple-KO mESCs — Dam-Emd maps "virtually indistinguishable" from WT; lamins dispensable for LAD organization (scope precedent for null DamID results, not GC).
- **Meuleman et al. 2013** (already in prior note): cLADs are AT-rich; fLADs adhere to the "A/T rule" in ESCs but not differentiated cells — steady-state composition gradient, not LMNA perturbation.
- **Zheng et al. 2018 Mol Cell**, **eLife 10.7554/eLife.99116**, **van Schaik et al. 2025 NAR gkaf964**, **Martin et al. 2025 Genome Res** (T1/T2-adjacent), **van Schaik et al. EMBO Rep 202050636** (cell-cycle detaching LADs not weaker at baseline) — all covered in the prior note; none reports a GC-graded LMNA-loss effect.
- General-variability literature (fLADs GC-richer/gene-richer than cLADs; T2-LADs intermediate/gene-richer — Manzo et al. 2023 Genome Biol 10.1186/s13059-023-02849-5) describes the *correlate* (GC/gene-rich ↔ weak/variable lamina contact) without the LMNA-loss causal claim.

## Q4 — Technical GC bias in DamID/pA-DamID

- Standard correction is the **Dam-only normalization**: *"In conventional DamID, m6A maps obtained with a Dam-fusion protein are typically normalized to a Dam-only control. This is done to correct for local variation in chromatin accessibility and for possible biases in PCR amplification or sequencing"* (van Schaik et al., EMBO Rep 2021, DOI 10.15252/embr.202050636). This corrects library-level amplification bias *only if* the Dam-only control shares the same PCR/sequencing GC response — the GSE277503 within-genotype rho +0.61 observation suggests residual inter-library GC structure that the ratio does not remove [inference, unverified in literature].
- Luperchio/Reddy pipeline normalized Hi-C for GC content via HiFive binning, but the DamID arm is reported as log2(Dam-LMNB1/Dam) with LADetector segmentation; no explicit GC normalization of the DamID signal is described in retrieved text [unverified].

## Gaps

- bioRxiv 481598 full text not read directly; quotes for shAC/drug DamID come from the sibling preprint 10.1101/122226 (same lab, same samples). GEO pages CAPTCHA-blocked (per prior note).
- Harr et al. 2015 full text accessed via JCB/search excerpts; a GC statement in its body cannot be fully excluded.
- Whether Wong et al. 2021 or Luperchio contain supplementary GC analyses of LAD boundaries: no hits, but supplementals not fully searched.

## URLs consulted

- https://doi.org/10.1101/122226 and https://www.biorxiv.org/content/10.1101/122226v1.full.pdf
- https://bxlab.github.io/conformation-paints-2017/
- https://datamed.org/dataset/5394956
- https://seqout.org/s/GSM3525687 and https://seqout.org/s/GSM3525677
- https://pmc.ncbi.nlm.nih.gov/articles/PMC8591896/ and https://link.springer.com/article/10.1186/s13059-021-02516-7
- https://genomebiology.biomedcentral.com/counter/pdf/10.1186/s13059-021-02516-7.pdf
- https://doi.org/10.1083/jcb.201405110, https://pubmed.ncbi.nlm.nih.gov/25559185/, https://pmc.ncbi.nlm.nih.gov/articles/PMC4511709/, https://www.nature.com/articles/nrm3948
- https://pmc.ncbi.nlm.nih.gov/articles/PMC8106635/, https://doi.org/10.1016/j.stem.2020.12.016, http://www.cell.com/article/S1934590920306007/pdf
- https://www.embopress.org/doi/pdf/10.15252/embr.201439789
- https://link.springer.com/article/10.15252/embr.202050636
- https://doi.org/10.1093/bioinformatics/btv386, https://www.nki.nl/research/research-groups/bas-van-steensel/our-technologies/damid-and-pa-damid
- https://link.springer.com/article/10.1186/s13059-023-02849-5
- https://pmc.ncbi.nlm.nih.gov/articles/PMC6719452/
- https://doi.org/10.1101/gr.141028.112
