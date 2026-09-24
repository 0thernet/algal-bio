# Calibration release delivery evidence

The [immutable prerelease](https://github.com/0thernet/algal-bio/releases/tag/v0.1.0-calibration.1)
was published on 2026-09-24 at 04:41:18 UTC. GitHub release `395329583` reports
`draft: false`, `prerelease: true`, and `immutable: true`. Its tag points directly
to `d9dea446d192c590721f29e9f29839cec779bae7`. This is software/calibration
publication; prospective biology remains `not_run` / `no_go`.

## Reviewed source and checks

- [Biology PR #1](https://github.com/0thernet/algal-bio/pull/1) merged the
  `feat/reproducible-biology-campaigns` branch. Its final candidate was
  `e102ce4668f5762f48e8d088b57c2a89b59c59c5`; the release merge commit has exactly
  the same Git tree. The qualification-file manifest names that qualified source
  candidate. The [PR check](https://github.com/0thernet/algal-bio/actions/runs/35956031470)
  and fresh [post-merge check](https://github.com/0thernet/algal-bio/actions/runs/35956512968)
  passed.
- Independent AI-assisted workers reviewed the implementation, source provenance,
  accounting/recovery, prospective gate and publication selection. The integrator
  ran final aggregate checks. This is software review, not external peer review or
  approval of a biological endpoint; see [contributions](contributions.md).
- Final clean-checkout `make check` passed **126 Python tests, 35 Bun tests with
  166 assertions, TypeScript, environment, tracked-path and historical-retention
  checks**. `make reproduce-fixture` passed. All 1,742 baseline files and 289
  native receipts remain intact. Historical studies were not re-executed.
- The clean checkout used Python 3.12.14, uv 0.12.12 and Bun 1.3.14 on macOS arm64;
  CI independently installed the frozen locks on Ubuntu. Receipt replay and
  fresh recomputation of the relocated retained qualification both passed.
- [Algal Lab PR #27](https://github.com/hraness/algal-lab/pull/27) merged as
  `134ae039b36efcacd40f3037cffb02897be625af`. Its exact integration candidate
  `927eeb2026ed0239a7e6dbc87e1b0e78e07aed2f` passed the required
  [Check](https://github.com/hraness/algal-lab/actions/runs/35954630964) and CodeQL.
  Bio retains qualified Lab source `865ea6ab125a4dc200a6a5b1c55f87de22ca5287`;
  the merge changed none of its source/package/runtime bytes. ALGAL remains
  `f899456e497656eb292d97d7c0aef5e06f1437dc`.

## Published assets

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| `algal-bio-calibration.tar.gz` | 124,438 | `de0cc72412c370dbf80d800e1f65b5d79f21665a2f2df4965ac93c7b44f11797` |
| `algal-bio-qualification.tar.gz` | 19,632 | `a34173d3f0f52ef6193182b4ca5ff95721d2da197017d3c864a4af18cf89253e` |
| `qualification-manifest.json` | 20,855 | `53e4c9161afbd8291d97bf2192e25f92d4ffce0375e56f6de0607e1361bd86a6` |
| `SHA256SUMS` | 286 | `d74a4603eac533d655bb292dd4272c0af5f461faa6410f49c6a63bda624887e2` |

The selected archive contains 68 explicitly reviewed files plus selection and byte
manifests. The receipt archive contains 108 regular JSON files (178,669 payload
bytes), including all successful, failed and rejected attempts, 30 content-addressed
artifacts and the 34-event coordinator journal. Independent publication review found
no private paths, contact data, credentials, symlinks or special files. Three
scripted repetitions passed with zero provider calls or external spending.

Staged downloads matched the local verified artifacts byte for byte. After
publication, a separate download again matched all four hashes and all 108
receipt-file hashes. A new extraction installed frozen dependencies, then passed
`check_release.py`, `reproduce_bio_fixture.py --offline`,
`qualify_campaign.py --verify`, and `qualify_campaign.py --recompute` against the
published receipt archive. These are separate byte-retention, replay and fresh
measurement checks. Extracted assets correctly report publication identity as
`not_recorded`; this later operator record is excluded from the self-hashed archive.

## Local verification limitations

Two isolated unexpected biology measurement failures occurred during macOS
validation: one relocated fresh-recomputation attempt and one integration-test
control. The original failed recomputation receipt was not retained by the
verifier; integration-test cleanup removed its temporary receipt. Bounded retained
CLI/test diagnostics and ten direct fixed-tool calls did not reproduce either
failure. Their cause remains unresolved; neither sandbox restrictions nor startup
latency was established. The final unchanged command-line gate, standalone-archive
checks, post-publication checks and Ubuntu CI passed. No admission rule, timeout or
required test was weakened.

The separate local Lab aggregate encountered unchanged XCB subprocess timeout
failures. Independent diagnostics measured long pre-user-code Bun startup latency
on that host. Its complete required CI check passed before merge. These host
observations do not qualify live providers, arbitrary-code isolation, or biological
research. Those routes remain disabled and require a separate funded, reviewed study.
