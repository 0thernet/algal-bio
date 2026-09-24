#!/usr/bin/env python3
"""Copy the campaign record into the public repository worktree.

Excludes raw data, the full GEO SOFT export, and anything containing a personal
filesystem path. Prints every copied file with its SHA-256 so the public README
can cite frozen identities. Usage: assemble_public.py <repo_worktree>
"""
import hashlib, json, pathlib, re, shutil, sys
ROOT = pathlib.Path(__file__).resolve().parents[1]
SLUG = "lmna-acute-lamina-vs-chronic-compartment-2026-09-24"
repo = pathlib.Path(sys.argv[1]).resolve()
camp = repo / "campaigns" / SLUG
rep = repo / "reports" / SLUG
PRIVATE = re.compile("/Use" + "rs/|/ho" + "me/|/private/t" + "mp|~/")
COPY = {
    "code/compartment.py": camp / "compartment.py",
    "code/test_compartment.py": camp / "test_compartment.py",
    "code/requirements.in": camp / "requirements.in",
    "code/requirements.lock": camp / "requirements.lock",
    "registration/protocol.frozen.json": camp / "registration.frozen.json",
    "registration/protocol.draft.json": camp / "registration.reviewed-draft.json",
    "registration/freeze.json": camp / "freeze.json",
    "registration/intake.json": camp / "intake.json",
    "registration/freeze.py": camp / "freeze.py",
    "registration/intake.py": camp / "intake.py",
    "design/protocol.md": camp / "design" / "fixed-protocol.md",
    "design/skeptical-review.md": camp / "design" / "skeptical-review.md",
    "design/independent-review.json": camp / "design" / "independent-review.json",
    "results/predictor/predictor.manifest.json": camp / "predictor.manifest.json",
    "results/predictor/predictor.tsv": camp / "predictor.tsv",
    "data-audit/eligibility.md": rep / "data-audit" / "eligibility.md",
    "data-audit/GSE126459-outcome-audit.json": rep / "data-audit" / "GSE126459-outcome-audit.json",
    "prior-art/report.md": rep / "prior-art" / "report.md",
    "prior-art/findings.json": rep / "prior-art" / "findings.json",
    "prior-art/query-ledger.json": rep / "prior-art" / "query-ledger.json",
    "results/run-002/summary.json": rep / "results" / "summary.json",
    "results/run-002/tiles.tsv": rep / "results" / "tiles.tsv",
    "results/run-001/FAILED.md": rep / "results" / "run-001-FAILED.md",
    "results/run-001/format-check.txt": rep / "results" / "run-001-format-check.txt",
    "report.md": rep / "report.md",
    "registration/protocol.frozen-001.json": camp / "registration.frozen-001.json",
    "registration/freeze-001.json": camp / "freeze-001.json",
    "registration/intake-001.json": camp / "intake-001.json",
    "registration/archive-001/compartment.py": camp / "archive-001" / "compartment.py",
    "registration/archive-001/test_compartment.py": camp / "archive-001" / "test_compartment.py",
    "registration/archive-001/README.md": camp / "archive-001" / "README.md",
    "registration/archive-002/compartment.py": camp / "archive-002" / "compartment.py",
    "registration/archive-002/test_compartment.py": camp / "archive-002" / "test_compartment.py",
    "registration/archive-002/requirements.lock": camp / "archive-002" / "requirements.lock",
    "registration/assemble_public.py": camp / "assemble_public.py",
}
for src in sorted((ROOT / "prior-art" / "sources").glob("*.md")):
    COPY[f"prior-art/sources/{src.name}"] = rep / "prior-art" / "sources" / src.name
manifest = []
for rel, dst in COPY.items():
    src = ROOT / rel
    if not src.exists():
        print("MISSING", rel); continue
    data = src.read_bytes()
    if PRIVATE.search(data.decode("utf-8", "replace")):
        print("PRIVATE PATH, NOT COPIED", rel); continue
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    manifest.append({"source": rel, "published": str(dst.relative_to(repo)), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    print(f"{hashlib.sha256(data).hexdigest()[:16]} {len(data):>9} {dst.relative_to(repo)}")
(rep / "assembly.manifest.json").parent.mkdir(parents=True, exist_ok=True)
with open(rep / "assembly.manifest.json", "w") as fh:
    json.dump({"schema": "bio.public-assembly.v1", "files": manifest}, fh, indent=2); fh.write("\n")
