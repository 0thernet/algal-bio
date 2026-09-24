"""Admission tests target source fidelity, leakage, and unsupported claims."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil

import pytest

from scripts.check_registration import (
    CANDIDATE_SCHEMA, ROOT, SCHEMA, RegistrationError, check_candidate,
    check_manifest, check_registration, check_semantics, read_json, safe_path,
    validate_schema,
)

CAMPAIGN = Path("campaigns/lamina-context-pilot")


def registration():
    return read_json(ROOT / CAMPAIGN / "registration.json")


def manifests():
    return [read_json(ROOT / f"datasets/manifests/{accession}.json") for accession in ("GSE330298", "GSE89520")]


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def artifact(path, root):
    payload = path.read_bytes()
    return {"path": str(path.relative_to(root)), "sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload)}


@pytest.fixture
def isolated_root(tmp_path):
    for name in ("schemas", "datasets/manifests", str(CAMPAIGN), "tests/fixtures/bio"):
        shutil.copytree(ROOT / name, tmp_path / name)
    return tmp_path


def test_current_registration_is_explicitly_data_limited():
    report = check_registration(ROOT / CAMPAIGN)
    assert report["libraries"] == 75
    assert report["assays"] == {"atac": 2, "bulk_rna": 12, "chip": 32, "cutandrun": 18, "hic": 8, "scrna": 3}
    assert report["outcome"] == "data_limited"
    assert report["confirmatory_contrasts"] == report["verified_independent_biological_units"] == 0
    assert report["full_source_verification"] is False


def test_important_source_facts_are_retained_without_replication_assumptions():
    cm, esc = manifests()
    samples = {s["id"]: s for m in (cm, esc) for s in m["samples"]}
    assert len([s for s in cm["samples"] if s["assay"] == "bulk_rna"]) == 8
    assert len([s for s in esc["samples"] if s["assay"] == "bulk_rna"]) == 4
    for gsm, age in [("GSM9718017", "P0.6"), ("GSM9718018", "P0.7"), ("GSM9718019", "P0.8"), ("GSM9718020", "P0.9")]:
        assert samples[gsm]["age_reported"] == age
        assert samples[gsm]["age_in_title"] == "P0.5"
        assert samples[gsm]["genotype_reported"] == "Wildtype"
        assert "genotype_title_characteristics_conflict" in samples[gsm]["issues"]
    assert samples["GSM9715171"]["genome_build"] == "GRCm38"
    assert samples["GSM2375116"]["genome_build"] == "mm9"
    assert all(s["biological_unit_id"] is None and s["independence"] == "unresolved" for s in samples.values())


@pytest.mark.parametrize("mutate", [
    lambda d: d.update(unreviewed_override=True),
    lambda d: d["precision"].update(biological_replicates=True),
    lambda d: d["features"][0].update(eligible="false"),
    lambda d: d["contrasts"][0].update(genome_compatible="yes"),
    lambda d: d["resources"].update(funded_budget_usd=False),
    lambda d: d["decision"].update(reasons=[]),
    lambda d: d["endpoints"][0].update(absolute_tolerance=float("inf")),
])
def test_schema_rejects_unknown_fields_and_wrong_nested_types(mutate):
    data = registration()
    mutate(data)
    with pytest.raises(RegistrationError):
        validate_schema(data, read_json(ROOT / SCHEMA))


@pytest.mark.parametrize("mutate,reason", [
    (lambda d: d.update(mode="confirmatory"), "confirmatory mode"),
    (lambda d: d["decision"].update(status="qualified"), "data_limited"),
    (lambda d: d["precision"].update(biological_replicates=75000), "biological replicate"),
    (lambda d: d["splits"]["discovery_sample_ids"].append("GSM9715171"), "overlap"),
    (lambda d: d["splits"]["holdout"].update(status="reserved", identity_commitment="a" * 64), "No independent holdout"),
    (lambda d: d["features"][2].update(use="prediction"), "Post-perturbation"),
    (lambda d: d["features"][1].update(eligible=True), "No predictive feature"),
    (lambda d: d["contrasts"][0].update(biological_units_known=True), "biological identity"),
    (lambda d: d["contrasts"][-1].update(status="confirmatory_eligible"), "confirmatory contrast"),
    (lambda d: d["contrasts"][-1].update(perturbation_matched=True), "confounding"),
    (lambda d: d["contrasts"][-1].update(genome_compatible=True), "Genome build"),
    (lambda d: d["contrasts"][2].update(age_compatible=True), "Age compatibility"),
    (lambda d: d["contrasts"][2].update(preparation_compatible=True), "Cell preparation"),
    (lambda d: d["contrasts"][4].update(status="descriptive_only"), "Ambiguous genotype"),
    (lambda d: d["endpoints"][1].update(status="active"), "qualified independent"),
    (lambda d: d["controls"][0].update(eligible_for_novelty=True), "Controls and decoys"),
    (lambda d: d["multiple_testing"].update(inference_enabled=True), "Biological inference"),
])
def test_semantics_prevent_unsupported_confirmation_and_leakage(mutate, reason):
    data = registration()
    mutate(data)
    with pytest.raises(RegistrationError, match=reason):
        check_semantics(data, manifests())


def test_sample_reuse_is_not_independent_replication():
    data = manifests()
    data[1]["samples"][0]["biosample_id"] = data[0]["samples"][0]["biosample_id"]
    with pytest.raises(RegistrationError, match="BioSample across libraries"):
        check_semantics(registration(), data)


def test_freeze_detects_registration_change(isolated_root):
    path = isolated_root / CAMPAIGN / "registration.json"
    value = read_json(path)
    value["question"] = "A modified question after seeing results"
    write_json(path, value)
    with pytest.raises(RegistrationError, match="freeze changed"):
        check_registration(isolated_root / CAMPAIGN, root=isolated_root)


def test_numeric_fixture_is_frozen(isolated_root):
    path = isolated_root / "tests/fixtures/bio/rna-counts.tsv"
    path.write_text(path.read_text().replace("ENSMUSG", "CHANGED", 1))
    with pytest.raises(RegistrationError, match="Artifact hash/size mismatch"):
        check_registration(isolated_root / CAMPAIGN, root=isolated_root)


def test_normalized_sample_cannot_silently_repair_source_conflict(isolated_root):
    path = isolated_root / "datasets/manifests/GSE330298.json"
    manifest = read_json(path)
    sample = next(s for s in manifest["samples"] if s["id"] == "GSM9718017")
    sample["age_reported"] = "P0.5"
    write_json(path, manifest)
    with pytest.raises(RegistrationError, match="Normalized samples disagree"):
        check_manifest(isolated_root, artifact(path, isolated_root), read_json(isolated_root / SCHEMA))


def test_normalized_sample_cannot_invent_animal_identity(isolated_root):
    path = isolated_root / "datasets/manifests/GSE330298.json"
    manifest = read_json(path)
    manifest["samples"][0].update(biological_unit_id="mouse-1", independence="verified", pooling="individual")
    write_json(path, manifest)
    with pytest.raises(RegistrationError, match="overstate biological identity"):
        check_manifest(isolated_root, artifact(path, isolated_root), read_json(isolated_root / SCHEMA))


def test_full_source_mode_rejects_an_unrelated_file(isolated_root, tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "GSE330298-samples.soft").write_text("Not the original GEO source\n")
    with pytest.raises(RegistrationError, match="Full source hash/size mismatch"):
        check_registration(isolated_root / CAMPAIGN, root=isolated_root, source_directory=source)


@pytest.mark.parametrize("relative", ["../secret", "/tmp/secret", "a/../secret", "a//b", "a\\b"])
def test_paths_cannot_escape_or_alias_artifacts(tmp_path, relative):
    with pytest.raises(RegistrationError):
        safe_path(tmp_path, relative)


def test_symlink_cannot_read_outside_repository(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "outside").symlink_to(tmp_path / "secret")
    with pytest.raises(RegistrationError, match="escapes repository"):
        safe_path(root, "outside")


@pytest.mark.parametrize("payload", ['{"a": 1, "a": 2}', '{"x": NaN}', '{"x": Infinity}'])
def test_ambiguous_json_is_rejected(tmp_path, payload):
    path = tmp_path / "invalid.json"
    path.write_text(payload)
    with pytest.raises(RegistrationError):
        read_json(path)


def sample_candidate():
    reg = registration()
    freeze = read_json(ROOT / CAMPAIGN / "freeze.json")
    return {
        "schema_version": "1", "candidate_id": "software-filter-control", "study_id": reg["study_id"],
        "classification": "software_control",
        "provenance": {"registration_sha256": freeze["registration_sha256"], "instrument_sha256": "0" * 64,
            "input_artifacts": [deepcopy(reg["qualification_fixture"]["inputs"][0])], "source_sample_ids": ["GSM9715171"]},
        "observation": {"description": "An unassessed test dossier for the pre-TMM filter", "measurement": 28,
            "unit": "source rows", "uncertainty": None, "biological_replicates": None},
        "inference": {"claim": "Only a software control", "scope": "software_reproduction", "alternatives": ["Unassessed instrument errors"], "mechanism_established": False},
        "novelty": {"status": "not_applicable_control", "reviewed_on": None, "search_queries": [], "sources": []},
        "validation": {"status": "unassessed", "independent_recomputation": False, "holdout_opened": False,
            "evidence": [], "wet_lab": "not_performed", "limitations": ["Synthetic test dossier, no independent biology"]},
    }


def test_candidate_separates_observation_inference_novelty_and_validation(tmp_path):
    candidate = sample_candidate()
    validate_schema(candidate, read_json(ROOT / CANDIDATE_SCHEMA))
    path = tmp_path / "candidate.json"
    write_json(path, candidate)
    check_candidate(path, registration(), ROOT, candidate["provenance"]["registration_sha256"])


@pytest.mark.parametrize("mutate,reason", [
    (lambda c: c["novelty"].update(status="candidate_unreported"), "Novelty review"),
    (lambda c: c["validation"].update(holdout_opened=True), "No holdout"),
    (lambda c: c["validation"].update(status="independent_support"), "Independent validation"),
    (lambda c: c["observation"].update(biological_replicates=128), "overstates biological"),
    (lambda c: c["inference"].update(scope="independent_association"), "No independent association"),
    (lambda c: c["validation"].update(independent_recomputation=True), "requires evidence"),
    (lambda c: c["provenance"].update(registration_sha256="b" * 64), "registration hash"),
])
def test_candidate_cannot_upgrade_a_control_into_a_discovery(tmp_path, mutate, reason):
    candidate = sample_candidate()
    registered = candidate["provenance"]["registration_sha256"]
    mutate(candidate)
    path = tmp_path / "candidate.json"
    write_json(path, candidate)
    with pytest.raises(RegistrationError, match=reason):
        check_candidate(path, registration(), ROOT, registered)
