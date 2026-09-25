# Campaign: context-specific dependencies against a sealed cross-library holdout (2026-09-25)

A pre-registration, published before the holdout was opened.

## The question

Public CRISPR knockout screens are mined continuously for context-specific dependencies: a lesion in one gene predicts that cells need another gene. Several public resources publish such associations on a standing basis. Almost none are confirmed against data produced by a different CRISPR library in a different laboratory, and the fraction that would survive such a test has never been measured under a design fixed in advance.

This campaign measures it. A genome-wide screen on one library nominates 77 associations under a rule fixed before any holdout data was read (the rule caps the selection at 100; the genetic stratum came in short at 27 of 50, and the cap was not loosened after that was seen). A sealed holdout, produced with a different library by a different laboratory and including 119 cell lines the discovery set never saw, is then opened once.

## Why the holdout is real

DepMap's `ScreenGeneEffect.csv` is Chronos-fitted per library and concatenated, so splitting its rows by library gives a genuinely separate inference run rather than a re-slicing of one joint fit. The jointly fitted `CRISPRGeneEffect.csv` would have destroyed the holdout and is deliberately not used.

| part | library | laboratory | screens | role |
|---|---|---|---|---|
| AV | Avana, Cas9 | Broad Achilles | 1046 over 1043 models | discovery |
| KY | Kosuke Yusa, Cas9 | Sanger Project Score | 315 | sealed holdout |
| CD | Humagne-CD, Cas12a | Broad | 40 | reported only, a different nuclease |

`code/split_screens.py` routed rows by the library suffix of the screen identifier and computed nothing. Context features and covariates for holdout models come from shared omics files that are not sealed. That is deliberate and is what makes holdout testability checkable in advance; those files carry no dependency information.

## Every outcome is informative

A high replication rate makes the nominated pairs a validated target list. A low rate is a calibration result about a class of analysis, measured against a sensitivity floor that says whether the test could have detected a true effect at all. That symmetry is what makes the registration worth making rather than a formality.

## What is registered

`registration/protocol.json` fixes the data, the feature and statistic definitions, the selection rule, the three confirmation tiers, 24 registered positive controls with citations (18 available in the data, 4 of them self-dependencies), three lineage-permuted placebos, five predictions with thresholds, five outcome labels with their precedence, and the abort rules. `code/confirm.py:verdict` assigns the label from the numbers, so the outcome is produced by the frozen code rather than chosen after the numbers are seen.

## Order of events (UTC, 2026-09-25)

Times are local file modification times converted to UTC.

- 03:59 `data/split.receipt.json`: the release split by library suffix; the KY rows sealed. Nothing computed.
- 04:04 `data/sanger_holdout.sha256`: the Sanger Project Score archive hashed, never opened.
- 04:37 `data/refs/refs.receipt.json`: prior-knowledge references fetched and validated.
- 05:52 `data/depmap24q4.receipt.json`: re-issued when the jointly fitted `CRISPRGeneEffect.csv` was moved under `data/sealed/` and three further release files were added.
- 06:15 to 06:28: after two independent pre-freeze reviews, the repaired pipeline re-ran from a wiped `results/`: `prep`, the real screen (06:19), then three lineage-permuted placebo screens.
- 06:38 `registration/gold_controls.json`: positive controls evaluated on discovery only.
- 06:38: the Claude Code session running this campaign hit its usage limit; Devin continued from the on-disk state.
- 07:24 and 07:27: annotation and tier testability re-run after an I/O caching fix in `code/contexts.py` (same values, one read per file instead of one per lookup).
- 07:30 `registration/protocol.json` version 2 generated from the artifacts by `code/make_protocol.py`.
- 07:34 the unsplit release file `ScreenGeneEffect.csv`, which carries every KY row and had been read only by `code/split_screens.py`, moved under `data/sealed/` with `mv` (no bytes read).
- Third independent pre-freeze review (`registration/prefreeze-review-3.json`): PASS_WITH_REPAIRS, no blocker; repairs applied and the protocol regenerated.
- Freeze, public pre-registration and confirmation times are recorded below once they happen.

## Disclosures

- The sealed holdout and the Sanger Project Score archive were downloaded and hashed but never opened. Hashing reads bytes and produces a digest; it reads no value into the analysis.
- Personal filesystem prefixes are replaced in published copies; `assembly.manifest.json` records original and published hashes, and frozen hashes refer to the originals.
- Not published: the DepMap 24Q4 release and every matrix derived from it, about 1.8 GB of public data. Hashes are in `data/depmap24q4.receipt.json` and `data/split.receipt.json`, and every file is free to download from the Figshare article named in the protocol.
- Paid spend for this campaign: $0. No paid inference and no paid compute; all data is public and free.

## Reproduce

Python 3.12 with numpy, scipy, pandas, statsmodels and pytest. Tests are deterministic and need no network and no DepMap data except where noted: `python -m pytest tests/ -q`.

Full pipeline, in order: `code/fetch_depmap.py` (downloads and md5-verifies the release), `code/split_screens.py` (creates the seal), `code/prep.py`, `code/screen.py real`, `code/screen.py placebo SEED` for each of the three seeds, `code/fetch_refs.py`, `code/annotate.py`, `code/gold.py`, `code/testability.py`, `code/freeze.py`, then `code/confirm.py`.
