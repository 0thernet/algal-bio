# ORCS transfer: **ORCS_REPLICATED**

Run 2026-09-25T21:57:39Z under freeze `f2e60009` (2026-09-25T21:54:42Z).

## Question
Do the depmap campaign's 77 registered context→dependency associations
replicate in **independently published** genome-scale CRISPR screens —
BioGRID ORCS 2.0.18, human tarball — with DepMap-ingested PMIDs
excluded?

## Registered result

| Set | Tested | Replicated | Rate | Gate | Verdict |
|---|---|---|---|---|---|
| Primary | 68 | 25 | **0.368** | >= 0.30 (P1) | pass |
| Placebo | 2 | 0 | 0.0 | <= 0.15 (P2) | pass* |
| Novel subset | 32 | 10 | 0.313 | report-only | — |
| Gold controls | 13 | 12 | **0.923** | >= 0.50 (P5) | pass |
| P3 same-line subset | 61 | 24 | 0.393 | report-only | — |
| P3 disjoint subset | 35 | 4 | **0.114** | report-only | — |

*P2's placebo denominator is 2 (one placebo file empty; permuted
contexts nominate almost nothing after the discovery gates) — disclosed,
consistent with campaign C.

## Holdout coverage

1,952 human index rows → 998 pass the registered usable filter → 665
PMID-excluded as DepMap-ingested → 122 screens enter the test after
cell-line mapping (103 unmapped), the >= 5,000-gene floor (79 dropped),
and direction resolution (29 undecidable - counted, never guessed).

Mechanism highlights among the replications: `SIG:MSI_HIGH→WRN` (the
canonical WRN-MSI dependency), `MUT_HOT:BRAF→MAPK1`/`MAP2K1`,
`MUT_DAM:APC→CTNNB1`, `MUT_HOT:NRAS→RAF1` — oncogene-addiction biology
recovering under independent screens is itself a positive calibration.

The sole gold miss is `MUT_DAM:SMARCA4→SMARCA2` — SMARCA4-deficient
models are rare in the mapped corpus (its DNAI_REPLICATED arm in
campaign C used RNAi; here the arm relies on independent screens where
SMARCA4 loss is uncommon).

## What this means

Three orthogonal holdouts now agree: DepMap's context-dependency
associations transfer to RNAi knockdown (C: `RNAI_REPLICATED`,
41/72), to independent published CRISPR screens (D: `ORCS_REPLICATED`,
25/68), and the flagship paralog-loss subset to combinatorial
double-KO data (A: `DOUBLEKO_REPLICATED`, 4/9). The pair set is not a
DepMap artifact.

## P3: same-line vs disjoint stratification

Replication is concentrated where the ORCS screen's cell line was itself
CRISPR-profiled in DepMap 24Q4 (shared specimen): **24/61 = 0.39** in
same-line screens vs **4/35 = 0.11** on disjoint lines — a 3.4x
difference. The associations travel with the specimen's measured
context, not just the context label; disjoint-line transfer is weak but
nonzero (the label's primary gate does not depend on this split - it is
a registered report-only stratifier).

## Errata and integrity notes

- This evaluation is the **third** scored run: run1 (21:26Z) crashed on
  a stale gold-controls filename before any score read; run2 (21:53Z
  boundary) read screen scores then crashed in post-parse bookkeeping
  (`TypeError` in the context union); the bookkeeping fix was applied,
  the campaign re-frozen (intermediate digest `50968b8d` → `f2e60009`,
  then this run's `9124f42f`), the sealed archive re-fetched (receipted
  sha256 `39222a96` on the analyzed bytes), and this run re-evaluated.
  The archive SHA is recorded in `data/sealed/fetch.receipt.json`.
- `confirm.py` gained the streaming single-pass member extraction after
  run1 (gzip members are not seekable) and the P3 overlap split for this
  run (the registered deliverable was missing from the first scored
  version). `fetch_holdout.py` gained a UA header after a 403 to the
  bare urllib client. All amendments are bound by the refreeze chain;
  the P3 refreeze postdates the first scored run but the paired
  re-fetch produced byte-identical bytes (sha256 `39222a96` both times).
- `logs/fetch.log` records one early fetch printing a different sha
  (`323bce3d`) - a truncated HTTP read, recorded as such by the fetcher;
  the analyzed bytes are the receipted `39222a96`.
- Prior freeze manifests are not retained - only their digests survive
  in the runs ledger and reports.
- All claims are association-level. None are mechanistic or
  experimental.
