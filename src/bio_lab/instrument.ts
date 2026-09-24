import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import {
  observationDigest, parseObservationInput,
  type ArtifactReference, type Observation, type ObservationInput, type ObservationInstrument,
} from "@hraness/algal-lab/observation";

const root = new URL("../../", import.meta.url);
const fixture = new URL("tests/fixtures/bio/", root);
const files = ["cscore-minus-provenance.json", "cscore-minus.bedgraph", "cscore-plus-provenance.json",
  "cscore-plus.bedgraph", "expected.json", "rna-counts.tsv", "rna-provenance.json"];
const data = { task: "processed-data-calibration", dataRole: "reproduction", registration: "lamina-context-pilot" };
export const bioDesign = { analysis: "rna-pre-tmm-filter-and-cscore-interval-mean", version: 1 };
const limitations = ["Reproduction data are public and exposed; this is not an independent biological holdout.",
  "RNA and chromatin have different ages and cell preparations and are not joined by sample.",
  "Preprocessing calibration only; no differential expression, novelty, mechanism, or model-capability claim."];
function reportedMeasurements(values: Record<string, number | string>) {
  return [
    { name: "rna-retained-genes", value: Number(values.rna_passing), unit: "genes",
      uncertainty: { method: "exact descriptive count; biological uncertainty not estimated", lower: null, upper: null, level: null } },
    { name: "mean-cscore-interval-delta", value: Number(values.chromatin_mean_delta), unit: "C-score",
      uncertainty: { method: "decimal arithmetic; aggregate intervals are not independent replicates", lower: null, upper: null, level: null } },
  ];
}

/** Inputs name a fixed, admitted public fixture. Neither model text nor a file
 * attachment can select a command, interpreter, data path, or remote resource.
 */
export async function makeBioFixtureInput(): Promise<ObservationInput> {
  const artifacts: ArtifactReference[] = [];
  for (const name of files) {
    const bytes = await readFile(new URL(name, fixture));
    artifacts.push({ name, digest: `sha256:${createHash("sha256").update(bytes).digest("hex")}`,
      bytes: bytes.length, mediaType: name.endsWith(".json") ? "application/json" : "text/tab-separated-values" });
  }
  return { contract: "bio.calibration-input.v1", data, artifacts };
}

async function assertInput(input: ObservationInput): Promise<void> {
  if (observationDigest(input) !== observationDigest(await makeBioFixtureInput())) {
    throw new Error("input differs from the admitted fixed public fixture");
  }
}

async function expectedValues(): Promise<Record<string, number | string>> {
  return JSON.parse(await readFile(new URL("expected.json", fixture), "utf8"));
}

async function boundedOutput(stream: ReadableStream<Uint8Array>, maximum: number): Promise<string> {
  const chunks: Uint8Array[] = [];
  let size = 0;
  for await (const chunk of stream) {
    size += chunk.length;
    if (size > maximum) throw new Error("trusted instrument exceeded its output bound");
    chunks.push(chunk);
  }
  return Buffer.concat(chunks).toString("utf8");
}

async function compute(): Promise<Observation> {
  // This is a fixed trusted local tool, not an arbitrary-code sandbox. External
  // and investigator-generated code are not dispatched through this adapter.
  const python = fileURLToPath(new URL(".venv/bin/python", root));
  const env = { PYTHONDONTWRITEBYTECODE: "1", PYTHONHASHSEED: "0", LANG: "C.UTF-8" };
  const version = Bun.spawnSync([python, "-I", "-S", "--version"], { env, stdout: "pipe", stderr: "pipe", timeout: 5000 });
  const pin = (await readFile(new URL(".python-version", root), "utf8")).trim();
  if (version.exitCode !== 0 || version.stdout.toString().trim() !== `Python ${pin}`) {
    throw new Error("run make install with the registered Python toolchain before measuring");
  }
  const child = Bun.spawn([python, "-I", "-S", fileURLToPath(new URL("scripts/reproduce_bio_fixture.py", root)), "--offline", "--json"],
    { cwd: fileURLToPath(root), env, stdin: "ignore", stdout: "pipe", stderr: "pipe", timeout: 30_000 });
  let stdout: string, stderr: string, exitCode: number;
  try {
    [stdout, stderr, exitCode] = await Promise.all([boundedOutput(child.stdout, 65_536), boundedOutput(child.stderr, 8192), child.exited]);
  } catch (error) { child.kill(); await child.exited; throw error; }
  if (exitCode !== 0 || stderr.length) throw new Error("fixed biological measurement failed; inspect inputs and pinned toolchain");
  const result = JSON.parse(stdout);
  if (result.contract !== "bio.fixture-reproduction.v1" || result.independent_arithmetic !== "passed") {
    throw new Error("instrument returned an unqualified result");
  }
  const values = { rna_genes: result.rna.genes, rna_passing: result.rna.passing_count,
    chromatin_intervals: result.chromatin.intervals, chromatin_mean_delta: result.chromatin.mean_interval_delta };
  if (observationDigest(values) !== observationDigest(await expectedValues())) throw new Error("registered reference changed");
  return {
    contract: "bio.calibration-observation.v1", realizedDesign: bioDesign, values,
    measurements: reportedMeasurements(values),
    artifacts: (await makeBioFixtureInput()).artifacts,
    limitations,
  };
}

export const bioFixtureInstrument: ObservationInstrument = {
  contract: "algal.lab.instrument.v1", id: "bio-public-calibration-v1",
  inputContract: "bio.calibration-input.v1", outputContract: "bio.calibration-observation.v1", execution: "pure",
  sources: {
    trees: { fixture, coordinator: new URL("orchestrator/", root) },
    // Exact executed closure: the adapter only imports the pinned lab and these
    // Python sources. Listing source files avoids platform-specific __pycache__.
    files: { adapter: new URL("src/bio_lab/instrument.ts", root),
      measurements: new URL("src/bio_lab/measurements.py", root),
      init: new URL("src/bio_lab/__init__.py", root),
      reproduction: new URL("scripts/reproduce_bio_fixture.py", root),
      qualification: new URL("src/bio_lab/qualification.ts", root),
      registration: new URL("campaigns/qualification/registration.json", root),
      python: new URL(".python-version", root), "python-project": new URL("pyproject.toml", root), "python-lock": new URL("uv.lock", root),
      package: new URL("package.json", root), "bun-lock": new URL("bun.lock", root) },
  },
  parseInput(value) {
    const input = parseObservationInput(value);
    if (input.contract !== "bio.calibration-input.v1" || observationDigest(input.data) !== observationDigest(data)) {
      throw new Error("unsupported biology measurement request");
    }
    return input;
  },
  async verify(input, proposal, observation) {
    await assertInput(input);
    if (observationDigest(proposal.design) !== observationDigest(bioDesign) ||
      observationDigest(observation.realizedDesign) !== observationDigest(bioDesign)) throw new Error("unadmitted biological design");
    const expected = await expectedValues();
    if (observationDigest(observation.values) !== observationDigest(expected)) throw new Error("measurement disagrees with frozen reference");
    if (observationDigest(observation.artifacts) !== observationDigest(input.artifacts)) throw new Error("observation input artifacts differ");
    if (observationDigest(observation.measurements) !== observationDigest(reportedMeasurements(expected))) {
      throw new Error("reported measurement does not match observed values");
    }
    if (observationDigest(observation.limitations) !== observationDigest(limitations)) throw new Error("measurement limitations missing or changed");
  },
  async measure(input, proposal) {
    await assertInput(input);
    if (observationDigest(proposal.design) !== observationDigest(bioDesign)) throw new Error("proposed analysis has no execution authority");
    return compute();
  },
};
