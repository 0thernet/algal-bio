#!/usr/bin/env python3
"""Copy the wide-screen campaign record into the algal-bio worktree.
Excludes raw and reference data (hashes in intake receipts and manifests) and pycache.
Replaces personal filesystem prefixes with <research-root>/ or <home>/ and records both
hashes. Usage: assemble_public.py <repo_worktree>"""
import hashlib, json, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
SLUG = "wide-screen-lamina-compartment-expression-2026-09-24"
repo = Path(sys.argv[1]).resolve()
camp, rep = repo / "campaigns" / SLUG, repo / "reports" / SLUG
SKIP_DIRS = {"data", "panel/data", "damid/data", "__pycache__"}
SKIP_FILES = {"features/tiles.base.tsv"}
REPORT_PREFIXES = ("report.md", "results/", "design/", "logs/", "control/result.json", "control/robust_explore.json", "panel/results/", "damid/results/")
HOME = "/" + "Users/" + "bg"
SUBS = [(HOME + "/Documents/research/", "<research-root>/"), (HOME + "/", "<home>/"), ("/private/t" + "mp/", "<tmp>/")]
PRIV = re.compile("/Use" + "rs/|/ho" + "me/|/private/t" + "mp")
def skip(rel):
    parts = rel.split("/")
    return rel in SKIP_FILES or any("/".join(parts[:i]) in SKIP_DIRS for i in range(1, len(parts))) or rel.endswith(".pyc")
manifest = []
for src in sorted(ROOT.rglob("*")):
    if not src.is_file(): continue
    rel = str(src.relative_to(ROOT))
    if skip(rel): continue
    data = src.read_bytes(); orig = hashlib.sha256(data).hexdigest()
    out = data; redacted = False
    try:
        txt = data.decode()
        new = txt
        for a, b in SUBS: new = new.replace(a, b)
        if new != txt: out = new.encode(); redacted = True
        if PRIV.search(new): sys.exit(f"private path remains in {rel}")
    except UnicodeDecodeError:
        sys.exit(f"binary file not expected: {rel}")
    dst = (rep if rel.startswith(REPORT_PREFIXES) else camp) / rel
    dst.parent.mkdir(parents=True, exist_ok=True); dst.write_bytes(out)
    manifest.append({"source": rel, "published": str(dst.relative_to(repo)), "bytes": len(data), "sha256_original": orig,
                     "sha256_published": hashlib.sha256(out).hexdigest(), "path_prefix_redacted": redacted})
(rep / "assembly.manifest.json").write_text(json.dumps({"schema": "bio.assembly-manifest.v2", "slug": SLUG,
    "excluded": sorted(SKIP_DIRS | SKIP_FILES), "note": "frozen hashes refer to sha256_original; redaction replaces personal path prefixes only",
    "files": manifest}, indent=1) + "\n")
print(len(manifest), "files;", sum(m["path_prefix_redacted"] for m in manifest), "redacted")
