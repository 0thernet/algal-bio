# Method-validation attempts (every attempt retained)

## Attempt 1 — 2026-09-24 ~20:30Z (approximate; no receipt written) — FAILED (input format), no comparison produced
Smoke run of `code/pc1.py` (sha 669d880a…) on GSM3602092 valid pairs: 55,164,246 lines read, 0 kept, all counted as trans; peak RSS 8.1 GB. Cause: the GSE126459 files use the 4DN-style column order (read chr1 pos1 chr2 pos2 strand1 strand2), not HiC-Pro's (read chr1 pos1 strand1 chr2 pos2 strand2); column 4 (pos2) was read as chr2 and fed the chromosome-name cache, which grew without bound. The formal validation run started in parallel was stopped before producing any comparison. No PC1 values were produced or seen.
Repair: layout auto-detection from the first data line with `stats["format"]`, bounded name cache, one new test (`PairsLayoutDetectionTests`). New pc1.py sha 137b18c8…, test_pc1.py sha e8e0a066…; 27 tests OK. Slice check (3,000,000 lines): format=pairs, 2,102,351 cis kept, RSS 189 MB.
GSE314556 is stated by the depositors as HiC-Pro output; both layouts are now handled.

## Attempt 2 — 2026-09-24T20:58:22Z — PASSED (script had a hard-coded personal path; not bound)
pc1.py 137b18c8…: V1 0.9225 (GSM3602092), 0.8804 (GSM3602088); V2 0.5471; n 5,262 tiles; no chromosome flipped or excluded in either track. Record kept as design/method-validation.attempt2-unbound-script.json.

## Attempt 3 — 2026-09-24T21:02:48Z — PASSED (bound script)
Same pc1.py bytes (137b18c8…); validate_pc1.py repaired (deposited-PC1 directory as argument, per-chromosome table, script hash recorded; sha 3449aa15…). V1 0.9225 (GSM3602092), 0.8804 (GSM3602088); V2 0.5471; n 5,262 tiles. Numbers identical to attempt 2, as expected from identical pipeline bytes. Record: design/method-validation.json (the file freeze.py binds).
Per-chromosome agreement below 0.8: GSM3602092 — chr9 0.68, chr22 0.21; GSM3602088 — chr4 0.40, chr9 0.73, chr22 0.22. chr21 has no value in either sample: the deposited GSE126459 PC1 tracks contain no chr21 rows, so fewer than 10 comparable tiles exist. chr22 (0.21/0.22) and chr4 in one sample (0.40) agree weakly with the deposited HOMER track; the genome-wide criteria V1/V2 were registered as the validation gates and are met. These chromosome-level disagreements are disclosed here before freeze and are not used to alter any threshold; the registered per-chromosome pipeline QC (cross-sample concordance >= 0.5 against the WT mean, more than 3 excluded autosomes = PIPELINE_FAILURE) is the only chromosome-level gate in the outcome run.
