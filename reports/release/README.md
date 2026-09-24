# Public calibration artifact admission

`selection.json` is the reviewed file allowlist. Every entry names its role,
rights basis, attribution, and source URLs. The builder reads only those paths;
it never discovers files by walking the repository. It rejects symlinks,
nonportable paths, transient/historical roots, unapproved file types, selected
private-path/credential patterns (including control-manifest metadata), and
inconsistent scientific status. Each input is bounded before reading; selections
have finite file-count and total-byte limits.

`manifest.json` records exact hashes, byte counts, source-evidence identities, and
environment/package identities. Review selection/content changes first, then:

```sh
uv run --frozen --offline python scripts/check_release.py reports/release --build --replace
uv run --frozen --offline python scripts/check_release.py reports/release
```

`--build` without `--replace` creates a new manifest exclusively. Rebuilding a
manifest is not independent review or authority to change a frozen study. The
builder preserves `data_limited` and `not_run` decisions and checks the full-RNA
calibration claim against its retained provenance/report. Runtime Git pins and
final offline qualification summary may initially be pending; this is reported
explicitly. Artifact admission does not run CI, recompute the external full input,
replay qualification receipts, or verify a remote release.

The exact final qualification summary is selected as
`reports/qualification/offline.json` with project report rights. After verifying
its separate receipt bundle, rebuild and create a deterministic selected-asset
archive:

```sh
uv run --frozen --offline python scripts/check_release.py reports/release \
  --archive artifacts/algal-bio-calibration.tar.gz
```

Create the ignored destination directory first. The tool refuses to overwrite an
existing asset and refuses archive creation while immutable pins, independent
selection review, or the final offline summary are absent. Runtime checks bind
the package declarations, locked workspace, resolved package records, and the
lab's transitive ALGAL pin; mentioning a SHA somewhere in a lock is insufficient.
The archive includes only selected files plus its
selection and manifest. A separate qualification receipt archive must preserve
all successful, failed, and rejected attempts from the exact verified run. Its
creation/publication belongs to the integration owner after `--verify` and
`--recompute` pass.

The selected archive is sufficient for direct fixture, registration, and scripted
qualification commands after `make install`. Full repository `make check` also
verifies retained historical files and must run in the full clone. Releasing this
subset does not repackage historical experiments, native receipts, restricted
article text, or author scripts. The corresponding public Git release still has
the repository's own separately documented history.

`publication.json` is a separate operator record. It begins with null identities
and `pending`; a local hash check cannot fill these in. After the required delivery
gates, the owner records the exact source revision, tag, release URL, both archive
hashes, and completed remote verification. Because an archive cannot contain its
own final hash, this post-publication record is not embedded in it. A subset
without that file reports `not_recorded`, not a published status.

The [study report](../../docs/study-report.md) and
[contribution record](../../docs/contributions.md) define claim and attribution
limits. In particular, this is software/calibration publication. It is neither a
prospective biological search nor a search with zero surviving candidates.
