# Historical evidence retention

Baseline: `a712fbec69bd03b10c20d8078b478c38734d9c02`. The historical README is
retained in [legacy-studies.md](legacy-studies.md), with its reported claims,
corrections, and negative findings. No historical script, result, receipt, or
data file was rewritten to create the portable environment.

Every one of the baseline's 1,742 tracked files other than the editable README and
gitignore is listed with a byte count and SHA-256 in
[`tests/fixtures/legacy/manifest.json`](../tests/fixtures/legacy/manifest.json).
This includes **289 `algal.run.v1` run receipts**, eight native execution manifests,
1,305 content-store values, all retained analysis code, and retained outputs.
`make check` detects changed or missing files and changes to the native receipt set.
Retention is a byte-level claim, not native replay, fresh reproduction, rights
clearance, source truth, or independent verification of the reported statistics.

| Historical study/report area | Retained source and outputs | Missing qualification |
| --- | --- | --- |
| OpenGenes facts, 44 candidates, 83 contradictions | `extract.py`, `project.py`, `report.py`, `rules/`, `facts/`, `out/candidates.json`, `out/contradicted.json`, `.algal/values/` | Original `out/opengenes.json` is excluded from Git; live refetch is not an exact historical input. Exact native CLI build and source-input completeness are unqualified. |
| Model memory, grounding, scale, contamination, unknowns, depth | `experiment*.py`, `arms.py`, `modelscale.py`, `contamination.py`, `unknown.py`, `depth.py`; corresponding `out/*.json`; `.algal-{arms,gw,gw2,contam,unknown,depth}/runs/` | Original model/provider configuration and immutable native executor build are not qualified by the new environment. A rerun would incur separately authorized inference and is not receipt verification. |
| Prose extraction and measurement corrections | `prose.py`, `prose_score.py`, `decompose.py`, `measurement.py`, `triage.py`; `out/prose*`, `out/decompose.json`, `out/measurement.json`, `out/triage*`; `.algal-prose/runs/` | Original source corpus completeness and toolchain are unqualified. Corrections remain part of the report; no new accuracy claim is inferred from preservation. |
| Source-code dependency derivation and engine work | `codebase/` snapshots, queries, results, CAS records; `scale.py`, `out/scale*` | Source extraction uses a personal native ALGAL source checkout; exact source/build provenance is not re-established. |
| CELLxGENE extraction signals | `signals.py`, `signals_ci.py`, `out/cellxgene.json`, `out/signals*`, `.algal-signals/runs/` | Historical provider runs, API snapshot coverage, and statistical analysis are not freshly repeated. |
| scBaseCount comparison, ontology correction, release churn, provenance | `scbc_*.py`, `out/scbc-*`, `out/scbc/old/`, `out/scbc/all/`, retained ontology/curation JSON | The analysis expects excluded `out/scbc/sample_metadata.parquet`; the prior release and species files do not establish the identity of that missing aggregate. `pyarrow` and its historical version were not locked. |

The old `run.sh`, root scripts, and `codebase/run.sh` retain local native CLI
paths. Model experiments originally read `AI_GATEWAY_API_KEY` from an operator's
environment; no such key is included or requested by the portable checks. Some
scripts fetch source data, so do not treat invoking them as an offline replay.
The retained receipts report native runtime version 0.2.0; that label alone is
not an immutable build identity.

New work goes into registered campaigns and ignored local `runs/`. Do not append
new receipts to historical `.algal*` trees. The manifest is a reviewed preservation
baseline, not a tool for blessing a new run or overwriting old evidence. Any
intentional historical correction must retain its previous record and explain
the amendment; do not update hashes just to make a failure pass.

The repository license applies to original code and the new synthetic fixture.
The retention manifest makes no new licensing assertion about third-party data
already present. A future publication bundle must explicitly select artifacts,
verify redistribution terms and provenance, and keep an independent reviewed
release manifest. This preservation work does not republish additional source
text or claim a biological discovery.
