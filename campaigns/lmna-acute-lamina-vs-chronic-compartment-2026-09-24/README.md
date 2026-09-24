# Campaign: acute lamina change vs chronic compartment change (2026-09-24)

Registered cross-study test. Report and outcome: [`reports/lmna-acute-lamina-vs-chronic-compartment-2026-09-24/report.md`](../../reports/lmna-acute-lamina-vs-chronic-compartment-2026-09-24/report.md).
**Registered outcome: not passed** (direction as hypothesised in every arm; one raw effect below the frozen floor).

## Frozen identities (freeze-002, the run that produced the outcome)

| Artefact | SHA-256 |
|---|---|
| `registration.frozen.json` | `80c668a2599bc9c3a45d01b8e3a6526cf8dd15308daf952eccfebae83dae6ab6` |
| `compartment.py` (= `archive-002/compartment.py`) | `776ccedec155bfe2c45ed0a8092b38f6c7558c585fdcf8366f1d6be643fd4019` |
| `test_compartment.py` | `65dbccdf2d63fc6879d38398106cdcd5fabfcbb249e769e69bb2f613cb29f46e` |
| `requirements.lock` | `b3b8f376548d81e1ab9f8a430112e1e84f13ac7de0cc064dac2340e44c2b0865` |
| `predictor.tsv` (exposed predictor, built before freeze-001) | `680ba99815b9fd79cca7b5d566987bccaeba60bcef4fee3315d74f47d8cf0817` |
| `freeze.json` | `0f0a2d01c674da587822af3b1ed8ce59e166827b2b56c1a54b00a09bcb797f34` |
| frozen at | 2026-09-24T20:19:49.242851+00:00 |

Six outcome files (GSE126459 HOMER 500 kb Active.PC1 bedGraphs) are hash-bound in `intake.json` and kept outside Git; `intake-001.json` records the first download and `intake.json` confirms byte-identity on re-download.

## History in this directory

- `registration.reviewed-draft.json` — the draft as reviewed; differs from the frozen file only by status, `frozen_utc` and the predictor hash binding.
- `registration.frozen-001.json`, `freeze-001.json`, `intake-001.json`, `archive-001/` — the first freeze. Its run failed with zero eligible tiles (chromosome naming); no outcome value was observed. `archive-001/` holds byte-exact reconstructions of the freeze-001 code and tests (hash-verified) so the amendment can be diffed.
- `registration.frozen.json` (freeze-002) — identical to freeze-001 except `amendments`, `code.tests` count and `frozen_utc`.
- `design/` — fixed protocol, three rounds of independent pre-outcome review (`independent-review.json`, `skeptical-review.md`).
- `freeze.py`, `intake.py`, `assemble_public.py` — the helpers that produced the receipts and this directory.

## Reproduce

Inputs: the four GSE300197 z-score bigWigs, `hg38-ncbiRefSeqSelect.txt.gz` (hashes in the registration), and the six PC1 bedGraphs (hashes in `intake.json`).

```
python -m venv .venv && .venv/bin/pip install -r requirements.lock
.venv/bin/python -m unittest -v test_compartment
.venv/bin/python compartment.py predictor --registration registration.frozen.json --data-dir <predictor inputs> --out-dir predictor-check
.venv/bin/python compartment.py run --registration registration.frozen.json --freeze freeze.json --intake intake.json \
  --predictor predictor.tsv --outcome-dir <six bedGraphs> --out-dir run-check
```

`run` refuses to start unless every hash in `freeze.json` and `intake.json` matches. Campaign tests are not collected by `make check`; run them explicitly with a numpy/scipy/pyBigWig environment.

## Claim ceiling

See the report. Nothing here is a discovery claim; the registered rule did not pass and no threshold was changed after outcome access.
