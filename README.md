# algal-bio

Reproducible biology research campaigns with registered predictions, traceable
observations, explicit controls, and independent review. This is the biology
research home in the Hraness ecosystem; it does not establish a formal joint lab
or imply institutional affiliation. Actual contributions and review belong in
each study's record.

The first direction is lamin/chromatin organization and cell-state responses,
using public datasets before any separately arranged wet-lab follow-up. The
credential-free fixtures qualify software behavior. They are not novel biological
findings or evidence that an autonomous investigator succeeds at research.

> [!WARNING]
> **Prospective predictions need a person to evaluate them. Nothing does it automatically.**
>
> Some campaigns freeze predictions against releases that did not exist at freeze time.
> They list those sources in `registration/protocol.json` with `"usage": "future"`. The
> next DepMap, GO, ClinGen, ORCS, UniProt or Rhea release is their holdout. No scheduled
> job watches for those releases. When one lands:
>
> 1. List the waiting campaigns: `grep -l '"future"' campaigns/*/registration/protocol.json`.
> 2. For each one, run that campaign's own `fetch_holdout.py` and then `confirm.py`
>    exactly as frozen. Do not edit the registration, the thresholds or the code.
> 3. Publish the outcome in an outcome PR, whether it confirms, fails or is inconclusive.
>
> A prediction that is never evaluated is a lost result. It is not a pass.

## Start with the portable fixture

Install Python **3.12.14**, uv **0.12.12**, Bun **1.3.14**, and Make. The Python-only
utilities support Python 3.12+; the lab instrument requires the exact reference
version selected by `.python-version`. A first install
fetches public packages identified by `uv.lock` and `bun.lock`. It needs no account,
API key, native ALGAL binary, or sibling repository.

```sh
git clone https://github.com/0thernet/algal-bio.git
cd algal-bio
make install
make check
make reproduce-fixture
uv run --frozen --offline python scripts/qualify_campaign.py --offline
uv run --frozen --offline python scripts/qualify_campaign.py --verify runs/qualification
```

After installation, the checks and fixtures run offline. `make check` verifies
historical artifact hashes, checks tracked-path policy, typechecks the TypeScript
integration, and discovers every Python and Bun test under `tests/`.
`make reproduce-fixture` recomputes an original synthetic artifact identity and
the source-bound public biology fixture. The latter reproduces the authors'
preprocessing filter on 128 retained RNA records (28 pass) and an aggregate
chromatin-track summary on 64 listed intervals. See the
[instrument method](docs/bio-instrument.md) and [registered data audit](campaigns/lamina-context-pilot/README.md).

The integrated qualification repeats three scripted controls through real Algal
Lab/ALGAL receipts, retains failed and rejected attempts, freezes selection, and
checks replay separately from fresh computation. Its coordinator transports
retained observations through a local fake provider for scripted curation and
editorial review. This qualifies the evidence handoff; it does not exercise a
live model or externally scheduled computation. An output directory must be new;
use `--out runs/another-qualification` for another retained run. To recompute a
retained run separately, use `scripts/qualify_campaign.py --recompute <directory>`.

The commands are relative to the checkout and do not read `.env` files. New local
output belongs in ignored `runs/`, `artifacts/`, or `downloads/`; caches remain in
`.cache/`. Publicly released results need a separately reviewed artifact manifest.

## Responsibilities

| Component | Responsibility |
| --- | --- |
| [Algal Lab](https://github.com/hraness/algal-lab) | Registration, prediction/observation joins, frozen study evidence |
| [ALGAL](https://github.com/hraness/algal) | Bounded execution and runtime evidence |
| algal-bio | Biological datasets, instruments, controls, campaigns, and scoped claims |
| Sponge | Optional literature and review interface; never required for reproduction |

The new package route and archived native CLI route are separate qualifications.
Algal Lab and ALGAL are pinned to immutable Git commits in the package manifest
and lockfile; source identities also bind the code actually installed. See
[environment and verification](docs/environment.md).

## Evidence and limits

Keep these gates distinct: retained bytes, receipt verification, replay, fresh
computation, independent biological support, novelty assessment, and experimental
mechanism. A checksum or receipt cannot establish that a scientific claim is true.
Investigators must not access reserved evaluation data or select candidates using
its outcomes. Paid inference, external compute, and prospective research remain
disabled unless a campaign provides verified capabilities, prices, limits, and a
funded budget.

The current [prospective decision](reports/prospective-001/decision.json) is
**no-go / not run**. The initial datasets confound cell context, perturbation and
study, and do not identify independent biological units. A new independently
evaluable design, domain review, execution qualification and funded live-run
envelope are needed before a discovery campaign. The current release is software
and calibration evidence; it contains no new biological finding. Read the
[study report](docs/study-report.md), [campaign operations](docs/campaign-operations.md),
and [implementation status](docs/implementation-status.md) for the completed and
deferred portions.

The previous OpenGenes, model-grounding, and scBaseCount studies are preserved,
including their corrections and negative findings. All **289 historical native
ALGAL run receipts** and **1,742 baseline files** are hash-manifested. They are
**not freshly reproduced by this environment**: some original inputs are absent,
and the native CLI/Python analysis toolchains were not pinned sufficiently for
portable re-execution. Read the [historical evidence index](docs/legacy-evidence.md)
and [retained study report](docs/legacy-studies.md) before interpreting those claims.

See [AGENTS.md](AGENTS.md) for contribution and delivery rules. Current campaigns,
instruments, and qualification records live in `campaigns/`, `src/bio_lab/`,
`orchestrator/`, and `reports/` as they are admitted. A software fixture passing
does not authorize or complete a live research campaign.
