#!/usr/bin/env python3
"""Offline foundation checks; hashes attest retention, never scientific truth."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "a712fbec69bd03b10c20d8078b478c38734d9c02"
LEGACY_MANIFEST = Path("tests/fixtures/legacy/manifest.json")
FOUNDATION_FIXTURE = Path("tests/foundation/fixtures/artifact.json")
LEGACY_FILE_COUNT = 1742
LEGACY_RECEIPT_COUNT = 289


class RepositoryError(ValueError):
    """A checked invariant was not satisfied."""


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RepositoryError(f"Expected a JSON object: {path}")
    return value


def safe_artifact_path(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative:
        raise RepositoryError("Artifact paths must be nonempty strings")
    path = PurePosixPath(relative)
    if path.is_absolute() or ".." in path.parts or str(path) != relative:
        raise RepositoryError(f"Noncanonical artifact path: {relative!r}")
    resolved = root.joinpath(*path.parts).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise RepositoryError(f"Artifact escaped repository: {relative!r}")
    return resolved


def verify_artifact(root: Path, entry: dict) -> bytes:
    if set(entry) != {"path", "sha256", "bytes", "kind"}:
        raise RepositoryError("Unexpected retained-artifact fields")
    path = safe_artifact_path(root, entry["path"])
    if not path.is_file():
        raise RepositoryError(f"Missing retained artifact: {entry['path']}")
    data = path.read_bytes()
    if len(data) != entry["bytes"] or hashlib.sha256(data).hexdigest() != entry["sha256"]:
        raise RepositoryError(f"Changed retained artifact: {entry['path']}")
    return data


def verify_legacy(root: Path = ROOT) -> dict:
    manifest = read_json(root / LEGACY_MANIFEST)
    if manifest.get("schema") != "algal-bio.legacy-retention.v1":
        raise RepositoryError("Unsupported legacy manifest schema")
    if manifest.get("baseline_git_commit") != BASELINE:
        raise RepositoryError("Legacy baseline changed; historical review required")
    entries = manifest.get("artifacts", [])
    if len(entries) != LEGACY_FILE_COUNT:
        raise RepositoryError(f"Expected {LEGACY_FILE_COUNT} retained legacy files")
    paths = [entry["path"] for entry in entries]
    if paths != sorted(set(paths)):
        raise RepositoryError("Legacy artifact paths must be sorted and unique")
    receipts = set()
    total_bytes = 0
    for entry in entries:
        data = verify_artifact(root, entry)
        total_bytes += len(data)
        if entry["kind"] == "native-algal-run":
            receipt = json.loads(data)
            if receipt.get("contract") != "algal.run.v1":
                raise RepositoryError(f"Unexpected receipt contract: {entry['path']}")
            receipts.add(entry["path"])
    if len(receipts) != LEGACY_RECEIPT_COUNT:
        raise RepositoryError(f"Expected {LEGACY_RECEIPT_COUNT} retained native receipts")
    observed_receipts = {
        path.relative_to(root).as_posix() for path in root.glob(".algal*/runs/*.json")
    }
    if receipts != observed_receipts:
        raise RepositoryError("Native receipt set changed; retain history and use runs/ for new work")
    return {"artifacts": len(entries), "native_receipts": len(receipts), "bytes": total_bytes}


def verify_public_paths(root: Path = ROOT) -> str:
    """Reject prohibited Git paths, without pretending to be a secret scanner."""
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode or Path(result.stdout.strip()).resolve() != root.resolve():
        return "not checked: source archive has no repository index"
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        capture_output=True, text=True, check=True,
    )
    prohibited = []
    for name in result.stdout.split("\0"):
        if not name:
            continue
        path = PurePosixPath(name)
        secret_name = path.name == ".env" or (
            path.name.startswith(".env.") and path.name != ".env.example"
        )
        transient = path.parts[0] in {"runs", "artifacts", "downloads", "coverage"}
        local_dependency = bool({"node_modules", ".venv", ".cache"} & set(path.parts))
        if secret_name or path.suffix in {".pem", ".key"} or transient or local_dependency:
            prohibited.append(name)
    if prohibited:
        raise RepositoryError("Prohibited tracked paths: " + ", ".join(prohibited))
    return "passed (tracked paths only; not a content secret scan)"


def verify_environment(root: Path = ROOT) -> dict:
    project = tomllib.loads((root / "pyproject.toml").read_text())
    package = read_json(root / "package.json")
    python_pin = (root / ".python-version").read_text().strip()
    if sys.version_info < (3, 12):
        raise RepositoryError("Python 3.12 or newer is required")
    if project["project"]["requires-python"] != ">=3.12":
        raise RepositoryError("Review the documented Python compatibility before changing it")
    if package.get("packageManager") != "bun@1.3.14":
        raise RepositoryError("Bun package manager identity changed")
    bun = subprocess.run(["bun", "--version"], capture_output=True, text=True, check=True)
    if bun.stdout.strip() != "1.3.14":
        raise RepositoryError("Use the pinned Bun 1.3.14 toolchain")
    for name in ("uv.lock", "bun.lock"):
        if not (root / name).is_file():
            raise RepositoryError(f"Missing dependency lock: {name}")
    for section in ("dependencies", "devDependencies", "optionalDependencies"):
        for name, version in package.get(section, {}).items():
            if version.startswith(("file:", "link:", "../", "/")):
                raise RepositoryError(f"Nonportable package dependency: {name}")
    return {"python": ".".join(map(str, sys.version_info[:3])), "reference_python": python_pin,
            "bun": bun.stdout.strip()}


def reproduce_fixture(root: Path = ROOT) -> dict:
    fixture = read_json(root / FOUNDATION_FIXTURE)
    if set(fixture) != {"schema", "license", "source", "expected"}:
        raise RepositoryError("Unexpected foundation fixture fields")
    if fixture["schema"] != "algal-bio.portability-fixture.v1" or fixture["license"] != "MIT":
        raise RepositoryError("Unexpected fixture identity or license")
    source = fixture["source"]
    if not isinstance(source, str):
        raise RepositoryError("Fixture source must be UTF-8 text")
    encoded = source.encode("utf-8")
    actual = {"sha256": hashlib.sha256(encoded).hexdigest(), "bytes": len(encoded)}
    if fixture["expected"] != actual:
        raise RepositoryError("Foundation fixture did not reproduce its expected artifact identity")
    return {"fixture": fixture["schema"], **actual, "scope": "synthetic artifact identity only"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reproduce-fixture", action="store_true")
    args = parser.parse_args()
    try:
        if args.reproduce_fixture:
            report = reproduce_fixture()
        else:
            report = {"environment": verify_environment(), "legacy": verify_legacy(),
                      "tracked_path_policy": verify_public_paths(), "fixture": reproduce_fixture()}
        print(json.dumps(report, sort_keys=True, indent=2))
        return 0
    except (RepositoryError, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print(f"Repository check failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
