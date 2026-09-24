# Public-data calibration and a data-limited biology pilot

This release provides reproducible research infrastructure and a bounded public-data
calibration. **Prospective research was not run.** The audited starting datasets do
not admit the planned independent cross-context test, and no funded live-agent
comparison is authorized. There is no novel biological finding, no zero-survivor
search result, and no estimate of an agent's discovery ability.

The implementation follows the research discipline motivated by Anthropic's
[announcement](https://www.anthropic.com/news/claude-discovers-novel-enzyme-system)
and linked [technical report](https://www-cdn.anthropic.com/22573675ada52a8ca8a97a1a4b4326b2f208a071.pdf).
Those are inspiration and prior context; this project does not reproduce their
enzyme discovery or experimentally validate a comparable result.

## What was measured

| Measurement | Retained evidence | Result and scope |
|---|---|---|
| Complete public GSE330013 bulk-RNA preprocessing | [Full-input report](../reports/calibration/full-rna-filter.json), [source provenance](../tests/fixtures/bio/rna-provenance.json), [analysis](../scripts/calibrate_public_data.py) | 55,335 source genes, 8 libraries, 16,336 passing raw CPM > 0.26 in at least 4 libraries; independent decimal arithmetic agrees. This is the pre-TMM filter, not differential expression. |
| Offline RNA subset | [Frozen expectation](../tests/fixtures/bio/expected.json), [source rows](../tests/fixtures/bio/rna-counts.tsv) | First 128 source-order genes, 28 passing the same filter using full-input library totals. |
| Offline chromatin subset | [Frozen expectation](../tests/fixtures/bio/expected.json), [control provenance](../tests/fixtures/bio/cscore-plus-provenance.json), [mutant provenance](../tests/fixtures/bio/cscore-minus-provenance.json) | First 64 coordinate-matched intervals; mean mutant-minus-control C-score difference `0.04620996875`. Descriptive arithmetic, without an inferential p-value. |
| Source eligibility audit | [Registration](../campaigns/lamina-context-pilot/registration.json), [freeze](../campaigns/lamina-context-pilot/freeze.json), [assay decisions](../campaigns/lamina-context-pilot/README.md) | 75 submitted libraries across two studies; biological animal/culture independence unresolved; zero admitted confirmatory contrasts. |

The processed RNA source is [GSE330013](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE330013),
within [GSE330298](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE330298).
Its compressed input SHA-256 is
`4b20553eff75f70049f2e6526a7f6af965dcd4873cb479dc342f0e61ddd504fb`.
The source-order passing gene-ID list has SHA-256
`3efe2108f20e91ccbc6bf37b024880030d6b20a72fc26f41d256d48ce3971c70`.
These identify bytes/results; they do not establish biological truth.

The filtering criterion comes from the authors'
[public analysis at its inspected revision](https://github.com/katherinebossone/Lamin_CM_Paper/blob/f85db2b7b5ae4e542bb74bd7d06fadf258bc04bd/Bulk_and_scRNA/Bulk_RNA_P7_5_DE_analysis.R).
The implementation independently expresses its pre-TMM step. It does not run the
authors' full edgeR workflow, re-estimate dispersions, or reproduce significance
claims. Author scripts and article full text are not included in this release.

The [GSE330103](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE330103)
C-score tracks are genotype aggregates. Their listed intervals include source
coordinate overlaps, which are preserved and reported; the measurement is an
interval mean, not a genome-coverage weighted mean. Neither 64 intervals nor 128
genes is a biological sample count. The RNA and chromatin fixtures are separate:
P7.5 whole-heart RNA cannot be silently treated as paired with P0.5 isolated
cardiomyocyte chromatin.

## Qualification and evidence boundaries

The [offline qualification registration](../campaigns/qualification/registration.json)
fixes three scripted repetitions. Each repetition registers a known control,
retains a failed unadmitted analysis, rejects a malformed proposal, and freezes
selection before evaluation. Expected values are supplied to the scripted control.
Consequently, successful recovery measures software behavior, not discovery.

The [retained final qualification summary](../reports/qualification/offline.json)
records three passing repetitions, each with one successful control, one failed
measurement, and one rejected proposal. Receipt replay and separate fresh
computation passed, with zero provider calls or external spending. The coordinator
retains 34 events for three scripted review tasks. Repetition count is not
biological replication.

The separate qualification archive contains the exact registration, immutable
artifacts, receipts, selection, failures, and score report. Run `--verify` on that
retained run to check replay, and `--recompute` for fresh measurements. A summary
without its verified artifact chain is insufficient; use the published bundle
identified in the release record for this check.

Algal Lab owns registration, observation joins, freezing, and evidence verification.
ALGAL supplies bounded runtime effects. Algal Bio owns the biological instrument,
eligibility decisions, and scoped claims. Sponge is an optional source/review
interface; none of these reproduction commands requires a Sponge account. Package
and dependency identities are taken from the release's `package.json`, `bun.lock`,
`pyproject.toml`, and `uv.lock`; no sibling checkout or mutable branch is a runtime
substitute.

This calibration does not qualify paid providers, unrestricted proposed code,
production job isolation, or a scientific autonomous investigator. Registration
integrity, deterministic replay, fresh computation, independent association,
novelty, and experimental mechanism remain separate judgments.

## Why prospective research is not admitted

The proposed future question is whether unperturbed reference chromatin improves
out-of-study expression-response direction prediction over an expression-only
baseline. The second audited study,
[GSE89520](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE89520), uses embryonic
stem cells with lamin-B1/B2/A triple knockout; the cardiac study uses a conditional
Lmnb1 perturbation. Study, context, and perturbation are confounded. The sources
also differ in age, cell preparation, assembly/annotation qualification, and assay
coverage. Adding regression covariates cannot resolve the missing design.

The source audit preserves contradictory IgG ages/genotypes and the scRNA
processing-text/library-count discrepancy. GSM/BioSample accessions and `Rep`
labels identify deposited material, but do not by themselves establish animal,
culture, pooling, litter, batch, or cross-assay independence. No suitable reserved
cohort has been selected. All inspected named data are public reproduction
material; none is retrospectively relabeled as a holdout.

The resulting decision is **data-limited / no-go**. It is not a negative biological
association result and not a failed search for new candidates: that search did
not occur. The future campaign requires a separately reviewed design with eligible
independent data, prediction-time features, biological-unit precision, frozen
nulls/multiplicity policy, domain endpoint review, evaluator isolation, and a
funded live-run envelope if providers are used. Wet-lab follow-up remains a
separate, unstarted study whose endpoint and actual resources must be specified
with participating scientists.

## Reproduce and inspect

Use the published Git revision and reference toolchain in
[environment.md](environment.md). From a full repository clone:

```sh
make install
make check
make reproduce-fixture
uv run --frozen --offline python scripts/check_registration.py campaigns/lamina-context-pilot
uv run --frozen --offline python scripts/qualify_campaign.py --offline --out runs/qualification-review
uv run --frozen --offline python scripts/qualify_campaign.py --verify runs/qualification-review
uv run --frozen --offline python scripts/qualify_campaign.py --recompute runs/qualification-review
uv run --frozen --offline python scripts/check_release.py reports/release
```

Installation may fetch the locked public dependencies; subsequent commands are
offline and need no credentials or paid inference. The qualification output path
must be new: prior runs are retained rather than overwritten.

To recheck the complete 55,335-gene source, download the exact compressed artifact
named in `rna-provenance.json` to an external/ignored directory, then run:

```sh
uv run --frozen --offline python scripts/calibrate_public_data.py \
  --rna downloads/GSE330013_P7_5_Bulk_RNAseq_Counts.txt.gz
```

The tool verifies the complete input hash, library totals, retained projection,
and independently calculated passing IDs. The large source download is separate
from the offline fixture. No source file is silently fetched or substituted.

## Release scope and credit

The [selection](../reports/release/selection.json) explicitly lists public
software/calibration assets, rights basis, attribution, and evidence role. The
[manifest](../reports/release/manifest.json) binds the selected bytes. The release
checker neither walks arbitrary repository history nor automatically republishes
transient runs. Its content scan is a bounded safeguard, not legal or security
review. Third-party molecular data retains its own source terms; the software MIT
license does not relicense it.

The optional selected-asset archive is a calibration subset, not the complete
historical repository. Run its fixture, registration, and qualification commands
directly after installation. Full `make check` also verifies historical retention
and belongs in the full clone. Historical studies and native receipts remain in
the repository, with their reproduction limits documented separately.

Publication identity is recorded separately in
[publication.json](../reports/release/publication.json). A valid local manifest
does not mean a PR merged, a release was published, or the published bytes were
verified. The delivery owner records those exact identities after the required
review, CI, clean-checkout reproduction, and publication verification.
This mutable post-publication record is not embedded in the selected-asset archive;
an extracted subset therefore reports publication identity as `not_recorded`.

See [contributions.md](contributions.md) for attribution and the currently
unfilled scientific review roles. Cite this software using `CITATION.cff` and
cite the dataset authors separately when using their measurements.
