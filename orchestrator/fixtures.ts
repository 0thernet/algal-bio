/** Small executable recovery/budget fixture. All monetary values are simulated micros. */
import { mkdirSync } from "node:fs";
import { join } from "node:path";
import { Campaign, FixtureCrash, createOfflineProvider, type CampaignConfig, type Costs } from "./index.ts";

export function runBudgetFixtures(directory: string) {
  mkdirSync(directory, { recursive: true });
  let now = 1000;
  const clock = () => now;
  const config: CampaignConfig = {
    schema: "algal-bio.campaign.v1", campaignId: "recovery-fixture", currency: "USD", budgetMicros: 100,
    registrationSha256: "a".repeat(64), judgeSha256: "b".repeat(64),
    limits: { maxTasks: 4, maxRetries: 1, maxRevisions: 1, maxEvents: 200, jobTimeoutMs: 1000, leaseMs: 100, maxArtifactBytes: 1024 },
    discoveryArtifacts: [], excludedAccessions: ["EXCLUDED"], reservedArtifactIds: ["reserved"],
  };
  const estimate: Costs = { inferenceMicros: 20, computeMicros: 20, storageMicros: 10, egressMicros: 10, recoveryMicros: 40 };
  const proposal = (taskId: string) => ({ taskId, question: "Offline recovery fixture", instrumentId: "json-fixture-v1", inputArtifactIds: [], action: "json-observation", parameters: { simulated: true } });
  const run = join(directory, "recovery");
  const campaign = new Campaign(run, config, "first", { clock }); campaign.acquireLease();
  campaign.propose("investigator", proposal("control"), estimate);
  campaign.critique("supervisor", "control", "admit", "All five budget components reserved");
  const provider = createOfflineProvider(join(directory, "provider"), { clock, crashAfterSubmitOnce: true, actualCost: null, result: { kind: "synthetic-primary-observation", value: 3 } });
  try { campaign.dispatch("control", provider); }
  catch (error) { if (!(error instanceof FixtureCrash)) throw error; }
  now += 101;
  const recovered = new Campaign(run, config, "recovered", { clock }); recovered.acquireLease();
  recovered.dispatch("control", provider); recovered.collect("control", provider);
  recovered.propose("investigator", proposal("followup"), estimate);
  let unknownSpendBlocked = false;
  try { recovered.critique("supervisor", "followup", "admit", "Must remain denied while cost is unknown"); }
  catch { unknownSpendBlocked = true; }
  provider.resolveCost(recovered.snapshot().tasks.control!.submissionKey!, estimate);
  recovered.collect("control", provider);
  let exhaustionBlocked = false;
  try { recovered.critique("supervisor", "followup", "admit", "Must remain denied at exhausted budget"); }
  catch { exhaustionBlocked = true; }
  recovered.critique("supervisor", "followup", "reject", "Budget is exhausted; retain rejected follow-up");
  const primary = recovered.primaryEvidence("control");
  recovered.readPrimaryBundle("curator", "control");
  const curation = recovered.recordReview("curator", "control", "curation", "Primary bundle checked; synthetic value only", [primary]);
  recovered.recordReview("editor", "control", "editorial", "No biological or model intelligence claim", [curation, primary]);
  recovered.releaseLease();
  const result = { schema: "algal-bio.budget-fixture-result.v1", unknownSpendBlocked, exhaustionBlocked,
    submissionCount: provider.submissionCount, spentMicros: recovered.snapshot().spentMicros,
    reservedMicros: recovered.snapshot().reservedMicros, journal: "recovery/events", headSha256: recovered.snapshot().headSha256 };
  if (!unknownSpendBlocked || !exhaustionBlocked || result.submissionCount !== 1 || result.spentMicros !== 100 || result.reservedMicros !== 0) throw new Error("Budget fixture failed");
  return result;
}

if (import.meta.main) {
  if (process.argv.length !== 3) throw new Error("Usage: bun orchestrator/fixtures.ts OUTPUT_DIRECTORY");
  console.log(JSON.stringify(runBudgetFixtures(process.argv[2]!), null, 2));
}
