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
| `BIO_MINING_DIR` | The program's private mining directory: `cache/`, `slots/`, `data-budget.jsonl`, `data-budget.reservations/` |
| `BIO_RUN_ID` | The run id that downloads are charged to in `data-budget.jsonl` |
| `BIO_DATA_BUDGET_GB` | That run's download cap, in GB (10^9 bytes) |

When a guard refuses, it raises `KitError`, or a subclass that names the
guard. The message says what failed. From the command line, a refusal prints
`refusing: <reason>` and exits with status 2. Messages never quote file
contents or deny-list names.

Every sealed-path comparison is caseless. APFS ignores letter case and
Unicode normalization, so `Data/Sealed/` and `data/SEALED/` name the same
directory as `data/sealed/`, and the kit compares path parts after
`common.fold` (NFKD, then casefold). This applies to the fetch and import
guards, the freeze and the public assembly alike.

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
   `python -m bio_lab.campaign_kit.ledger record-open --ledger <ledger> --source <id> --campaign <name> --barrier audit/group-barrier.json --usage holdout|reused_disjoint`
   for each source that the lane opens or reuses. `--usage` must match the
   registration: `holdout` for a source nobody has opened, `reused_disjoint`
   for one an earlier, disjoint group opened.
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
- Before downloading, the fetch checks the disk floor and caps the stream at
  the free space above the floor, and at `bytes` or `max_bytes` when those are
  registered. It then reserves the cap times the number of attempts against
  the run's budget, under the budget lock, so two concurrent fetches cannot
  both spend the same headroom. The reservation is a file under
  `$BIO_MINING_DIR/data-budget.reservations/`; a fetch that finds too little
  room waits up to `budget_wait` seconds for other reservations to settle, and
  otherwise refuses. Each attempt streams at most what is still reserved.
- Every byte transferred is charged, in a `finally`, when the fetch settles:
  `download` for an accepted body, `download_rejected` for a body that failed
  validation, and `download_partial` for dropped or refused attempts.
- While the reservation is held, SIGTERM, SIGHUP and SIGINT raise
  `guards.Interrupted` in the main thread instead of ending Python at once,
  so the `finally` still settles what moved. The previous handlers are then
  restored and the signal is sent again, so the process still ends by it. A
  signal that nohup set to be ignored stays ignored. A second signal during
  that cleanup is deferred, not raised again, and a signal that arrives while
  the fetch settles waits until the bytes are recorded. This covers the
  documented cleanup too: SIGTERM to the slot runner's `--pidfile` pid is
  forwarded to the fetch.
- For a fetch killed outright (SIGKILL), the reservation file holds the path
  of its `.part` file and a metered byte count, rewritten at least every
  4 MiB or 2 seconds and whenever an attempt starts or ends. The next budget
  check charges the dead fetch as `download_unsettled` with the larger of
  that count and the earlier attempts plus the `.part` file's size, deletes
  the `.part` file, and records the reservation size alongside. It charges the
  whole reservation only when neither the count nor the file can be read (a
  reservation from an older kit). `.part` files in `cache/kit-tmp/` whose
  process is gone and that no open reservation names are deleted.
- When the body starts with the gzip magic, the HTML and JSON-error checks
  also run on its first 64 KB after decompression, so a compressed error page
  is refused too.
- The cache is content-addressed and lives under `$BIO_MINING_DIR/cache/`, in
  `kit-index/`, `kit-blobs/`, `kit-locks/` and `kit-tmp/`. Each URL has its
  own lock. On a cache hit the blob is re-hashed and re-validated, and it costs
  nothing against the budget, so a cached file counts once. Files are placed
  with a copy-on-write clone (`cp -c`, or a reflink), falling back to a copy
  checked against the disk floor, and are read-only. A file placed under
  `data/sealed/` or `data/sanger_holdout/` (by `fetch` or `import_local`) is
  never cloned, since a clone keeps the cached file's read bits: it is
  streamed into a temporary `.<name>.part-<pid>` created with mode 000,
  hashed on the way, synced and renamed into place, so it has no read bit at
  any moment, even when the fetch is killed with SIGKILL. A copy that does
  not match is deleted, and `seal.lock()` deletes the temporary files of
  dead processes.
- The receipt is one line appended to `receipts.jsonl` next to the file. It
  records the url, bytes, sha256, fetch and receipt times, the source
  (network, cache or import_local), the checks that passed and the budget run.
  A second call for the same destination returns the existing receipt. A
  receipt with a different sha, or an existing file with no receipt, is
  refused. A receipt for a sealed destination is also appended to
  `audit/sealed-receipts.jsonl` (with its campaign-relative path), which is
  how sealed receipts reach the public copy without anything under
  `data/sealed/` being read.
- `import_local(name, dest, receipts_file=..., barrier=proof)` or
  `import_local(name, dest, receipts_file=..., ledger=..., campaign=..., source=...)`
  brings in an owner-downloaded file from
  `$BIO_MINING_DIR/cache/depmap-26q1-portal/`. It refuses unless it has this
  campaign's barrier proof for the destination, or the holdout ledger records
  this campaign's discovery use of the named source (`record-discovery`); the
  default subdirectory implies the source `depmap-26q1-portal-omics`. It
  checks the size and SHA-256 recorded in the owner's receipts file
  (`<sha256>  <name>  md5=<hex>  bytes=<n>`), refuses on any mismatch and
  writes the same kind of receipt.

### freeze: the write-once manifest

`build` hashes `lane.json` and every file under `registration/`, `code/`
(which includes the vendored kit) and `tests/`, plus any `--include` paths.
Paths are campaign-relative, so the same manifest verifies the private copy
and the public copy. `build` refuses when:

- the freeze already exists
- any file exists under `results/`, `data/sealed/` or `data/sanger_holdout/`
  (in any letter case)
- a registered path is a symlink, or sits under a sealed or discovery path
  (caseless)
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
any destination under `data/sealed/`, and it must belong to the same campaign
(the destination must sit under that campaign's `data/`, compared caseless).

### seal: permissions and hash-verified reads

- `lock` sets sealed files to mode 000, `receipts.jsonl` to 444 and the
  directories to 500.
- `writable()` opens the directory for a fetch and locks it again afterwards,
  whatever happens. SIGTERM, SIGHUP and SIGINT inside the block raise
  `guards.Interrupted`, so the lock runs before the signal is sent again and
  the process ends by it; a signal during the lock waits for it to finish.
  It also locks the directory on entry, before opening it.
- One SIGKILL window remains: `open_sealed`'s brief mode 400. A file left
  readable there is locked again by the next `writable()` or `runguard.run`,
  which both lock on entry.
- `status()` reports counts and modes only, never names.
- `open_sealed(campaign_dir, name, active_run)` is the only reader. It needs
  the active run handle from `runguard.run`. It opens the file, restores mode
  000 at once (a signal meanwhile waits until mode 000 is back), and checks
  the SHA-256 against the file's receipt on the open descriptor. The run's
  `finish` record lists what was opened.

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
process may hold it. Before its `start` record it locks `data/sealed/` again
if the directory is not locked, and it refuses one that holds a symlink. It refuses a second run if `results/confirmation.runs.jsonl`
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
- **Data budget.** Records in `$BIO_MINING_DIR/data-budget.jsonl` have the
  form `{"run", "bytes", "utc", "kind", ...}`, where kind is `download`,
  `download_rejected`, `download_partial` or `download_unsettled`; all of them
  count. `reserve` holds headroom for a fetch before it starts and `settle`
  charges what it actually moved. `budget_totals` sums the bytes for each run,
  and `budget_remaining` subtracts open reservations too. The budget comes
  from `budget_gb` or `BIO_DATA_BUDGET_GB` and must be a positive, finite
  number of GB; anything else refuses.
- **Downloads made outside the kit.** Check first, then record:

  ```
  python -m <kit>.guards check --run RUN --need-bytes N   # or --need-gb G
  python -m <kit>.guards record --run RUN --bytes N [--url U] [--sha256 S] [--file F]
  ```

  `check` (`check_budget`) settles stale reservations under the budget lock,
  then refuses (exit 2) when N more bytes would pass the run's budget,
  counting recorded bytes and open reservations. `record`
  (`record_download`) always appends, because the bytes were spent; when the
  run's recorded total then passes its budget it prints the total and exits
  3 (`BudgetExceeded` in Python): stop downloading and report.
- **Compute slots.** `compute_slot()` holds an fcntl lock over
  `$BIO_MINING_DIR/slots/slot-*.lock`. `python -m <kit>.slot run [--no-wait] [--timeout S] [--pidfile P] -- <cmd>`
  runs a command inside a slot, sets `BIO_SLOT` and forwards SIGTERM, SIGINT
  and SIGHUP to the command. The command inherits the locked descriptor, so
  the slot stays busy until both the runner and the command exit; killing the
  runner, even with SIGKILL, does not free it early.
- **Conflict markers.** `find_conflict_markers(paths)` checks only the paths
  given to it. A bare separator line counts only in a file that also has an
  open or close marker.
- **Orientation.** `assert_direction(label, lower, higher)` checks the
  direction against registered reference groups. `assert_sign` checks a sign,
  and `assert_axis(label, ids, pattern)` catches a transposed matrix.

### ledger: the private holdout ledger

- `record_discovery(ledger, source, campaign)`
- `record_open(ledger, source, frozen_campaigns, campaign, date, barrier_sha256, usage=...)`

Both run under `<ledger>.lock` and are idempotent for each campaign and
source. `usage` is `holdout` or `reused_disjoint` (`--usage` on the command
line) and must agree with the ledger: `holdout` needs a source that is not yet
`OPENED`, and `reused_disjoint` needs one that is. A reuse must be disjoint:
it is refused when any frozen campaign is already in the entry's `campaigns`
or in the `opened_for` of any earlier opening. After each change the kit
checks that the change only added:

- the target entry's status may change
- lists may only grow at the end
- no key may disappear

Otherwise nothing is written.

The first group to open a source sets its status to `OPENED`, and records
`opened_for` (every frozen member's campaign), `opened_on`, `campaign` and
`frozen_set_sha256`. Later members append a `group_member` history item. A
later, disjoint group appends a `reused_disjoint` opening and does not change
the first one.

`python -m <kit>.ledger export-public --ledger <path> --deny-file F` prints the
public copy (schema `bio-holdout-ledger-public/2`), deterministic with sorted
keys: id, kind, status, opened_for, opened_on, campaigns and verified. The
free-text `name` is dropped. It refuses when id, kind or status is not a
plain token, a status is not one of the ledger's statuses, `opened_on` is not
a `YYYY-MM-DD` date or null, `verified` is not a boolean, an id repeats, or
the deny-list scan of the output finds a hit. List items that are not plain
tokens are replaced with `<free-text-withheld>` and counted.

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
  (including names split across a line break, and names joined by `-`, `_`,
  `.` or a path separator, as in `first-last`, `first_last`, `First.Last@`
  or `name_suffix`). An entry that has its own separators matches any of
  these joins, so `A-B C` also matches `a_b.c`, `A B-C` and `a-b` then `c` on
  the next line. Files over 4 MB are flagged too. The same content scan guards
  `ledger export-public` and `assemble_public --deny-file`. The deny
  file has one name per line, and lines starting with `#` are comments. A hit
  is reported as `file:line: kind`, never with the matched text. File and
  directory names are checked too (`file: deny-list name (file path)`), and a
  label that itself holds a deny-list name is printed as a neutral
  `<path #n sha256:...>`. `--staged` also reads the blobs and paths in the git
  index.

### assemble_public

`assemble_public <campaign> <worktree> --name <name> --stage prereg|outcome`
copies the campaign to `campaigns/<name>/`. At the outcome stage `report.md`
goes to `reports/<name>/report.md`. It writes an `assembly.manifest.json` with
the schema `bio.assembly-manifest.v2`.

It never walks, lists or reads a directory under `data/sealed/` or
`data/sanger_holdout/`, or any other `sealed/` directory, at any depth and in
any letter case, receipts included. Sealed receipts are published through
`audit/sealed-receipts.jsonl`, an ordinary campaign file. A `data/discovery/`
directory at any depth is not walked either; only its `receipts.jsonl` is
published. In every directory it walks, the files listed in that directory's
`receipts.jsonl` are third-party data: they are skipped and only the receipts
file is published. A malformed receipts file refuses.

It skips caches, locks, and unregistered binary data or unregistered files
over 4 MB, recording each skip with its hash. In unregistered files it
replaces personal path prefixes with `<research-root>`, `<mining-dir>`,
`<home>` and `<tmp>`.

It refuses before writing anything when:

- the freeze does not verify
- a registered file would change, would be skipped, or differs from a copy
  already in the worktree
- a symlink is present
- a personal path survives scrubbing, or would appear in the manifest
- with `--deny-file`, the hygiene lint finds a hit in a published path, a
  published file or the manifest

At the prereg stage it also refuses when `results/` or `report.md` exists.

## Tests

`tests/campaign_kit/` exercises the guards' failure paths, using synthetic
fixtures in temporary directories only. It covers:

- an HTML body served with status 200 by a local HTTP server, plain and
  gzip-compressed
- fetch failures: a conflicting receipt, an over-cap stream with no
  Content-Length, a truncated body, exhausted retries, a malformed cache
  index, a missing or truncated blob, a cache hit that fails a new
  expectation, a non-http(s) URL
- budget accounting: rejected bodies, dropped attempts, a concurrent fetch
  refused by a reservation, a stale reservation charged as unsettled
- a fetch with no size hint stopped mid-transfer by SIGTERM, by SIGTERM to the
  slot runner, and by SIGKILL, each charged close to the bytes served rather
  than its reservation, with no `.part` file left; stale reservations charged
  from their count, their `.part` file, or in full; orphaned `.part` files;
  the signal handling of `interruptible()`, including a second signal during
  cleanup and a signal while settling; the metered count written to the
  reservation before each retry; a `.part` path outside `kit-tmp/`, which is
  neither read nor deleted; and every malformed reservation field
- a scaffolded `fetch_holdout.py` stopped during its second file by SIGTERM,
  by SIGTERM to the slot runner and by SIGKILL, which leaves no readable
  sealed file (and, for SIGTERM, a locked `data/sealed/`); `writable()` and
  `open_sealed` under a signal, including a signal partway through the final
  lock; a sealed copy killed with SIGKILL mid-copy, before its rename and
  after it, which leaves nothing readable, and whose temporary file the next
  lock deletes; a sealed copy with mode 000 at every chunk; a mismatched
  sealed copy deleted; `writable()` and `runguard.run` locking a file left
  at mode 400
- budget values that are not a positive finite number, negative or
  non-integer sizes, `guards check` and a `guards record` past the budget
- `validate_content`: a first-line prefix that matches and one that does not,
  and `allow_json` with a well-formed and a truncated body
- sealed destinations in other letter cases, with no barrier, or with another
  lane's barrier
- `import_local` refusals: no authority, a size mismatch, traversal, a
  symlinked source, a missing receipts file
- barrier refusals: a lane id mismatch, a freeze replaced after the barrier,
  an invalid barrier file, and every malformed barrier `write` refuses
  without creating the file
- freeze refusals, including a deny-list hit, symlinks (a symlinked
  registered root too), escaping includes, and a manifest that is not a kit
  freeze or lacks its file list
- seal and runguard refusals, and rerun refusal
- the disk floor
- slot contention, SIGTERM forwarding, the pidfile, and a runner killed with
  SIGKILL while its command still holds the slot
- ledger idempotence, the ledger's refusal to rewrite, disjoint reuse and
  usage mismatches, and every public-export refusal
- a protocol mismatch, for numbers, strings, bools against ints, lists,
  dicts and sets; a missing or empty constants block and an unregistered
  constant
- deny-list hits in contents, file names and directory names, reported
  without the name, including names joined by `-`, `_` or `.` in the lint,
  the ledger's public export and the public assembly, and deny entries that
  contain their own separators, joined any way or across a line break
- path scrubbing, receipted files and nested private directories in the
  public assembly, and its refusals when a registered file would change or
  would not be published
- cache reuse
- a scaffolded campaign whose vendored kit freezes and whose tests pass, and
  whose tests never reach a mining dir set in the environment

One test runs the hygiene lint and the conflict-marker check over the kit's
own files.
