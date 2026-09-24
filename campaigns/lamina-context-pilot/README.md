# Lamina context pilot: registered data-limited qualification

The admitted study is a **descriptive software qualification** on public mouse
data. It cannot identify an isolated cell-context effect or support independent
biological confirmation. The active numerical fixture reproduces one published
RNA filtering step and summarizes a fixed chromatin subset. It does not reproduce
the complete paper, establish new biology, or measure agent research ability.

The intended future question is whether unperturbed reference chromatin improves
out-of-study expression-response direction prediction over an expression-only
baseline. The audited corpus does not yet admit that experiment. A new registration
needs a qualified matched/crossed independent cohort, identified biological units,
annotation qualification, a precision calculation, and domain review.

The user supplied Yixian Zheng / Hraness as the research context. No institutional
partnership, author endorsement, authorship, or completed domain review is implied.

## Run the registration checks

From the repository root:

```sh
uv run python scripts/check_registration.py campaigns/lamina-context-pilot
uv run pytest tests/registration
```

The checker runs offline. It checks strict nested types and unknown fields,
registration/schema hashes, every retained artifact, normalized source facts,
split membership, feature timing, assay compatibility, and unsupported claims.
It returns `data_limited`, 75 submitted libraries, zero **verified** independent
biological units, and zero confirmatory contrasts. Zero verified units means that
their identities/independence have not been established; it does not mean that no
independent biological replication was performed by the authors.

`registration.json` is the machine-readable protocol; `freeze.json` binds its
bytes and both schemas. Any amendment creates a newly reviewed registration;
recomputing hashes cannot confer scientific or operational authority. A reviewed
Git commit/release provides an immutable public anchor. The local hash file alone
does not prove trustworthy time, provenance, or evaluator isolation.

## Source intake and retained evidence

The manifests in `datasets/manifests/` bind the complete downloaded SOFT sources
by SHA-256 and byte count. The complete files remain external. The small
`metadata/` projections retain factual sample fields, their original line
numbers, and short method excerpts needed to document contradictions. They omit
contact information, platform tables, long protocols, and publication full text.
Each normalized sample must agree with that retained projection.

| Source | Retained source identity | Admitted use |
|---|---|---|
| [GSE330298](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE330298) | 187,023-byte sample SOFT, SHA-256 `f025b3f26e647020e0518ad4d787f3b7d9fbed18142e351fc7480f85175a32c2` | 35-library assay/sample audit; bounded processed-data qualification |
| [GSE89520](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE89520) | 18,825,497-byte full SOFT, SHA-256 `a2a150541072253f34ce87025cee58d3b1660e004bfc3fbfb590e75271c5d4b8` | 40-library second-context metadata and prior-art audit; measurements not acquired for this fixture |

To independently check every retained line/excerpt against the complete sources,
place the exact files at `GSE330298-samples.soft` and `GSE89520-full.soft` in an
external directory and run:

```sh
uv run python scripts/check_registration.py campaigns/lamina-context-pilot \
  --source-directory /path/to/external-intake
```

This command hashes the original bytes before comparing retained source lines.
It performs no network requests. The original SOFT responses were checked during
intake; future GEO changes must be handled as new source versions. The default
offline check verifies the retained evidence chain, not live NCBI contents.

NCBI's [molecular-data policy](https://www.ncbi.nlm.nih.gov/home/about/policies/)
permits use/distribution without NCBI-imposed restrictions, while noting possible
third-party rights. The public fixture retains factual molecular metadata and
bounded numeric measurements with attribution. This is not a blanket license for
linked publications or author software.

The [public author code](https://github.com/katherinebossone/Lamin_CM_Paper/tree/f85db2b7b5ae4e542bb74bd7d06fadf258bc04bd)
was inspected at `f85db2b7b5ae4e542bb74bd7d06fadf258bc04bd`.
`author-code-audit.json` records the complete file inventory and API response hash.
No license file was present in that tree. No author script is vendored or executed.
The RNA fixture independently implements the published pre-TMM CPM filter found
in `Bulk_and_scRNA/Bulk_RNA_P7_5_DE_analysis.R`; it does not implement edgeR's full
differential-expression workflow.

## Assay and contrast eligibility

| Contrast / assay | Submitted library labels | Age and preparation | Decision and reason |
|---|---|---|---|
| GSE330013 bulk RNA | Flox/+ 4; Flox/- 4 | P7.5, whole heart | Descriptive filter reproduction. Animal, litter, pooling, and batch identities remain unresolved; genes are not biological replicates. |
| GSE330103 Hi-C | Flox/+ 2; Flox/- 2 | P0.5, isolated cardiomyocytes | Descriptive C-score summary. The processed scores combine data by genotype; two tracks do not supply replicated phenotype estimates. |
| Bulk RNA × Hi-C | Eight RNA + four Hi-C libraries | P7.5 whole heart versus P0.5 isolated cardiomyocytes | Matched predictive join excluded. These are different developmental stages and populations. |
| GSE330100 scRNA | Flox/+ 1; Flox/- 2 | P0.5, all heart cells | Replicated genotype inference excluded. Cell counts cannot supply the missing control biological groups. Processing prose describes both four samples and three datasets. |
| GSE330099 ATAC | Flox/+ 2 | P0.5, isolated cardiomyocytes | Reference/QC lead only. Flox/+ is the genetic control, not verified wildtype/unperturbed. No mutant ATAC libraries in this accession. |
| GSE330102 CUT&RUN | 18 across histones, lamin, and IgG | Mostly reported P0.5 isolated cardiomyocytes | Predictive normalized join excluded pending IgG metadata resolution and measurement qualification. |
| GSE89520 RNA/Hi-C | RNA WT 2 + TKO 2; Hi-C WT 2 + TKO 2 | ESC; developmental age unspecified | Known-result context only. Rep labels do not establish independently cultured units or exclude reuse across assays. |
| GSE330298 × GSE89520 | Cardiomyocyte Lmnb1 conditional versus ESC triple-lamin knockout | Distinct study, context, perturbation, genome, and preparation | Confirmation excluded. Regression cannot separate perfectly confounded study/context/perturbation effects. |

GSM/BioSample IDs and the exact `Rep` labels are retained for every sample. None
of the inspected metadata establishes an animal/culture identity with an audited
pooling or relatedness map. The manifests therefore retain `null` biological unit
IDs and `unresolved` independence. Identical BioSample IDs across libraries would
cause admission to fail until an explicit relationship is reviewed.

Four IgG records require particular care: **GSM9718017–GSM9718020** have P0.5 and
Flox/+ or Flox/- in their titles, but their characteristics say `Wildtype` and
P0.6, P0.7, P0.8, P0.9 respectively. Both original values are retained. The checker
rejects silently normalizing them to the title or admitting their contrast.

The cardiac sources use GRCm38/mm10; the ESC source uses mm9 and reports Gencode
vM1 for RNA. The cardiac bulk-RNA annotation release is not established; ATAC
reports iGenomes UCSC without a qualified versioned file. No cross-build mapping
or gene annotation file has been admitted. Shared gene names do not establish
compatible coordinate or transcript definitions.

## Registered numerical controls and limits

The active fixture and all its input/provenance files are hash-bound through
`qualification_fixture`. Its [expected values](../../tests/fixtures/bio/expected.json)
are 128 source-order RNA genes, 28 passing the strict CPM > 0.26 in at least four
libraries rule, and 64 coordinate-matched chromatin intervals with mean
mutant-minus-control C-score delta `0.04620996875`. RNA normalization uses full
source library totals, not the deliberately small fixture totals. Selection is
source order; no genes/windows were selected for a favorable biological effect.

Success requires all retained RNA source/filter decisions to agree and independent
numeric computation to agree within absolute tolerance `1e-12`. An input hash,
sample label, source row, filter decision, or decisive numeric disagreement fails
software qualification. Corrupt inputs, negative counts, malformed intervals,
wrong assemblies, and partial libraries are negative software controls. Synthetic
negative controls are labeled separately from measured public data. Established
lamin/chromatin biology is prior art, never an unknown candidate.

Passing this control is not whole-study reproduction. It does not test effect
significance, differential expression, a biological mechanism, or an agent's
ability to discover anything. Genomic windows, genes, cells, and reads must not be
counted as independently perturbed organisms/cultures. No inferential p-values,
multiple-testing claims, or power numbers are issued in this version.

## Future discovery admission

All 75 named libraries are inspected public reproduction data. Discovery membership
is empty; an independent holdout has **not** been selected. No holdout manifest or
location is published. `evaluator_only` states a future requirement; the JSON
label does not implement a sandbox. An evaluator must use restricted mounts,
credentials, explicit artifact/accession denials, access logs, and frozen
candidates. Public-data/model-training exposure remains unknown even then.

Unperturbed reference features must be distinguishable from changes measured after
the perturbation. Wildtype P0.5 histone profiles are prospective feature leads,
currently ineligible. Mutant/control C-score changes are post-perturbation and
usable only for descriptive explanation. A model cannot use them as information
available before perturbation. Fitting transforms, selecting features, and choosing
modules on the future holdout is prohibited.

The proposed future practical threshold is a balanced-accuracy gain of at least
0.05 over an expression-only baseline, with a biological-unit 95% lower confidence
bound above zero. It is **not** an active success criterion here. A domain reviewer
must settle response thresholds, biological effect size, independent groups,
assay-specific compatibility, and precision before a new prospective registration.
No credible power calculation is possible from unresolved independent units.

That future registration must freeze the gene/module family, BH multiplicity
policy, matched expression/length/chromosome nulls, biological-stratum permutations,
and chromosome/contiguous-block sensitivity analysis. Genomic blocking addresses
local correlation; it cannot repair missing biological replication or cohort
confounding. Candidate observations, inferences, novelty review, and biological
validation have separate fields in `schemas/candidate.schema.json`.

Prior-art intake here is bounded to these accessions, the associated paper, and
author code. Before asserting an unreported association, independently search gene
and module synonyms, lamin/lamina/chromatin-context terms, the same perturbation in
other cell states, and cited/reused datasets; retain dated queries, exclusions, and
source-specific findings. Obtain an independent recomputation and expert review.
Neither candidate explanations nor a passed hash check establish novelty.

If no suitable cohort is available, **data-limited qualification is the complete
registered outcome**. Public reproduction and a documented failed admission are
valid deliverables. Wet-lab validation and any funded provider campaign remain
separate, unstarted studies.
