"""Assemble a campaign's public copy into a repository worktree.

    python -m bio_lab.campaign_kit.assemble_public <campaign_dir> <repo_worktree> \
        --name NAME --stage prereg|outcome [--exclude REL]... [--deny-file F]

Everything goes to campaigns/<name>/ except, at the outcome stage, report.md,
which goes to reports/<name>/report.md. The manifest (schema
bio.assembly-manifest.v2) goes to campaigns/<name>/assembly.manifest.json at
prereg and reports/<name>/assembly.manifest.json at outcome, where the lane
adds its rights list.

Skipped: data/sealed/, data/sanger_holdout/, data/discovery/ and any other
sealed/ directory are never walked (only their receipts.jsonl is published), caches, locks, known binary data formats, and
unregistered files over 4 MB; each skip is recorded with its sha256 when
readable. Personal path prefixes are scrubbed. The assembly refuses, before
writing anything, when: the freeze does not verify; a registered file (or
freeze.json) would change in scrubbing, would be skipped, or differs from a
copy already in the worktree; a symlink is present; a personal path survives
scrubbing; or, with --deny-file, the hygiene lint finds a hit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

from .common import (KitError, MAX_PUBLIC_BYTES, MINING_ENV, NAME_RE, PERSONAL_RE, die,
                     safe_relative, sha256_bytes)
from . import freeze as _freeze

SCHEMA = "bio.assembly-manifest.v2"
PRIVATE_DATA = ("data/sealed", "data/sanger_holdout", "data/discovery")
SKIP_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".ipynb_checkpoints", ".git"}
SKIP_NAMES = {".DS_Store", ".confirmation.lock"}
BINARY_DATA = (".npz", ".npy", ".gz", ".zip", ".bz2", ".xz", ".parquet", ".feather", ".h5",
               ".hdf5", ".pkl", ".pickle", ".rds", ".xlsx", ".xls", ".pyc")


class AssemblyError(KitError):
    pass


def scrub_rules(campaign_dir: Path) -> list[tuple[str, str]]:
    """Longest-first literal substitutions for the private locations of this machine."""
    rules = []
    mining = os.environ.get(MINING_ENV)
    if mining:
        rules.append((str(Path(mining).resolve()), "<mining-dir>"))
        rules.append((mining.rstrip("/"), "<mining-dir>"))
    for base in {str(campaign_dir.parent), str(campaign_dir.parent.resolve())}:
        rules.append((base, "<research-root>"))
    home = str(Path.home())
    if PERSONAL_RE.match(home + "/"):
        rules.append((home, "<home>"))
    rules = [(a, b) for a, b in rules if a and a != "/"]
    return sorted(set(rules), key=lambda r: -len(r[0]))


_GENERIC = [
    (re.compile("/" + "private" + r"/(?:tmp|var)/[^\s\"'<>)]*"), "<tmp>"),
    (re.compile("/" + "(?:Users|home)" + r"/[^/\s\"'<>)]+"), "<home>"),
]


def scrub(text: str, rules) -> str:
    for old, new in rules:
        text = text.replace(old, new)
    for pattern, new in _GENERIC:
        text = pattern.sub(new, text)
    return text


def _skip_reason(rel: str, size: int, registered: bool) -> str | None:
    parts = rel.split("/")
    if any(p in SKIP_DIRS for p in parts[:-1]) or parts[-1] in SKIP_NAMES:
        return "cache or lock"
    if registered:
        return None
    if rel.endswith(BINARY_DATA):
        return "binary data format"
    if size > MAX_PUBLIC_BYTES:
        return "over 4 MB"
    return None


def plan(campaign_dir, repo, name: str, stage: str, exclude=(), deny_file=None) -> dict:
    """Compute every write without performing one. Raises AssemblyError on any refusal."""
    campaign_dir = Path(campaign_dir).resolve()
    repo = Path(repo).resolve()
    if not NAME_RE.match(name or ""):
        raise AssemblyError("name must be a lowercase campaign name")
    if stage not in ("prereg", "outcome"):
        raise AssemblyError("stage must be prereg or outcome")
    if not (repo / ".git").exists():
        raise AssemblyError("the target is not a git worktree")
    if campaign_dir == repo or repo.is_relative_to(campaign_dir) or campaign_dir.is_relative_to(repo):
        raise AssemblyError("the campaign dir and the worktree must be separate trees")
    try:
        _freeze.verify(campaign_dir)
    except KitError as error:
        raise AssemblyError(f"freeze verify failed: {error}") from None
    manifest = json.loads((campaign_dir / _freeze.FREEZE).read_text(encoding="utf-8"))
    registered = set(manifest["sha256"]) | {_freeze.FREEZE}
    excluded = {safe_relative(e).as_posix() for e in exclude}
    for rel in excluded:
        if any(rel == r or r.startswith(rel + "/") for r in registered):
            raise AssemblyError(f"--exclude {rel} would drop a registered file")
    if stage == "prereg":
        if (campaign_dir / "report.md").exists():
            raise AssemblyError("report.md exists; a preregistration is assembled before any outcome")
        results = campaign_dir / "results"
        if results.is_dir() and any(p.name != ".confirmation.lock" for p in results.rglob("*")
                                    if p.is_file()):
            raise AssemblyError("results/ holds files; a preregistration is assembled before any outcome")
    camp, rep = repo / "campaigns" / name, repo / "reports" / name
    rules = scrub_rules(campaign_dir)
    writes, files, skipped = [], [], []
    for root, dirs, names in os.walk(campaign_dir):
        root = Path(root)
        rel_root = root.relative_to(campaign_dir).as_posix()
        for d in list(dirs):
            if (root / d).is_symlink():
                raise AssemblyError(f"symlink in the campaign dir: {(root / d).relative_to(campaign_dir)}")
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        kept = []
        for d in dirs:
            rel_d = d if rel_root == "." else f"{rel_root}/{d}"
            if rel_d in PRIVATE_DATA or d == "sealed":
                # never walked, read or hashed; only the receipts file is public
                skipped.append({"source": rel_d + "/", "reason": "private data"})
                receipts = root / d / "receipts.jsonl"
                if receipts.is_file() and not receipts.is_symlink():
                    names.append(f"{d}/receipts.jsonl")
            else:
                kept.append(d)
        dirs[:] = kept
        for fname in sorted(names):
            src = root / fname
            rel = fname if rel_root == "." else f"{rel_root}/{fname}"
            if src.is_symlink():
                raise AssemblyError(f"symlink in the campaign dir: {rel}")
            if rel in excluded or any(rel.startswith(e + "/") for e in excluded):
                skipped.append({"source": rel, "reason": "excluded by flag"})
                continue
            is_reg = rel in registered
            reason = _skip_reason(rel, src.stat().st_size, is_reg)
            if reason:
                entry = {"source": rel, "reason": reason, "bytes": src.stat().st_size}
                if reason != "cache or lock":
                    entry["sha256"] = hashlib.sha256(src.read_bytes()).hexdigest()
                skipped.append(entry)
                continue
            data = src.read_bytes()
            if len(data) > MAX_PUBLIC_BYTES:
                raise AssemblyError(f"{rel} is registered and over 4 MB")
            try:
                out = scrub(data.decode("utf-8"), rules).encode("utf-8")
            except UnicodeDecodeError:
                out = data
            if PERSONAL_RE.search(out.decode("utf-8", errors="replace")):
                raise AssemblyError(f"a personal path survives scrubbing in {rel}")
            if is_reg and out != data:
                raise AssemblyError(f"registered file {rel} would change in the public copy")
            if rel == "report.md" and stage == "outcome":
                dst = rep / "report.md"
            else:
                dst = camp / rel
            if is_reg and dst.exists() and dst.read_bytes() != data:
                raise AssemblyError(f"registered file {rel} differs from the copy already in the "
                                    "worktree")
            writes.append((dst, out))
            files.append({"source": rel, "published": dst.relative_to(repo).as_posix(),
                          "bytes": len(data), "bytes_published": len(out),
                          "sha256_original": sha256_bytes(data),
                          "sha256_published": sha256_bytes(out),
                          "path_prefix_redacted": out != data, "registered": is_reg})
    missing = sorted(registered - {f["source"] for f in files})
    if missing:
        raise AssemblyError(f"registered files would not be published: {', '.join(missing)}")
    if deny_file is not None:
        from .lint import _scan, load_deny
        patterns = load_deny(deny_file)
        for dst, out in writes:
            hits = _scan(dst.relative_to(repo).as_posix(), out, patterns)
            if hits:
                raise AssemblyError(f"hygiene: {hits[0]}")
    manifest_path = (camp if stage == "prereg" else rep) / "assembly.manifest.json"
    public_manifest = {
        "schema": SCHEMA, "slug": name, "stage": stage,
        "freeze_top_digest": manifest["top_digest"],
        "excluded": sorted(PRIVATE_DATA), "skipped": skipped,
        "note": ("Frozen hashes refer to sha256_original; registered files are published "
                 "byte-identical. Redaction replaces personal path prefixes in unregistered "
                 "files only. Sealed and discovery data stay external; their receipts are "
                 "published."),
        "files": files,
    }
    return {"writes": writes, "manifest_path": manifest_path, "manifest": public_manifest}


def assemble(campaign_dir, repo, name: str, stage: str, exclude=(), deny_file=None) -> dict:
    result = plan(campaign_dir, repo, name, stage, exclude, deny_file)
    for dst, out in result["writes"]:
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(out)
    path = result["manifest_path"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result["manifest"], indent=1) + "\n", encoding="utf-8")
    return result["manifest"]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="campaign_kit.assemble_public", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("campaign_dir")
    parser.add_argument("repo")
    parser.add_argument("--name", required=True)
    parser.add_argument("--stage", required=True, choices=("prereg", "outcome"))
    parser.add_argument("--exclude", action="append", default=[])
    parser.add_argument("--deny-file")
    args = parser.parse_args(argv)
    try:
        manifest = assemble(args.campaign_dir, args.repo, args.name, args.stage, args.exclude,
                            args.deny_file)
    except KitError as error:
        return die(error)
    print(f"{len(manifest['files'])} files; "
          f"{sum(f['path_prefix_redacted'] for f in manifest['files'])} redacted; "
          f"{len(manifest['skipped'])} skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
