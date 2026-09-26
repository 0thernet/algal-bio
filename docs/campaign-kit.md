# Campaign kit

`src/bio_lab/campaign_kit/` holds the fail-closed guards that sealed-holdout
campaigns share. The completed transfer campaigns wrote these steps by hand:
receipted downloads, a write-once freeze, a single confirmation run, sealed
reads and public assembly. The kit generalises them and adds what a group of
lanes needs when they share a holdout source: a group barrier, a locked
holdout ledger, compute slots and a data budget.

The kit uses the standard library only. Every module imports its siblings
relatively, so the same files work as `bio_lab.campaign_kit` in this repository
and as `campaign_kit` once `scripts/new_campaign.py` has vendored them into a
campaign's `code/` directory. The code holds no machine paths. Private
locations come from explicit arguments or from these environment variables:

| Variable | Meaning |
| --- | --- |
| `BIO_MINING_DIR` | The program's private mining directory: `cache/`, `slots/`, `data-budget.jsonl` |
| `BIO_RUN_ID` | The run id that downloads are charged to in `data-budget.jsonl` |
| `BIO_DATA_BUDGET_GB` | That run's download cap, in GB (10^9 bytes) |

When a guard refuses, it raises `KitError`, or a subclass that names the
guard. The message says what failed. From the command line, a refusal prints
`refusing: <reason>` and exits with status 2. Messages never quote file
contents or deny-list names.

## Lane lifecycle

A lane is one campaign. Its private directory is `biology-<name>`, where
`<name>` is `<slug>-<date>`. Its public copies go under `campaigns/<name>/` and
`reports/<name>/`.

1. **Lane card.** The orchestrator writes `lane.json` once. It holds at least
   the lane `id`.
2. **Scaffold.** Create the directory layout:
   `python scripts/new_campaign.py <name> <research-root>/biology-<name> --lane-json card.json`.
   The script creates only the parts that are missing and never overwrites a
   file.
3. **Build.** Do the metadata audit and the prior-art search, then write
   `registration/protocol.json`. Every number the evaluation uses goes in its
   `"constants"` object. Write the discovery code, a deterministic selection
   rule, `code/fetch_holdout.py` and `code/confirm.py` from the templates, and
   pure tests. Record any discovery use of a ledger source with
   `ledger record-discovery` before reading it.
4. **Lint.** Run `python -m campaign_kit.lint protocol .` and
   `python -m campaign_kit.lint hygiene --deny-file <deny list> <files>`, with
   `code/` on `PYTHONPATH`.
5. **Freeze.** Run `python code/freeze.py build` once, after the independent
   pre-freeze review. It writes `registration/freeze.json`, and the lane's
   freeze sha is the SHA-256 of that file's bytes.
6. **Preregistration.** Run
   `python -m bio_lab.campaign_kit.assemble_public <campaign> <worktree> --name <name> --stage prereg --deny-file <deny list>`,
   then open the PR and merge it.
7. **Group barrier.** Once every member of the holdout group has frozen and
   merged, or has been released, the orchestrator writes
   `audit/group-barrier.json`. Then `barrier require` must pass for this lane
   and this freeze sha.
8. **Holdout ledger.** Run
   `python -m bio_lab.campaign_kit.ledger record-open --ledger <ledger> --source <id> --campaign <name> --barrier audit/group-barrier.json`
   for each source that the lane opens or reuses.
9. **Fetch.** Run `python code/fetch_holdout.py --freeze-sha256 <sha>`. It
   calls `barrier.require` before any network access, then fetches every
   registered holdout file into `data/sealed/` with receipts, and locks the
   directory again.
10. **Confirm.** Run
    `python -m campaign_kit.slot run -- python code/confirm.py` exactly once.
    A rerun needs `--erratum errata/E<n>.md`.
11. **Outcome.** Write `report.md` and do the post-outcome audit. Then run
    `assemble_public ... --stage outcome` and open the outcome PR.

## Modules

### receipts: downloads validated by content

```python
from campaign_kit.receipts import Expect, fetch, import_local

receipt = fetch(url, dest, Expect(first_line="ModelID,GeneID,score",
                                  required_columns=("ModelID",), max_bytes=2_000_000_000),
                barrier=proof)            # proof only for data/sealed/ destinations
```

- Every request sends a descriptive User-Agent (`receipts.USER_AGENT`).
  Validation looks at the content, never at the HTTP status. The kit rejects:
  - an empty body
  - an HTML page, such as an error or login page served with status 200
  - a JSON body where a data file was expected
  - a JSON error object, even when `allow_json` is set

  It then checks, as registered: magic bytes, the first line or a prefix of it
  (read through gzip when the file is gzip), required header columns, the size
  and a published SHA-256.
- Retries cover status 408, 425, 429 and 5xx, and dropped connections, with
  backoff. Any other HTTP error fails at once.
- Before downloading, the fetch checks the disk floor and the run's remaining
  budget. The stream is capped at the smaller of the two, and at `bytes` or
  `max_bytes` when those are registered.
- The cache is content-addressed and lives under `$BIO_MINING_DIR/cache/`, in
  `kit-index/`, `kit-blobs/`, `kit-locks/` and `kit-tmp/`. Each URL has its
  own lock. On a cache hit the blob is re-hashed and re-validated, and it costs
  nothing against the budget, so a cached file counts once. Files are placed
  with a copy-on-write clone (`cp -c`, or a reflink), falling back to a copy
  checked against the disk floor. A placed file is read-only.
- The receipt is one line appended to `receipts.jsonl` next to the file. It
  records the url, bytes, sha256, fetch and receipt times, the source
  (network, cache or import_local), the checks that passed and the budget run.
  A second call for the same destination returns the existing receipt. A
  receipt with a different sha, or an existing file with no receipt, is
  refused.
- `import_local(name, dest, receipts_file=...)` brings in an owner-downloaded
  file from `$BIO_MINING_DIR/cache/depmap-26q1-portal/`. It checks the size
  and SHA-256 recorded in the owner's receipts file
  (`<sha256>  <name>  md5=<hex>  bytes=<n>`), refuses on any mismatch and
  writes the same kind of receipt.

### freeze: the write-once manifest

`build` hashes `lane.json` and every file under `registration/`, `code/`
(which includes the vendored kit) and `tests/`, plus any `--include` paths.
Paths are campaign-relative, so the same manifest verifies the private copy
and the public copy. `build` refuses when:

- the freeze already exists
- any file exists under `results/` or `data/sealed/`
- a registered path is a symlink, or sits under a sealed or discovery path
- a registered file is over 4 MB, contains a personal path, or (with
  `--deny-file`) hits the deny list

`verify` reports changed, missing and added files, and fails if the manifest's
own top digest no longer matches.

### barrier: the holdout-group barrier

`audit/group-barrier.json` is compact JSON with a fixed key order. It is the
same bytes as the orchestrator's `JSON.stringify` output:

```json
{"schema":"bio-group-barrier/1","run_id":"...","members":["S01","S02"],"frozen":[{"id":"S01","campaign":"<name>","freeze_sha256":"<64 hex>","merge_sha":"<40 hex>"}],"released":["S02"]}
```

Every member must be either frozen or released. `write` stores the file once:
writing identical content again does nothing, and different content is
refused. `require(campaign_dir, lane_id, freeze_sha256)` refuses unless all of
these hold:

- the file exists and validates
- it lists this lane as frozen with this freeze sha and a merge sha
- it names this directory
- `lane.json` agrees
- `registration/freeze.json` hashes to the freeze sha
- `freeze verify` passes

It returns a `BarrierProof`. `fetch` and `import_local` require that proof for
any destination under `data/sealed/`, and it must belong to the same campaign.

### seal: permissions and hash-verified reads

- `lock` sets sealed files to mode 000, `receipts.jsonl` to 444 and the
  directories to 500.
- `writable()` opens the directory for a fetch and locks it again afterwards.
- `status()` reports counts and modes only, never names.
- `open_sealed(campaign_dir, name, active_run)` is the only reader. It needs
  the active run handle from `runguard.run`. It opens the file, restores mode
  000 at once, and checks the SHA-256 against the file's receipt on the open
  descriptor. The run's `finish` record lists what was opened.

These permissions are a speed bump against accidental reads. The evidence is
the freeze, the barrier and the run ledger.

### runguard: one confirmation run

```python
with runguard.run(ROOT, lane_id=LANE_ID, erratum=args.erratum) as run:
    with seal.open_sealed(ROOT, "holdout.csv", run) as handle:
        ...
    run.finish("SUPPORTED", outputs=["results/confirmation.summary.json"])
```

A run requires the freeze and passes through `barrier.require`, and only one
process may hold it. It refuses a second run if `results/confirmation.runs.jsonl`
already has records or any `results/confirmation.*` file exists. A rerun
needs `erratum="errata/E<n>.md"`: an existing, nonempty file that no earlier
run has used. An erratum on a first run is refused.

The ledger is append-only. It gets a `start` record, then one of:

- `finish`: the label, a sha256 for each output, and the sealed files opened
- `crash`: the exception type only, since a message could quote a sealed value
- `incomplete`: the block ended without `finish`

### stats

`bh_qvalues`, returned in input order. It matches R's `p.adjust(p, "BH")`, and
the name is kept from the earlier campaigns. The module also has:

- `permute_within` and `permutation_test`, with optional strata
- `permutation_pvalue`, computed as (1 + extreme) / (1 + n)
- `bootstrap_ci`
- the exact tests `binom_sf`, `sign_test` and `sign_test_differences`
- `wilson_interval`

Randomness always comes from an explicit integer seed or a `random.Random`.

### guards

- **Disk floor.** `require_disk_floor(path, need_bytes, floor_gb=10)` refuses
  unless free space stays above the floor after the write.
- **Data budget.** `record_download` appends to
  `$BIO_MINING_DIR/data-budget.jsonl`. The check and the append happen under
  one lock, with records of the form `{"run", "bytes", "utc", "kind": "download", ...}`.
  `budget_totals` sums the bytes for each run.
- **Compute slots.** `compute_slot()` holds an fcntl lock over
  `$BIO_MINING_DIR/slots/slot-*.lock`. `python -m <kit>.slot run [--no-wait] [--timeout S] [--pidfile P] -- <cmd>`
  runs a command inside a slot, sets `BIO_SLOT` and forwards SIGTERM, SIGINT
  and SIGHUP to the command.
- **Conflict markers.** `find_conflict_markers(paths)` checks only the paths
  given to it. A bare separator line counts only in a file that also has an
  open or close marker.
- **Orientation.** `assert_direction(label, lower, higher)` checks the
  direction against registered reference groups. `assert_sign` checks a sign,
  and `assert_axis(label, ids, pattern)` catches a transposed matrix.

### ledger: the private holdout ledger

- `record_discovery(ledger, source, campaign)`
- `record_open(ledger, source, frozen_campaigns, campaign, date, barrier_sha256)`

Both run under `<ledger>.lock` and are idempotent for each campaign and
source. After each change the kit checks that the change only added:

- the target entry's status may change
- lists may only grow at the end
- no key may disappear

Otherwise nothing is written.

The first group to open a source sets its status to `OPENED`, and records
`opened_for` (every frozen member's campaign), `opened_on`, `campaign` and
`frozen_set_sha256`. Later members append a `group_member` history item. A
later, disjoint group appends a `reused_disjoint` opening and does not change
the first one.

`python -m <kit>.ledger export-public --ledger <path>` prints the public copy,
deterministic with sorted keys: id, kind, name, status, opened_for, opened_on,
campaigns and verified.

### lint

- `lint protocol <campaign>` checks `code/confirm.py`, or the files given with
  `--code`. It flags:
  - a module-level UPPER_CASE literal that is not registered in `constants`,
    or that differs from the registered value
  - a constant read by key (`K["X"]`, `K.get("X")`, `constant(dir, "X")`,
    `["constants"]["X"]`) that is not registered
  - a bare float in a comparison

  `constants_exempt` names the constants to skip, each with a reason.
- `lint hygiene --deny-file F [--staged --repo DIR] [paths]` flags personal
  paths, whole-word case-insensitive matches of the names in the deny file
  (including names split across a line break) and files over 4 MB. The deny
  file has one name per line, and lines starting with `#` are comments. A hit
  is reported as `file:line: kind`, never with the matched text. `--staged`
  also reads the blobs in the git index.

### assemble_public

`assemble_public <campaign> <worktree> --name <name> --stage prereg|outcome`
copies the campaign to `campaigns/<name>/`. At the outcome stage `report.md`
goes to `reports/<name>/report.md`. It writes an `assembly.manifest.json` with
the schema `bio.assembly-manifest.v2`.

It never walks `data/sealed/`, `data/sanger_holdout/`, `data/discovery/` or
any other `sealed/` directory. Only their `receipts.jsonl` is published.

It skips caches, locks, and unregistered binary data or unregistered files
over 4 MB, recording each skip with its hash. In unregistered files it
replaces personal path prefixes with `<research-root>`, `<mining-dir>`,
`<home>` and `<tmp>`.

It refuses before writing anything when:

- the freeze does not verify
- a registered file would change, would be skipped, or differs from a copy
  already in the worktree
- a symlink is present
- a personal path survives scrubbing
- the hygiene lint finds a hit

At the prereg stage it also refuses when `results/` or `report.md` exists.

## Tests

`tests/campaign_kit/` exercises every guard's failure path, using synthetic
fixtures in temporary directories only. It covers:

- an HTML body served with status 200 by a local HTTP server
- freeze refusals
- rerun refusal
- a fetch with no barrier, or with another lane's barrier
- the disk floor
- slot contention
- a budget overrun
- ledger idempotence and the ledger's refusal to rewrite
- a protocol mismatch
- a deny-list hit reported without the name
- path scrubbing
- cache reuse
- a scaffolded campaign whose vendored kit freezes and whose tests pass

One test runs the hygiene lint and the conflict-marker check over the kit's
own files.
