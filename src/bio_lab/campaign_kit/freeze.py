"""Write-once SHA-256 freeze of a campaign's registered files, and its verification.

    python -m bio_lab.campaign_kit.freeze build <campaign_dir> [--include REL]... [--deny-file F]
    python -m bio_lab.campaign_kit.freeze verify <campaign_dir>

The manifest (registration/freeze.json) binds lane.json and every file under
registration/, code/ (including the vendored kit) and tests/, plus any
--include paths, by campaign-relative POSIX path. Relative paths make the
public copy byte-identical: the same manifest verifies both trees.

build refuses when the freeze already exists, when any file exists under
results/ or data/sealed/, when a registered file is a symlink, sits under a
sealed path, is larger than 4 MB, or contains a personal path (the public
copy of a registered file must not need scrubbing). verify refuses when any
registered file changed, went missing, or a new file appeared under a
registered root.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from . import KIT_VERSION
from .common import (KitError, MAX_PUBLIC_BYTES, PERSONAL_RE, dir_has_files, die,
                     is_sealed_path, read_json, safe_relative, sha256_bytes, sha256_file,
                     utc_now)

SCHEMA = "bio-kit-freeze/1"
FREEZE = "registration/freeze.json"
DEFAULT_ROOTS = ("lane.json", "registration", "code", "tests")
SKIP_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".ipynb_checkpoints"}
SKIP_FILES = {".DS_Store"}
SKIP_SUFFIXES = (".pyc", ".pyo")
FORBIDDEN_ROOTS = ("results", "data/sealed", "data/sanger_holdout", "data/discovery")


class FreezeError(KitError):
    pass


def top_digest(sha_map: dict[str, str]) -> str:
    lines = "".join(f"{path}\x00{sha_map[path]}\n" for path in sorted(sha_map))
    return sha256_bytes(lines.encode())


def _check_root(relative: str) -> str:
    path = safe_relative(relative)
    text = path.as_posix()
    for forbidden in FORBIDDEN_ROOTS:
        if text == forbidden or text.startswith(forbidden + "/"):
            raise FreezeError(f"{text} may not be registered: {forbidden}/ is never frozen")
    if "sealed" in path.parts:
        raise FreezeError(f"{text} may not be registered: sealed paths are never frozen")
    return text


def collect(campaign_dir: Path, roots) -> list[str]:
    """Campaign-relative paths of every registered file under the given roots."""
    files: set[str] = set()
    for relative in roots:
        text = _check_root(relative)
        path = campaign_dir / text
        if path.is_symlink():
            raise FreezeError(f"{text} is a symlink; register real files only")
        if path.is_file():
            files.add(text)
            continue
        if not path.is_dir():
            if relative in DEFAULT_ROOTS and relative != "lane.json":
                continue
            raise FreezeError(f"registered path is missing: {text}")
        for root, dirs, names in os.walk(path):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
            for d in dirs:
                if (Path(root) / d).is_symlink():
                    raise FreezeError(f"{(Path(root) / d).relative_to(campaign_dir).as_posix()} "
                                      "is a symlink; register real files only")
            for name in names:
                if name in SKIP_FILES or name.endswith(SKIP_SUFFIXES):
                    continue
                full = Path(root) / name
                rel = full.relative_to(campaign_dir).as_posix()
                if full.is_symlink():
                    raise FreezeError(f"{rel} is a symlink; register real files only")
                files.add(rel)
    files.discard(FREEZE)
    for rel in files:
        if is_sealed_path(campaign_dir / rel):
            raise FreezeError(f"{rel} is under a sealed path")
    return sorted(files)


def _publishable(campaign_dir: Path, rel: str, deny_file) -> None:
    data = (campaign_dir / rel).read_bytes()
    if len(data) > MAX_PUBLIC_BYTES:
        raise FreezeError(f"{rel} is over 4 MB; a registered file must be publishable")
    text = data.decode("utf-8", errors="replace")
    for number, line in enumerate(text.splitlines(), 1):
        if PERSONAL_RE.search(line):
            raise FreezeError(f"{rel}:{number} contains a personal path; the public copy would "
                              "differ from the registered file")
    if deny_file is not None:
        from .lint import hygiene_hits
        hits = hygiene_hits([campaign_dir / rel], deny_file=deny_file, root=campaign_dir)
        if hits:
            raise FreezeError(f"{hits[0]}; fix it before freezing")


def build(campaign_dir: os.PathLike | str, include=(), *, deny_file=None) -> tuple[dict, str]:
    """Write registration/freeze.json once. Returns (manifest, sha256 of its bytes)."""
    campaign_dir = Path(campaign_dir).resolve()
    freeze_path = campaign_dir / FREEZE
    if freeze_path.exists():
        raise FreezeError("registration/freeze.json already exists; the freeze is write-once "
                          "(use verify)")
    if dir_has_files(campaign_dir / "results"):
        raise FreezeError("results/ already holds files; a freeze must come before any result")
    if dir_has_files(campaign_dir / "data" / "sealed"):
        raise FreezeError("data/sealed/ already holds files; nothing may be fetched before the freeze")
    lane = read_json(campaign_dir / "lane.json", "lane.json")
    if not isinstance(lane.get("id"), str) or not lane["id"]:
        raise FreezeError("lane.json has no lane id")
    if not (campaign_dir / "registration" / "protocol.json").is_file():
        raise FreezeError("registration/protocol.json is missing")
    declared = sorted(set(DEFAULT_ROOTS) | {_check_root(r) for r in include})
    files = collect(campaign_dir, declared)
    for rel in files:
        _publishable(campaign_dir, rel, deny_file)
    shas = {rel: sha256_file(campaign_dir / rel) for rel in files}
    sizes = {rel: (campaign_dir / rel).stat().st_size for rel in files}
    manifest = {
        "schema": SCHEMA,
        "kit_version": KIT_VERSION,
        "lane_id": lane["id"],
        "frozen_utc": utc_now(),
        "declared": declared,
        "file_count": len(files),
        "sha256": shas,
        "bytes": sizes,
        "top_digest": top_digest(shas),
        "python": ".".join(map(str, sys.version_info[:3])),
        "meaning": ("Every listed file was fixed before any holdout value was read. "
                    "Paths are campaign-relative, so this manifest verifies the private "
                    "and the public copy alike."),
    }
    data = (json.dumps(manifest, indent=1, sort_keys=True) + "\n").encode()
    freeze_path.parent.mkdir(parents=True, exist_ok=True)
    with open(freeze_path, "xb") as handle:          # exclusive create: write-once
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    return manifest, sha256_bytes(data)


def freeze_sha256(campaign_dir: os.PathLike | str) -> str:
    path = Path(campaign_dir) / FREEZE
    if not path.is_file():
        raise FreezeError("registration/freeze.json does not exist; freeze first")
    return sha256_file(path)


def verify(campaign_dir: os.PathLike | str) -> dict:
    """Recompute every registered hash. Returns a summary or raises FreezeError."""
    campaign_dir = Path(campaign_dir).resolve()
    manifest = read_json(campaign_dir / FREEZE, "registration/freeze.json")
    if manifest.get("schema") != SCHEMA:
        raise FreezeError("registration/freeze.json is not a kit freeze manifest")
    shas = manifest.get("sha256")
    declared = manifest.get("declared")
    if not isinstance(shas, dict) or not shas or not isinstance(declared, list):
        raise FreezeError("registration/freeze.json lacks its file list")
    if top_digest(shas) != manifest.get("top_digest") or manifest.get("file_count") != len(shas):
        raise FreezeError("registration/freeze.json does not match its own top digest")
    changed, missing = [], []
    for rel, want in sorted(shas.items()):
        safe_relative(rel)
        path = campaign_dir / rel
        if path.is_symlink() or not path.is_file():
            missing.append(rel)
        elif sha256_file(path) != want:
            changed.append(rel)
    try:
        present = collect(campaign_dir, declared)
    except FreezeError as error:
        raise FreezeError(f"registered roots no longer collect cleanly: {error}") from None
    added = sorted(set(present) - set(shas))
    if changed or missing or added:
        parts = []
        for label, items in (("changed", changed), ("missing", missing), ("added", added)):
            if items:
                parts.append(f"{label}: {', '.join(items)}")
        raise FreezeError("registered files differ from the freeze; " + "; ".join(parts))
    return {"ok": True, "files": len(shas), "top_digest": manifest["top_digest"],
            "freeze_sha256": freeze_sha256(campaign_dir), "lane_id": manifest.get("lane_id")}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="campaign_kit.freeze", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=("build", "verify"))
    parser.add_argument("campaign_dir")
    parser.add_argument("--include", action="append", default=[],
                        help="extra campaign-relative file or directory to register")
    parser.add_argument("--deny-file", help="private name deny list for the hygiene check")
    args = parser.parse_args(argv)
    try:
        if args.action == "build":
            manifest, digest = build(args.campaign_dir, args.include, deny_file=args.deny_file)
            print(json.dumps({"frozen_utc": manifest["frozen_utc"], "files": manifest["file_count"],
                              "top_digest": manifest["top_digest"], "freeze_sha256": digest},
                             indent=1))
        else:
            print(json.dumps(verify(args.campaign_dir), indent=1))
    except KitError as error:
        return die(error)
    return 0


if __name__ == "__main__":
    sys.exit(main())
