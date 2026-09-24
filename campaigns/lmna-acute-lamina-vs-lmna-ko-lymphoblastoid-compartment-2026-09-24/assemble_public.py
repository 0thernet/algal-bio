#!/usr/bin/env python3
"""Copy the replication campaign record into the public repository worktree.

Excludes raw data (pairs files, deposited PC1, per-sample pipeline bedGraphs of the
validation runs), the large tools files (chain, RefSeq tables; hashes are in the
registration and freeze receipt) and anything containing a personal filesystem path.
Writes reports/<slug>/assembly.manifest.json with a hash of every published file.
Usage: assemble_public.py <repo_worktree>
"""
import hashlib, json, pathlib, re, shutil, sys
ROOT = pathlib.Path(__file__).resolve().parents[1]
SLUG = "lmna-acute-lamina-vs-lmna-ko-lymphoblastoid-compartment-2026-09-24"
repo = pathlib.Path(sys.argv[1]).resolve()
camp = repo / "campaigns" / SLUG
rep = repo / "reports" / SLUG
PRIVATE = re.compile("/Use" + "rs/|/ho" + "me/|/private/t" + "mp|~" + "/")
# Bound files whose bytes contain a string the filter rejects are published as a redacted copy
# with the substitution recorded in the manifest; the frozen hash of the original stays in freeze.json.
REDACT = {"design/independent-review.json": [("'" + "/Use" + "rs/" + "'", "'<home-prefix>/'")],
          "registration/archive-001/independent-review.json": [("'" + "/Use" + "rs/" + "'", "'<home-prefix>/'")]}
COPY = {
    "code/replicate.py": camp / "replicate.py",
    "code/compartment.py": camp / "compartment.py",
    "code/pc1.py": camp / "pc1.py",
    "code/lift_predictor.py": camp / "lift_predictor.py",
    "code/per_chromosome_table.py": camp / "per_chromosome_table.py",
    "results/run-001/per-chromosome-validation-vs-outcome.json": rep / "results" / "per-chromosome-validation-vs-outcome.json",
    "logs/run-001.argv-error.log": rep / "results" / "run-001-argv-error.log",
    "code/test_replicate.py": camp / "test_replicate.py",
    "code/test_pc1.py": camp / "test_pc1.py",
    "code/requirements.in": camp / "requirements.in",
    "code/requirements.lock": camp / "requirements.lock",
    "registration/protocol.frozen.json": camp / "registration.frozen.json",
    "registration/protocol.draft.json": camp / "registration.reviewed-draft.json",
    "registration/freeze.json": camp / "freeze.json",
    "registration/intake.json": camp / "intake.json",
    "registration/freeze.py": camp / "freeze.py",
    "registration/intake.py": camp / "intake.py",
    "registration/assemble_public.py": camp / "assemble_public.py",
    "design/fixed-protocol.md": camp / "design" / "fixed-protocol.md",
    "design/skeptical-review.md": camp / "design" / "skeptical-review.md",
    "design/independent-review.json": camp / "design" / "independent-review.json",
    "design/null-sd-estimate.json": camp / "design" / "null-sd-estimate.json",
    "design/method-validation.json": camp / "design" / "method-validation.json",
    "design/method-validation.attempt2-unbound-script.json": camp / "design" / "method-validation.attempt2-unbound-script.json",
    "design/method-validation-attempts.md": camp / "design" / "method-validation-attempts.md",
    "design/validate_pc1.py": camp / "design" / "validate_pc1.py",
    "results/predictor/predictor_hg19.manifest.json": camp / "predictor_hg19.manifest.json",
    "results/predictor/predictor_hg19.tsv": camp / "predictor_hg19.tsv",
    "tools/SHA256SUMS": camp / "tools.SHA256SUMS",
    "tools/FETCHED_UTC": camp / "tools.FETCHED_UTC",
    "tools/hg19.chrom.sizes": camp / "hg19.chrom.sizes",
    "prior-art/caruso-2026.md": rep / "prior-art" / "caruso-2026.md",
    "prior-art/caruso-2026.json": rep / "prior-art" / "caruso-2026.json",
    "prior-art/query-ledger.json": rep / "prior-art" / "query-ledger.json",
    "data-audit/GSE126459-filelist.txt": rep / "data-audit" / "GSE126459-filelist.txt",
    "data-audit/GSE126459-validation-SHA256SUMS": rep / "data-audit" / "GSE126459-validation-SHA256SUMS",
    "results/run-001/summary.json": rep / "results" / "summary.json",
    "report.md": rep / "report.md",
    "README.campaign.md": camp / "README.md",
}
for arch in sorted((ROOT / "registration").glob("archive-*")):
    for f in sorted(arch.iterdir()):
        if f.is_file() and f.stat().st_size < 2_000_000:
            COPY[f"registration/{arch.name}/{f.name}"] = camp / arch.name / f.name
for f in sorted((ROOT / "results" / "run-001").glob("core/*")) if (ROOT / "results" / "run-001" / "core").exists() else []:
    COPY[f"results/run-001/core/{f.name}"] = rep / "results" / "core" / f.name
for f in sorted((ROOT / "results" / "run-001").glob("pc1/*.stats.json")) if (ROOT / "results" / "run-001" / "pc1").exists() else []:
    COPY[f"results/run-001/pc1/{f.name}"] = rep / "results" / "pc1-stats" / f.name
for f in sorted((ROOT / "results" / "run-001").glob("pc1-qc/*.bedGraph")) if (ROOT / "results" / "run-001" / "pc1-qc").exists() else []:
    COPY[f"results/run-001/pc1-qc/{f.name}"] = rep / "results" / "pc1" / f.name
manifest = []
for rel, dst in COPY.items():
    src = ROOT / rel
    if not src.exists():
        print("MISSING", rel); continue
    data = src.read_bytes()
    entry = {"source": rel, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    if rel in REDACT:
        text = data.decode("utf-8")
        for old, new in REDACT[rel]:
            assert text.count(old) >= 1, (rel, old)
            text = text.replace(old, new)
        data = text.encode("utf-8")
        dst = dst.with_name(dst.stem + ".redacted" + dst.suffix)
        entry.update({"redacted": True, "original_sha256": entry["sha256"],
                      "substitutions": [{"replaced": "the quoted 7-character macOS home-directory prefix literal that appears in the round-1 advice text", "with": new, "occurrences": text.count(new)} for _, new in REDACT[rel]],
                      "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    if PRIVATE.search(data.decode("utf-8", "replace")):
        print("PRIVATE PATH, NOT COPIED", rel); continue
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(data)
    entry["published"] = str(dst.relative_to(repo))
    manifest.append(entry)
    print(f"{hashlib.sha256(data).hexdigest()[:16]} {len(data):>9} {dst.relative_to(repo)}")
rep.mkdir(parents=True, exist_ok=True)
with open(rep / "assembly.manifest.json", "w") as fh:
    json.dump({"schema": "bio.public-assembly.v1", "files": manifest}, fh, indent=2); fh.write("\n")
