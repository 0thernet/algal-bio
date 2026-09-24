# run-001: failed before any outcome contrast (2026-09-24)

The frozen `compartment.py` was executed with the freeze and intake receipts.
All six PC1 bedGraphs produced zero eligible tiles, so the contrast arrays were
empty; NumPy raised an IndexError in `decile_contrast` after the correlation
helpers returned NaN on empty inputs. No correlation, p-value, orientation
statistic or per-tile outcome value was observed. Cause: a bedGraph format
mismatch against the tile grid (see `format-check.txt`), diagnosed from the
first coordinate columns and chromosome-name counts only.
