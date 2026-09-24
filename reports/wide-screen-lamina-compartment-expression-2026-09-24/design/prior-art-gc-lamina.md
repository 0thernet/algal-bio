# Prior art: GC dependence of lamina-contact change after lamin A/C vs LBR loss

Date: 2026-09-24. Method: web search + reading only. Each claim marked VERIFIED (quote + DOI/PMID) or UNVERIFIED.

## Result under test

After LMNA loss, change in lamin B1 contact is negatively related to GC content (GC-rich loses lamina contact), rank-partial for baseline LMNB1 and gene density, 500 kb tiles, Spearman rho ~ -0.25; found in acute siLMNA (GSE300197) and replicated in LMNA-KO K562 pA-DamID (GSE263012). LBR KO and LMNA/LBR DKO show rho ~ +0.3.

## Q1. What paper is GSE263012, and what does it report?

**VERIFIED — identity.** GSE263012 belongs to Belmont-lab work published as *"Major nuclear locales define nuclear genome organization and function beyond A and B compartments"*, eLife 2025 (preprint: bioRxiv 2024.04.23.590809). PMID 40279158; DOI 10.7554/eLife.99116. GEO description: "K562 LMNA, LBR, and LMNA/LBR DamID-seq, Repli-seq, and RNA-seq raw and processed data." (Accession string appears in the paper's data availability; retrieved via search indexing of the bioRxiv/eLife record — the GEO page itself was CAPTCHA-blocked.)

**VERIFIED — LMNA KO vs LBR KO vs DKO.** Quote: "Whereas the LMNA KO shows little change in lamina DamID from K562 wild-type (wt) or the parental clone, the LBR KO and the LMNA/LBR double knockout (DKO) lines show similar but partial reduction in the lamina DamID for most LADs and increases for some iLADs." (bioRxiv 2024.04.23.590809 / eLife 10.7554/eLife.99116)

**VERIFIED — direction of DKO movement by subtype.** Quote: "most LADs in DKO cells decrease their interaction and relative proximity with the lamina and increase their proximity to nucleoli"; and "most p-w-v-fiLADs instead increase their lamina association while decreasing their proximity to nucleoli." Same source. The paper frames this as H3K9me3-enriched regions moving to nucleoli while H3K27me3-enriched regions move to the lamina.

**VERIFIED — LAD subtypes / marks / replication timing are covered.** cLADs, fLADs, fiLADs (peak-within-valley vs valley); four LAD clusters C1 H3K9me3, C2 H3K27me3, C3 H3K9me2/H2A.Z, C4 low-mark; LADs late-replicating, p-w-v fiLADs mid-to-late, iLADs early. Same source.

**VERIFIED (negative) — no sequence-composition analysis.** Two independent full-text reads of bioRxiv 2024.04.23.590809 returned no occurrence of GC content, AT content, AT-rich, GC-rich, isochore, or gene density. So the GSE263012 paper does **not** report the result or a stated equivalent, and its own headline for LMNA KO ("little change") is the opposite emphasis from a systematic GC-graded LMNA effect.

## Q2. Does Shen et al. 2026 (GSE300197) report a GC dependence?

**VERIFIED — identity.** Shen KM, Shields EJ, Barka V, Karnay A, Kurzlechner LM, Yang JD, Wang Q, Lee BW, Suay-Corredera C, Nguyen SC, Joyce EF, Margulies KB, Prosser BL, Shah PP, Jain R. *"The cytoskeleton contributes to abnormal genome-lamina interactions in LMNA-deficient cardiomyocytes."* J Cell Biol 2026; DOI 10.1083/jcb.202506137; PMID 41891953. GSE300197 is listed in its data availability. Note: the system is siLMNA in hiPSC-derived **cardiomyocytes**, not undifferentiated iPSCs — worth correcting in the result statement.

**VERIFIED — a CpG/gene-density signature is reported.** Quote: "LMNA-sensitive LADs were less enriched for chromatin modified by H3K9me3, typically associated with transcriptional repression, demonstrated higher CpG density, and were flanked by regions of higher transcriptional activity compared to LMNA-insensitive LADs." Also quoted: "lower LMNB1 enrichment in siScr hiPSC-CMs compared to LMNA-insensitive LADs...smaller in size"; and for the preserved class, "LADs enriched for heterochromatin features and higher LMNB1 occupancy were preserved...lower gene density, and lower transcriptional activity." There is a quantified panel: "CpG density across the LAD body for LMNA-insensitive or LMNA-sensitive LADs. Statistical comparisons by Welch two-sample t-test, ****=p<0.0001." (DOI 10.1083/jcb.202506137)

**VERIFIED (negative) — no genome-wide GC correlation.** The full-text read found no genome-wide correlation between GC content and change in lamin B1 DamID, no use of "GC content"/"AT-rich"/"isochore", and no rank-partial adjustment for baseline LMNB1 and gene density. The reported statistic is a two-class t-test on CpG density, and baseline LMNB1 difference is reported as a *co-feature* rather than adjusted away.

**Interpretive note (UNVERIFIED inference, not a literature claim):** CpG density and GC content are strongly coupled at 500 kb scale, so the Shen CpG result is a categorical, unadjusted shadow of the continuous GC claim in the same dataset.

## Q3. Other prior art on lamin A/C vs LBR tethering different sequence classes

- **Meuleman et al. 2013, Genome Res 23:270. VERIFIED.** Quotes: "cLADs are universally characterized by long stretches of DNA of high A/T content" and "The spatial organization of mammalian genomes is highly conserved and tightly linked to local nucleotide composition." DOI 10.1101/gr.141028.112; PMID 23124521. Establishes the AT-rich baseline for constitutive LADs — i.e. that base composition grades lamina association at steady state — but says nothing about LMNA or LBR perturbation.
- **Solovei et al. 2013, Cell 152:584. VERIFIED (identity and the two-tether claim).** DOI 10.1016/j.cell.2013.01.009; PMID 23374351. Establishes LBR and lamin A/C as sequential, developmentally staged tethers with inverse effects on differentiation, and that losing both inverts nuclear architecture. **UNVERIFIED:** I found no sentence in this paper assigning the two tethers different *sequence* (GC/AT) classes; the search-engine paraphrase "LBR mediates constitutive heterochromatin tethering to AT-rich domains" could not be traced to a quotable sentence and should be treated as absent.
- **Zheng et al. 2018, Mol Cell 71:802 (lamin TKO mESC). VERIFIED (negative).** Full-text read found no GC/AT/gene-density statement about detached vs retained LADs. Detached LADs are distinguished by chromatin state instead: "The HiLands-B and -P divide LADs into distinct chromatin states with HiLands-P covering a longer stretch of chromatin and having higher lamin-B1 DamID values but lower H3K27me3 than HiLands-B." DOI 10.1016/j.molcel.2018.05.017; PMID 30201095. The detaching class (shorter, lower DamID, higher H3K27me3) is the same *kind* of class as Shen's LMNA-sensitive LADs, described without sequence composition.
- **Chang et al. 2022, Protein Cell 13:258 (lamin B1). VERIFIED (scope only).** B-type lamin depletion partially detaches LADs with minimal effect on non-LAD regions. DOI 10.1007/s13238-020-00794-8. Not an LMNA-vs-LBR sequence contrast.
- **T1/T2 LAD subtypes (Manzo/van Schaik lineage of work). PARTIALLY VERIFIED.** The current published statement of LAD subtypes I could verify is Martin CJ, Oser EA, Nagarajan P, Popova LV, Sunkel BD, Stanton BZ, Parthun MR, *"Distinct classes of lamina-associated domains are defined by differential patterns of repressive histone methylation,"* Genome Res 2025; DOI 10.1101/gr.280380.124; PMID 40764057. **VERIFIED (negative):** no mention of GC content, AT content, isochore or CpG; it does state "gene density is highest in K27me3 LADs" and describes "small, more gene-rich LADs" enriched in H3K27me3; it does **not** differentiate mechanistic dependence of LAD classes on lamin A/C vs LBR. The T1/T2 description (T1 = high LMNB1/H3K9me2, late-replicating, gene-poor; T2 = intermediate LMNB1, accessible, replication-timing-transition, gene-rich, H3K27me3-bordered) is **UNVERIFIED** at quote level — I could not retrieve a quotable primary sentence with DOI in this pass.
- **van Schaik et al. 2025, Nucleic Acids Res 53:gkaf964 (TOP2B and LBR). VERIFIED.** DOI 10.1093/nar/gkaf964. Reports bidirectional LBR-loss effects: "220 LADs significantly losing interactions with LMNB2" and "Three hundred LADs increased their NL association upon LBR loss", plus LAD/iLAD inversion on TOP2B+LBR co-depletion. Base composition appears only as a control caveat — "LADs are generally AT-rich" — not as an analysis axis, and there is no LMNA comparison beyond noting LBR acts "in synergy with the NL component lamin A."

**Is the opposite GC direction of LMNA vs LBR loss already stated?** **VERIFIED (negative) across all sources read above:** no paper found states a GC- or AT-graded change in lamina contact for LBR loss, and none contrasts the sign of such a relation between LMNA loss and LBR loss.

## Q4. Verdict

**PARTIALLY_KNOWN.**

- **Known part:** the LMNA arm. That the regions losing lamina contact after lamin A/C reduction are the CpG-dense, gene-rich, H3K9me3-poor, weakly-lamina-bound LADs is stated by Shen et al. 2026 in the very dataset (GSE300197) the result is derived from. A referee will see a GC-graded LMNA effect as a restatement of that figure on a continuous axis.
- **Novel parts (no prior statement found):** (a) the continuous, genome-wide GC gradient at 500 kb with rank-partial adjustment for baseline LMNB1 and gene density — the adjustment matters precisely because Shen's sensitive class is confounded with low baseline LMNB1; (b) the K562 LMNA-KO replication, which runs against the GSE263012 paper's own framing that LMNA KO shows "little change"; (c) the **sign reversal** for LBR KO and LMNA/LBR DKO. (c) is the strongest novelty claim — nothing found reports GC dependence of LBR-loss effects at all, in either direction.

**Single closest prior statement:** Shen et al. 2026, J Cell Biol, DOI 10.1083/jcb.202506137 — "LMNA-sensitive LADs were less enriched for chromatin modified by H3K9me3, typically associated with transcriptional repression, demonstrated higher CpG density, and were flanked by regions of higher transcriptional activity compared to LMNA-insensitive LADs."

## Open verification gaps

1. GEO pages for GSE263012 and GSE300197 were not read directly (NCBI CAPTCHA); accession-to-paper mapping rests on search indexing plus the papers' data-availability statements as reported by full-text reads.
2. Solovei 2013 and the Cell Reports 2025 lamin-KO paper (DOI in PMID 41205174) are paywalled to WebFetch (403); only abstract-level content verified. A GC/AT statement inside Solovei 2013's body text cannot be excluded.
3. The T1/T2 LAD primary source needs a direct quote before being cited as prior art.
