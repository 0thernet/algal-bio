import { readFile, mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import type { Executor } from "@hraness/algal";
import {
  completeObservationAttempt, createObservationStudy, evaluateObservationStudy, freezeObservationStudy,
  observationDigest, registerObservationAttempt, verifyObservationStudy,
} from "@hraness/algal-lab/observation";
import { bioDesign, bioFixtureInstrument, makeBioFixtureInput } from "./instrument";
import { Campaign, canonical, createOfflineProvider, readEvents, sha256, type CampaignConfig, type Json } from "../../orchestrator";

const root = new URL("../../", import.meta.url);
const registrationURL = new URL("campaigns/qualification/registration.json", root);
const zeroCost = { inferenceMicros: 0, computeMicros: 0, storageMicros: 0, egressMicros: 0, recoveryMicros: 0 };
const proposal = {
  design: bioDesign, hypothesis: "The fixed public processed-data fixture reproduces its admitted reference.",
  prediction: { rnaPassingGenes: 28, meanCscoreDelta: "0.04620996875" },
  rationale: "A supplied known-result control, not a generated biological hypothesis.", parents: [],
};

function scripted(output: unknown, onCall: () => void): Executor {
  return { id: "bio:scripted-control.v1", capabilities: { effects: ["agent"] }, retryable: false,
    async execute() { onCall(); return JSON.parse(JSON.stringify(output)); } };
}

async function registration() {
  const value = JSON.parse(await readFile(registrationURL, "utf8"));
  // This qualification is fixed, not an agent-editable general campaign engine.
  if (value.contract !== "bio.offline-qualification.v1" || JSON.stringify(value.repetitions) !== "[0,1,2]" ||
    value.prospective_decision !== "no_go" || value.cost.external_spend_micros !== 0) {
    throw new Error("offline qualification registration changed; review and register a new study");
  }
  return value;
}

async function artifactAt(directory: string, pointer: string) {
  const ref = JSON.parse(await readFile(join(directory, pointer), "utf8"));
  if (!/^sha256:[a-f0-9]{64}$/.test(ref.artifact)) throw new Error("invalid retained artifact reference");
  const value = JSON.parse(await readFile(join(directory, "artifacts", ref.artifact.slice(7) + ".json"), "utf8"));
  if (observationDigest(value) !== ref.artifact) throw new Error("retained artifact changed");
  return value;
}

async function coordinatorConfig(plan: unknown): Promise<CampaignConfig> {
  const bytes = await readFile(new URL("tests/fixtures/bio/rna-counts.tsv", root));
  return { schema: "algal-bio.campaign.v1", campaignId: "offline-evidence-curation-v1", currency: "USD", budgetMicros: 0,
    registrationSha256: sha256(canonical(plan)), judgeSha256: sha256(await readFile(new URL("tests/fixtures/bio/expected.json", root))),
    limits: { maxTasks: 3, maxRetries: 0, maxRevisions: 0, maxEvents: 120, jobTimeoutMs: 30_000, leaseMs: 60_000, maxArtifactBytes: 65_536 },
    discoveryArtifacts: [{ id: "rna-fixture", path: "tests/fixtures/bio/rna-counts.tsv", sha256: sha256(bytes), accession: "GSE330013" }],
    excludedAccessions: ["GSE89520"], reservedArtifactIds: ["prospective-evaluation"] };
}

export async function runQualification(directory: string) {
  const started = performance.now();
  const plan = await registration();
  await mkdir(directory); // never overwrite a previous attempt or its failures
  await writeFile(join(directory, "registration.json"), JSON.stringify(plan, null, 2) + "\n", { flag: "wx" });
  const input = await makeBioFixtureInput();
  const coordinator = new Campaign(join(directory, "curation"), await coordinatorConfig(plan), "offline-controller", { dataRoot: fileURLToPath(root) });
  coordinator.acquireLease();
  coordinator.readArtifact("investigator", { kind: "artifact", value: "rna-fixture" });
  for (const request of [{ kind: "artifact" as const, value: "prospective-evaluation" },
    { kind: "path" as const, value: "holdout/hidden.json" }, { kind: "accession" as const, value: "GSE89520" }]) {
    let denied = false;
    try { coordinator.readArtifact("investigator", request); } catch { denied = true; }
    if (!denied) throw new Error("unadmitted data access succeeded");
  }
  const repetitionReports = [];
  for (const repetition of plan.repetitions as number[]) {
    const path = join(directory, `repetition-${repetition}`);
    const protocol = { contract: "algal.lab.observation-study.v1", name: `biology-calibration-${repetition}`, maxAttempts: 3,
      evaluation: { inputDigest: observationDigest(input), specification: { endpoint: plan.endpoint,
        registrationDigest: observationDigest(plan), exposure: plan.evaluation } } };
    await createObservationStudy(protocol, path, bioFixtureInstrument);
    let calls = 0;
    const count = () => { calls++; };
    await registerObservationAttempt(path, bioFixtureInstrument, { attemptId: "known-control", input,
      context: { arm: "scripted", repetition, referenceIsExposed: true }, executor: scripted(proposal, count) });
    const pending = await verifyObservationStudy(path, bioFixtureInstrument);
    if (pending.pending !== 1 || pending.observations !== 0) throw new Error("prediction was not durably registered first");
    const control = await completeObservationAttempt(path, bioFixtureInstrument, "known-control");
    if (!control.observation.observation) throw new Error("known calibration failed; retained its failed receipt");
    // Retain a real failed tool receipt and a rejected bounded proposal. Neither
    // is a scientific decoy; these exercise software admission only.
    await registerObservationAttempt(path, bioFixtureInstrument, { attemptId: "unadmitted-analysis", input,
      context: { control: "unadmitted-design" }, executor: scripted({ ...proposal, design: { analysis: "execute-arbitrary-code" } }, count) });
    const failed = await completeObservationAttempt(path, bioFixtureInstrument, "unadmitted-analysis");
    if (failed.observation.observation !== null || failed.observation.receipt.outcome !== "failed") throw new Error("unadmitted analysis executed");
    const rejected = await registerObservationAttempt(path, bioFixtureInstrument, { attemptId: "malformed-proposal", input,
      context: { control: "contract-rejection" }, executor: scripted({ ...proposal, unexpected: true }, count) });
    if (!rejected.registration.rejection) throw new Error("malformed proposal was admitted");
    await freezeObservationStudy(path, bioFixtureInstrument, ["known-control"]);
    await evaluateObservationStudy(path, bioFixtureInstrument, input);
    const replay = await verifyObservationStudy(path, bioFixtureInstrument);
    const fresh = await verifyObservationStudy(path, bioFixtureInstrument, { recompute: true });
    if (calls !== 3 || replay.rejected !== 1 || replay.observations !== 2 || replay.evaluated !== 1 || !replay.frozen) {
      throw new Error("qualification evidence cardinality changed");
    }
    // The coordinator admits review of an already computed lab observation.
    // Its offline provider simulates transport; it does not execute the biology
    // tool, invoke a model, or establish external-job isolation.
    coordinator.acquireLease();
    const taskId = `curate-${repetition}`;
    coordinator.propose("investigator", { taskId, question: "Review retained calibration evidence and its limits.",
      instrumentId: "retained-lab-observation-v1", inputArtifactIds: ["rna-fixture"], action: "json-observation",
      parameters: { archive: `repetition-${repetition}`, observationDigest: control.observationDigest } }, zeroCost);
    coordinator.critique("supervisor", taskId, "admit", "Only bounded review of already retained public calibration evidence is admitted.");
    const provider = createOfflineProvider(join(directory, "offline-provider", taskId), { actualCost: zeroCost,
      result: { archive: `repetition-${repetition}`, observationDigest: control.observationDigest,
        observation: control.observation.observation } as unknown as Json });
    coordinator.dispatch(taskId, provider);
    coordinator.collect(taskId, provider);
    const primary = coordinator.primaryEvidence(taskId);
    coordinator.readPrimaryBundle("curator", taskId);
    const curation = coordinator.recordReview("curator", taskId, "curation", "Scripted curation: source-bound observation matches the supplied reference; biological inference remains unavailable.", [primary]);
    coordinator.recordReview("editor", taskId, "editorial", "Scripted editorial check: publish as calibration only, with no discovery or model-capability claim.", [curation, primary]);
    repetitionReports.push({ repetition, scriptedProposalCalls: calls, providerCalls: 0,
      controlValues: control.observation.observation.values, successfulControls: 1, failedMeasurements: 1,
      rejectedProposals: 1, selected: ["known-control"], receiptReplay: replay.receiptReplay,
      freshComputation: fresh.freshComputation });
  }
  coordinator.releaseLease();
  const ledger = coordinator.snapshot();
  const report = { contract: "bio.qualification-report.v1", registrationDigest: observationDigest(plan),
    status: "offline_passed", repetitions: repetitionReports, externalSpendMicros: 0,
    wallTimeMs: Math.ceil(performance.now() - started), inputBytes: input.artifacts.reduce((sum, artifact) => sum + artifact.bytes, 0),
    coordinator: { headSha256: ledger.headSha256, eventCount: ledger.eventCount, spentMicros: ledger.spentMicros,
      reservedMicros: ledger.reservedMicros, mode: "offline transport and scripted review of retained lab observations" },
    prospectiveDecision: "no_go", liveAgentComparison: "not_run", independentBiologicalHoldout: "not_available",
    limitations: plan.limits };
  await writeFile(join(directory, "report.json"), JSON.stringify(report, null, 2) + "\n", { flag: "wx" });
  return report;
}

export async function verifyQualification(directory: string, recompute = false) {
  const plan = await registration();
  const retained = JSON.parse(await readFile(join(directory, "registration.json"), "utf8"));
  const report = JSON.parse(await readFile(join(directory, "report.json"), "utf8"));
  if (observationDigest(retained) !== observationDigest(plan) || report.registrationDigest !== observationDigest(plan) ||
    report.contract !== "bio.qualification-report.v1" || report.status !== "offline_passed" ||
    report.prospectiveDecision !== "no_go" || report.liveAgentComparison !== "not_run" ||
    report.externalSpendMicros !== 0 || report.repetitions.length !== 3 ||
    observationDigest(report.limitations) !== observationDigest(plan.limits) ||
    report.independentBiologicalHoldout !== "not_available" || !Number.isSafeInteger(report.wallTimeMs) || report.wallTimeMs < 0 ||
    report.inputBytes !== (await makeBioFixtureInput()).artifacts.reduce((sum, artifact) => sum + artifact.bytes, 0)) throw new Error("qualification registration/report mismatch");
  const expected = plan.expected;
  for (const repetition of plan.repetitions as number[]) {
    const row = report.repetitions[repetition];
    const path = join(directory, `repetition-${repetition}`);
    const verified = await verifyObservationStudy(path, bioFixtureInstrument, { recompute });
    const control = await artifactAt(path, "attempts/known-control/observed.json");
    const failure = await artifactAt(path, "attempts/unadmitted-analysis/observed.json");
    const rejection = await artifactAt(path, "attempts/malformed-proposal/registered.json");
    const selection = await artifactAt(path, "freeze.json");
    const baselineOutputs = { "known-control": proposal,
      "unadmitted-analysis": { ...proposal, design: { analysis: "execute-arbitrary-code" } },
      "malformed-proposal": { ...proposal, unexpected: true } };
    for (const [attemptId, expectedOutput] of Object.entries(baselineOutputs)) {
      const registered = await artifactAt(path, `attempts/${attemptId}/registered.json`);
      const receipt = registered.receipt;
      if (receipt.work.agentCalls !== 1 || receipt.effects.length !== 1 || receipt.effects[0].executor !== "bio:scripted-control.v1" ||
        observationDigest(receipt.cells.propose.outputs.out) !== observationDigest(expectedOutput)) {
        throw new Error("qualification archive differs from its registered scripted baseline");
      }
    }
    if (!verified.frozen || verified.attempts !== 3 || verified.pending !== 0 || verified.rejected !== 1 ||
      verified.observations !== 2 || verified.evaluated !== 1 || row.repetition !== repetition ||
      row.scriptedProposalCalls !== 3 || row.providerCalls !== 0 || row.successfulControls !== 1 ||
      row.failedMeasurements !== 1 || row.rejectedProposals !== 1 || row.receiptReplay !== true || row.freshComputation !== "passed" ||
      control.receipt.outcome !== "complete" || !control.observation || failure.receipt.outcome !== "failed" || failure.observation !== null ||
      rejection.proposal !== null || !rejection.rejection || JSON.stringify(selection.selected) !== '["known-control"]' ||
      observationDigest(control.observation.values) !== observationDigest(row.controlValues) ||
      JSON.stringify(row.selected) !== '["known-control"]' || observationDigest(row.controlValues) !== observationDigest(expected)) {
      throw new Error("qualification score does not match frozen evidence");
    }
  }
  const events = readEvents(join(directory, "curation", "events"));
  if (!events.length) throw new Error("coordinator evidence missing");
  const state = new Campaign(join(directory, "curation"), await coordinatorConfig(plan), "offline-verifier").snapshot();
  if (state.headSha256 !== report.coordinator.headSha256 || state.eventCount !== report.coordinator.eventCount || state.spentMicros !== 0 ||
    report.coordinator.spentMicros !== state.spentMicros || report.coordinator.reservedMicros !== state.reservedMicros ||
    report.coordinator.mode !== "offline transport and scripted review of retained lab observations" ||
    state.reservedMicros !== 0 || state.uncertain || state.breached || state.lease !== null || Object.keys(state.tasks).length !== 3 ||
    events.filter((event) => event.kind === "access-denied").length !== 3 ||
    events.filter((event) => event.kind === "review-recorded").length !== 6) throw new Error("coordinator qualification evidence mismatch");
  for (const repetition of plan.repetitions as number[]) {
    const task = state.tasks[`curate-${repetition}`];
    const control = await artifactAt(join(directory, `repetition-${repetition}`), "attempts/known-control/observed.json");
    if (task?.status !== "completed" || observationDigest(task.result) !== observationDigest({ archive: `repetition-${repetition}`,
      observationDigest: observationDigest(control), observation: control.observation })) throw new Error("curation lost the primary lab observation");
  }
  return { ok: true, registrationDigest: observationDigest(plan), repetitions: 3, receiptReplay: true,
    freshComputation: recompute ? "passed" : "not-requested", prospectiveDecision: "no_go" };
}
