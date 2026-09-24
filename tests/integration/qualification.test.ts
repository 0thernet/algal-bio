import { expect, test } from "bun:test";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { runQualification, verifyQualification } from "../../src/bio_lab/qualification";

test("public biology instrument, real lab receipts, frozen selection and coordinator evidence qualify together", async () => {
  const temporary = await mkdtemp(join(tmpdir(), "algal-bio-qualification-"));
  const directory = join(temporary, "run");
  try {
    const report = await runQualification(directory);
    expect(report.status).toBe("offline_passed");
    expect(report.repetitions).toHaveLength(3);
    expect(report.repetitions.every((r) => r.providerCalls === 0 && r.failedMeasurements === 1 && r.rejectedProposals === 1)).toBe(true);
    expect(report.externalSpendMicros).toBe(0);
    expect(report.liveAgentComparison).toBe("not_run");
    expect(await verifyQualification(directory)).toMatchObject({ ok: true, receiptReplay: true, freshComputation: "not-requested", prospectiveDecision: "no_go" });
    expect(await verifyQualification(directory, true)).toMatchObject({ ok: true, freshComputation: "passed" });
    await expect(runQualification(directory)).rejects.toThrow();
    const path = join(directory, "report.json");
    const original = await readFile(path, "utf8");
    const changed = JSON.parse(original);
    changed.repetitions[0].controlValues.rna_passing += 1;
    await writeFile(path, JSON.stringify(changed));
    await expect(verifyQualification(directory)).rejects.toThrow("score");
    const changedCost = JSON.parse(original);
    changedCost.coordinator.spentMicros = 1000;
    await writeFile(path, JSON.stringify(changedCost));
    await expect(verifyQualification(directory)).rejects.toThrow("coordinator");
    const changedBytes = JSON.parse(original);
    changedBytes.inputBytes = 0;
    await writeFile(path, JSON.stringify(changedBytes));
    await expect(verifyQualification(directory)).rejects.toThrow("registration/report");
    await writeFile(path, original);
    const pointer = join(directory, "repetition-0", "attempts", "known-control", "observed.json");
    const reference = JSON.parse(await readFile(pointer, "utf8"));
    const artifact = join(directory, "repetition-0", "artifacts", reference.artifact.slice(7) + ".json");
    const corrupt = JSON.parse(await readFile(artifact, "utf8"));
    corrupt.observation.values.rna_passing += 1;
    await writeFile(artifact, JSON.stringify(corrupt));
    await expect(verifyQualification(directory)).rejects.toThrow("digest");
  } finally { await rm(temporary, { recursive: true, force: true }); }
}, 120_000);
