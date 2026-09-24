from pathlib import Path
import json
import shutil

import pytest

from scripts.evaluate_candidates import ROOT, readiness


def test_readiness_cannot_be_mistaken_for_negative_research_result():
    result = readiness(ROOT / "campaigns/prospective-001")
    assert result["status"] == "not_run"
    assert result["decision"] == "no_go"
    assert result["holdout_opened"] is False
    assert "not a biological negative finding" in result["interpretation"]


def test_closed_gate_never_opens_supplied_run(tmp_path):
    # The path need not exist: admission must fail before candidate data access.
    with pytest.raises(ValueError, match="supplied run was not opened"):
        readiness(ROOT / "campaigns/prospective-001", tmp_path / "secret-candidate-run")


def test_unreviewed_study_cannot_use_current_evaluator(tmp_path):
    with pytest.raises(ValueError, match="admitted evaluator"):
        readiness(tmp_path)


@pytest.fixture
def registered_copy(tmp_path):
    # Keep the actual frozen source corpus while varying the readiness record.
    for path in ["campaigns/lamina-context-pilot", "campaigns/prospective-001", "datasets/manifests", "schemas", "tests/fixtures/bio"]:
        shutil.copytree(ROOT / path, tmp_path / path)
    return tmp_path


@pytest.mark.parametrize("changes", [
    {"interpretation": "No biological candidates survived our search."},
    {"missing": ["none", "none", "none", "none"]},
    {"campaign": "another-study"},
    {"new_biological_result": True},
])
def test_no_go_record_cannot_smuggle_an_unperformed_result(registered_copy, changes):
    path = registered_copy / "campaigns/prospective-001/registration.json"
    record = json.loads(path.read_text())
    record.update(changes)
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="unsupported prospective state|unexpected readiness fields"):
        readiness(path.parent, root=registered_copy)
