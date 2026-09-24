# Independent review of the LMNA follow-up

Review date: 2026-09-24. Scope: existing public report, frozen registration,
`analysis.py`, `corroborate.py`, published metadata, and primary methodological
sources. No new expression matrix was opened, downloaded, or evaluated by this
reviewer. No paid call or repository edit was made.

## Actionable verdict

Run one registered falsification of the **original ten-gene panel** in
GSE126458. Do not focus the inferential family on only the two H222P survivors.
The ten-gene calculation costs essentially the same, preserves the original
selection, and allows an honest record of context dependence. Use independent
differentiations, two separate corrected-clone contrasts, a minimum 0.5 effect
on the declared log-expression scale, and Holm correction over all ten original
hypotheses. This is a test of a line-level expression prediction. It cannot
establish new lamin binding, causal repression, a general LMNA effect, or
mechanistic novelty.

The proposed two-variant analysis in GSE136252 must remain descriptive until
sample units and comparable raw measurements are resolved. The coordinating
data-audit lane reports missing clone/differentiation identifiers, inconsistent
replicate counts between manuscript and GEO, and raw counts unavailable for one
variant. I did not independently resolve those issues; this review does not
authorize an inferential workaround.

## Existing result and code assessment

No concrete arithmetic or selection defect was found by inspection. The count
contrasts, seven leave-one-column-out contrasts, median-ratio sensitivity,
strand-aware TSS windows, common finite-base averaging, top-decile threshold,
fixed ranking/spacing, and exact-symbol external evaluation match the frozen
registration. This review is code inspection, not an independent rerun of all
results. The existing interval-oracle and synthetic-test receipts remain the
numerical validation evidence.

Four scientific features sharply limit what follows from those computations:

1. The external gate (`corroborate.py`, `evaluate_candidates`) tests direction
   and leave-one-out stability, without testing uncertainty or a minimum effect.
   LYSMD3's external contrast is approximately −0.092 log2 CPM; CMTM5's control
   and case means are approximately 0.114 and 0.050 CPM. Their gate passage does
   not establish a practically large or statistically supported difference.
   A 2/9 sign-and-stability success count is not itself evidence of enrichment;
   the null success probability for that composite gate was never calibrated.
2. Selection on a large gain and a negative difference-in-differences is
   mathematically dependent. With G = LMNA-effect in mCh and R = LMNA-effect in
   DNKASH, the interaction is I = R − G. Therefore
   Cov(I,G) = Cov(R,G) − Var(G). Even when R and G are unrelated, selecting large
   G favors negative I. The report already acknowledges this correctly.
3. The four smoothed condition-level z-score tracks have no replicate variance
   and no absolute calibration. Neighboring windows and alternate window widths
   share data; they are not independent replications. The tiny class effect and
   circular-shift diagnostic cannot support a general biological mechanism.
4. Holding one library out leaves most of the same libraries in every contrast.
   These are sensitivity checks, not seven or twelve independent confirmations.
   The biological units in GSE300197/GSE304575 remain unresolved.

The report's wording that a future study should repeat candidate selection
should not be implemented as replacement after external failure. The next
falsification must carry the exact existing panel and retain all prior outcomes.

## Current novelty status

CMTM5 already has lamin-A interaction prior art. The coordinating prior-art
lane has now located LYSMD3 in Table 1 of the 2012 lamin-A/progerin promoter
mapping study (PMC3443488). That retires a broad claim that LYSMD3 is a newly
identified lamin-related gene. The precise follow-up claim would instead concern
relative expression of a named gene in particular cardiomyocyte models.
Any claim that this association is previously unreported needs its own alias,
supplement, and dataset audit. A lack of search hits cannot prove absence.

The proper evidence ladder is:

| Claim | What can support it here |
| --- | --- |
| Reproducible computational observation | Fixed inputs/code and independent numerical reproduction |
| Cross-context expression association | Qualified independent cultures, predeclared contrasts, uncertainty/effect threshold, retained discordances |
| Previously unreported association | Bounded documented prior-art review plus qualified language; no universal proof of novelty |
| LMNA causes the target change | Appropriate independent clone/background controls and a causal experimental design |
| Lamina recruitment represses this gene | Orthogonal locus-position/occupancy evidence and perturbation/rescue that separates the proposed pathway |
| New biological mechanism | Independent experimental validation and exclusion of credible competing mechanisms |

## Why this dataset and endpoint

[GSE126458](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE126458)
describes an R225X mutant line, two separately corrected isogenic lines, and
three biological replicates from independent differentiations per line. It
provides a per-sample FPKM table. It is independent of the original acute siLMNA
discovery and H222P check. Two correction contrasts reduce reliance on a single
edited clone, but one mutant clone still prevents generalizing a line difference
to every LMNA genotype or genetic background.

FPKM values are not raw counts. They must not be passed to DESeq2, edgeR count
models, or voom as if they were integer observations. The proposed small-sample
Welch analysis is a transparent model of transformed expression across cultures.
It trades the stronger count/precision model available from raw sequencing for
a bounded, inexpensive falsification. The [DESeq2 paper](https://doi.org/10.1186/s13059-014-0550-8)
explains why count variability and small replicate numbers require explicit
modeling. The [TREAT paper](https://doi.org/10.1093/bioinformatics/btp053)
supports testing a minimum effect rather than filtering a zero-effect p-value
afterward; it does not validate this particular FPKM/Welch model.

## Consequence for continued discovery work

If all ten fail the fixed prediction, retire this large-effect cross-context
claim. Preserve the negative result and start any next hypothesis as a new
registered study with untouched evaluation data. Do not keep loosening thresholds,
substituting datasets, normalizations, genes, or cell types until something passes.
If a gene passes, prioritize raw-count reanalysis and independent biological
validation before treating it as a result ready for a mechanistic claim.

A potentially more informative later project is a registered comparison of
lamina/chromatin effects across perturbation contexts, rather than another
ranked-gene fishing exercise. Public GSE120838 includes human cardiac RNA and
LMNA ChIP with five control and five LMNA-DCM donors, but disease severity and
genotype are confounded, and processed ChIP outputs are limited. GSE164065 is
mechanistically closer to acute depletion, but its title/characteristic mismatch
must be resolved. Neither is an automatic substitute after a failed test.

This one bounded follow-up is justified. An instruction to continue until a
positive result is not a statistical stopping rule or evidence of novelty.
