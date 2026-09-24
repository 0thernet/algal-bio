/** Offline JSON-only campaign control. This module grants no process/network authority. */
import {
  existsSync, mkdirSync, readdirSync, realpathSync, linkSync,
  openSync, writeFileSync, fsyncSync, closeSync, unlinkSync, renameSync,
  constants, fstatSync, readSync,
} from "node:fs";
import { dirname, join, relative, resolve, sep } from "node:path";
import { randomUUID } from "node:crypto";

export type Json = null | boolean | number | string | Json[] | { [key: string]: Json };
export type Role = "investigator" | "supervisor" | "curator" | "editor" | "evaluator";
export type Costs = {
  inferenceMicros: number; computeMicros: number; storageMicros: number;
  egressMicros: number; recoveryMicros: number;
};
export type CampaignConfig = {
  schema: "algal-bio.campaign.v1";
  campaignId: string;
  currency: "USD";
  budgetMicros: number;
  registrationSha256: string;
  judgeSha256: string;
  limits: {
    maxTasks: number; maxRetries: number; maxRevisions: number; maxEvents: number;
    jobTimeoutMs: number; leaseMs: number; maxArtifactBytes: number;
  };
  discoveryArtifacts: { id: string; path: string; sha256: string; accession: string | null }[];
  excludedAccessions: string[];
  reservedArtifactIds: string[];
};
export type Proposal = {
  taskId: string; question: string; instrumentId: string;
  inputArtifactIds: string[]; action: "json-observation" | "execute-code";
  parameters: Json;
};
export type EvidenceRef = {
  id: string; sha256: string; kind: "primary-observation" | "curation" | "assessment" | "editorial" | "source";
  locator: string;
};
export type Event = {
  schema: "algal-bio.campaign-event.v1"; sequence: number; previousSha256: string | null;
  atMs: number; kind: string; data: Json; sha256: string;
};
type Task = {
  proposal: Proposal; estimate: Costs; status: string; attempt: number;
  retries: number; revisions: number; submissionKey?: string; expiresAtMs?: number;
  jobId?: string; actualCost?: Costs; result?: Json;
  providerSha256?: string;
};
type State = {
  config: CampaignConfig; configSha256: string; tasks: Record<string, Task>;
  lease: { owner: string; session: string; fence: number; expiresAtMs: number } | null;
  spentMicros: number; reservedMicros: number; uncertain: boolean; breached: boolean;
  eventCount: number; headSha256: string;
};
const COST_KEYS = ["inferenceMicros", "computeMicros", "storageMicros", "egressMicros", "recoveryMicros"] as const;
const MAX_MICROS = 1_000_000_000_000;
const ZERO: Costs = { inferenceMicros: 0, computeMicros: 0, storageMicros: 0, egressMicros: 0, recoveryMicros: 0 };
const HASH = /^[a-f0-9]{64}$/;
const ID = /^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$/;
const EVENT_KINDS = new Set([
  "campaign-created", "lease-acquired", "lease-released", "task-proposed", "task-revised",
  "task-retried", "task-rejected", "task-admitted", "dispatch-intent", "job-observed",
  "spend-uncertain", "task-settled", "review-recorded", "access-granted", "access-denied",
  "admission-denied", "capability-denied",
  "proposal-invalid",
]);

export class CampaignError extends Error {}
export class ConcurrentUpdate extends CampaignError {}
export class FixtureCrash extends CampaignError {}

function fail(message: string): never { throw new CampaignError(message); }
function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value) || ![Object.prototype, null].includes(Object.getPrototypeOf(value)))
    fail("Expected a plain JSON object");
  return value as Record<string, unknown>;
}
function keys(value: unknown, expected: readonly string[]): Record<string, unknown> {
  const record = object(value);
  if (Object.keys(record).sort().join("\0") !== [...expected].sort().join("\0")) fail("Unexpected or missing fields");
  return record;
}
function integer(value: unknown, min = 0, max = Number.MAX_SAFE_INTEGER): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < min || value > max) fail("Unsafe integer");
  return value;
}
function label(value: unknown, max = 2048): string {
  if (typeof value !== "string" || !value.length || value.length > max) fail("Invalid bounded text");
  return value;
}
function id(value: unknown): string { const text = label(value, 96); if (!ID.test(text)) fail("Invalid identifier"); return text; }
function hash(value: unknown): string { const text = label(value, 64); if (!HASH.test(text)) fail("Invalid SHA-256"); return text; }
function strings(value: unknown, limit = 128): string[] {
  if (!Array.isArray(value) || value.length > limit) fail("Expected a bounded string array");
  const result = value.map((item) => label(item, 512));
  if (new Set(result).size !== result.length) fail("Duplicate values");
  return result;
}
export function canonical(value: unknown, depth = 0): string {
  if (depth > 16) fail("JSON nesting limit exceeded");
  if (value === null || typeof value === "boolean") return JSON.stringify(value);
  if (typeof value === "string") { if (value.length > 65536) fail("JSON string too large"); return JSON.stringify(value); }
  if (typeof value === "number") { if (!Number.isFinite(value)) fail("Nonfinite JSON number"); return JSON.stringify(value); }
  if (Array.isArray(value)) {
    if (value.length > 1024) fail("JSON array too large");
    return `[${value.map((item) => canonical(item, depth + 1)).join(",")}]`;
  }
  const record = object(value);
  if (Object.keys(record).length > 256) fail("JSON object too large");
  return `{${Object.keys(record).sort().map((key) => `${JSON.stringify(key)}:${canonical(record[key], depth + 1)}`).join(",")}}`;
}
export function sha256(value: string | Uint8Array): string { return new Bun.CryptoHasher("sha256").update(value).digest("hex"); }
function clone<T>(value: T): T { return JSON.parse(canonical(value)); }
export function validateCosts(value: unknown): Costs {
  const record = keys(value, COST_KEYS);
  let total = 0;
  for (const key of COST_KEYS) total += integer(record[key], 0, MAX_MICROS);
  if (!Number.isSafeInteger(total) || total > MAX_MICROS) fail("Cost total exceeds safe bound");
  return clone(record) as Costs;
}
export function costTotal(value: Costs): number { return COST_KEYS.reduce((sum, key) => sum + value[key], 0); }
function relativePath(value: unknown): string {
  const path = label(value, 512);
  if (path.startsWith("/") || path.includes("\\") || path.split("/").some((part) => !part || part === "." || part === "..")) fail("Invalid relative artifact path");
  if (path.split("/").some((part) => /^(holdout|evaluator|evaluation|credentials)$/i.test(part))) fail("Reserved storage cannot be mounted");
  return path;
}
export function validateConfig(value: unknown): CampaignConfig {
  const record = keys(value, ["schema", "campaignId", "currency", "budgetMicros", "registrationSha256", "judgeSha256", "limits", "discoveryArtifacts", "excludedAccessions", "reservedArtifactIds"]);
  if (record.schema !== "algal-bio.campaign.v1" || record.currency !== "USD") fail("Unsupported campaign identity/currency");
  id(record.campaignId); integer(record.budgetMicros, 0, MAX_MICROS); hash(record.registrationSha256); hash(record.judgeSha256);
  const limits = keys(record.limits, ["maxTasks", "maxRetries", "maxRevisions", "maxEvents", "jobTimeoutMs", "leaseMs", "maxArtifactBytes"]);
  integer(limits.maxTasks, 1, 100); integer(limits.maxRetries, 0, 9); integer(limits.maxRevisions, 0, 10);
  integer(limits.maxEvents, 20, 10000); integer(limits.jobTimeoutMs, 1, 86_400_000);
  integer(limits.leaseMs, 1, 60_000); integer(limits.maxArtifactBytes, 1, 1_048_576);
  const excluded = strings(record.excludedAccessions); const reserved = strings(record.reservedArtifactIds);
  if (!Array.isArray(record.discoveryArtifacts) || record.discoveryArtifacts.length > 128) fail("Invalid discovery allowlist");
  const artifactIds = new Set<string>(); const paths = new Set<string>();
  for (const item of record.discoveryArtifacts) {
    const artifact = keys(item, ["id", "path", "sha256", "accession"]);
    const name = id(artifact.id); const path = relativePath(artifact.path); hash(artifact.sha256);
    if (artifact.accession !== null) label(artifact.accession, 96);
    if (artifactIds.has(name) || paths.has(path) || reserved.includes(name) || excluded.includes(artifact.accession as string)) fail("Conflicting artifact access policy");
    artifactIds.add(name); paths.add(path);
  }
  return clone(record) as CampaignConfig;
}
function validateProposal(value: unknown): Proposal {
  const proposal = keys(value, ["taskId", "question", "instrumentId", "inputArtifactIds", "action", "parameters"]);
  id(proposal.taskId); label(proposal.question); id(proposal.instrumentId); strings(proposal.inputArtifactIds, 32).forEach(id);
  if (!["json-observation", "execute-code"].includes(proposal.action as string)) fail("Unsupported action");
  if (Buffer.byteLength(canonical(proposal.parameters), "utf8") > 8192) fail("Proposal parameters too large");
  return clone(proposal) as Proposal;
}
function atomicNewFile(path: string, text: string): void {
  const temporary = join(dirname(path), `.pending-${randomUUID()}`);
  const fd = openSync(temporary, "wx", 0o600);
  try { writeFileSync(fd, text); fsyncSync(fd); } finally { closeSync(fd); }
  try { linkSync(temporary, path); }
  catch (error) { if ((error as NodeJS.ErrnoException).code === "EEXIST") throw new ConcurrentUpdate("Another writer advanced the journal; reopen and retry"); throw error; }
  finally { unlinkSync(temporary); }
  const directory = openSync(dirname(path), "r");
  try { fsyncSync(directory); } finally { closeSync(directory); }
}
function eventPath(directory: string, sequence: number): string { return join(directory, `${String(sequence).padStart(8, "0")}.json`); }
function boundedFile(path: string, maximum: number): Uint8Array {
  const fd = openSync(path, constants.O_RDONLY | constants.O_NONBLOCK | constants.O_NOFOLLOW);
  try {
    const stat = fstatSync(fd);
    if (!stat.isFile() || stat.size > maximum) fail("Expected a bounded regular file");
    const bytes = Buffer.alloc(maximum + 1);
    let length = 0;
    while (length < bytes.length) {
      const count = readSync(fd, bytes, length, bytes.length - length, null);
      if (!count) break;
      length += count;
    }
    if (length > maximum) fail("File grew beyond its byte bound");
    return bytes.subarray(0, length);
  } finally { closeSync(fd); }
}
export function readEvents(directory: string): Event[] {
  if (!existsSync(directory)) return [];
  const names = readdirSync(directory).filter((name) => !name.startsWith(".pending-")).sort();
  if (names.length > 10000) fail("Journal event limit exceeded");
  const result: Event[] = [];
  for (let i = 0; i < names.length; i++) {
    if (names[i] !== `${String(i).padStart(8, "0")}.json`) fail("Journal sequence missing or invalid");
    const bytes = boundedFile(join(directory, names[i]!), 131072);
    const record = keys(JSON.parse(Buffer.from(bytes).toString()), ["schema", "sequence", "previousSha256", "atMs", "kind", "data", "sha256"]);
    const { sha256: digest, ...body } = record;
    if (record.schema !== "algal-bio.campaign-event.v1" || record.sequence !== i || record.previousSha256 !== (result.at(-1)?.sha256 ?? null)) fail("Broken journal chain");
    integer(record.atMs); if (!EVENT_KINDS.has(record.kind as string)) fail("Unknown journal event");
    if (hash(digest) !== sha256(canonical(body))) fail("Changed journal event");
    result.push(record as unknown as Event);
  }
  return result;
}
function totals(state: State): void {
  state.reservedMicros = 0; state.uncertain = false;
  for (const task of Object.values(state.tasks)) {
    if (["reserved", "submitting", "submitted", "uncertain"].includes(task.status)) state.reservedMicros += costTotal(task.estimate);
    if (["uncertain", "submitting"].includes(task.status)) state.uncertain = true;
  }
}
function checkReview(data: Record<string, unknown>, state: State, previous: Event[]): void {
  keys(data, ["taskId", "role", "kind", "reason", "evidence"]);
  const taskId = id(data.taskId); const task = state.tasks[taskId];
  const required: Record<string, string> = { curation: "curator", editorial: "editor", assessment: "evaluator" };
  if (!task || typeof data.kind !== "string" || !Object.hasOwn(required, data.kind) || data.role !== required[data.kind]) fail("Invalid journal review authority");
  label(data.reason);
  if (!Array.isArray(data.evidence) || data.evidence.length < 1 || data.evidence.length > 32) fail("Review needs bounded evidence");
  for (const value of data.evidence) {
    const ref = keys(value, ["id", "sha256", "kind", "locator"]); id(ref.id); hash(ref.sha256); label(ref.locator, 256);
    if (ref.kind === "primary-observation") {
      if (task.status !== "completed" || ref.id !== `observation-${sha256(taskId).slice(0, 32)}` || ref.sha256 !== sha256(canonical(task.result)) || ref.locator !== `provider-result:${task.submissionKey}`) fail("Primary bundle identity mismatch");
    } else if (["curation", "assessment", "editorial"].includes(ref.kind as string)) {
      const source = previous.find((event) => event.sha256 === ref.sha256 && event.kind === "review-recorded");
      if (!source || object(source.data).taskId !== taskId || object(source.data).kind !== ref.kind || ref.locator !== `event:${ref.sha256}` || ref.id !== `${ref.kind}-${sha256(taskId).slice(0, 32)}`) fail("Review reference is not an observed event");
    } else if (ref.kind === "source") {
      if (!state.config.discoveryArtifacts.some((entry) => entry.id === ref.id && entry.sha256 === ref.sha256 && ref.locator === `artifact:${entry.id}`)) fail("Source evidence is outside the frozen allowlist");
    } else fail("Unknown evidence kind");
  }
  if (data.kind === "curation" && !data.evidence.some((ref) => object(ref).kind === "primary-observation")) fail("Curation requires primary evidence");
  if (data.kind === "editorial" && !data.evidence.some((ref) => object(ref).kind === "curation")) fail("Editorial review requires prior curation");
}
function replay(events: Event[]): State {
  if (!events.length || events[0]!.kind !== "campaign-created") fail("Missing campaign registration");
  const initial = keys(events[0]!.data, ["config", "configSha256"]);
  const config = validateConfig(initial.config);
  const digest = sha256(canonical(config));
  if (initial.configSha256 !== digest) fail("Campaign configuration identity mismatch");
  if (events.length > config.limits.maxEvents) fail("Campaign event limit exceeded");
  const state: State = { config, configSha256: digest, tasks: Object.create(null), lease: null,
    spentMicros: 0, reservedMicros: 0, uncertain: false, breached: false, eventCount: events.length, headSha256: events.at(-1)!.sha256 };
  let leaseCount = 0;
  for (const [index, event] of events.entries()) {
    if (!index) continue;
    if (event.atMs < events[index - 1]!.atMs) fail("Journal time moved backwards");
    const data = object(event.data); const task = state.tasks[data.taskId as string];
    const needsTask = ["task-revised", "task-retried", "task-rejected", "task-admitted", "dispatch-intent", "job-observed", "spend-uncertain", "task-settled", "review-recorded", "admission-denied"].includes(event.kind);
    if (needsTask && (!task || id(data.taskId) !== data.taskId)) fail("Journal references an unknown task");
    if (event.kind !== "lease-acquired" && (!state.lease || state.lease.expiresAtMs <= event.atMs)) fail("Journal mutation lacks a live lease");
    switch (event.kind) {
      case "lease-acquired": {
        keys(data, ["owner", "session", "fence", "expiresAtMs"]); id(data.owner); id(data.session);
        if (integer(data.fence, 1) !== ++leaseCount || integer(data.expiresAtMs) <= event.atMs || (data.expiresAtMs as number) > event.atMs + config.limits.leaseMs) fail("Invalid journal lease bounds");
        if (state.lease && state.lease.expiresAtMs > event.atMs && (data.session !== state.lease.session || data.owner !== state.lease.owner)) fail("Journal lease stole an active owner");
        state.lease = data as State["lease"]; break;
      }
      case "lease-released":
        keys(data, ["owner"]); if (data.owner !== state.lease!.owner) fail("Journal released another owner's lease"); state.lease = null; break;
      case "task-proposed": {
        keys(data, ["proposal", "estimate"]);
        const proposal = validateProposal(data.proposal);
        if (state.tasks[proposal.taskId] || Object.keys(state.tasks).length >= config.limits.maxTasks) fail("Duplicate task or journal task limit");
        state.tasks[proposal.taskId] = { proposal, estimate: validateCosts(data.estimate), status: "proposed", attempt: 0, retries: 0, revisions: 0 }; break;
      }
      case "task-revised": {
        keys(data, ["taskId", "proposal", "estimate"]);
        const proposal = validateProposal(data.proposal);
        if (!["proposed", "rejected"].includes(task!.status) || task!.revisions >= config.limits.maxRevisions || proposal.taskId !== data.taskId) fail("Invalid journal revision");
        task!.proposal = proposal; task!.estimate = validateCosts(data.estimate); task!.revisions++; task!.status = "proposed"; break;
      }
      case "task-retried":
        keys(data, ["taskId", "reason"]); label(data.reason);
        if (!["failed", "cancelled"].includes(task!.status) || !task!.actualCost || task!.retries >= config.limits.maxRetries) fail("Invalid journal retry");
        task!.retries++; task!.status = "proposed"; delete task!.actualCost; delete task!.result; break;
      case "task-rejected":
        keys(data, ["taskId", "reason"]); label(data.reason);
        if (task!.status !== "proposed") fail("Journal rejection cannot release an admitted reservation");
        task!.status = "rejected"; break;
      case "task-admitted": {
        keys(data, ["taskId", "reason", "submissionKey", "proposalSha256", "inputArtifactIds", "expiresAtMs"]); label(data.reason);
        if (task!.status !== "proposed" || state.uncertain || state.breached || task!.proposal.action !== "json-observation" || task!.proposal.inputArtifactIds.some((name) => !config.discoveryArtifacts.some((entry) => entry.id === name))) fail("Invalid journal admission");
        if (state.spentMicros + state.reservedMicros + costTotal(task!.estimate) > config.budgetMicros) fail("Journal admission exceeded budget");
        if (hash(data.submissionKey) !== sha256(`${digest}:${data.taskId}:${task!.attempt + 1}`) || data.proposalSha256 !== sha256(canonical(task!.proposal)) || canonical(data.inputArtifactIds) !== canonical(task!.proposal.inputArtifactIds)) fail("Journal admission intent identity mismatch");
        if (integer(data.expiresAtMs) > event.atMs + config.limits.jobTimeoutMs || (data.expiresAtMs as number) < events[index - 1]!.atMs) fail("Invalid journal job expiry");
        task!.attempt++; task!.submissionKey = hash(data.submissionKey); task!.expiresAtMs = integer(data.expiresAtMs); task!.status = "reserved"; delete task!.jobId; delete task!.providerSha256; break;
      }
      case "dispatch-intent":
        keys(data, ["taskId", "submissionKey", "providerSha256"]);
        if (task!.status !== "reserved" || data.submissionKey !== task!.submissionKey) fail("Journal dispatch lacks its reserved intent");
        task!.status = "submitting"; task!.providerSha256 = hash(data.providerSha256); break;
      case "job-observed":
        keys(data, ["taskId", "jobId"]);
        if (!["submitting", "uncertain"].includes(task!.status) || !task!.providerSha256 || (task!.jobId && task!.jobId !== data.jobId)) fail("Invalid journal job identity/transition");
        task!.jobId = id(data.jobId); task!.status = "submitted"; break;
      case "spend-uncertain":
        keys(data, ["taskId", "reason"]); label(data.reason);
        if (!["submitting", "submitted", "uncertain"].includes(task!.status) || !task!.providerSha256) fail("Uncertain journal task lacks dispatch intent");
        task!.status = "uncertain"; break;
      case "task-settled": {
        keys(data, ["taskId", "status", "actualCost", "result", "breached"]);
        if (!["submitting", "submitted", "uncertain"].includes(task!.status) || !["completed", "failed", "cancelled"].includes(data.status as string)) fail("Journal settlement is duplicate or has no dispatch");
        const actualCost = validateCosts(data.actualCost);
        if (!task!.jobId && (data.status !== "cancelled" || costTotal(actualCost) !== 0 || data.result !== null || event.atMs < task!.expiresAtMs!)) fail("Unobserved job cannot claim an outcome or charge");
        if (Buffer.byteLength(canonical(data.result), "utf8") > 8192) fail("Journal result exceeds fixture bound");
        const breached = COST_KEYS.some((key) => actualCost[key] > task!.estimate[key]) || state.spentMicros + costTotal(actualCost) > config.budgetMicros;
        if (data.breached !== breached) fail("Journal budget breach flag disagrees with actual charges");
        task!.actualCost = actualCost; task!.status = data.status as string; task!.result = data.result as Json;
        state.spentMicros = integer(state.spentMicros + costTotal(actualCost));
        state.breached ||= breached;
        break;
      }
      case "review-recorded": checkReview(data, state, events.slice(0, index)); break;
      case "access-granted": {
        if (!["investigator", "supervisor", "curator", "editor", "evaluator"].includes(data.role as string)) fail("Invalid journal reader role");
        if (Object.hasOwn(data, "taskId")) {
          keys(data, ["role", "taskId", "evidence"]);
          const target = state.tasks[id(data.taskId)];
          if (!target || target.status !== "completed" || canonical(data.evidence) !== canonical({ id: `observation-${sha256(data.taskId as string).slice(0, 32)}`, sha256: sha256(canonical(target.result)), kind: "primary-observation", locator: `provider-result:${target.submissionKey}` })) fail("Journal primary read identity mismatch");
        } else {
          keys(data, ["role", "request", "artifactId", "sha256", "bytes"]);
          const request = keys(data.request, ["kind", "value"]);
          const allowed = config.discoveryArtifacts.filter((entry) => request.kind === "artifact" ? entry.id === request.value : request.kind === "path" ? entry.path === request.value : request.kind === "accession" ? entry.accession === request.value : false);
          if (allowed.length !== 1 || data.artifactId !== allowed[0]!.id || data.sha256 !== allowed[0]!.sha256) fail("Journal read was outside frozen allowlist");
          integer(data.bytes, 0, config.limits.maxArtifactBytes);
        }
        break;
      }
      case "access-denied": keys(data, ["role", "request", "reason"]); label(data.role, 96); label(data.reason); keys(data.request, ["kind", "value"]); break;
      case "admission-denied": keys(data, ["taskId", "reason"]); label(data.reason); if (task!.status !== "proposed") fail("Invalid denied-admission state"); break;
      case "capability-denied": keys(data, ["taskId", "reason"]); label(data.taskId, 96); label(data.reason); break;
      case "proposal-invalid": keys(data, ["reason", "payloadSha256"]); label(data.reason); if (data.payloadSha256 !== null) hash(data.payloadSha256); break;
      default: fail("Invalid repeated campaign registration");
    }
    totals(state);
  }
  return state;
}
/** Hash integrity alone is insufficient: recovery verifies every admitted state
 * transition, budget equation, lease, and evidence reference as well.
 */
export function verifyCampaignJournal(directory: string): State { return clone(replay(readEvents(directory))); }

export class Campaign {
  readonly directory: string;
  readonly owner: string;
  readonly eventsDirectory: string;
  private readonly configSha256: string;
  private readonly now: () => number;
  private readonly dataRoot: string;
  private readonly session = randomUUID();
  constructor(directory: string, value: unknown, owner: string, options: { clock?: () => number; dataRoot?: string } = {}) {
    const config = validateConfig(value); this.configSha256 = sha256(canonical(config));
    this.directory = resolve(directory); this.eventsDirectory = join(this.directory, "events"); this.owner = id(owner);
    this.now = options.clock ?? Date.now; this.dataRoot = resolve(options.dataRoot ?? this.directory);
    mkdirSync(this.eventsDirectory, { recursive: true, mode: 0o700 });
    if (!readEvents(this.eventsDirectory).length) {
      try { this.append([], "campaign-created", { config, configSha256: this.configSha256 } as unknown as Json); }
      catch (error) { if (!(error instanceof ConcurrentUpdate)) throw error; }
    }
    this.snapshot();
  }
  private time(): number { return integer(this.now()); }
  private append(events: Event[], kind: string, data: Json): void {
    if (events.length && events.length >= replay(events).config.limits.maxEvents) fail("Campaign event limit reached");
    const body = { schema: "algal-bio.campaign-event.v1", sequence: events.length,
      previousSha256: events.at(-1)?.sha256 ?? null, atMs: this.time(), kind, data };
    const text = canonical({ ...body, sha256: sha256(canonical(body)) });
    if (Buffer.byteLength(text, "utf8") + 1 > 131072) fail("Event exceeds byte limit");
    replay([...events, { ...body, sha256: sha256(canonical(body)) } as Event]);
    atomicNewFile(eventPath(this.eventsDirectory, events.length), text + "\n");
  }
  private current(requireLease = true): { events: Event[]; state: State } {
    const events = readEvents(this.eventsDirectory); const state = replay(events);
    if (state.configSha256 !== this.configSha256) fail("Frozen campaign budget/judge/config changed");
    if (requireLease && (!state.lease || state.lease.owner !== this.owner || state.lease.session !== this.session || state.lease.expiresAtMs <= this.time())) fail("Controller does not hold a live lease");
    return { events, state };
  }
  snapshot(): State { return clone(this.current(false).state); }
  acquireLease(): void {
    const { events, state } = this.current(false); const now = this.time();
    if (state.lease && state.lease.session !== this.session && state.lease.expiresAtMs > now) fail("Another controller owns this campaign");
    const fence = events.filter((event) => event.kind === "lease-acquired").length + 1;
    this.append(events, "lease-acquired", { owner: this.owner, session: this.session, fence, expiresAtMs: integer(now + state.config.limits.leaseMs) });
  }
  releaseLease(): void { const { events } = this.current(); this.append(events, "lease-released", { owner: this.owner }); }
  private role(actual: Role, required: Role): void { if (actual !== required) fail(`Only ${required} may perform this action`); }
  private task(state: State, taskId: string): Task { const task = state.tasks[id(taskId)]; if (!task) fail("Unknown task"); return task; }
  propose(role: Role, value: unknown, estimate: unknown): void {
    this.role(role, "investigator");
    const { events, state } = this.current();
    let proposal: Proposal; let costs: Costs;
    try { proposal = validateProposal(value); costs = validateCosts(estimate); }
    catch (error) {
      let payloadSha256: string | null = null;
      try { payloadSha256 = sha256(canonical({ proposal: value, estimate })); } catch { /* Non-JSON values have no admitted encoding. */ }
      this.append(events, "proposal-invalid", { reason: "Proposal or complete cost estimate failed bounded JSON validation", payloadSha256 });
      throw error;
    }
    if (state.tasks[proposal.taskId]) fail("Task already exists");
    if (Object.keys(state.tasks).length >= state.config.limits.maxTasks) fail("Campaign task limit reached");
    this.append(events, "task-proposed", { proposal, estimate: costs } as unknown as Json);
  }
  revise(role: Role, taskId: string, value: unknown, estimate: unknown): void {
    this.role(role, "investigator"); const proposal = validateProposal(value); const costs = validateCosts(estimate);
    const { events, state } = this.current(); const task = this.task(state, taskId);
    if (proposal.taskId !== taskId || !["proposed", "rejected"].includes(task.status)) fail("Task is not revisable");
    if (task.revisions >= state.config.limits.maxRevisions) fail("Revision limit reached");
    this.append(events, "task-revised", { taskId, proposal, estimate: costs } as unknown as Json);
  }
  critique(role: Role, taskId: string, decision: "admit" | "reject", reason: string): void {
    this.role(role, "supervisor"); label(reason); const { events, state } = this.current(); const task = this.task(state, taskId);
    if (task.status !== "proposed") fail("Only proposed tasks may be reviewed");
    if (decision === "reject") { this.append(events, "task-rejected", { taskId, reason }); return; }
    if (decision !== "admit") fail("Unknown critique decision");
    const denied = task.proposal.action !== "json-observation" ? "Arbitrary code and external execution are disabled" :
      task.proposal.inputArtifactIds.some((artifactId) => !state.config.discoveryArtifacts.some((entry) => entry.id === artifactId)) ? "Unadmitted data requested" :
      state.uncertain ? "Uncertain spend blocks all new work" : state.breached ? "Budget breach requires a new operator-reviewed campaign" :
      state.spentMicros + state.reservedMicros + costTotal(task.estimate) > state.config.budgetMicros ? "Campaign budget exhausted" : null;
    if (denied) { this.append(events, "admission-denied", { taskId, reason: denied }); fail(denied); }
    const submissionKey = sha256(`${state.configSha256}:${taskId}:${task.attempt + 1}`);
    this.append(events, "task-admitted", { taskId, reason, submissionKey,
      proposalSha256: sha256(canonical(task.proposal)), inputArtifactIds: task.proposal.inputArtifactIds,
      expiresAtMs: integer(this.time() + state.config.limits.jobTimeoutMs) });
  }
  retry(role: Role, taskId: string, reason: string): void {
    this.role(role, "supervisor"); label(reason); const { events, state } = this.current(); const task = this.task(state, taskId);
    if (!["failed", "cancelled"].includes(task.status) || !task.actualCost) fail("Retry requires a reconciled failed/cancelled attempt");
    if (task.retries >= state.config.limits.maxRetries) fail("Retry limit reached");
    this.append(events, "task-retried", { taskId, reason });
  }
  private provider(value: unknown, taskId: string): OfflineProvider {
    const provider = offlineProviders.get(value as object);
    if (!provider) {
      const { events } = this.current();
      this.append(events, "capability-denied", { taskId, reason: "External providers require qualified OS isolation, broker and provider expiry; route disabled" });
      fail("External providers are disabled");
    }
    return provider;
  }
  private uncertain(taskId: string, reason: string): void {
    const { events } = this.current(); this.append(events, "spend-uncertain", { taskId, reason });
  }
  private lookup(provider: OfflineProvider, taskId: string, key: string): Lookup {
    try {
      const lookup = provider.lookup(key);
      if (lookup.certainty === "known" && lookup.job) {
        const { state } = this.current(); const task = this.task(state, taskId);
        if (lookup.job.proposalSha256 !== sha256(canonical(task.proposal)) || lookup.job.expiresAtMs !== task.expiresAtMs || (task.jobId && lookup.job.jobId !== task.jobId)) fail("Provider job differs from recorded submission intent");
      }
      return lookup;
    }
    catch (error) { this.uncertain(taskId, "Provider lookup failed; spend remains unresolved"); throw error; }
  }
  dispatch(taskId: string, candidate: unknown): void {
    const provider = this.provider(candidate, taskId); let { events, state } = this.current(); let task = this.task(state, taskId);
    if (task.providerSha256 && task.providerSha256 !== provider.identity) fail("Recovery must use the originally recorded provider route");
    if (["submitted", "completed", "failed", "cancelled"].includes(task.status)) return;
    if (!["reserved", "submitting", "uncertain"].includes(task.status)) fail("Task is not dispatchable");
    if (task.status === "reserved") { this.append(events, "dispatch-intent", { taskId, submissionKey: task.submissionKey!, providerSha256: provider.identity }); }
    ({ events, state } = this.current()); task = this.task(state, taskId);
    const lookup = this.lookup(provider, taskId, task.submissionKey!);
    if (lookup.certainty === "uncertain") { this.uncertain(taskId, "Provider lookup could not establish submission/spend"); return; }
    let job = lookup.job;
    if (!job && task.jobId) { this.uncertain(taskId, "Previously observed provider job is unavailable; outcome and spend remain unresolved"); return; }
    if (!job && this.time() >= task.expiresAtMs!) { this.settle(taskId, "cancelled", ZERO, null); return; }
    if (!job) {
      // Submission identity and all cost components are durable before this effect.
      try {
        job = provider.submit({ submissionKey: task.submissionKey!, expiresAtMs: task.expiresAtMs!,
          proposalSha256: sha256(canonical(task.proposal)) });
      } catch (error) {
        if (!(error instanceof FixtureCrash)) this.uncertain(taskId, "Submission outcome is unresolved");
        throw error;
      }
    }
    ({ events } = this.current());
    this.append(events, "job-observed", { taskId, jobId: job.jobId });
    if (job.status !== "running") {
      if (job.actualCost === null) this.uncertain(taskId, "Final spend is unknown; reservation remains held");
      else this.settle(taskId, job.status, job.actualCost, job.result);
    }
  }
  collect(taskId: string, candidate: unknown): void {
    const provider = this.provider(candidate, taskId); const { state } = this.current(); const task = this.task(state, taskId);
    if (task.providerSha256 !== provider.identity) fail("Collection must use the originally recorded provider route");
    if (["completed", "failed", "cancelled"].includes(task.status)) return;
    if (!["submitting", "submitted", "uncertain"].includes(task.status)) fail("Task has no pending provider effect");
    let lookup = this.lookup(provider, taskId, task.submissionKey!);
    if (lookup.certainty === "uncertain" || !lookup.job) { this.uncertain(taskId, "Provider job or final cost is unresolved"); return; }
    if (!task.jobId) {
      const { events } = this.current();
      this.append(events, "job-observed", { taskId, jobId: lookup.job.jobId });
    }
    if (this.time() >= task.expiresAtMs! && lookup.job.status === "running") {
      try { provider.cancel(task.submissionKey!); }
      catch (error) { this.uncertain(taskId, "Cancellation failed; provider outcome remains unresolved"); throw error; }
      lookup = this.lookup(provider, taskId, task.submissionKey!);
    }
    if (lookup.certainty === "uncertain" || !lookup.job) { this.uncertain(taskId, "Cancellation result is unresolved"); return; }
    if (lookup.job.status === "running") return;
    if (lookup.job.actualCost === null) { this.uncertain(taskId, "Final spend is unknown; reservation remains held"); return; }
    this.settle(taskId, lookup.job.status, lookup.job.actualCost, lookup.job.result);
  }
  private settle(taskId: string, status: string, value: Costs, result: Json): void {
    if (!["completed", "failed", "cancelled"].includes(status)) fail("Invalid provider terminal status");
    const actualCost = validateCosts(value); const { events, state } = this.current(); const task = this.task(state, taskId);
    if (!["reserved", "submitting", "submitted", "uncertain"].includes(task.status)) fail("Attempt already settled");
    const breached = COST_KEYS.some((key) => actualCost[key] > task.estimate[key]) || state.spentMicros + costTotal(actualCost) > state.config.budgetMicros;
    this.append(events, "task-settled", { taskId, status, actualCost, result, breached } as unknown as Json);
  }
  primaryEvidence(taskId: string): EvidenceRef {
    const { state } = this.current(); const task = this.task(state, taskId);
    if (task.status !== "completed" || task.result === undefined) fail("No completed primary observation bundle");
    return { id: `observation-${sha256(taskId).slice(0, 32)}`, sha256: sha256(canonical(task.result)), kind: "primary-observation", locator: `provider-result:${task.submissionKey}` };
  }
  readPrimaryBundle(role: Role, taskId: string): Json {
    if (!["investigator", "supervisor", "curator", "editor", "evaluator"].includes(role)) fail("Unknown reader role");
    const evidence = this.primaryEvidence(taskId); const { events, state } = this.current();
    this.append(events, "access-granted", { role, taskId, evidence } as unknown as Json);
    return clone(this.task(state, taskId).result!);
  }
  recordReview(role: Role, taskId: string, kind: "curation" | "editorial" | "assessment", reason: string, evidence: EvidenceRef[]): EvidenceRef {
    const required = { curation: "curator", editorial: "editor", assessment: "evaluator" } as const;
    if (!Object.hasOwn(required, kind)) fail("Unknown review kind"); this.role(role, required[kind]);
    const { events, state } = this.current();
    checkReview({ taskId, role, kind, reason, evidence }, state, events);
    this.append(events, "review-recorded", { taskId, role, kind, reason, evidence } as unknown as Json);
    const event = readEvents(this.eventsDirectory).at(-1)!;
    return { id: `${kind}-${sha256(taskId).slice(0, 32)}`, sha256: event.sha256, kind, locator: `event:${event.sha256}` };
  }
  readArtifact(role: Role, request: { kind: "artifact" | "path" | "accession"; value: string }): Uint8Array {
    const { events, state } = this.current();
    keys(request, ["kind", "value"]); label(request.value, 512);
    const allowedRole = ["investigator", "supervisor", "curator", "editor", "evaluator"].includes(role);
    const matches = state.config.discoveryArtifacts.filter((entry) => request.kind === "artifact" ? entry.id === request.value : request.kind === "path" ? entry.path === request.value : request.kind === "accession" ? entry.accession === request.value : false);
    let bytes: Uint8Array | null = null; let reason = "Artifact is outside the frozen discovery allowlist";
    if (allowedRole && matches.length === 1) {
      try {
        const root = realpathSync(this.dataRoot); const target = realpathSync(join(root, matches[0]!.path));
        const path = relative(root, target);
        if (path === ".." || path.startsWith(`..${sep}`) || resolve(root, path) !== target) fail("Artifact escaped discovery mount");
        bytes = boundedFile(target, state.config.limits.maxArtifactBytes);
        if (sha256(bytes) !== matches[0]!.sha256) fail("Artifact size/hash mismatch");
      } catch { bytes = null; reason = "Artifact missing, changed, or outside discovery mount"; }
    }
    if (!bytes) { this.append(events, "access-denied", { role, request, reason } as unknown as Json); fail(reason); }
    this.append(events, "access-granted", { role, request, artifactId: matches[0]!.id, sha256: matches[0]!.sha256, bytes: bytes.byteLength } as unknown as Json);
    return bytes;
  }
}

type Job = { submissionKey: string; proposalSha256: string; jobId: string; expiresAtMs: number;
  submittedAtMs: number; completeAtMs: number | null; status: "running" | "completed" | "failed" | "cancelled";
  outcome: "completed" | "failed"; actualCost: Costs | null; result: Json };
type Lookup = { certainty: "known"; job: Job | null } | { certainty: "uncertain" };
const offlineProviders = new WeakMap<object, OfflineProvider>();
type FixtureOptions = {
  clock?: () => number; completeAfterMs?: number | null; outcome?: "completed" | "failed";
  actualCost?: Costs | null; result?: Json; crashBeforeSubmitOnce?: boolean; crashAfterSubmitOnce?: boolean;
};
class OfflineProvider {
  readonly identity: string;
  private now: () => number;
  private uncertainLookup = false;
  private options: FixtureOptions;
  constructor(private directory: string, options: FixtureOptions) {
    this.now = options.clock ?? Date.now; this.options = { ...options };
    if (options.completeAfterMs !== undefined && options.completeAfterMs !== null) integer(options.completeAfterMs, 0, 86_400_000);
    if (options.actualCost !== undefined && options.actualCost !== null) validateCosts(options.actualCost);
    if (options.outcome !== undefined && !["completed", "failed"].includes(options.outcome)) fail("Invalid fixture outcome");
    if (Buffer.byteLength(canonical(options.result ?? null), "utf8") > 8192) fail("Fixture result too large");
    mkdirSync(directory, { recursive: true, mode: 0o700 });
    const identityPath = join(directory, "identity.json");
    if (!existsSync(identityPath)) {
      try { atomicNewFile(identityPath, canonical({ schema: "algal-bio.offline-provider.v1", sha256: sha256(randomUUID()) })); }
      catch (error) { if (!(error instanceof ConcurrentUpdate)) throw error; }
    }
    const identity = keys(JSON.parse(Buffer.from(boundedFile(identityPath, 1024)).toString()), ["schema", "sha256"]);
    if (identity.schema !== "algal-bio.offline-provider.v1") fail("Wrong provider identity schema");
    this.identity = hash(identity.sha256);
  }
  private path(key: string): string { return join(this.directory, `${hash(key)}.json`); }
  private save(job: Job): void {
    const path = this.path(job.submissionKey); const temp = `${path}.${randomUUID()}.tmp`;
    writeFileSync(temp, canonical(job), { mode: 0o600 }); renameSync(temp, path);
  }
  setLookupUncertain(value: boolean): void { this.uncertainLookup = value; }
  get submissionCount(): number { return readdirSync(this.directory).filter((name) => /^[a-f0-9]{64}\.json$/.test(name)).length; }
  lookup(key: string): Lookup {
    if (this.uncertainLookup) return { certainty: "uncertain" };
    if (!existsSync(this.path(key))) return { certainty: "known", job: null };
    const record = keys(JSON.parse(Buffer.from(boundedFile(this.path(key), 16384)).toString()), ["submissionKey", "proposalSha256", "jobId", "expiresAtMs", "submittedAtMs", "completeAtMs", "status", "outcome", "actualCost", "result"]);
    if (hash(record.submissionKey) !== key) fail("Provider submission identity mismatch");
    hash(record.proposalSha256); id(record.jobId); integer(record.expiresAtMs); integer(record.submittedAtMs);
    if (record.completeAtMs !== null) integer(record.completeAtMs);
    if (!["running", "completed", "failed", "cancelled"].includes(record.status as string) || !["completed", "failed"].includes(record.outcome as string)) fail("Invalid provider status");
    if (record.actualCost !== null) validateCosts(record.actualCost);
    if (Buffer.byteLength(canonical(record.result), "utf8") > 8192) fail("Oversized provider result");
    const job = record as Job;
    const now = integer(this.now());
    if (job.status === "running") {
      if (job.completeAtMs !== null && job.completeAtMs <= now && job.completeAtMs < job.expiresAtMs) { job.status = job.outcome; this.save(job); }
      else if (now >= job.expiresAtMs) { job.status = "cancelled"; this.save(job); }
    }
    return { certainty: "known", job: clone(job) };
  }
  submit(request: { submissionKey: string; proposalSha256: string; expiresAtMs: number }): Job {
    hash(request.submissionKey); hash(request.proposalSha256); integer(request.expiresAtMs);
    const existing = this.lookup(request.submissionKey);
    if (existing.certainty === "uncertain") fail("Fixture lookup uncertainty");
    if (existing.job) {
      if (existing.job.proposalSha256 !== request.proposalSha256 || existing.job.expiresAtMs !== request.expiresAtMs) fail("Submission key reused for different intent");
      return existing.job;
    }
    if (this.options.crashBeforeSubmitOnce) { this.options.crashBeforeSubmitOnce = false; throw new FixtureCrash("Simulated crash before provider submission"); }
    const now = integer(this.now()); if (now >= request.expiresAtMs) fail("Provider refuses expired work");
    const delay = this.options.completeAfterMs === undefined ? 0 : this.options.completeAfterMs;
    const job: Job = { ...request, jobId: `offline-${request.submissionKey.slice(0, 24)}`, submittedAtMs: now,
      completeAtMs: delay === null ? null : integer(now + delay), status: "running", outcome: this.options.outcome ?? "completed",
      actualCost: this.options.actualCost === null ? null : validateCosts(this.options.actualCost ?? ZERO), result: clone(this.options.result ?? null) };
    try { atomicNewFile(this.path(request.submissionKey), canonical(job)); }
    catch (error) { if (!(error instanceof ConcurrentUpdate)) throw error; return this.submit(request); }
    if (this.options.crashAfterSubmitOnce) { this.options.crashAfterSubmitOnce = false; throw new FixtureCrash("Simulated lost provider job-ID response"); }
    return job;
  }
  cancel(key: string): void {
    const result = this.lookup(key); if (result.certainty === "uncertain") fail("Cannot establish cancellation outcome");
    if (result.job?.status === "running") { result.job.status = "cancelled"; this.save(result.job); }
  }
  resolveCost(key: string, value: unknown): void {
    const costs = validateCosts(value); const result = this.lookup(key);
    if (result.certainty === "uncertain" || !result.job || result.job.actualCost !== null) fail("Only unresolved fixture costs can be reconciled");
    result.job.actualCost = costs; this.save(result.job);
  }
}
/** Synthetic provider only: no network, shell, credentials, model invocation, or code loading. */
export function createOfflineProvider(directory: string, options: FixtureOptions = {}) {
  const provider = new OfflineProvider(resolve(directory), options);
  const handle = Object.freeze({
    lookup: provider.lookup.bind(provider), submit: provider.submit.bind(provider), cancel: provider.cancel.bind(provider),
    resolveCost: provider.resolveCost.bind(provider), setLookupUncertain: provider.setLookupUncertain.bind(provider),
    get submissionCount() { return provider.submissionCount; },
    identity: provider.identity,
  });
  offlineProviders.set(handle, provider);
  return handle;
}
