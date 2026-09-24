# Campaign: acute lamina change vs LMNA-KO lymphoblastoid compartment (2026-09-24)

Pre-registered replication of the compartment campaign
(`lmna-acute-lamina-vs-chronic-compartment-2026-09-24`) in an outcome cohort never opened
by this program: GSE314556, GM12878 B-lymphoblastoid *LMNA* CRISPR-KO pool vs control-sgRNA
pool, 2 vs 2 Hi-C, hg19, HiC-Pro valid pairs only. Report and outcome:
[`reports/lmna-acute-lamina-vs-lmna-ko-lymphoblastoid-compartment-2026-09-24/report.md`](../../reports/lmna-acute-lamina-vs-lmna-ko-lymphoblastoid-compartment-2026-09-24/report.md).
**Registered outcome: not passed** (label `NOT_PASSED`: adjusted ρ −0.018, p 0.06; no effect floor met; replicate pairs of mixed sign; no chromosome excluded).

## Frozen identities (freeze-001)

| Artefact | SHA-256 |
|---|---|
| `registration.frozen.json` | `8d6cd76cb4bcb80b35ea4e34fd64fd55b359e5f4ae81ff8aea60b6be17151465` |
| `replicate.py` (evaluator wrapper) | `a084a245bab2b1935e12ada74127de31ee69535ea25d403fa4c5ebf74aef9ee1` |
| `compartment.py` (byte-identical to the compartment campaign freeze-002) | `776ccedec155bfe2c45ed0a8092b38f6c7558c585fdcf8366f1d6be643fd4019` |
| `pc1.py` (pairs → 500 kb PC1) | `137b18c854e9c9163cf1302217e8e8c050e412125c60899e364b6b71872f5650` |
| `test_replicate.py` / `test_pc1.py` | `a6568d079179b0cdcfcb9a725d59d606c6ef8b158443ee00f8fd7fbcaf6e5289` / `e8e0a0666a89c2eaf8ac61e55a5f4b16911dcf56c7a96e93a19ef0b82609f6af` |
| `requirements.lock` | `d7d4cab0a8090d4c616efdc49fe58905c22a6b5453e404c73465f0ea961c59aa` |
| `predictor_hg19.tsv` (compartment-campaign predictor lifted hg38→hg19 before freeze) | `1670a3c99c296b455d17a79a7143fc7fb06cb3e5b1d18c5ed7031b65843c0e53` |
| `hg19.chrom.sizes` / `hg19.ncbiRefSeqSelect.txt.gz` | `b404927655a4aada254ea94ad4da0c8901ed0737e67a0dcabedf673354b1f505` / `efe060c0c623c9f9286120e251158b9cabf47e3ae91220f1ad77d6c7654a65c9` |
| `design/method-validation.json` (+ script) | `50e63f26e221e56810fb8282b638193990dc85263176c741d4ffbe3614e14973` / `3449aa15b10eaf12f2a9b4fba4ec7052c5de8625f2aab87cbd33bbeffe27b896` |
| `design/independent-review.json` | `630582f9931c937af9fa497b368f319b8acf60fe37ef1e70bfa8c37fcf841587` |
| `freeze.json` | (this file's own hash is recorded in `intake.json` as `freeze_sha256`) |
| frozen at | 2026-09-24T21:14:10.175061+00:00 |

Four outcome files (GSE314556 HiC-Pro `allValidPairs.txt.gz`, ≈ 7.4 GB) are byte-count- and
hash-bound in `intake.json` and kept outside Git. `freeze.py` refused to run while any outcome
file existed; `intake.py` streamed the files to disk without inspection; `replicate.py run`
refuses unless every hash in `freeze.json` and `intake.json`, and every byte count in the
registration, matches.

## What is in this directory

- `registration.reviewed-draft.json` — the draft as reviewed (round 1 PASS_WITH_REPAIRS, round 2 PASS, round-2 minor repairs verified); differs from the frozen file only by status, `frozen_utc` and the method-validation record binding.
- `registration.frozen.json`, `freeze.json`, `intake.json`, `archive-001/` — the single freeze; `archive-001/` holds the bytes of every bound file.
- `design/` — fixed protocol, skeptical review (items 1–12), independent pre-outcome review, null SD estimate, and the method validation of `pc1.py` against the deposited GSE126459 HOMER PC1 tracks (every attempt retained in `design/method-validation-attempts.md`, including the failed first attempt and the second attempt whose script carried a personal path).
- `lift_predictor.py`, `predictor_hg19.tsv`, `predictor_hg19.manifest.json` — the hg19 predictor and how it was produced from the compartment campaign's frozen predictor.
- `tools.SHA256SUMS`, `tools.FETCHED_UTC`, `hg19.chrom.sizes` — the UCSC inputs (chain and RefSeq table are not copied; their hashes are bound).
- `freeze.py`, `intake.py`, `assemble_public.py` — the helpers that produced the receipts and this directory.

## Record gaps, disclosed

- `design/independent-review.redacted.json` and `archive-001/independent-review.redacted.json`: the bound file (sha `630582f9…`, in `freeze.json`) contains, inside the round-1 reviewer's advice text, a quoted seven-character macOS home-directory prefix literal (slash, the word Users, slash: a grep pattern the reviewer suggested, not a real path). The repository forbids personal path prefixes, so the published copy replaces that one quoted string with `'<home-prefix>/'`; the substitution and both hashes are recorded in `reports/…/assembly.manifest.json`.
- The registration's `secondary_reported_only` entry for the per-chromosome table cites "the evaluator's per-chromosome output"; the evaluator records per-chromosome orientation ρ only, so the outcome column was computed from `core/tiles.tsv` by `per_chromosome_table.py` after the outcome was known (a secondary with no threshold; see the report).
- The first intake attempt was stopped by the operator at ≈ 0.8 GB to move it out of a capped shell; no receipt was written and the partial file was deleted. The first run launch failed at argument parsing before any binding check (`reports/…/results/run-001-argv-error.log`).
- The UCSC chain and RefSeq Select table are not copied (size); their hashes and fetch time are in `tools.SHA256SUMS` / `tools.FETCHED_UTC` and in the registration.

## Reproduce

Inputs: the four GSE314556 pairs files (URLs, byte counts and hashes in `registration.frozen.json` and `intake.json`), `hg19.chrom.sizes`, `hg19.ncbiRefSeqSelect.txt.gz` (UCSC; hash in the registration), `predictor_hg19.tsv`.

```
python -m venv .venv && .venv/bin/pip install -r requirements.lock
cd <this directory> && .venv/bin/python -m unittest -v test_pc1 test_replicate
.venv/bin/python replicate.py --registration registration.frozen.json --freeze freeze.json --intake intake.json \
  --predictor predictor_hg19.tsv --outcome-dir <four pairs files> --tools-dir <hg19 tools> --out-dir run-check --python .venv/bin/python
```

`replicate.py` expects `compartment.py` and `pc1.py` beside it, as here. Campaign tests are not collected by `make check`; run them explicitly with a numpy/scipy/pyBigWig/pyliftover environment.

## Claim ceiling

See the report. The verdict label is mechanical (`pass_criteria.verdict_labels` in the frozen registration) and no threshold was changed after outcome access.
