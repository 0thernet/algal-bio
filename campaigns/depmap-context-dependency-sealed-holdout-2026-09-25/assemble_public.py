#!/usr/bin/env python3
"""Copy this campaign's record into the algal-bio worktree.

Excludes the DepMap release itself and every derived matrix (1.8 GB of public
data, hashes in data/depmap24q4.receipt.json and data/split.receipt.json), the
sealed holdout, the reference downloads, the virtualenv and pycache. Replaces
personal filesystem prefixes and records both hashes.

Usage: assemble_public.py <repo_worktree>
"""
import hashlib, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SLUG = "depmap-context-dependency-sealed-holdout-2026-09-25"
repo = Path(sys.argv[1]).resolve()
camp, rep = repo / "campaigns" / SLUG, repo / "reports" / SLUG

SKIP_DIRS = {"data/depmap24q4", "data/discovery", "data/sealed", "data/other",
             "data/sanger_holdout", "data/prep", "data/refs", ".venv",
             "__pycache__", ".pytest_cache"}
SKIP_FILES = {"data/figshare_24q4_files.json"}
KEEP_ANYWAY = {"data/depmap24q4.receipt.json", "data/split.receipt.json",
               "data/prep/prep.receipt.json", "data/prep/dep_genes.json",
               "data/prep/ctx_names.json", "data/prep/ctx_group.json",
               "data/prep/ctx_duplicates.json", "data/refs/refs.receipt.json"}
REPORT_PREFIXES = ("report.md", "results/", "logs/", "prior-art/", "review/")

HOME = "/" + "Users/" + "bg"
SUBS = [(HOME + "/Documents/research/", "<research-root>/"),
        (HOME + "/Documents/research", "<research-root>"),
        (HOME + "/", "<home>/"),
        ("/private/t" + "mp/", "<tmp>/"),
        ("/Use" + "rs/", "<home-prefix>/"),
        ("/ho" + "me/", "<home-root>/")]
PRIV = re.compile("/Use" + "rs/|/ho" + "me/|/private/t" + "mp")
MAX_BYTES = 4 << 20


def skip(rel):
    if rel in KEEP_ANYWAY:
        return False
    parts = rel.split("/")
    return (rel in SKIP_FILES
            or any("/".join(parts[:i]) in SKIP_DIRS for i in range(1, len(parts) + 1))
            or rel.endswith((".pyc", ".npz", ".csv.gz")))


def main():
    manifest = []
    for src in sorted(ROOT.rglob("*")):
        if not src.is_file():
            continue
        rel = str(src.relative_to(ROOT))
        if skip(rel):
            continue
        data = src.read_bytes()
        if len(data) > MAX_BYTES:
            sys.exit(f"refusing to publish a large file: {rel} ({len(data)} bytes)")
        orig = hashlib.sha256(data).hexdigest()
        try:
            txt = data.decode()
        except UnicodeDecodeError:
            sys.exit(f"binary file not expected: {rel}")
        new = txt
        for a, b in SUBS:
            new = new.replace(a, b)
        if PRIV.search(new):
            sys.exit(f"private path remains in {rel}")
        out = new.encode()
        pub_rel = "README.md" if rel == "README.campaign.md" else rel
        dst = (rep if rel.startswith(REPORT_PREFIXES) else camp) / pub_rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(out)
        manifest.append({"source": rel, "published": str(dst.relative_to(repo)),
                         "bytes": len(data), "bytes_published": len(out),
                         "sha256_original": orig,
                         "sha256_published": hashlib.sha256(out).hexdigest(),
                         "path_prefix_redacted": out != data})
    (rep / "assembly.manifest.json").parent.mkdir(parents=True, exist_ok=True)
    (rep / "assembly.manifest.json").write_text(json.dumps(
        {"schema": "bio.assembly-manifest.v2", "slug": SLUG,
         "excluded": sorted(SKIP_DIRS | SKIP_FILES),
         "note": ("frozen hashes refer to sha256_original; redaction replaces personal "
                  "path prefixes only. The DepMap 24Q4 release, the library split, the "
                  "prepared matrices and the reference downloads stay external; their "
                  "hashes are in the published receipts."),
         "files": manifest}, indent=1) + "\n")
    print(len(manifest), "files;", sum(m["path_prefix_redacted"] for m in manifest), "redacted")


if __name__ == "__main__":
    main()
