# Proposed fixed-panel R225X falsification

Status: review-ready proposal; not an executed or externally timestamped
preregistration. Freeze the exact intake mapping, code, input identities and
rules before opening any GSE126458 expression values. Existing siLMNA and H222P
results have already been seen and remain part of the evidence record.

## Question and fixed family

For each original candidate, is log-transformed expression in the R225X mutant
line lower by more than 0.5 units than in **each** of two independently corrected
clones, reproducibly across the deposited differentiation cultures?

The family remains exactly ten: CMTM5, SLC2A14, NID2, DCAF8, PIANP, MEX3B,
ANKRD52, ZFTA, FYCO1, LYSMD3. The primary error threshold is 0.05 with Holm over
ten gene hypotheses. This is the first formal test of this exact family in this
dataset; it does not retroactively turn the prior exploratory campaign into a
confirmatory one. Further searching would require new untouched data and a
separate, transparently tracked testing plan.

## Intake gates

- Admit GSE126458's nine individual samples: three mutant, three corrected-clone
  1, three corrected-clone 2. Document the mapping from GEO identities to every
  expression column before outcomes. A suffix such as `rep1` alone does not
  establish matching across lines.
- Verify each observation is a distinct differentiation culture, not another
  sequencing run or library of one culture. If the source record contradicts the
  deposited matrix or independence cannot be established, retain descriptive
  results only. If documented paired batches exist, do not use the independent
  Welch protocol; freeze a revised block-aware model before outcomes instead.
- Verify that matrix values are finite, nonnegative per-sample FPKM, not log
  FPKM, summary estimates, or normalized count labels. Do not round to counts.
  No outcome-based sample exclusion, outlier removal, or column relabeling.
- Resolve exact unique gene identities before evaluation. A frozen authoritative
  identifier crosswalk may identify the same original gene. No alias switch or
  duplicate-row selection after seeing expression; missing/ambiguous genes are
  non-evaluable and retain family membership.
- Hash all files and dependency pins. Preserve the original ten-gene freeze.
  Evaluate only these identities; genome-wide candidate replacement is forbidden.

## Eligibility and contrasts

For each corrected clone separately, require FPKM ≥ 1 in at least two of its
three cultures and mean FPKM ≥ 1. Both corrected clones must qualify. Ineligible genes have
inferential p = 1 and a visible low-expression status, not a shortened family.

Primary transformed values are y = log2(FPKM + 0.5). For j in {1,2}, define
Δj = mean(y_mutant) − mean(y_corrected_j). This is a difference in expected
transformed abundance, not an exact log2 ratio of mean FPKM and not an absolute
transcription measure. The 0.5 threshold is a prioritization criterion selected
before this observation; it is not a known biological threshold for these genes.

Use sample variances with ddof = 1 and nM = nC = 3:

    A = sM² / 3
    B = sCj² / 3
    SEj = sqrt(A + B)
    νj = (A + B)² / (A² / 2 + B² / 2)
    tj = (Δj + 0.5) / SEj
    pj = StudentT_CDF(tj, νj)

This tests H0j: Δj ≥ −0.5 against H1j: Δj < −0.5. A formula oracle is
`scipy.stats.ttest_ind(y_mutant + 0.5, y_corrected_j, equal_var=False,
alternative="less")`. That added 0.5 is the hypothesis threshold, separate from
the 0.5 inside the logarithm. Freeze Python/SciPy versions. The official
[SciPy t-test documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ttest_ind.html)
defines independent unequal-variance and one-sided options.

If either group has zero variance, or a statistic is nonfinite, mark the
contrast non-evaluable and set its p to 1. A single constant group with positive
variance in the other group has a mathematically defined Welch statistic, but
the admitted protocol conservatively excludes it from promotion. Do not invent
epsilon variance.

The gene-level intersection–union p-value is max(p1,p2), because the proposed
claim requires both correction contrasts. The shared mutant cultures create
dependence but do not invalidate this max-p combination. Holm across ten also
does not require between-gene independence if each input p-value is valid:
sort all ten p values, multiply the kth smallest by (11−k), apply a cumulative
maximum and clip to 1, then map back to the original identities. Missing,
ineligible and undefined results contribute p = 1.

The inferential guarantee is conditional on the data model. Welch's small-sample
p-values are approximate and depend on independent cultures and approximately
normal within-line log expression. With n = 3, those assumptions cannot be
established empirically. Therefore report “model-based Holm-adjusted p”, never
“proof” or unconditional verified FWER. An exact two-group permutation test with
3+3 observations has only 20 allocations and a minimum one-sided p of 0.05;
it cannot pass the first Holm threshold of 0.005 for ten genes. Do not choose a
different test after seeing which gives significance.

## Promotion rule, frozen before execution

A candidate passes this **computational follow-up** only if all hold:

1. Both clone-specific primary contrasts are ≤ −0.5 and the max-p gene result
   has Holm-adjusted p ≤ 0.05.
2. Every leave-one-culture-out primary contrast remains negative for both
   correction comparisons. These are sensitivities, not independent tests.
3. Recomputing only effect estimates with pseudocounts 0.1 and 1 leaves **both**
   clone contrasts ≤ −0.5 at each pseudocount. These cannot rescue a primary
   failure, change the p-value, or identify a replacement gene.
4. The independent numerical reviewer confirms input mapping, transform,
   threshold direction, variances, max-p combination, Holm m = 10, missingness,
   and all previous H222P results in the same report.

Report the nine individual FPKM values, contrasts, SE/df, raw and adjusted
p-values, all sensitivity results and all failure reasons for every gene.
The public figure should show individual culture points separated by clone,
not only bars or a selected winner. Do not claim that GSE304575 confirmed a
large effect: it evaluated sign alone, and some candidates reversed there.

## Stopping and claim rules

Run this protocol once. If no gene passes, close this particular cross-context
large-effect prediction as unsupported. No threshold relaxation, sequential
dataset substitution or candidate backfill is allowed in this run. A failure
to reject does not establish absence of a smaller or context-specific effect.

If a gene passes, the permitted language is a reproducible, model-dependent
expression decrease in the tested R225X line relative to both correction clones,
with explicitly retained outcomes in acute depletion and H222P. One mutant
clone and one donor background do not support a population-wide genotype effect.
Novelty review must evaluate this exact contextual claim, not “gene X is linked
to lamin.” Broad LYSMD3/CMTM5 lamina novelty is already unavailable.

Before sharing it as a new biological finding, require an independent
reproduction, raw-count or orthogonal RNA confirmation, the prior-art and
supplement audit, and an explicit domain-review account of alternative
explanations. Lamina causation additionally needs an orthogonal occupancy or
position assay and an experimental perturbation/rescue design. No new paid or
wet-lab expenditure is needed or authorized by this protocol itself.
