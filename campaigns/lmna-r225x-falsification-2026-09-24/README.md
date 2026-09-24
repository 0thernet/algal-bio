# LMNA R225X fixed-panel falsification campaign

This campaign is the registered follow-up to the
[LMNA relative lamina-gain campaign](../lmna-relative-gain-2026-09-24/README.md).
It tests the original ten frozen candidates, unchanged and unreplaced, in an
independent public dataset: [GSE126458](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE126458),
day-14 hiPSC-derived cardiomyocytes carrying LMNA R225X versus two separately
corrected isogenic clones, with three independent differentiations per line
(Bertero et al., 2019, DOI 10.1083/jcb.201902117).

The question was fixed before any GSE126458 expression value was opened: does
each candidate show a decrease exceeding 0.5 in mean log2(FPKM + 0.5) in the
mutant line against **each** corrected clone, with Holm correction over all ten
original hypotheses, negative leave-one-culture-out contrasts, and agreement at
two pseudocount sensitivities?

Outcome: **0 of 10 passed.** The cross-context large-repression claim for this
panel is retired. See the reviewed report under
`reports/lmna-r225x-falsification-2026-09-24/`.

## Frozen identities

- registration SHA-256: `4501c0a26b4accab301fc447aff4e0fc5aabf8760984a061583a20e2b7e091ae`
- analysis code SHA-256: `c89c28484061c3f063eb377f085a0225598fd80672044835c46d5b12c831c977`
- candidate map SHA-256: `8406cee3cc65eceaa22493ced1cd508130e12d002ec07db66b1ff83c3e14046e`
- freeze receipt SHA-256: `63223df4077e2f32c4fcd2044a71fcd7f33c20d0759bed5211b1d9a6b17dc876`
- public input matrix SHA-256: `3d398d6d9d8b9b130c91ece7169a06c3c88a0b9dbdb51b87c8f79b7df5d28f9b`

`freeze.json` binds the registration, candidate map, code, dependency lock and
the independent pre-outcome review. The published `design/independent-review.json`
is a public copy in which two private local filesystem paths were replaced; its
`public_copy_note` records the original hash, which is the one bound by the
freeze receipt. `intake.json` was written when the matrix was downloaded, after
the freeze, and records that no value was opened before download.

The freeze is a within-session record. It is not an independently timestamped
preregistration, and public-data or model-training exposure of GSE126458 cannot
be excluded.

## Reproduction

Download the single public input in `sources.json` to a local `data/` directory,
install the exact packages in `requirements.lock`, and run:

```sh
uv venv --python 3.12 .venv
UV_CACHE_DIR=.cache/uv uv pip sync --python .venv/bin/python --require-hashes requirements.lock
.venv/bin/python -m unittest -v test_falsify.py
.venv/bin/python falsify.py --registration registration.frozen.json --freeze freeze.json \
  --mapping candidate-map.json --intake intake.json \
  --counts data/GSE126458_genes.fpkm_table.txt.gz --out runs/r225x-001
```

The code refuses a draft registration, a changed mapping source, an oversized or
changed input, a changed dependency lock, and an existing output directory. A
second independent run on 2026-09-24 reproduced `outcomes.tsv` and `summary.json`
byte for byte (`reports/lmna-r225x-falsification-2026-09-24/reproduction.json`).

## Claim ceiling

A pass would have supported a model-dependent expression association in cultured
lines. A fail retires the specific large-effect cross-context prediction for the
failing gene and keeps the original context-specific observation as exploratory.
Neither outcome establishes novelty, lamin binding, mechanism, or biological
validation. FPKM values are processed relative abundance, not raw counts; the
Welch model on three cultures per line is approximate; one patient-derived
mutant clone and two corrected clones cannot separate genotype from clone
effects.
