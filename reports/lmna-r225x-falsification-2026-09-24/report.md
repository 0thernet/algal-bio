# Registered follow-up: the LMNA relative-gain panel fails in R225X cardiomyocytes

The ten candidates frozen by the
[relative lamina-gain campaign](../lmna-relative-gain-2026-09-24/report.md)
were tested, unchanged, in an independent public dataset under a protocol that
was reviewed and frozen before any outcome value was opened. **None of the ten
passed.** The cross-context prediction that these genes are strongly repressed
whenever lamin A/C is lost in human cardiomyocytes is retired. This is a complete
negative result, retained in full, not a partial or exploratory one.

## Design

- **Dataset:** [GSE126458](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE126458),
  Bertero et al. 2019. Day-14 hiPSC-derived cardiomyocytes: one LMNA R225X
  patient line, two separately corrected isogenic clones (R225R clone 15 and
  clone 38), three independent differentiations per line. The deposited
  Cuffnorm FPKM matrix has nine sample columns.
- **Selection before data access:** a metadata-only audit of seven candidate
  datasets (five with metadata receipts) ([`data-audit/eligibility.md`](data-audit/eligibility.md)) chose
  GSE126458 as the only cohort with explicit independent culture units, a
  per-sample matrix, and two separate corrected-clone contrasts. GSE136252 was
  excluded for unresolved clone/batch mapping; GSE164065 for contradictory
  genotype labels; GSE185620 measures mouse translating RNA; GSE120836 is
  confounded whole-heart tissue.
- **Fixed family:** CMTM5, SLC2A14, NID2, DCAF8, PIANP, MEX3B, ANKRD52, ZFTA,
  FYCO1, LYSMD3, mapped to Ensembl identifiers from the deposited annotation
  columns before outcomes. ZFTA was mapped through its prior symbol C11orf95
  using the HGNC rename notice.
- **Test:** for each corrected clone separately, Δ = mean log2(FPKM+0.5) in the
  mutant minus the corrected clone. One-sided Welch threshold test of
  H0: Δ ≥ −0.5. Family p is the maximum over the two clone comparisons. Holm
  correction over all ten genes. Passing also required negative contrasts in
  every leave-one-culture-out combination and Δ ≤ −0.5 at pseudocounts 0.1 and
  1.0. Genes failing the frozen expression rule (FPKM ≥ 1 in at least two of three
  cultures and mean FPKM ≥ 1 in each corrected clone) kept p = 1 and family
  membership.
- **Independent pre-outcome review:** a pre-outcome review lane (recorded as
  `falsification_design`) verified the code
  against SciPy on 250 synthetic cases, checked the Holm oracle, the intersection
  rule, and the intake guards, and required three repairs before freeze
  ([`design/independent-review.json`](../../campaigns/lmna-r225x-falsification-2026-09-24/design/independent-review.json),
  [`design/skeptical-review.md`](../../campaigns/lmna-r225x-falsification-2026-09-24/design/skeptical-review.md)).

## Outcome

| Gene | Status | Δ vs clone 15 | Δ vs clone 38 | Family p | Holm p | Pass |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| CMTM5 | ineligible (FPKM < 1) | +0.053 | −0.448 | 1.000 | 1.000 | no |
| SLC2A14 | ineligible (FPKM < 1) | +0.603 | +0.865 | 1.000 | 1.000 | no |
| NID2 | evaluable | +0.756 | +0.452 | 0.972 | 1.000 | no |
| DCAF8 | evaluable | +0.150 | −0.059 | 0.990 | 1.000 | no |
| PIANP | ineligible (FPKM < 1) | −0.695 | −0.051 | 1.000 | 1.000 | no |
| MEX3B | evaluable | −0.318 | −0.383 | 0.703 | 1.000 | no |
| ANKRD52 | evaluable | +0.045 | +0.092 | 0.992 | 1.000 | no |
| ZFTA | evaluable | −0.136 | −0.295 | 0.968 | 1.000 | no |
| FYCO1 | evaluable | −0.416 | −0.318 | 0.819 | 1.000 | no |
| LYSMD3 | evaluable | −0.109 | −0.152 | 0.952 | 1.000 | no |

Δ is the primary contrast in log2(FPKM+0.5) units. Full per-culture values,
standard errors, degrees of freedom, leave-one-out and sensitivity contrasts are
in [`results/summary.json`](results/summary.json); the compact table is
[`results/outcomes.tsv`](results/outcomes.tsv).

The two genes that had survived the earlier H222P direction check behave
differently here. LYSMD3 is expressed and evaluable, and its contrasts are
small and negative in both clone comparisons (about −0.1 to −0.15), far from the
registered 0.5 threshold. CMTM5 is below the expression floor in the corrected
clones, so it is ineligible rather than refuted; its low counts were already the
stated weakness of the earlier check. Two of the three genes with the largest earlier
discovery RNA decreases (SLC2A14, NID2) move in the opposite direction here.

## Interpretation and claim boundary

- The fixed prediction failed. Under the frozen failure policy, the specific
  cross-context large-repression claim is retired for every gene in the panel.
- The original GSE300197 observations remain as recorded context-specific
  exploratory results after acute siRNA depletion at day 35. Failure at day 14
  in a truncating patient mutation does not erase them; it shows they do not
  generalize under this protocol.
- This result does not show that these genes are unaffected by lamin A/C in
  every context. n = 3 cultures per line, one patient background, FPKM rather
  than counts, and an approximate Welch model bound what a null here means.
- No candidate was replaced, no threshold was loosened, and no analysis was
  rerun with different rules after the outcome was seen. A second run from the
  same frozen inputs reproduced both output files byte for byte
  ([`reproduction.json`](reproduction.json)).

## Prior-art correction carried by this record

The table-aware audit in [`prior-art/report.md`](prior-art/report.md) found
mouse Lysmd3 in main Table 1 of Kubben et al. 2012 (PMC3443488) as a shared
lamin-A/progerin promoter target in embryonic fibroblasts. The earlier audit's
statement that the main text did not name the gene was wrong; the retained
capture already contained the row. The earlier report and
`novelty-audit.json` are corrected in this same change. This retires any claim
that LYSMD3 is a newly identified lamin-related gene, independently of the
expression outcome above.

## Execution record

- Registration frozen 2026-09-24T17:05:31Z (`freeze.json`); matrix downloaded
  17:06:46Z (`intake.json`); outcomes computed in the same session immediately
  afterwards (no artifact records the outcome time). Not an external timestamp.
- Public input: one 616,733-byte gzip matrix from NCBI GEO, hash-bound in the
  campaign `sources.json`; kept outside Git.
- Spend: $0 new provider or compute spend. Cumulative campaign spend remains
  $0.019722 against a $25 ceiling.
- No hosted Sponge write, no model-generated code executed, no collaborator
  contacted. Sharing material for a domain scientist has not been sent.

## Decision

Do not carry this panel forward as a discovery lead. Any next study must be a
new registration on data not yet opened, with a prespecified family and effect
threshold, rather than a rescue of these genes. The retained evidence suggests
that ranked-gene screens on condition-aggregate lamina tracks without replicate
variance produce leads that do not survive an independent culture test; a next
design should start from a question with replicate-level evidence on both sides.
