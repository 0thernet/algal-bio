# Exploratory result: relative lamina-gain screen after acute LMNA depletion

The campaign ran on public data after its candidate-selection rules were frozen.
It did **not** establish a novel biological discovery. It produced two useful
follow-up leads, one of which is weakened by low counts and known lamin-interactor
prior art; the other has a small independent RNA-direction signal but unresolved
lamina prior art.

The discovery question was whether expressed loci with increased relative LMNB1
signal after acute LMNA depletion in differentiated human cardiomyocytes also
show lower RNA, a DNKASH-context contrast, and the same RNA direction in an
independent LMNA-H222P study. The discovery data were GSE300197. The external
direction check was GSE304575.

The public study records are [GSE300197](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE300197)
and [GSE304575](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE304575); exact
download URLs and hashes are retained in the campaign's `sources.json`.

The workflow follows the evidence discipline suggested by Anthropic's
[enzyme-system announcement](https://www.anthropic.com/news/claude-discovers-novel-enzyme-system)
and linked [technical report](https://www-cdn.anthropic.com/22573675ada52a8ca8a97a1a4b4326b2f208a071.pdf),
but it does not claim to reproduce that system, scale, or discovery result.

## Setup decision for future campaigns

Center the public workflow on **Algal Lab's registration and evidence boundary**.
Keep bounded execution and receipts in **ALGAL**, biological source adapters and
reports in **algal-bio**, and prior-art review in a local **Sponge** packet. A
qualified XCB/Devin investigator route can be attached later; a model is an
adviser whose suggestions remain outside the frozen candidate and claim path.
For this run the exact SWE-2 qualification was unavailable, so a Vercel Gateway
call was limited to a public-data, tool-free methods critique. This separation
is the reusable setup: public source hashes and registration first, model-assisted
interpretation second, independent data and domain review before any wet-lab
decision.

## What was measured

The deposited GSE300197 RNA matrix contained seven processed columns: three
siScr controls and four siLMNA columns. The paper caption and GEO's technical
library metadata disagree about the number of controls; this record uses the
deposited seven-column matrix and does not infer independent biological
replicates. Four condition-aggregate, smoothed z-score bigWigs supplied the
relative LMNB1 and DNKASH profiles. The unavailable LAD spreadsheet was not
reconstructed.

Each unique autosomal hg38 RefSeq Select gene was measured at its strand-aware
TSS in a fixed ±50 kb half-open window. The primary screen required control-only
RNA eligibility, nonpositive baseline relative signal, positive LMNB1 gain, and
the top decile of gain among eligible genes. RNA selection then required a
case-minus-control contrast ≤ −0.5 log2 CPM, negative direction in all seven
leave-one-column-out contrasts, and a negative DNKASH interaction. The DNKASH
criterion is mathematically coupled to selecting a large initial gain, so it is a
descriptive prioritization feature rather than independent rescue evidence.

The complete discovery run had 19,241 source genes, 12,181 eligible genes, and
1,006 signal-screen genes. Thirty-eight passed the candidate filters before the
registered 500 kb same-chromosome spacing rule; ten were retained in the fixed
lexicographic ranking.

## Frozen candidates and independent direction check

| Rank | Gene | Discovery RNA Δ | Relative LMNB1 gain | H222P RNA direction | Interpretation |
| ---: | --- | ---: | ---: | --- | --- |
| 1 | CMTM5 | −1.4743 | 0.3046 | pass | Low external counts; known lamin-A interactor |
| 2 | SLC2A14 | −1.0689 | 0.3160 | fail LOO | No direction confirmation |
| 3 | NID2 | −1.0233 | 0.4910 | fail LOO | No direction confirmation |
| 4 | DCAF8 | −0.9770 | 0.2900 | fail | External direction reverses |
| 5 | PIANP | −0.9617 | 0.4525 | fail LOO | Prior LMNA-cardiomyopathy transcriptomic association |
| 6 | MEX3B | −0.9017 | 0.4301 | fail LOO | No direction confirmation |
| 7 | ANKRD52 | −0.8537 | 0.4173 | fail | External direction reverses |
| 8 | ZFTA | −0.8383 | 0.3147 | missing | No exact external symbol |
| 9 | FYCO1 | −0.8017 | 0.2917 | fail | Known cardiac autophagy/pressure-overload biology |
| 10 | LYSMD3 | −0.7338 | 0.6419 | pass | Small external decrease; lamina prior-art supplement unresolved |

Nine candidates were evaluable in GSE304575. Only CMTM5 and LYSMD3 passed the
predeclared requirement of negative CPM and median-ratio contrasts plus negative
direction in every leave-one-library-out contrast. CMTM5 fell from 0.114 to
0.050 mean CPM in that study, so its apparent agreement is low-count evidence.
LYSMD3 fell from 32.67 to 30.47 mean CPM, a small relative decrease. ZFTA was
retained as a missing-symbol outcome; no alias was used after seeing the result.

The class-level result is negative or weak. The screen-minus-matched-control
RNA difference was −0.00736 log2 units, with a descriptive spatial bootstrap
interval of [−0.02823, +0.01438]. The full-universe Spearman association was
−0.0331. A circular gene-order diagnostic gave a lower-tail value of 0.0005,
but it is not a biological-replicate p-value, does not preserve exact genomic
distance, and cannot turn the tiny effect into a general recruitment/repression
claim.

## Prior-art decision

The bounded literature audit rules out several easy novelty claims. CMTM5 is
already reported as a lamin-A interactor; FYCO1 already has cardiac autophagy
and pressure-overload evidence; PIANP appears in an LMNA cardiomyopathy
transcriptomic study; and the 2012 lamin-A/progerin promoter-mapping paper is
directly relevant to LYSMD3, although its supplementary gene table was not
rechecked. The audit therefore treats LYSMD3 as a hypothesis lead, not a novel
lamina-associated gene. The other candidates remain unresolved after a bounded
search, which is not evidence of novelty. Details and source links are in
[`novelty-audit.json`](novelty-audit.json).

The local Sponge packet was validated and exported with ten retained evidence
items and thirteen findings. Its public-safe receipt is
[`sponge-evidence-receipt.json`](sponge-evidence-receipt.json); no hosted Sponge
credential or remote document write was used.

## Reproducibility and execution record

- Discovery registration: `201e24b9870349bd5a2234fd40f52dbfd7a618fb37b700feb0eb474c0b128efa`.
- Frozen candidate list: `b09d1eeb9c8de5fff5a8653ded43e7fd13b78d8496243d770daa2db2b43acb1c`.
- Discovery code: `575e21b471111eb61d84ed2339b0ac9b68895bfdc79b4322d0f09705b0a88`.
- Independent review checked 250 interval windows against a brute-force oracle and
  the complete 1,999-draw null branch; focused synthetic tests passed.
- The preferred XCB/Devin SWE-2 route was unavailable because the exact current
  XCB source/build did not satisfy its qualification evidence. One public-only,
  tool-free Vercel/Anthropic methods critique was run for **$0.019722**; its
  temporary $5 key was revoked and the charge reconciled. No model-generated code
  was executed and no private campaign draft was sent.
- Sponge was used as a local literature packet. No hosted Sponge token was
  available, and no private remote write occurred.

## Decision

Do not call these genes discoveries or begin a mechanistic wet-lab claim from
this run. If the lab wants one next computational target, prioritize **LYSMD3**
for independent replicate-level reanalysis and a predeclared orthogonal lamina
measurement. Treat **CMTM5** as a lower-priority control because it is already a
lamin-A interactor and is low-count in the independent RNA study. Before any
wet-lab spend, check the 2012 lamin-mapping supplement, obtain a genuinely
independent cardiomyocyte dataset, and repeat candidate selection without using
the outcome of either check.
