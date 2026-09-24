# Environment and verification

The portable route uses Python 3.12.14, uv 0.12.12, and Bun 1.3.14 as its reference
toolchain. Python 3.12+ is the compatibility floor for the Python utilities; the
lab instrument requires the exact pinned Python version. `.python-version`,
`pyproject.toml`, `uv.lock`, `package.json`, and `bun.lock` record the environment.
The Python runtime has no third-party analysis dependencies in the foundation;
pytest is a locked development dependency. Add dependencies only with a reviewed
lock update and focused validation.

`make install` installs the frozen public dependency locks. This setup step may
use the network. Python automatic downloads are disabled by the Makefile, so
install the documented Python version first. `make check` and
`make reproduce-fixture` invoke uv with `--frozen --offline`; test and fixture
implementations must likewise make no network or paid calls. Bun has no provider
configuration in the foundation. No command reads a credential file.

The repository-local `.cache/` is ignored. Override `UV_CACHE_DIR` or
`BUN_INSTALL_CACHE_DIR` if an execution environment supplies a managed cache.
`UV` and `BUN` Make variables select installed executable commands; use the pinned
versions. Nothing assumes a particular checkout path or a sibling repository.

## Checks and extension contract

`scripts/check_repository.py` hashes every manifest-listed historical file,
requires all 289 native receipts, parses their `algal.run.v1` envelopes, verifies
the portable fixture, and rejects prohibited tracked output/credential paths.
It does not re-execute legacy native receipts, inspect credentials, or establish
rights clearance. Its path check is not a content secret scanner. When Git
metadata is absent from a source archive, it explicitly reports the tracked-path
check as unavailable; byte retention and fixture checks still run.

`uv run --frozen --offline pytest` discovers `test_*.py` under `tests/` and adds
the repository and `src/` to imports. `bun test ./tests` discovers `*.test.ts`
under the same directory. New instruments and coordinator work add tests in their
owned directories; they do not edit a central list. Focused examples are:

```sh
uv run --frozen --offline pytest tests/foundation
bun test ./tests/foundation
```

The integrator runs `make check` and `make reproduce-fixture` after convergence,
then repeats both on the exact candidate in a clean checkout outside the original
workspace. CI starts from a fresh checkout and runs installation plus those gates.
A clean-checkout result must identify its Git revision, toolchains, lockfiles,
commands, and outcome. Do not reuse another tree's validation as final evidence.

`make reproduce-fixture` first recomputes the original fixture's UTF-8 SHA-256
and byte count. Python and Bun tests independently derive that same identity.
When `scripts/reproduce_bio_fixture.py` exists, the target also invokes its
`--offline` route. That instrument owns the measurement, controls, and tolerance
checks; the tiny foundation fixture establishes only portable artifact handling.

## ALGAL routes

The old scripts run a native ALGAL 0.2.0 CLI through original local paths. Those
paths are deliberately retained as historical source, not used by portable
checks. Their exact build identity is unresolved. This environment does not
claim native replay compatibility or install a replacement binary.

New integration must consume the versioned Algal Lab observation contract through
an immutable dependency or vendored distribution with provenance. Bind ALGAL and
every executable instrument source to study identity. Do not point package
dependencies at local siblings or qualify the current TypeScript package merely
because a legacy native receipt exists. Retain old verifier identities for old
runs; report replay and fresh recomputation separately.
