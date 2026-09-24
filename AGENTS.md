# Algal Bio

This repository owns biology protocols, analyses, and research records. Algal Lab
owns experimental registration and evidence contracts; ALGAL owns bounded runtime
effects; Sponge is an optional source and review interface. Public fixtures must
work without a sibling checkout, account, API key, or paid inference.

- Preserve historical scripts, data, results, and all 289 native ALGAL receipts.
  `tests/fixtures/legacy/manifest.json` records their baseline hashes. A deliberate
  historical correction requires review and an explanation; never regenerate the
  manifest to conceal a changed or missing artifact.
- Keep evidence integrity, deterministic replay, fresh computation, computational
  association, novelty review, and experimental biology as separate claims.
- Register predictions and controls before observations; freeze selection before
  evaluator access. Retain failures, exclusions, and negative findings. Synthetic
  fixtures establish software behavior, not biological discoveries or agent merit.
- Model output is untrusted data. Proposed code gains no execution authority until
  admitted. Keep holdout data and evaluator credentials outside investigator mounts.
- Live inference and compute default to disabled. Admit them only with a verified
  account, exact model/provider configuration, current prices, resource limits, and
  an explicitly funded campaign envelope. Never infer a budget from a proposal.
- Do not add credentials, private collaborator data, restricted full text, transient
  runs, or personal filesystem paths. Large public data stays external with hashes.
  Publication artifacts need their own explicit reviewed rights/evidence manifest.
- Keep Python and Bun dependencies locked; use immutable qualified Algal Lab/ALGAL
  identities. The old native CLI is a separate, currently unqualified toolchain.
- Add Python tests under `tests/` as `test_*.py`, and Bun tests as `*.test.ts`.
  `make check` discovers both. Tests must be deterministic and credential-free;
  network-dependent scientific work belongs to an explicitly configured campaign.
- Implementers run focused checks and report commands/results. The integrator owns
  the final `make check`, `make reproduce-fixture`, and clean-checkout reproduction.
  Follow any host scheduling requirement before broad or heavyweight validation.
- Deliver through a feature branch and PR, independent review, and required checks.
  Do not force-push or change unrelated work. Routine delivery is authorized by the
  user's standing instructions after applicable gates pass.

## Layout

- `campaigns/`, `datasets/manifests/`, `schemas/`: registered designs and contracts.
- `src/bio_lab/`, `orchestrator/`: domain instrument and bounded campaign control.
- `scripts/`, `tests/`: portable verification and offline fixtures.
- `docs/`, `reports/`: method, evidence limits, and reviewed public results.
- Root legacy scripts, `facts/`, `rules/`, `out/`, `codebase/`, `.algal*`: retained
  historical work; see `docs/legacy-evidence.md` before attempting reproduction.
