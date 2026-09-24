"""Public packaging rejects drift, unsupported claims, and unsafe selections."""

from copy import deepcopy
import json
from pathlib import Path
import shutil
import tarfile

import pytest

from scripts.check_release import (
    FULL_RNA, QUALIFICATION_REPORT, ROOT, ReleaseError, build_manifest,
    check_release, check_selection, publication_identity, scan_public_text,
    selected_path, write_archive, runtime_identity,
)
from scripts.check_registration import read_json

RELEASE = Path("reports/release")


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


@pytest.fixture
def subset(tmp_path):
    selection = read_json(ROOT / RELEASE / "selection.json")
    for relative in [item["path"] for item in selection["artifacts"]] + [str(RELEASE / "selection.json"), str(RELEASE / "publication.json")]:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    write_json(tmp_path / RELEASE / "manifest.json", build_manifest(tmp_path, tmp_path / RELEASE))
    return tmp_path


def test_current_manifest_describes_calibration_without_publication_claim():
    report = check_release(ROOT, ROOT / RELEASE)
    assert report["artifact_admission"] == "passed"
    assert report["scientific_status"] == "data_limited"
    assert report["prospective_status"] == "not_run"
    assert report["publication_status"] in {"pending", "published", "not_recorded"}


def test_explicit_subset_is_self_contained_for_registration_and_manifest(subset):
    report = check_release(subset, subset / RELEASE)
    assert report["artifact_admission"] == "passed"
    assert not (subset / ".algal").exists()
    assert not (subset / "out").exists()


def test_document_drift_invalidates_selected_bytes(subset):
    with (subset / "docs/study-report.md").open("a") as stream:
        stream.write("\nChanged after artifact admission.\n")
    with pytest.raises(ReleaseError, match="Selected artifact bytes"):
        check_release(subset, subset / RELEASE)


def test_full_source_count_claim_cannot_be_rewritten_by_regenerating_manifest(subset):
    path = subset / FULL_RNA
    value = read_json(path)
    value["passing_genes"] += 1
    write_json(path, value)
    with pytest.raises(ReleaseError, match="Full-input report"):
        build_manifest(subset, subset / RELEASE)


@pytest.mark.parametrize("field,value", [("status", "completed"), ("decision", "go"), ("holdout_opened", True)])
def test_unrun_prospective_campaign_cannot_become_a_search_result(subset, field, value):
    path = subset / "campaigns/prospective-001/registration.json"
    data = read_json(path)
    data[field] = value
    write_json(path, data)
    with pytest.raises(ReleaseError, match="Prospective research was not admitted"):
        build_manifest(subset, subset / RELEASE)


def test_duplicate_and_missing_rights_selection_is_rejected(subset):
    selection = read_json(subset / RELEASE / "selection.json")
    selection["artifacts"].append(deepcopy(selection["artifacts"][0]))
    with pytest.raises(ReleaseError, match="Duplicate"):
        check_selection(selection, subset)
    selection = read_json(subset / RELEASE / "selection.json")
    del selection["artifacts"][0]["rights"]["attribution"]
    with pytest.raises(ReleaseError, match="rights"):
        check_selection(selection, subset)


def test_public_measurements_are_not_relicensed_as_project_code(subset):
    selection = read_json(subset / RELEASE / "selection.json")
    item = next(row for row in selection["artifacts"] if row["path"] == "tests/fixtures/bio/rna-counts.tsv")
    item["rights"].update(basis="project_mit", license="MIT")
    with pytest.raises(ReleaseError, match="retain their source rights"):
        check_selection(selection, subset)


def test_unadmitted_redistribution_blocks_packaging(subset):
    selection = read_json(subset / RELEASE / "selection.json")
    selection["artifacts"][0]["rights"]["redistribution"] = "unknown"
    with pytest.raises(ReleaseError, match="not been admitted"):
        check_selection(selection, subset)


@pytest.mark.parametrize("relative", [".", "../private.json", "/tmp/private.json", "runs/report.json", ".env", ".algal/run.json", "docs/../../private.json", "docs//study-report.md"])
def test_portable_allowlist_rejects_escapes_and_transient_roots(subset, relative):
    with pytest.raises(ReleaseError):
        selected_path(subset, relative)


def test_symlinks_are_rejected_even_when_target_is_inside_selection(subset):
    source = subset / "docs/study-report.md"
    source.unlink()
    source.symlink_to(subset / "docs/contributions.md")
    with pytest.raises(ReleaseError, match="Symlink"):
        selected_path(subset, "docs/study-report.md")


def test_registration_dependency_cannot_be_silently_omitted(subset):
    path = subset / RELEASE / "selection.json"
    selection = read_json(path)
    selection["artifacts"] = [item for item in selection["artifacts"] if item["path"] != "campaigns/lamina-context-pilot/metadata/GSE89520.json"]
    write_json(path, selection)
    with pytest.raises(ReleaseError, match="provenance dependency"):
        build_manifest(subset, subset / RELEASE)


@pytest.mark.parametrize("payload", [
    ("/" + "Users/" + "private-person/" + "secret.txt").encode(),
    ("ghp" + "_" + "a" * 40).encode(),
    ("sk" + "-" + "z" * 40).encode(),
    ("-----BEGIN " + "PRIVATE KEY-----").encode(),
    b"binary\x00payload",
])
def test_selected_sensitive_content_is_rejected(payload):
    with pytest.raises(ReleaseError):
        scan_public_text(payload, "fixture.txt")


def test_pending_publication_cannot_claim_an_asset_identity(subset):
    path = subset / RELEASE / "publication.json"
    record = {
        "contract": "bio.publication-identity.v1", "status": "pending",
        "source_revision": None, "tag": None, "release_url": None,
        "selected_archive_sha256": None, "qualification_archive_sha256": None,
        "verification": "pending",
    }
    write_json(path, record)
    assert publication_identity(subset / RELEASE) == record
    record["source_revision"] = "a" * 40
    write_json(path, record)
    with pytest.raises(ReleaseError, match="Pending publication"):
        publication_identity(subset / RELEASE)


def test_absent_publication_record_is_not_a_published_claim(subset):
    (subset / RELEASE / "publication.json").unlink()
    report = check_release(subset, subset / RELEASE)
    assert report["publication_status"] == "not_recorded"


@pytest.mark.parametrize("missing", ["source_revision", "selected_archive_sha256", "qualification_archive_sha256"])
def test_published_status_needs_source_and_both_asset_identities(subset, missing):
    path = subset / RELEASE / "publication.json"
    record = {
        "contract": "bio.publication-identity.v1", "status": "published",
        "source_revision": "a" * 40, "tag": "test-calibration",
        "release_url": "https://github.com/0thernet/algal-bio/releases/tag/test-calibration",
        "selected_archive_sha256": "b" * 64, "qualification_archive_sha256": "c" * 64,
        "verification": "operator_verified",
    }
    write_json(path, record)
    assert publication_identity(subset / RELEASE) == record
    record[missing] = None
    write_json(path, record)
    with pytest.raises(ReleaseError, match="identity missing"):
        publication_identity(subset / RELEASE)


def prepare_synthetic_archive_test(root):
    """Test-only report/pins exercise packing, never live/research qualification."""
    package = read_json(root / "package.json")
    package.setdefault("dependencies", {}).update({
        "@hraness/algal-lab": "github:hraness/algal-lab#" + "a" * 40,
        "@hraness/algal": "github:hraness/algal#" + "b" * 40,
    })
    package.get("devDependencies", {}).pop("@hraness/algal-lab", None)
    package.get("devDependencies", {}).pop("@hraness/algal", None)
    write_json(root / "package.json", package)
    # Format-valid synthetic lock for packing tests, never installed/qualified.
    # Pins must bind workspace dependencies and resolved package records.
    metadata = {
        "@hraness/algal": {"bin": {"algal": "./cli.ts"}},
        "@hraness/algal-lab": {"dependencies": {"@hraness/algal": package["dependencies"]["@hraness/algal"]}},
    }
    lock = {"lockfileVersion": 1, "configVersion": 1,
            "workspaces": {"": {"dependencies": package["dependencies"]}}, "packages": {}}
    for name, pin in package["dependencies"].items():
        short = pin.split("#")[1][:7]
        lock["packages"][name] = [f"{name}@{pin.split('#')[0]}#{short}", metadata[name],
                                  name.removeprefix("@").replace("/", "-") + "-" + short,
                                  "sha512-" + "A" * 86 + "=="]
    write_json(root / "bun.lock", lock)
    expected = read_json(root / "tests/fixtures/bio/expected.json")
    report = {"contract": "bio.qualification-report.v1", "status": "offline_passed", "prospectiveDecision": "no_go",
              "liveAgentComparison": "not_run", "independentBiologicalHoldout": "not_available", "externalSpendMicros": 0,
              "repetitions": [{"repetition": i, "scriptedProposalCalls": 3, "providerCalls": 0, "controlValues": expected,
                 "successfulControls": 1, "failedMeasurements": 1, "rejectedProposals": 1, "selected": ["known-control"],
                 "receiptReplay": True, "freshComputation": "passed"} for i in range(3)]}
    write_json(root / QUALIFICATION_REPORT, report)
    selection = read_json(root / RELEASE / "selection.json")
    selection["review_status"] = "independently_reviewed"
    if not any(item["path"] == QUALIFICATION_REPORT for item in selection["artifacts"]):
        item = deepcopy(next(item for item in selection["artifacts"] if item["path"] == FULL_RNA))
        item.update(path=QUALIFICATION_REPORT, role="report")
        selection["artifacts"].append(item)
        selection["artifacts"].sort(key=lambda item: item["path"])
    write_json(root / RELEASE / "selection.json", selection)
    write_json(root / RELEASE / "manifest.json", build_manifest(root, root / RELEASE))


def test_archive_requires_qualified_pins_and_final_summary(subset, tmp_path):
    package = read_json(subset / "package.json")
    package.get("dependencies", {}).pop("@hraness/algal-lab", None)
    package.get("devDependencies", {}).pop("@hraness/algal-lab", None)
    write_json(subset / "package.json", package)
    write_json(subset / RELEASE / "manifest.json", build_manifest(subset, subset / RELEASE))
    with pytest.raises(ReleaseError, match="immutable runtime pins"):
        write_archive(subset, subset / RELEASE, tmp_path / "blocked.tar.gz")


def test_archive_is_deterministic_selected_only_and_never_overwrites(subset, tmp_path, monkeypatch):
    prepare_synthetic_archive_test(subset)
    first = tmp_path / "first.tar.gz"
    second = tmp_path / "second.tar.gz"
    a = write_archive(subset, subset / RELEASE, first)
    # The documented CLI uses a relative control directory and output path.
    monkeypatch.chdir(subset)
    b = write_archive(subset, RELEASE, Path(second.name))
    assert a["archive_sha256"] == b["archive_sha256"]
    assert first.read_bytes() == second.read_bytes()
    with tarfile.open(first, "r:gz") as bundle:
        entries = bundle.getmembers()
        assert all(item.isfile() and item.mtime == 0 and item.uid == 0 for item in entries)
        assert all(item.name.startswith("algal-bio-calibration/") for item in entries)
        assert not any(item.name.endswith("publication.json") for item in entries)
        assert not any("/.algal/" in item.name or "/runs/" in item.name for item in entries)
    with pytest.raises(ReleaseError, match="Never overwrite"):
        write_archive(subset, subset / RELEASE, first)


def test_runtime_lock_must_bind_resolved_records_not_merely_mention_pins(subset):
    package = read_json(subset / "package.json")
    write_json(subset / "bun.lock", {"notes": package["dependencies"]})
    assert runtime_identity(subset)["immutable_runtime_pins"] is False


def test_runtime_lock_rejects_wrong_resolved_revision(subset):
    prepare_synthetic_archive_test(subset)
    lock = read_json(subset / "bun.lock")
    lock["packages"]["@hraness/algal-lab"][0] = "@hraness/algal-lab@github:hraness/algal-lab#ccccccc"
    write_json(subset / "bun.lock", lock)
    assert runtime_identity(subset)["immutable_runtime_pins"] is False


def test_runtime_lock_binds_the_labs_transitive_algal_pin(subset):
    prepare_synthetic_archive_test(subset)
    lock = read_json(subset / "bun.lock")
    lock["packages"]["@hraness/algal-lab"][1]["dependencies"]["@hraness/algal"] = "github:hraness/algal#" + "c" * 40
    write_json(subset / "bun.lock", lock)
    assert runtime_identity(subset)["immutable_runtime_pins"] is False


def test_archive_requires_independent_selection_review(subset, tmp_path):
    prepare_synthetic_archive_test(subset)
    selection = read_json(subset / RELEASE / "selection.json")
    selection["review_status"] = "explicit_selection_pending_independent_review"
    write_json(subset / RELEASE / "selection.json", selection)
    write_json(subset / RELEASE / "manifest.json", build_manifest(subset, subset / RELEASE))
    with pytest.raises(ReleaseError, match="independent selection review"):
        write_archive(subset, subset / RELEASE, tmp_path / "not-reviewed.tar.gz")


def test_selection_metadata_is_scanned_before_embedding_it_in_an_archive(subset):
    selection = read_json(subset / RELEASE / "selection.json")
    selection["artifacts"][0]["rights"]["attribution"] = "ghp" + "_" + "a" * 40
    write_json(subset / RELEASE / "selection.json", selection)
    with pytest.raises(ReleaseError, match="private path/credential"):
        build_manifest(subset, subset / RELEASE)


def test_release_control_directory_symlinks_cannot_import_external_metadata(subset, tmp_path):
    alias = subset / "release-alias"
    alias.symlink_to(subset / RELEASE, target_is_directory=True)
    with pytest.raises(ReleaseError, match="Symlink"):
        build_manifest(subset, alias)


def test_artifact_size_is_rejected_before_unbounded_read(subset):
    path = subset / "docs/study-report.md"
    with path.open("wb") as stream:
        stream.truncate(2 * 1024 * 1024 + 1)
    with pytest.raises(ReleaseError, match="Unbounded artifact"):
        build_manifest(subset, subset / RELEASE)


def test_negative_biology_claim_cannot_hide_in_a_prospective_decision(subset):
    path = subset / "reports/prospective-001/decision.json"
    decision = read_json(path)
    decision["interpretation"] = "Our prospective search found no biological candidates."
    write_json(path, decision)
    with pytest.raises(ReleaseError, match="reviewed readiness gate"):
        build_manifest(subset, subset / RELEASE)
