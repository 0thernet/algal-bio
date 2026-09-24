# Campaign: wide screen and GC-lamina replication (2026-09-24)

Record of one exploration round, kept whole: a registered 47-pair screen, an exploratory artifact control, a registered panel shape test (LEAK_PATTERN, not supported) and a registered fresh-cohort replication (REPLICATED). The report is `reports/wide-screen-lamina-compartment-expression-2026-09-24/report.md`.

## Order of events (UTC, 2026-09-24)
1. Screen registration (`registration/config.json`, `code/screen.py`) reviewed twice (`design/pre-discovery-review.json`, `design/repair-review.json`), frozen 22:54:12 (`registration/freeze-pre-discovery.json`).
2. Discovery on odd autosomes; survivors frozen 22:54:53 (`registration/freeze-survivors.json`); confirmation on even autosomes (`results/`).
3. Exploratory artifact control designed after confirmation, frozen before computing (`control/protocol.json`, `control/freeze.json`); descriptive robustness (`control/robust_explore.py`).
4. Panel shape test registered, reviewed (`design/panel-review.json`), frozen before download (`panel/freeze.json`), label LEAK_PATTERN.
5. GSE263012 replication registered, reviewed (`design/damid-review.json`), frozen 23:28:05 before download (`damid/freeze.json`, `damid/intake.json`), label REPLICATED; post-outcome review `design/damid-post-outcome-review.json` (CONFIRMED_WITH_CAVEATS).

## Disclosures
- `panel/freeze.json` binds `report.md` as context. The report was appended to afterwards; the bound bytes are `panel/report.at-panel-freeze.md` (hash-verified reconstruction). To re-run `panel/panel.py run`, put that file at `report.md` first.
- The frozen protocols describe GSE300197 cells as iPSC; they are hiPSC-derived cardiomyocytes (erratum in the report).
- Personal filesystem prefixes are replaced by `<research-root>/` or `<home>/` in published copies; `assembly.manifest.json` records original and published hashes. Frozen hashes refer to the originals.
- Not published (hashes in intake receipts or manifests): external UCSC tables and the gc5Base bigWig (`data/external`), ENCODE compartment bigWigs (`panel/data`), GSE263012 bigWigs (`damid/data`), and `features/tiles.base.tsv`. GSE126459 HOMER PC1 bedGraphs are read from the compartment campaign's data directory.
- Paid spend for this campaign: $0.

## Reproduce
Python 3.12 with numpy 2.3.3, scipy 1.16.2, pyBigWig, pyliftover. Tests: `python -m unittest test_screen` (in `code/`), `test_panel` (in `panel/`), `test_damid` (in `damid/`). Replication: `python damid/damid.py fetch` then `python damid/damid.py run` (the fetch checks the protocol hash against the freeze).
