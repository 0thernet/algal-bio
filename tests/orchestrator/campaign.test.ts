import { afterEach, expect, test } from "bun:test";
import { mkdtempSync, readFileSync, readdirSync, writeFileSync, rmSync, symlinkSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { Campaign, CampaignError, FixtureCrash, canonical, createOfflineProvider, readEvents, sha256, validateCosts,
  verifyCampaignJournal, type CampaignConfig, type Costs, type Event, type Proposal } from "../../orchestrator/index.ts";

const temporary: string[] = [];
afterEach(() => { for (const path of temporary.splice(0)) rmSync(path, { recursive: true, force: true }); });
const cost: Costs = { inferenceMicros: 20, computeMicros: 20, storageMicros: 10, egressMicros: 10, recoveryMicros: 40 };
function proposal(taskId = "control"): Proposal {
  return { taskId, question: "Reproduce an admitted measurement", instrumentId: "fixture-v1", inputArtifactIds: ["public"], action: "json-observation", parameters: { seed: 1 } };
}
function setup(overrides: Partial<CampaignConfig> = {}) {
  const directory = mkdtempSync(join(tmpdir(), "bio-campaign-test-")); temporary.push(directory);
  writeFileSync(join(directory, "input.json"), '{"value":1}\n');
  const config: CampaignConfig = {
    schema: "algal-bio.campaign.v1", campaignId: "offline-test", currency: "USD", budgetMicros: 200,
    registrationSha256: "a".repeat(64), judgeSha256: "b".repeat(64),
    limits: { maxTasks: 4, maxRetries: 1, maxRevisions: 1, maxEvents: 200, jobTimeoutMs: 1000, leaseMs: 100, maxArtifactBytes: 4096 },
    discoveryArtifacts: [{ id: "public", path: "input.json", sha256: sha256(readFileSync(join(directory, "input.json"))), accession: "GSEPUBLIC" }],
    excludedAccessions: ["GSEEXCLUDED"], reservedArtifactIds: ["holdout-1"], ...overrides,
  };
  let now = 1000;
  const clock = () => now;
  const run = join(directory, "campaign");
  const campaign = new Campaign(run, config, "owner-a", { clock, dataRoot: directory }); campaign.acquireLease();
  return { directory, run, config, campaign, clock, tick: (ms: number) => { now += ms; } };
}
function admit(campaign: Campaign, taskId = "control", estimate = cost) {
  campaign.propose("investigator", proposal(taskId), estimate);
  campaign.critique("supervisor", taskId, "admit", "Bounded registered control with reserved recovery allowance");
}
// Rehashing is deliberate: these regressions must fail semantic replay, not merely
// the outer hash-chain check. Journals still need an independently anchored head.
function forgedAppend(directory: string, kind: string, data: Event["data"], atMs?: number) {
  const events = readEvents(directory);
  const body = { schema: "algal-bio.campaign-event.v1", sequence: events.length,
    previousSha256: events.at(-1)!.sha256, atMs: atMs ?? events.at(-1)!.atMs, kind, data };
  writeFileSync(join(directory, `${String(events.length).padStart(8, "0")}.json`), canonical({ ...body, sha256: sha256(canonical(body)) }));
  expect(readEvents(directory)).toHaveLength(events.length + 1);
}
function forgedLast(directory: string, change: (data: Record<string, unknown>) => void) {
  const { sha256: _, ...body } = readEvents(directory).at(-1)!;
  change(body.data as Record<string, unknown>);
  writeFileSync(join(directory, `${String(body.sequence).padStart(8, "0")}.json`), canonical({ ...body, sha256: sha256(canonical(body)) }));
  expect(() => readEvents(directory)).not.toThrow();
}

test("registration, all cost components, primary data and review evidence persist", () => {
  const s = setup(); admit(s.campaign);
  expect(s.campaign.snapshot().reservedMicros).toBe(100);
  const bundle = { observations: [{ id: "known-control", measurement: 2.5 }], sourceSha256: "c".repeat(64) };
  const provider = createOfflineProvider(join(s.directory, "provider"), { clock: s.clock, actualCost: cost, result: bundle });
  s.campaign.dispatch("control", provider); s.campaign.collect("control", provider);
  s.campaign.collect("control", provider);
  expect(s.campaign.snapshot().spentMicros).toBe(100);
  expect(s.campaign.snapshot().reservedMicros).toBe(0);
  expect(s.campaign.readPrimaryBundle("curator", "control")).toEqual(bundle);
  const primary = s.campaign.primaryEvidence("control");
  const curation = s.campaign.recordReview("curator", "control", "curation", "Compared primary measurement against registered reference", [primary]);
  s.campaign.recordReview("editor", "control", "editorial", "Software fixture only; no discovery claim", [curation, primary]);
  const events = readEvents(s.campaign.eventsDirectory);
  expect(events.filter((event) => event.kind === "review-recorded")).toHaveLength(2);
  expect(events.findIndex((event) => event.kind === "task-admitted")).toBeLessThan(events.findIndex((event) => event.kind === "dispatch-intent"));
  expect(provider.submissionCount).toBe(1);
});

for (const point of ["before", "after"] as const) {
  test(`crash ${point} submission recovers persisted identity with no duplicate job`, () => {
    const s = setup(); admit(s.campaign);
    const provider = createOfflineProvider(join(s.directory, "provider"), {
      clock: s.clock, actualCost: cost,
      crashBeforeSubmitOnce: point === "before", crashAfterSubmitOnce: point === "after",
    });
    expect(() => s.campaign.dispatch("control", provider)).toThrow(FixtureCrash);
    const key = s.campaign.snapshot().tasks.control!.submissionKey;
    expect(s.campaign.snapshot().tasks.control!.status).toBe("submitting");
    expect(s.campaign.snapshot().uncertain).toBe(true);
    expect(provider.submissionCount).toBe(point === "before" ? 0 : 1);
    s.tick(101);
    const recovered = new Campaign(s.run, s.config, "owner-b", { clock: s.clock, dataRoot: s.directory }); recovered.acquireLease();
    recovered.dispatch("control", provider); recovered.collect("control", provider);
    expect(recovered.snapshot().tasks.control!.status).toBe("completed");
    expect(recovered.snapshot().tasks.control!.submissionKey).toBe(key);
    expect(recovered.snapshot().spentMicros).toBe(100);
    expect(provider.submissionCount).toBe(1);
    expect(() => s.campaign.collect("control", provider)).toThrow("live lease");
  });
}

test("collection directly reconciles a lost submission response before settlement", () => {
  const s = setup(); admit(s.campaign);
  const provider = createOfflineProvider(join(s.directory, "provider"), { clock: s.clock, actualCost: cost, crashAfterSubmitOnce: true });
  expect(() => s.campaign.dispatch("control", provider)).toThrow(FixtureCrash);
  s.campaign.collect("control", provider);
  expect(s.campaign.snapshot().tasks.control!.status).toBe("completed");
  expect(s.campaign.snapshot().spentMicros).toBe(100);
  expect(provider.submissionCount).toBe(1);
  const events = readEvents(s.campaign.eventsDirectory);
  expect(events.filter((event) => event.kind === "job-observed")).toHaveLength(1);
  expect(events.findIndex((event) => event.kind === "job-observed")).toBeLessThan(events.findIndex((event) => event.kind === "task-settled"));
});

test("expired lease cannot be stolen by reusing an owner label", () => {
  const s = setup();
  const rival = new Campaign(s.run, s.config, "owner-a", { clock: s.clock });
  expect(() => rival.acquireLease()).toThrow("Another controller");
  expect(() => rival.propose("investigator", proposal(), cost)).toThrow("live lease");
  s.campaign.releaseLease(); rival.acquireLease(); rival.propose("investigator", proposal(), cost);
  expect(() => s.campaign.propose("investigator", proposal("other"), cost)).toThrow("live lease");
});

test("budget reservation prevents overspending before any provider call", () => {
  const s = setup({ budgetMicros: 99 });
  s.campaign.propose("investigator", proposal(), cost);
  expect(() => s.campaign.critique("supervisor", "control", "admit", "Try reserve")).toThrow("budget exhausted");
  expect(s.campaign.snapshot().reservedMicros).toBe(0);
  expect(readEvents(s.campaign.eventsDirectory).at(-1)!.kind).toBe("admission-denied");
});

test("unknown final spend keeps reservation and blocks admissions until reconciled", () => {
  const s = setup(); admit(s.campaign);
  const provider = createOfflineProvider(join(s.directory, "provider"), { clock: s.clock, actualCost: null });
  s.campaign.dispatch("control", provider); s.campaign.collect("control", provider);
  s.campaign.propose("investigator", proposal("followup"), cost);
  expect(() => s.campaign.critique("supervisor", "followup", "admit", "Follow up")).toThrow("Uncertain spend");
  s.campaign.dispatch("control", provider);
  expect(s.campaign.snapshot().uncertain).toBe(true);
  provider.resolveCost(s.campaign.snapshot().tasks.control!.submissionKey!, cost);
  s.campaign.collect("control", provider);
  s.campaign.critique("supervisor", "followup", "admit", "Known total now fits budget");
  expect(s.campaign.snapshot().spentMicros + s.campaign.snapshot().reservedMicros).toBe(200);
});

test("uncertain lookup neither resubmits nor releases the reservation", () => {
  const s = setup(); admit(s.campaign);
  const provider = createOfflineProvider(join(s.directory, "provider"), { clock: s.clock, actualCost: cost });
  provider.setLookupUncertain(true); s.campaign.dispatch("control", provider);
  expect(provider.submissionCount).toBe(0); expect(s.campaign.snapshot().uncertain).toBe(true);
  expect(s.campaign.snapshot().reservedMicros).toBe(100);
  provider.setLookupUncertain(false); s.campaign.dispatch("control", provider); s.campaign.collect("control", provider);
  expect(provider.submissionCount).toBe(1); expect(s.campaign.snapshot().uncertain).toBe(false);
});

test("recovery cannot switch provider routes after losing a job-ID response", () => {
  const s = setup(); admit(s.campaign);
  const provider = createOfflineProvider(join(s.directory, "provider"), { clock: s.clock, crashAfterSubmitOnce: true });
  expect(() => s.campaign.dispatch("control", provider)).toThrow(FixtureCrash);
  const other = createOfflineProvider(join(s.directory, "other-provider"), { clock: s.clock });
  expect(() => s.campaign.dispatch("control", other)).toThrow("originally recorded provider route");
  expect(other.submissionCount).toBe(0);
  const reopened = createOfflineProvider(join(s.directory, "provider"), { clock: s.clock });
  s.campaign.dispatch("control", reopened); s.campaign.collect("control", reopened);
  expect(reopened.submissionCount).toBe(1);
});

test("a corrupted provider charge fails closed with an unresolved reservation", () => {
  const s = setup(); admit(s.campaign);
  const providerDirectory = join(s.directory, "provider");
  const provider = createOfflineProvider(providerDirectory, { clock: s.clock, actualCost: cost });
  s.campaign.dispatch("control", provider);
  const path = join(providerDirectory, `${s.campaign.snapshot().tasks.control!.submissionKey}.json`);
  const record = JSON.parse(readFileSync(path, "utf8")); record.actualCost.recoveryMicros = -1;
  writeFileSync(path, JSON.stringify(record));
  expect(() => s.campaign.collect("control", provider)).toThrow("Unsafe integer");
  expect(s.campaign.snapshot().uncertain).toBe(true); expect(s.campaign.snapshot().reservedMicros).toBe(100);
});

test("provider recovery binds the original proposal and deadline", () => {
  const s = setup(); admit(s.campaign);
  const directory = join(s.directory, "provider");
  const provider = createOfflineProvider(directory, { clock: s.clock, crashAfterSubmitOnce: true });
  expect(() => s.campaign.dispatch("control", provider)).toThrow(FixtureCrash);
  const path = join(directory, `${s.campaign.snapshot().tasks.control!.submissionKey}.json`);
  const record = JSON.parse(readFileSync(path, "utf8")); record.proposalSha256 = "f".repeat(64);
  writeFileSync(path, JSON.stringify(record));
  expect(() => s.campaign.dispatch("control", provider)).toThrow("differs from recorded submission intent");
  expect(s.campaign.snapshot().uncertain).toBe(true); expect(provider.submissionCount).toBe(1);
});

test("collection rejects a different job ID for an already observed submission", () => {
  const s = setup(); admit(s.campaign);
  const directory = join(s.directory, "provider");
  const provider = createOfflineProvider(directory, { clock: s.clock, actualCost: cost });
  s.campaign.dispatch("control", provider);
  const path = join(directory, `${s.campaign.snapshot().tasks.control!.submissionKey}.json`);
  const record = JSON.parse(readFileSync(path, "utf8")); record.jobId = "different-job";
  writeFileSync(path, JSON.stringify(record));
  expect(() => s.campaign.collect("control", provider)).toThrow("differs from recorded submission intent");
  expect(s.campaign.snapshot().reservedMicros).toBe(100);
  expect(s.campaign.snapshot().spentMicros).toBe(0);
  expect(s.campaign.snapshot().uncertain).toBe(true);
});

test("a missing previously observed provider job remains uncertain and is never resubmitted", () => {
  const s = setup(); admit(s.campaign);
  const directory = join(s.directory, "provider");
  const provider = createOfflineProvider(directory, { clock: s.clock, actualCost: cost });
  s.campaign.dispatch("control", provider);
  const task = s.campaign.snapshot().tasks.control!;
  expect(provider.submissionCount).toBe(1);
  rmSync(join(directory, `${task.submissionKey}.json`));
  s.campaign.collect("control", provider);
  s.campaign.dispatch("control", provider);
  expect(provider.submissionCount).toBe(0);
  expect(s.campaign.snapshot().reservedMicros).toBe(100);
  s.tick(1001); s.campaign.acquireLease();
  s.campaign.dispatch("control", provider);
  const unresolved = s.campaign.snapshot();
  expect(unresolved.uncertain).toBe(true);
  expect(unresolved.tasks.control!.jobId).toBe(task.jobId);
  expect(unresolved.reservedMicros).toBe(100);
  expect(unresolved.spentMicros).toBe(0);
  expect(provider.submissionCount).toBe(0);
  expect(readEvents(s.campaign.eventsDirectory).filter((event) => event.kind === "task-settled")).toHaveLength(0);
});

test("unresolved dispatched work blocks new admissions after a controller crash", () => {
  const s = setup(); admit(s.campaign);
  const provider = createOfflineProvider(join(s.directory, "provider"), { clock: s.clock, crashAfterSubmitOnce: true });
  expect(() => s.campaign.dispatch("control", provider)).toThrow(FixtureCrash);
  s.campaign.propose("investigator", proposal("other"), cost);
  expect(() => s.campaign.critique("supervisor", "other", "admit", "Cannot guess spend")).toThrow("Uncertain spend");
});

test("component budget breach is recorded and prevents further work", () => {
  const s = setup(); admit(s.campaign);
  const provider = createOfflineProvider(join(s.directory, "provider"), { clock: s.clock, actualCost: { ...cost, inferenceMicros: 21 } });
  s.campaign.dispatch("control", provider); s.campaign.collect("control", provider);
  expect(s.campaign.snapshot().breached).toBe(true); expect(s.campaign.snapshot().spentMicros).toBe(101);
  s.campaign.propose("investigator", proposal("other"), cost);
  expect(() => s.campaign.critique("supervisor", "other", "admit", "No overspend escalation")).toThrow("Budget breach");
});

test("deadline cancellation is reconciled and failed attempts remain visible", () => {
  const s = setup(); admit(s.campaign);
  const provider = createOfflineProvider(join(s.directory, "provider"), { clock: s.clock, completeAfterMs: null, actualCost: cost });
  s.campaign.dispatch("control", provider); s.tick(1001); s.campaign.acquireLease(); s.campaign.collect("control", provider);
  expect(s.campaign.snapshot().tasks.control!.status).toBe("cancelled");
  expect(s.campaign.snapshot().spentMicros).toBe(100);
  s.campaign.retry("supervisor", "control", "One registered retry");
  s.campaign.critique("supervisor", "control", "admit", "Reserve second bounded attempt");
  const failure = createOfflineProvider(join(s.directory, "failed-provider"), { clock: s.clock, outcome: "failed", actualCost: cost });
  s.campaign.dispatch("control", failure); s.campaign.collect("control", failure);
  expect(s.campaign.snapshot().tasks.control!.status).toBe("failed");
  expect(() => s.campaign.retry("supervisor", "control", "Another retry")).toThrow("Retry limit");
  expect(readEvents(s.campaign.eventsDirectory).filter((event) => event.kind === "task-settled")).toHaveLength(2);
});

test("expired undispatched intent creates no provider job and charges no spend", () => {
  const s = setup(); admit(s.campaign); s.tick(1001); s.campaign.acquireLease();
  const provider = createOfflineProvider(join(s.directory, "provider"), { clock: s.clock });
  s.campaign.dispatch("control", provider);
  expect(provider.submissionCount).toBe(0); expect(s.campaign.snapshot().tasks.control!.status).toBe("cancelled");
  expect(s.campaign.snapshot().spentMicros).toBe(0);
});

test("a reopened campaign cannot change frozen budget, judge or registration", () => {
  const s = setup();
  for (const override of [{ budgetMicros: 201 }, { judgeSha256: "c".repeat(64) }, { registrationSha256: "c".repeat(64) }]) {
    expect(() => new Campaign(s.run, { ...s.config, ...override }, "owner-b", { clock: s.clock })).toThrow("Frozen campaign");
  }
  s.config.budgetMicros = 999;
  expect(s.campaign.snapshot().config.budgetMicros).toBe(200);
  const snapshot = s.campaign.snapshot(); snapshot.config.budgetMicros = 10000;
  expect(s.campaign.snapshot().config.budgetMicros).toBe(200);
});

test("arbitrary code, injected providers, and unknown input artifacts are denied", () => {
  const s = setup();
  s.campaign.propose("investigator", { ...proposal("code"), action: "execute-code", parameters: { source: "process.exit()" } }, cost);
  expect(() => s.campaign.critique("supervisor", "code", "admit", "No execution authority")).toThrow("disabled");
  s.campaign.propose("investigator", { ...proposal("unknown"), inputArtifactIds: ["holdout-1"] }, cost);
  expect(() => s.campaign.critique("supervisor", "unknown", "admit", "No holdout access")).toThrow("Unadmitted data");
  admit(s.campaign);
  let called = false;
  expect(() => s.campaign.dispatch("control", { submit() { called = true; } })).toThrow("External providers");
  expect(called).toBe(false);
});

test("role separation and primary evidence are checked before reviews", () => {
  const s = setup(); s.campaign.propose("investigator", proposal(), cost);
  expect(() => s.campaign.critique("investigator", "control", "admit", "Self approve")).toThrow("Only supervisor");
  expect(() => s.campaign.recordReview("investigator", "control", "curation", "Self curate", [])).toThrow("Only curator");
  expect(() => s.campaign.recordReview("curator", "control", "curation", "Missing primary", [])).toThrow("evidence");
  s.campaign.critique("supervisor", "control", "admit", "Reviewed");
  const provider = createOfflineProvider(join(s.directory, "provider"), { clock: s.clock });
  s.campaign.dispatch("control", provider); s.campaign.collect("control", provider);
  expect(() => s.campaign.recordReview("editor", "control", "editorial", "No curation", [s.campaign.primaryEvidence("control")])).toThrow("curation");
  expect(() => s.campaign.recordReview("curator", "control", "curation", "Wrong bytes", [{ ...s.campaign.primaryEvidence("control"), sha256: "f".repeat(64) }])).toThrow("identity mismatch");
});

test("allowlist logs permitted reads and denies holdout paths, ids and excluded accessions", () => {
  const s = setup();
  expect(new TextDecoder().decode(s.campaign.readArtifact("investigator", { kind: "artifact", value: "public" }))).toBe('{"value":1}\n');
  for (const request of [{ kind: "path", value: "../private.json" }, { kind: "path", value: "holdout/test.json" }, { kind: "artifact", value: "holdout-1" }, { kind: "accession", value: "GSEEXCLUDED" }] as const) {
    expect(() => s.campaign.readArtifact("investigator", request)).toThrow("allowlist");
  }
  expect(readEvents(s.campaign.eventsDirectory).filter((event) => event.kind === "access-denied")).toHaveLength(4);
  writeFileSync(join(s.directory, "input.json"), "changed");
  expect(() => s.campaign.readArtifact("investigator", { kind: "path", value: "input.json" })).toThrow("missing, changed");
});

test("allowlisted artifact symlinks cannot escape the discovery root", () => {
  const s = setup(); const outside = mkdtempSync(join(tmpdir(), "bio-private-test-")); temporary.push(outside);
  writeFileSync(join(outside, "input.json"), '{"value":1}\n');
  rmSync(join(s.directory, "input.json")); symlinkSync(join(outside, "input.json"), join(s.directory, "input.json"));
  expect(() => s.campaign.readArtifact("investigator", { kind: "artifact", value: "public" })).toThrow("outside discovery mount");
});

test("allowlisted special files are rejected without waiting for a writer", () => {
  const s = setup(); const path = join(s.directory, "input.json"); rmSync(path);
  const created = Bun.spawnSync(["mkfifo", path]);
  expect(created.exitCode).toBe(0);
  expect(() => s.campaign.readArtifact("investigator", { kind: "artifact", value: "public" })).toThrow("missing, changed");
  expect(readEvents(s.campaign.eventsDirectory).at(-1)!.kind).toBe("access-denied");
});

test("finite revisions, tasks and rejected proposals remain in the ledger", () => {
  const s = setup(); s.campaign.propose("investigator", proposal(), cost);
  s.campaign.critique("supervisor", "control", "reject", "Missing control");
  s.campaign.revise("investigator", "control", { ...proposal(), question: "Revised with control" }, cost);
  expect(() => s.campaign.revise("investigator", "control", proposal(), cost)).toThrow("Revision limit");
  for (const name of ["a", "b", "c"]) s.campaign.propose("investigator", proposal(name), cost);
  expect(() => s.campaign.propose("investigator", proposal("d"), cost)).toThrow("task limit");
  expect(readEvents(s.campaign.eventsDirectory).some((event) => event.kind === "task-rejected")).toBe(true);
});

test("journal corruption fails and suffix truncation needs an external head anchor", () => {
  const s = setup(); const event = join(s.campaign.eventsDirectory, "00000001.json");
  const original = readFileSync(event, "utf8");
  writeFileSync(event, original.replace("owner-a", "owner-x"));
  expect(() => s.campaign.snapshot()).toThrow("Changed journal event");
  writeFileSync(event, original); rmSync(event);
  expect(() => s.campaign.snapshot()).not.toThrow(); // A removed trailing event is not detectable without an external head anchor.
  expect(() => s.campaign.propose("investigator", proposal(), cost)).toThrow("live lease");
});

test("missing interior journal events fail verification", () => {
  const s = setup(); s.campaign.propose("investigator", proposal(), cost);
  rmSync(join(s.campaign.eventsDirectory, "00000001.json"));
  expect(() => s.campaign.snapshot()).toThrow("sequence missing");
});

test("unsafe money and malformed proposal values are rejected", () => {
  for (const value of [-1, Infinity, NaN, 0.5, Number.MAX_SAFE_INTEGER + 1, true, "2"]) {
    expect(() => validateCosts({ ...cost, recoveryMicros: value })).toThrow();
  }
  expect(() => validateCosts({ inferenceMicros: 0 })).toThrow();
  const s = setup();
  expect(() => s.campaign.propose("investigator", { ...proposal(), unexpected: true }, cost)).toThrow("fields");
  expect(() => s.campaign.propose("investigator", { ...proposal(), parameters: { value: NaN } }, cost)).toThrow("Nonfinite");
  expect(() => canonical({ function: () => {} })).toThrow(CampaignError);
  expect(readEvents(s.campaign.eventsDirectory).filter((event) => event.kind === "proposal-invalid")).toHaveLength(2);
});

test("replay rejects a rehashed duplicate settlement and reserved-task rejection", () => {
  const s = setup(); admit(s.campaign);
  const provider = createOfflineProvider(join(s.directory, "provider"), { clock: s.clock, actualCost: cost });
  s.campaign.dispatch("control", provider); s.campaign.collect("control", provider);
  forgedAppend(s.campaign.eventsDirectory, "task-settled", readEvents(s.campaign.eventsDirectory).at(-1)!.data);
  expect(() => verifyCampaignJournal(s.campaign.eventsDirectory)).toThrow("duplicate");
  const reserved = setup(); admit(reserved.campaign);
  forgedAppend(reserved.campaign.eventsDirectory, "task-rejected", { taskId: "control", reason: "Release the reservation" });
  expect(() => reserved.campaign.snapshot()).toThrow("reservation");
});

test("replay checks admission identity and the total of existing reservations", () => {
  const altered = setup(); admit(altered.campaign);
  forgedLast(altered.campaign.eventsDirectory, (data) => { data.submissionKey = "f".repeat(64); });
  expect(() => altered.campaign.snapshot()).toThrow("intent identity");
  const s = setup({ budgetMicros: 100 }); admit(s.campaign); s.campaign.propose("investigator", proposal("second"), cost);
  const state = s.campaign.snapshot();
  forgedAppend(s.campaign.eventsDirectory, "task-admitted", { taskId: "second", reason: "Rehashed excess admission",
    submissionKey: sha256(`${state.configSha256}:second:1`), proposalSha256: sha256(canonical(proposal("second"))),
    inputArtifactIds: ["public"], expiresAtMs: 2000 });
  expect(() => s.campaign.snapshot()).toThrow("exceeded budget");
});

test("replay enforces retry and revision limits independently of API admission", () => {
  const s = setup(); s.campaign.propose("investigator", proposal(), cost);
  s.campaign.revise("investigator", "control", proposal(), cost);
  forgedAppend(s.campaign.eventsDirectory, "task-revised", readEvents(s.campaign.eventsDirectory).at(-1)!.data);
  expect(() => s.campaign.snapshot()).toThrow("revision");
  const retried = setup(); admit(retried.campaign);
  const provider = createOfflineProvider(join(retried.directory, "provider"), { clock: retried.clock, outcome: "failed", actualCost: cost });
  retried.campaign.dispatch("control", provider); retried.campaign.collect("control", provider);
  retried.campaign.retry("supervisor", "control", "One allowed retry");
  retried.campaign.critique("supervisor", "control", "admit", "Second attempt");
  retried.campaign.dispatch("control", provider); retried.campaign.collect("control", provider);
  forgedAppend(retried.campaign.eventsDirectory, "task-retried", { taskId: "control", reason: "Exceeds retry budget" });
  expect(() => retried.campaign.snapshot()).toThrow("retry");
});

test("replay rejects rehashed lease takeover, expiry and backwards time", () => {
  const stolen = setup();
  forgedAppend(stolen.campaign.eventsDirectory, "lease-acquired", { owner: "other", session: "other-session", fence: 2, expiresAtMs: 1100 });
  expect(() => stolen.campaign.snapshot()).toThrow("stole an active owner");
  const expired = setup();
  forgedAppend(expired.campaign.eventsDirectory, "task-proposed", { proposal: proposal(), estimate: cost } as unknown as Event["data"], 1100);
  expect(() => expired.campaign.snapshot()).toThrow("live lease");
  const backwards = setup();
  forgedAppend(backwards.campaign.eventsDirectory, "task-proposed", { proposal: proposal(), estimate: cost } as unknown as Event["data"], 999);
  expect(() => backwards.campaign.snapshot()).toThrow("time moved backwards");
});

test("replay binds review authority and exact primary evidence references", () => {
  for (const field of ["role", "evidence-id"] as const) {
    const s = setup(); admit(s.campaign);
    const provider = createOfflineProvider(join(s.directory, "provider"), { clock: s.clock });
    s.campaign.dispatch("control", provider); s.campaign.collect("control", provider);
    s.campaign.recordReview("curator", "control", "curation", "Bound to primary observation", [s.campaign.primaryEvidence("control")]);
    forgedLast(s.campaign.eventsDirectory, (data) => {
      if (field === "role") data.role = "investigator";
      else (data.evidence as { id: string }[])[0]!.id = "different-observation";
    });
    expect(() => s.campaign.snapshot()).toThrow(field === "role" ? "review authority" : "identity mismatch");
  }
});

test("UTF-8 byte limits reject oversized events and model data before persistence", () => {
  const s = setup();
  const oversized = { ...s.config, discoveryArtifacts: Array.from({ length: 128 }, (_, index) => ({
    id: `artifact-${index}`, path: `${index}-${"界".repeat(500)}`, sha256: "a".repeat(64), accession: null,
  })) };
  const directory = join(s.directory, "oversized-campaign");
  expect(() => new Campaign(directory, oversized, "owner")).toThrow("byte limit");
  expect(readdirSync(join(directory, "events"))).toEqual([]);
  expect(() => s.campaign.propose("investigator", { ...proposal(), parameters: "界".repeat(3000) }, cost)).toThrow("parameters too large");
  expect(() => createOfflineProvider(join(s.directory, "provider"), { result: "界".repeat(3000) })).toThrow("result too large");
});
