# Offline campaign operations

The coordinator in `orchestrator/index.ts` qualifies recoverable **JSON-only
fixture control**. It can record proposals, supervisor critiques, primary bundles,
curation, and editorial review without calling a model or external provider. Scripted roles
are not independent scientific reviewers or evidence of multi-agent superiority.

External compute, live inference, arbitrary tools, and proposed executable code
are **disabled**. A caller cannot supply a replacement provider object: only the
closed built-in fixture provider is accepted. This implementation does not claim
an OS sandbox, independently enforced cloud expiry, evaluator credential isolation,
or safe execution of model-generated code. No installed isolation boundary was
qualified, so those Phase 5 acceptance criteria remain activation gates.

## Persistent state and recovery

A campaign directory contains immutable, sequential `events/00000000.json` files.
Each binds the preceding digest, timestamp, event kind, and primary event data with
SHA-256 of canonical JSON. The first event stores the validated campaign config,
including the registration and judge identities, limits, discovery allowlist,
and total USD budget. Reopening with a changed budget, judge, registration, or
other configuration fails. Changes require a newly registered campaign.

The append protocol writes and fsyncs a temporary file, atomically creates the
next event path without overwriting an existing file, then fsyncs the directory.
Concurrent writers cannot silently replace each other's event. An interrupted
temporary file is ignored; there is no stale exclusive lock to remove after a
crash. A competing append fails with `ConcurrentUpdate`; reread and reconcile
before trying the operation again. Do not delete or renumber recorded events.

A recorded controller lease carries an owner, a fresh per-instance session,
expiry, and increasing fence number. Only that live session may mutate the
campaign. Another process, even with the same owner label, waits for release or
expiry before acquiring. Old sessions cannot append after a new owner acquires.
There are no background provider polling loops or externally held compute leases.
The integration owner controls one dispatcher/collector per campaign.

Hash chaining detects changed bytes and missing interior events. A removed suffix
cannot be detected from the remaining journal alone: anchor `headSha256` and event
count in the externally frozen qualification/release record. Journal files are
not signatures or protection against a filesystem owner rewriting all evidence.
Both append and recovery also validate the event transitions, lease bounds,
submission identity, retry/revision limits, budget equations, and review evidence.
A correctly rehashed but invalid transition is rejected. Journal events are capped
at 128 KiB of UTF-8 bytes and read only from bounded regular files.
Use supported local filesystems with atomic hard-link creation and directory
fsync; network/distributed filesystem semantics are unqualified.

## Budget and task transitions

Money uses nonnegative safe integer USD micros. Every estimate and final charge
must price inference, compute, storage, egress, and recovery. All five components
are reserved together before dispatch. Active reservations plus settled charges
cannot exceed the immutable campaign total. Unknown final spend or an unresolved
submission blocks new admission, retains its reservation, and requires provider
lookup/reconciliation. A component-level overrun is retained as a breach and
blocks further work; the controller cannot raise its own limit.

The ordinary path is:

```text
proposed → supervisor admission + reservation → dispatch intent → submitted
                                                           ↘ uncertain
submitted/uncertain → reconciled completed | failed | cancelled
proposed → rejected → bounded revision
failed/cancelled → bounded, newly reserved retry
```

Task, retry, revision, event, job-time, and artifact-size limits are finite.
Rejected and failed attempts remain in the event history. Invalid proposals add
a rejection event and a payload digest when a bounded JSON encoding exists;
their unvalidated content receives no authority. An admitted attempt
gets a deterministic submission key derived from frozen config identity, task,
and attempt before any dispatch. Dispatch records the provider route identity
before calling it. Recovery must use that same route and look up the submission
key before submitting; it never guesses that a lost response means no job exists.
The provider also treats that key idempotently. Repeated collection does not
double-charge a terminal task. Collection can recover a lost submission response,
recording the observed job identity before its outcome or charge is settled.
If a previously observed job later disappears from provider lookup, the attempt
keeps its reservation and requires reconciliation; it is not resubmitted or
treated as a never-submitted cancellation.

The fixture provider persists jobs and simulates completion, failure, expiry,
cancellation, lost job-ID responses, and unknown final costs. Jobs that were never
submitted before their deadline are cancelled at zero charge. Existing jobs are
cancelled/reconciled at the deadline. This demonstrates controller mechanics;
checking fixture time when polled is **not** evidence of independent provider
expiry when the controller is dead. Real execution cannot be activated through
this API, even if a user supplies nonzero simulated budgets.

## Data access and roles

The trusted host constructs a frozen list of discovery artifacts, each with an
identifier, relative path, SHA-256, and optional accession. Reads can request an
artifact ID, exact allowlisted path, or a uniquely matching accession. Anything
else is denied and recorded, including reserved IDs, holdout/evaluator paths,
excluded accessions, URL fetches, traversal, escaped symlinks, changed bytes, and
oversized data. No API fetches arbitrary accessions or executes a tool. Evaluator
storage is not mounted or opened by this route. Reads reject special files and
bound bytes while reading; a named pipe cannot stall the controller waiting for
a writer. Proposal parameters and fixture results are each capped at 8 KiB of
UTF-8 JSON, including multibyte text.

The current lamina pilot has reproduction inputs and no admitted prospective
discovery or holdout data. The fixture coordinator may map the exact public
`registration.qualification_fixture.inputs` into its read allowlist for software
qualification; the protocol remains `descriptive_qualification`. This mapping
does not convert reproduction data into an independent discovery corpus.

Investigator proposals have no self-approval or review authority. Supervisor
critique admits/rejects; curator review requires a hash-bound primary observation
bundle; editorial review requires the recorded curation evidence. Evaluator
assessment has its own role. Reviews cite artifact/event digests and locators;
the primary bundle can be read alongside prose and every such read is logged.
Role parameters are supplied by the trusted controller, never taken from model
JSON. These are application-level role checks, not user authentication or a host
sandbox. Host code with full filesystem authority is outside this boundary.

Untrusted models may return only the bounded `Proposal` JSON contract. Its
`parameters` remain data. An `execute-code` proposal can be retained but cannot
be admitted. Unknown fields, unsafe money, excessive nesting, and oversized
payloads are rejected. A model must never receive the Campaign object or host
filesystem/tool authority.

## API and focused checks

`CampaignConfig`, `Proposal`, `Costs`, and `EvidenceRef` are exported contracts.
The high-level call sequence is:

```typescript
const campaign = new Campaign(runDirectory, frozenConfig, "controller-1", {
  dataRoot: repositoryRoot,
});
campaign.acquireLease();
campaign.propose("investigator", boundedProposal, fiveComponentEstimate);
campaign.critique("supervisor", boundedProposal.taskId, "admit", critiqueReason);
const provider = createOfflineProvider(fixtureDirectory, {
  actualCost: fiveComponentActualCost,
  result: primaryObservationBundle,
});
campaign.dispatch(boundedProposal.taskId, provider);
campaign.collect(boundedProposal.taskId, provider);
const primary = campaign.primaryEvidence(boundedProposal.taskId);
campaign.readPrimaryBundle("curator", boundedProposal.taskId);
const curation = campaign.recordReview("curator", boundedProposal.taskId,
  "curation", curationReason, [primary]);
campaign.recordReview("editor", boundedProposal.taskId,
  "editorial", editorialReason, [curation, primary]);
campaign.releaseLease();
```

Reconstruct a Campaign with identical config to inspect/recover it. Acquire its
lease before writes; after a crash, wait for the previous lease to expire.
Recreate the fixture provider from the same provider directory, then call
`dispatch` to reconcile a lost submission response or `collect` to reconcile a
known job. Never switch provider directories to evade uncertain state.

```sh
bun test ./tests/orchestrator
uv run --frozen --offline pytest tests/orchestrator
uv run --frozen --offline python scripts/check_budget.py --fixtures
uv run --frozen --offline python scripts/check_budget.py --journal runs/example/events
```

The Python audit independently calculates reservations/charges and rejects
unpriced components, duplicate settlement, unsafe admission, or an incorrectly
reported breach. It invokes the Bun verifier for canonical JSON hash integrity
and valid event transitions;
this is explicitly separate from the independent integer arithmetic. The fixture
exercise retains a crash, uncertain spend, recovery, budget denial, rejected
follow-up, primary observation, and separate curator/editor records in one chain.

## Optional Sponge export

No Sponge account or product change is needed. A future adapter may export local
source notes and review references as JSON with original artifact/event SHA-256,
locator, role, date, and source URL. Import must validate the original referenced
artifact and append a new review event; it must not replace canonical local
evidence or import a new budget, judge, permission, or executable tool. Until
that adapter is implemented and tested, plain local records are authoritative.

## Remaining live activation evidence

Before supporting a live route, qualify an actual OS sandbox with restricted
mounts, an allowlisted tool/network broker, separately owned evaluator storage
and credentials, provider-enforced expiry and quotas, account/model/price
preflight, durable provider idempotency lookup, cancellation reconciliation, and
an explicitly funded envelope. Register contamination handling and data access
logs. Existing receipt or fixture integrity does not satisfy those gates.
