# Campaign: wide screen and GC-lamina replication (2026-09-24)

Record of one exploration round, kept whole: a registered 47-pair screen, an exploratory artifact control, a registered panel shape test (LEAK_PATTERN, not supported) and a registered fresh-cohort replication (REPLICATED). The report is `reports/wide-screen-lamina-compartment-expression-2026-09-24/report.md`.

## Order of events (UTC, 2026-09-24)
1. Screen registration (`registration/config.json`, `code/screen.py`) reviewed twice (`design/pre-discovery-review.json`, `design/repair-review.json`), frozen 22:54:12 (`registration/freeze-pre-discovery.json`).
2. Discovery on odd autosomes; survivors frozen 22:54:53 (`registration/freeze-survivors.json`); confirmation on even autosomes (`results/`).
3. Exploratory artifact control designed after confirmation, frozen before computing (`control/protocol.json`, `control/freeze.json`); descriptive robustness (`control/robust_explore.py`).
4. Panel shape test registered, reviewed (`design/panel-review.json`), frozen before download (`panel/freeze.json`), label LEAK_PATTERN.
5. GSE263012 replication registered, reviewed (`design/damid-review.json`), frozen 23:28:05 before download (`damid/freeze.json`, `damid/intake.json`), label REPLICATED; post-outcome review `design/damid-post-outcome-review.json` (CONFIRMED_WITH_CAVEATS).
6. (2026-09-25) GSE277503 LBR sign-reversal test registered, reviewed (`design/lbr-review.json`, PASS_WITH_REPAIRS), frozen 00:01:44 before download (`lbr/freeze.json`, `lbr/intake.json`), label DIRECTION_ONLY (`logs/lbr-run.log`, `lbr/results/result.json`).
7. Exploratory fine-scale diagnostic (`explore/`): the first run stopped after 3 of 10 contrasts (`logs/fine_scale.log`); a vectorized copy reproduced those rows and finished (`logs/fine_scale_fast.log`, `explore/fine_scale.json`). Uninformative.
8. Third-cohort test `mef/` (GSE124205): mm9 tile features built from UCSC annotation only (`mef/build_mm9_features.py`, `mef/features/`); literature lane (`design/prior-art-mef.md`); registered, reviewed (`design/mef-review.json`, PASS_WITH_REPAIRS, no blocking), frozen 2026-09-25T00:50:52Z before any GSE124205 data file was downloaded (`mef/freeze.json`). Fetched 01:05-01:06Z (`mef/intake.json`), run 01:16Z: label **DIRECTION_ONLY** in all three arms — primaries negative (rho ~-0.35) but between-embryo WT placebos exceed the registered bound; not replicated (`logs/mef-run.log`, `mef/results/result.json`). Post-outcome review `design/mef-post-outcome-review.json` (PASS_WITH_REPAIRS; integrator re-verified all hashes and ordering).

Rounds 6-8 were run by Devin, continuing the Claude Code session that ran rounds 1-5; reviews are by independent read-only Devin subagents.

## Disclosures
- `panel/freeze.json` binds `report.md` as context. The report was appended to afterwards; the bound bytes are `panel/report.at-panel-freeze.md` (hash-verified reconstruction). To re-run `panel/panel.py run`, put that file at `report.md` first.
- The frozen protocols describe GSE300197 cells as iPSC; they are hiPSC-derived cardiomyocytes (erratum in the report).
- Personal filesystem prefixes are replaced by `<research-root>/` or `<home>/` in published copies; `assembly.manifest.json` records original and published hashes. Frozen hashes refer to the originals.
- Not published (hashes in intake receipts or manifests): external UCSC tables and the gc5Base bigWig (`data/external`), ENCODE compartment bigWigs (`panel/data`), GSE263012 bigWigs (`damid/data`), GSE277503 bigWigs (`lbr/data`, hashes in `lbr/intake.json`), UCSC mm9 annotation (`mef/ref`, hashes in `mef/features/manifest.json`), GSE124205 bigWigs (`mef/data`, hashes in `mef/intake.json`), and `features/tiles.base.tsv`. GSE126459 HOMER PC1 bedGraphs are read from the compartment campaign's data directory.
- `lbr/` had no separate post-outcome review before publication; the PR #8 review checks its integrity (`design/pr8-review.json`). Separately, `lbr/lbr.py run` re-executed in a scratch copy (frozen code, features and intake-verified data) reproduced `lbr/results/result.json` and `logs/lbr-run.log` byte for byte.
- On 2026-09-25 a test-import name collision overwrote `features/tiles.tsv` and `features/manifest.json` in the private working copy; both were restored from the PR #7 published copies and re-verified against every freeze receipt (report, "Record note").
- Paid spend for this campaign: $0.

## Reproduce
Python 3.12 with numpy 2.3.3, scipy 1.16.2, pyBigWig, pyliftover. Tests: `python -m unittest test_screen` (in `code/`), `test_panel` (in `panel/`), `test_damid` (in `damid/`), `test_lbr` (in `lbr/`), `test_mef` (in `mef/`). Replication: `python damid/damid.py fetch` then `python damid/damid.py run` (the fetch checks the protocol hash against the freeze); the same for `lbr/lbr.py`. Fine-scale diagnostic: `python explore/fine_scale_fast.py` (needs `damid/data`, `lbr/data` and the gc5Base bigWig). Third cohort: download the three UCSC mm9 files named in `mef/features/manifest.json` into `mef/ref`, `python mef/build_mm9_features.py` (reproduces `mef/features`), then `python mef/mef.py fetch` and `python mef/mef.py run`.
