#!/usr/bin/env python3
"""Copy this campaign's record into the algal-bio worktree.

The DepMap release, derived matrices, the sealed holdout and the reference
downloads stay external - their hashes are in the published receipts. Personal
filesystem prefixes are redacted and both hashes are recorded.

Usage: assemble_public.py <repo_worktree>
"""
import hashlib, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SLUG = "paralog-sl-doubleko-2026-09-25"
repo = Path(sys.argv[1]).resolve()
camp, rep = repo / "campaigns" / SLUG, repo / "reports" / SLUG

SKIP_DIRS = {"data/discovery", "data/sealed", "data/prep", "data/refs",
             "data/depmap24q4", "__pycache__", ".pytest_cache"}
KEEP_ANYWAY = {"data/prep/prep.receipt.json", "data/prep/pair_universe.csv",
               "data/prep/ctx_group.json", "data/prep/ky_pos.json",
               "data/prep/lof_gene_models.json",
               "data/refs/depmap-refs.receipt.json"}
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
    return (any("/".join(parts[:i]) in SKIP_DIRS for i in range(1, len(parts) + 1))
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
         "excluded": sorted(SKIP_DIRS),
         "note": ("frozen hashes refer to sha256_original; redaction replaces personal "
                  "path prefixes only. The DepMap 24Q4 release, the prepared matrices, "
                  "the sealed holdout tables and the reference downloads stay external; "
                  "their hashes are in the published receipts."),
         "files": manifest}, indent=1) + "\n")
    print(len(manifest), "files;", sum(m["path_prefix_redacted"] for m in manifest), "redacted")


if __name__ == "__main__":
    main()
