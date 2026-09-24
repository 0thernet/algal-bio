#!/usr/bin/env python3
"""Build/verify an explicit public calibration selection; never walk the repository.

Hash admission is separate from CI, clean-checkout reproduction, source rights
review, and published-asset verification. Publication identity is a separate
operator record. The content checks below are bounded heuristics, not a complete
secret scanner or a license determination.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.check_registration import check_registration  # noqa: E402
from scripts.evaluate_candidates import readiness  # noqa: E402

SELECTION_KEYS = {"contract", "release_id", "scope", "scientific_status", "prospective_status", "review_status", "artifacts"}
ENTRY_KEYS = {"path", "role", "rights"}
RIGHTS_KEYS = {"basis", "license", "attribution", "sources", "redistribution"}
ROLES = {"source", "protocol", "fixture", "report", "documentation", "environment", "test"}
RIGHTS = {
    "project_mit": "MIT", "public_molecular_metadata": "NCBI-molecular-data-policy",
    "public_molecular_measurement": "NCBI-molecular-data-policy", "factual_source_inventory": "facts-only",
}
DENIED_ROOTS = {".git", ".cache", ".venv", "node_modules", "runs", "downloads", "artifacts", "out", "codebase", "facts", "rules"}
ALLOWED_SUFFIXES = {".md", ".json", ".py", ".ts", ".toml", ".lock", ".cff", ".yml", ".yaml", ".tsv", ".bedgraph", ".txt"}
SPECIAL_FILES = {"LICENSE", "Makefile", ".python-version", ".gitignore"}
STUDY = "campaigns/lamina-context-pilot/registration.json"
QUALIFICATION = "campaigns/qualification/registration.json"
PROSPECTIVE = "campaigns/prospective-001/registration.json"
DECISION = "reports/prospective-001/decision.json"
FULL_RNA = "reports/calibration/full-rna-filter.json"
EXPECTED = "tests/fixtures/bio/expected.json"
QUALIFICATION_REPORT = "reports/qualification/offline.json"
REQUIRED = {
    "LICENSE", "CITATION.cff", "Makefile", ".python-version", "package.json", "bun.lock", "pyproject.toml", "uv.lock", "tsconfig.json",
    "docs/study-report.md", "docs/contributions.md", STUDY, QUALIFICATION, PROSPECTIVE, DECISION, FULL_RNA, EXPECTED,
    "scripts/check_release.py", "scripts/check_registration.py", "scripts/reproduce_bio_fixture.py",
    "scripts/qualify_campaign.py", "scripts/run_bio_qualification.ts", "scripts/evaluate_candidates.py",
    "scripts/calibrate_public_data.py", "src/bio_lab/measurements.py", "src/bio_lab/instrument.ts", "src/bio_lab/qualification.ts",
    "schemas/bio-study.schema.json", "schemas/candidate.schema.json", "campaigns/lamina-context-pilot/freeze.json",
    "scripts/check_repository.py", "tests/foundation/fixtures/artifact.json",
}
CONTENT_PATTERNS = [
    re.compile(r"(?<![A-Za-z0-9:.])/(?:Users|home)/[A-Za-z0-9._-]+/"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{24,}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]
MAX_ARTIFACT_BYTES = 2 * 1024 * 1024
MAX_SELECTION_BYTES = 32 * 1024 * 1024
MAX_SELECTED_ARTIFACTS = 256


class ReleaseError(ValueError):
    """Selected bytes or release claims fail public admission."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReleaseError(message)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def keys(value: dict, expected: set[str], label: str) -> None:
    require(isinstance(value, dict) and set(value) == expected, f"Unexpected {label} fields")


def bounded_bytes(path: Path) -> bytes:
    require(path.stat().st_size <= MAX_ARTIFACT_BYTES, f"Unbounded artifact not admitted: {path.name}")
    with path.open("rb") as stream:
        payload = stream.read(MAX_ARTIFACT_BYTES + 1)
    require(len(payload) <= MAX_ARTIFACT_BYTES, f"Artifact grew beyond byte limit: {path.name}")
    return payload


def unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        require(key not in result, f"Duplicate JSON field: {key}")
        result[key] = value
    return result


def decode_json(text: str) -> dict:
    def invalid_constant(value: str):
        raise ReleaseError(f"Nonfinite JSON value: {value}")
    value = json.loads(text, object_pairs_hook=unique_object, parse_constant=invalid_constant)
    require(isinstance(value, dict), "Release inputs must be JSON objects")
    return value


def read_json(path: Path) -> dict:
    return decode_json(bounded_bytes(path).decode("utf-8"))


def control_path(root: Path, release_directory: Path, filename: str) -> Path:
    try:
        relative = (release_directory.absolute() / filename).relative_to(root.absolute()).as_posix()
    except ValueError as exc:
        raise ReleaseError("Release controls must remain inside the repository") from exc
    path = selected_path(root, relative)
    scan_public_text(bounded_bytes(path), relative)
    return path


def selected_path(root: Path, relative: str) -> Path:
    require(isinstance(relative, str) and bool(relative), "Selected path must be a nonempty string")
    path = PurePosixPath(relative)
    require(bool(path.parts) and not path.is_absolute() and str(path) == relative and ".." not in path.parts
            and "\\" not in relative and all(part not in {".git", ".env"} for part in path.parts), "Nonportable selected path")
    require(path.parts[0] not in DENIED_ROOTS and not path.parts[0].startswith(".algal"), "Historical/transient/private roots are not public calibration assets")
    require(not any(part.startswith(".env") for part in path.parts), "Environment/credential files are forbidden")
    require(path.suffix in ALLOWED_SUFFIXES or relative in SPECIAL_FILES, "Unreviewed file type")
    current = root
    for part in path.parts:
        current = current / part
        require(not current.is_symlink(), f"Symlink in selected path: {relative}")
    require(current.resolve().is_relative_to(root.resolve()), "Selected path escapes repository")
    require(current.is_file(), f"Missing selected artifact: {relative}")
    return current


def scan_public_text(payload: bytes, name: str) -> None:
    require(len(payload) <= MAX_ARTIFACT_BYTES, f"Unbounded/binary artifact not admitted: {name}")
    try:
        text = payload.decode("utf-8")
    except UnicodeError as exc:
        raise ReleaseError(f"Selected artifact must be UTF-8 text: {name}") from exc
    require("\x00" not in text, f"Binary content not admitted: {name}")
    for pattern in CONTENT_PATTERNS:
        require(pattern.search(text) is None, f"Potential private path/credential in selected artifact: {name}")


def check_selection(selection: dict, root: Path) -> list[dict]:
    keys(selection, SELECTION_KEYS, "release selection")
    require(selection["contract"] == "bio.release-selection.v1", "Unsupported selection contract")
    require(selection["release_id"] == "public-calibration-v1", "Unsupported release identity")
    require(selection["scope"] == "software_and_public_calibration", "Selection cannot claim a prospective study")
    require(selection["scientific_status"] == "data_limited" and selection["prospective_status"] == "not_run", "Unsupported scientific release status")
    require(selection["review_status"] in {"explicit_selection_pending_independent_review", "independently_reviewed"}, "Explicit rights selection review required")
    require(isinstance(selection["artifacts"], list) and 0 < len(selection["artifacts"]) <= MAX_SELECTED_ARTIFACTS, "Empty or unbounded explicit artifact selection")
    paths = []
    for entry in selection["artifacts"]:
        keys(entry, ENTRY_KEYS, "selection entry")
        require(entry["role"] in ROLES, "Unknown artifact role")
        path = entry["path"]
        selected_path(root, path)
        require(path not in {"reports/release/manifest.json", "reports/release/selection.json", "reports/release/publication.json"}, "Control manifests are bound separately")
        rights = entry["rights"]
        keys(rights, RIGHTS_KEYS, "rights")
        require(rights["basis"] in RIGHTS and rights["license"] == RIGHTS[rights["basis"]], "Unsupported or missing rights basis")
        require(isinstance(rights["attribution"], str) and bool(rights["attribution"].strip()), "Missing source attribution")
        require(rights["redistribution"] == "admitted", "Redistribution has not been admitted")
        require(isinstance(rights["sources"], list) and bool(rights["sources"])
                and all(isinstance(url, str) and re.fullmatch(r"https://[^\s]+", url) for url in rights["sources"]), "Source URLs required for each rights decision")
        if path.startswith(("campaigns/lamina-context-pilot/metadata/", "datasets/manifests/")):
            require(rights["basis"] == "public_molecular_metadata", "Molecular source metadata cannot be relicensed as project software")
        if path in {"tests/fixtures/bio/rna-counts.tsv", "tests/fixtures/bio/cscore-plus.bedgraph", "tests/fixtures/bio/cscore-minus.bedgraph"}:
            require(rights["basis"] == "public_molecular_measurement", "Biological measurements retain their source rights")
        paths.append(path)
    require(len(set(paths)) == len(paths), "Duplicate selected artifact")
    require(REQUIRED <= set(paths), f"Required reproducibility assets missing: {sorted(REQUIRED - set(paths))}")
    require(paths == sorted(paths), "Explicit selection must be sorted for review")
    return selection["artifacts"]


def scientific_evidence(root: Path, paths: set[str]) -> dict:
    check_registration(root / "campaigns/lamina-context-pilot", root=root)
    plan = read_json(root / STUDY)
    qualification = read_json(root / QUALIFICATION)
    prospective = read_json(root / PROSPECTIVE)
    decision = read_json(root / DECISION)
    full = read_json(root / FULL_RNA)
    expected = read_json(root / EXPECTED)
    provenance = read_json(root / "tests/fixtures/bio/rna-provenance.json")
    supporting = {plan["author_code"]["audit_artifact"]["path"], plan["qualification_fixture"]["expected"]["path"]}
    supporting.update(item["path"] for item in plan["qualification_fixture"]["inputs"])
    for item in plan["dataset_manifests"]:
        supporting.add(item["path"])
        supporting.add(read_json(root / item["path"])["projection"]["path"])
    require(supporting <= paths, "Selection omits a registration/provenance dependency")
    require(qualification["contract"] == "bio.offline-qualification.v1" and qualification["prospective_decision"] == "no_go"
            and qualification["live_agent_comparison"]["status"] == "not_run"
            and qualification["cost"]["external_spend_micros"] == 0, "Qualification cannot imply a live or prospective experiment")
    require(qualification["expected"] == expected and qualification["repetitions"] == [0, 1, 2], "Qualification controls disagree with frozen fixture")
    require(prospective["source_registration_sha256"] == sha((root / STUDY).read_bytes())
            and prospective["status"] == "not_run" and prospective["decision"] == "no_go"
            and prospective["candidate_selection"] == "not_performed" and prospective["holdout_opened"] is False,
            "Prospective research was not admitted")
    require(decision["registration_sha256"] == sha((root / PROSPECTIVE).read_bytes())
            and decision["status"] == "not_run" and decision["decision"] == "no_go"
            and type(decision["candidates_assessed"]) is int and decision["candidates_assessed"] == 0
            and decision["holdout_opened"] is False and decision["reasons"] == prospective["missing"], "Prospective decision/report mismatch")
    require(decision == readiness(root / "campaigns/prospective-001", root=root), "Prospective decision/report differs from the reviewed readiness gate")
    require(plan["decision"]["status"] == "data_limited", "Release claim exceeds admitted biology")
    require(full["contract"] == "bio.public-calibration.v1" and full["source_url"] == provenance["url"]
            and full["source_sha256"] == provenance["compressed_sha256"]
            and full["source_rows"] == provenance["source_rows"] == 55335
            and full["libraries"] == len(provenance["library_totals"]) == 8
            and full["passing_genes"] == 16336
            and full["passing_gene_ids_sha256"] == "3efe2108f20e91ccbc6bf37b024880030d6b20a72fc26f41d256d48ce3971c70"
            and full["method"] == "raw CPM > 0.26 in at least 4 libraries; before TMM"
            and full["independent_arithmetic"] == "passed"
            and full["fixture_projection"] == "verified against full source"
            and full["scientific_status"] == "preprocessing calibration; no new biological finding or differential expression",
            "Full-input report does not support the calibrated release claim")
    result = {"study_registration_sha256": sha((root / STUDY).read_bytes()),
              "qualification_registration_sha256": sha((root / QUALIFICATION).read_bytes()),
              "prospective_registration_sha256": sha((root / PROSPECTIVE).read_bytes()),
              "full_rna_report_sha256": sha((root / FULL_RNA).read_bytes()),
              "fixture_expectations_sha256": sha((root / EXPECTED).read_bytes()),
              "qualification_summary": "pending_final_run", "qualification_report_sha256": None,
              "receipt_verification": "external_verified_bundle_required"}
    if QUALIFICATION_REPORT in paths:
        report = read_json(root / QUALIFICATION_REPORT)
        require(report["contract"] == "bio.qualification-report.v1" and report["status"] == "offline_passed"
                and report["prospectiveDecision"] == "no_go" and report["liveAgentComparison"] == "not_run"
                and report["independentBiologicalHoldout"] == "not_available" and report["externalSpendMicros"] == 0
                and len(report["repetitions"]) == 3, "Offline qualification summary has unsupported status")
        for i, row in enumerate(report["repetitions"]):
            require(row["repetition"] == i and row["scriptedProposalCalls"] == 3 and row["providerCalls"] == 0
                    and row["controlValues"] == expected and row["successfulControls"] == 1
                    and row["failedMeasurements"] == 1 and row["rejectedProposals"] == 1
                    and row["selected"] == ["known-control"] and row["receiptReplay"] is True
                    and row["freshComputation"] == "passed", "Qualification summary/control mismatch")
        result["qualification_summary"] = "recorded_offline_pass_receipts_external"
        result["qualification_report_sha256"] = sha((root / QUALIFICATION_REPORT).read_bytes())
    return result


def runtime_identity(root: Path) -> dict:
    package = read_json(root / "package.json")
    dependencies = {**package.get("dependencies", {}), **package.get("devDependencies", {})}
    lab = dependencies.get("@hraness/algal-lab")
    algal = dependencies.get("@hraness/algal")
    # Bun's text lock uses JSON with comments/trailing commas. Match string
    # tokens first so commas/comment markers inside dependency strings survive.
    lock_text = bounded_bytes(root / "bun.lock").decode("utf-8")
    token = re.compile(r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*[\s\S]*?\*/|,\s*(?=[}\]])')
    lock = decode_json(token.sub(lambda match: match[0] if match[0].startswith('"') else " ", lock_text))
    require(isinstance(lock.get("workspaces", {}), dict) and isinstance(lock.get("packages", {}), dict), "Invalid runtime lock structure")
    workspace = lock.get("workspaces", {}).get("", {})
    require(isinstance(workspace, dict) and isinstance(workspace.get("dependencies", {}), dict)
            and isinstance(workspace.get("devDependencies", {}), dict), "Invalid runtime workspace lock")
    locked_dependencies = {**workspace.get("dependencies", {}), **workspace.get("devDependencies", {})}
    packages = lock.get("packages", {})
    def locked(name: str, pin: str) -> bool:
        if locked_dependencies.get(name) != pin:
            return False
        record = packages.get(name)
        if not isinstance(record, list) or len(record) != 4 or not isinstance(record[0], str):
            return False
        match = re.fullmatch(re.escape(f"{name}@{pin.split('#')[0]}#") + r"([a-f0-9]{7,40})", record[0])
        return bool(match and pin.split("#")[1].startswith(match[1]) and isinstance(record[1], dict)
                    and record[2] == name.removeprefix("@").replace("/", "-") + "-" + match[1]
                    and isinstance(record[3], str) and re.fullmatch(r"sha512-[A-Za-z0-9+/]{86}==", record[3]))
    pinned = bool(isinstance(lab, str) and re.fullmatch(r"github:hraness/algal-lab#[a-f0-9]{40}", lab)
                  and isinstance(algal, str) and re.fullmatch(r"github:hraness/algal#[a-f0-9]{40}", algal)
                  and locked("@hraness/algal-lab", lab) and locked("@hraness/algal", algal)
                  and isinstance(packages["@hraness/algal-lab"][1].get("dependencies"), dict)
                  and packages["@hraness/algal-lab"][1]["dependencies"].get("@hraness/algal") == algal)
    return {"algal_lab": lab, "algal": algal, "immutable_runtime_pins": pinned,
            "environment_sha256": {name: sha(bounded_bytes(root / name)) for name in ("package.json", "bun.lock", "pyproject.toml", "uv.lock", "tsconfig.json")}}


def build_manifest(root: Path, release_directory: Path) -> dict:
    selection_path = control_path(root, release_directory, "selection.json")
    selection = read_json(selection_path)
    entries = check_selection(selection, root)
    artifacts = []
    for entry in entries:
        payload = bounded_bytes(selected_path(root, entry["path"]))
        scan_public_text(payload, entry["path"])
        artifacts.append({**entry, "sha256": sha(payload), "bytes": len(payload)})
    require(sum(item["bytes"] for item in artifacts) <= MAX_SELECTION_BYTES, "Selected archive exceeds total byte bound")
    return {"contract": "bio.calibration-release.v1", "release_id": selection["release_id"],
            "scope": selection["scope"], "scientific_status": "data_limited", "prospective_status": "not_run",
            "selection_sha256": sha(selection_path.read_bytes()), "artifact_count": len(artifacts),
            "total_bytes": sum(item["bytes"] for item in artifacts), "artifacts": artifacts,
            "source_evidence": scientific_evidence(root, {item["path"] for item in artifacts}),
            "runtime": runtime_identity(root)}


def publication_identity(release_directory: Path, root: Path | None = None) -> dict:
    path = release_directory / "publication.json"
    require(not path.is_symlink(), "Publication file cannot be a symlink")
    if not path.exists():
        return {"status": "not_recorded", "verification": "not_recorded"}
    if root is not None:
        path = control_path(root, release_directory, "publication.json")
    scan_public_text(bounded_bytes(path), "publication.json")
    record = read_json(path)
    fields = {"contract", "status", "source_revision", "tag", "release_url", "selected_archive_sha256", "qualification_archive_sha256", "verification"}
    keys(record, fields, "publication record")
    require(record["contract"] == "bio.publication-identity.v1", "Unsupported publication record")
    if record["status"] == "pending":
        require(record["verification"] == "pending" and all(record[k] is None for k in fields - {"contract", "status", "verification"}), "Pending publication cannot invent completed identity")
    else:
        require(record["status"] == "published" and record["verification"] == "operator_verified", "Publication verification must be recorded separately")
        for field, length in (("source_revision", 40), ("selected_archive_sha256", 64), ("qualification_archive_sha256", 64)):
            require(isinstance(record[field], str) and re.fullmatch(rf"[a-f0-9]{{{length}}}", record[field]), "Published source/asset identity missing")
        require(isinstance(record["tag"], str) and re.fullmatch(r"[A-Za-z0-9._-]+", record["tag"]), "Invalid release tag")
        require(record["release_url"] == f"https://github.com/0thernet/algal-bio/releases/tag/{record['tag']}", "Publication target mismatch")
    return record


def check_release(root: Path, release_directory: Path) -> dict:
    manifest_path = control_path(root, release_directory, "manifest.json")
    expected = build_manifest(root, release_directory)
    require(read_json(manifest_path) == expected, "Selected artifact bytes, rights, runtime, or evidence changed; review before rebuilding the manifest")
    publication = publication_identity(release_directory, root)
    return {"artifact_admission": "passed", "release_id": expected["release_id"], "selected_artifacts": expected["artifact_count"],
            "scientific_status": "data_limited", "prospective_status": "not_run",
            "qualification_summary": expected["source_evidence"]["qualification_summary"],
            "immutable_runtime_pins": expected["runtime"]["immutable_runtime_pins"],
            "selection_review": read_json(release_directory / "selection.json")["review_status"],
            "publication_status": publication["status"], "publication_verification": publication["verification"],
            "limits": "Local artifact checks do not perform independent review, CI, full-source computation, receipt replay, or remote publication verification."}


def write_archive(root: Path, release_directory: Path, output: Path) -> dict:
    report = check_release(root, release_directory)
    require(report["immutable_runtime_pins"], "Archive requires admitted immutable runtime pins")
    require(report["qualification_summary"] == "recorded_offline_pass_receipts_external", "Archive requires the final offline qualification summary")
    require(report["selection_review"] == "independently_reviewed", "Archive requires independent selection review")
    manifest = read_json(release_directory / "manifest.json")
    # Snapshot only selected bytes and its control manifests. Post-publication
    # identity remains an external operator record to avoid self-hashing assets.
    files = [(item["path"], item["sha256"], item["bytes"]) for item in manifest["artifacts"]]
    for filename in ("selection.json", "manifest.json"):
        path = release_directory / filename
        relative = path.relative_to(root).as_posix()
        payload = bounded_bytes(path)
        files.append((relative, sha(payload), len(payload)))
    require(not output.is_symlink() and not output.exists(), "Never overwrite an existing release asset")
    try:
        with output.open("xb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as zipped:
            with tarfile.open(fileobj=zipped, mode="w", format=tarfile.USTAR_FORMAT) as archive:
                for relative, expected_hash, expected_bytes in sorted(files):
                    payload = bounded_bytes(selected_path(root, relative))
                    require(sha(payload) == expected_hash and len(payload) == expected_bytes, "Artifact changed while creating archive")
                    info = tarfile.TarInfo("algal-bio-calibration/" + relative)
                    info.size = len(payload)
                    info.mode = 0o644
                    info.uid = info.gid = info.mtime = 0
                    archive.addfile(info, io.BytesIO(payload))
    except Exception:
        # The output is created by this call with exclusive creation; a partial
        # archive has no publication authority. Preserve it for reconciliation.
        raise
    return {"archive_sha256": sha(output.read_bytes()), "bytes": output.stat().st_size, "receipt_bundle": "publish and verify separately"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("release_directory", type=Path)
    parser.add_argument("--build", action="store_true", help="Build hashes from the explicit reviewed selection only")
    parser.add_argument("--replace", action="store_true", help="Replace a task-owned manifest after reviewing changes")
    parser.add_argument("--archive", type=Path, help="Create a deterministic selected-asset archive after qualification/pins converge")
    args = parser.parse_args()
    try:
        if args.replace and not args.build:
            raise ReleaseError("--replace requires --build")
        if args.build:
            result = build_manifest(ROOT, args.release_directory)
            path = args.release_directory / "manifest.json"
            require(not path.is_symlink(), "Manifest cannot be a symlink")
            mode = "w" if args.replace else "x"
            with path.open(mode, encoding="utf-8") as stream:
                stream.write(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
        result = check_release(ROOT, args.release_directory)
        if args.archive:
            result["archive"] = write_archive(ROOT, args.release_directory, args.archive)
        print(json.dumps(result, sort_keys=True))
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"release rejected: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
