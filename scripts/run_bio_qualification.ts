import { resolve } from "node:path";
import { runQualification, verifyQualification } from "../src/bio_lab/qualification";

const [mode, directory] = Bun.argv.slice(2);
if (Bun.argv.length !== 4 || !directory || !["--offline", "--verify", "--recompute"].includes(mode!)) {
  throw new Error("usage: bun scripts/run_bio_qualification.ts <--offline|--verify|--recompute> <directory>");
}
console.log(JSON.stringify(mode === "--offline" ? await runQualification(resolve(directory)) :
  await verifyQualification(resolve(directory), mode === "--recompute")));
