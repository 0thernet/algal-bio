# Wide screen with a frozen holdout (2026-09-24)

Instruction: explore wide until a shareable positive result. Policy unchanged: register
before observation, retain failures, unsent-only material, $25 cap.

Method: screen many predictor/outcome pairs on odd autosomes only (discovery); freeze the
survivor list; test survivors on the untouched even autosomes (confirmation) with a
within-chromosome circular-shift null. Only confirmed survivors count.

Step 1: build a per-tile feature table (hg38, 500 kb) from data already on disk.
Step 2: screening code + synthetic tests.
Step 3: registration + independent review, then run discovery, freeze, confirm.
