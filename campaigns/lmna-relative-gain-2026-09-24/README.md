# LMNA relative lamina-gain campaign

This is a bounded exploratory analysis of public GEO data. It asks whether
loci with increased **relative LMNB1 signal** after acute LMNA depletion in
differentiated human cardiomyocytes also show lower RNA, and whether that RNA
direction is seen in a separate LMNA-H222P cardiomyocyte study.

The analysis does not reconstruct the paper's author-defined LAD calls. The
paper's supplementary LAD table could not be admitted through the supported
public routes, so the registered substitute uses common finite-base averages of
four deposited, condition-aggregate z-score bigWigs around fixed hg38 RefSeq
Select TSS windows. These are relative profiles, not absolute binding or
replicate-level effects.

The protocol was frozen before the complete discovery matrix was analyzed:

- registration SHA-256: `201e24b9870349bd5a2234fd40f52dbfd7a618fb37b700feb0eb474c0b128efa`
- discovery analysis SHA-256: `575e21b471111eb61d84ed2339b0ac9b68895bfdc79b4322d0f09705b0a88`
- candidate-freeze SHA-256: `b09d1eeb9c8de5fff5a8653ded43e7fd13b78d8496243d770daa2db2b43acb1c`

The discovery run produced ten ordered candidates. The independent direction
check was applied to exactly those ten genes and could not add or replace one.
See the reviewed report under `reports/lmna-relative-gain-2026-09-24/`.

## Reproduction

The six discovery inputs and the independent count matrix are public and
hash-bound in `sources.json`. They are intentionally kept outside this Git
repository. Download them to a local `data/` directory, install the exact
packages in `requirements.lock`, and run:

```sh
uv venv --python 3.12 .venv
UV_CACHE_DIR=.cache/uv uv pip sync --python .venv/bin/python --require-hashes requirements.lock
.venv/bin/python -m unittest -v test_analysis.py test_corroborate.py
.venv/bin/python analysis.py --data data --out runs/discovery-001 \
  --registration registration.frozen.json --inputs-manifest inputs.discovery.json
```

The external check requires the metadata-derived `external-header-map.json`,
the frozen candidate receipt, and the downloaded GSE304575 matrix:

```sh
.venv/bin/python corroborate.py --counts data/GSE304575_Raw_Counts_table.csv.gz \
  --mapping external-header-map.json \
  --candidates runs/discovery-001/candidates.frozen.json \
  --freeze-receipt discovery.freeze-receipt.json --out runs/corroboration-001
```

The code refuses changed inputs, changed registration or dependency locks,
ambiguous gene/sample headers, and identifier-only external matrices without an
explicit crosswalk. Outputs must be new directories; existing observations are
never overwritten.
