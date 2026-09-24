"""Focused regression checks for historical retention and portable evidence."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.check_repository import (
    FOUNDATION_FIXTURE,
    ROOT,
    RepositoryError,
    reproduce_fixture,
    safe_artifact_path,
    verify_artifact,
    verify_legacy,
)


def test_all_historical_receipts_are_retained():
    retained = verify_legacy()
    assert retained["native_receipts"] == 289
    assert retained["artifacts"] == 1742


def test_retention_rejects_changed_and_missing_artifacts(tmp_path):
    original = b'{"outcome":"failed"}\n'
    artifact = tmp_path / "run.json"
    artifact.write_bytes(original)
    entry = {"path": "run.json", "sha256": hashlib.sha256(original).hexdigest(),
             "bytes": len(original), "kind": "native-algal-run"}
    assert verify_artifact(tmp_path, entry) == original
    artifact.write_bytes(b'{"outcome":"passed"}\n')
    with pytest.raises(RepositoryError, match="Changed retained artifact"):
        verify_artifact(tmp_path, entry)
    artifact.unlink()
    with pytest.raises(RepositoryError, match="Missing retained artifact"):
        verify_artifact(tmp_path, entry)


@pytest.mark.parametrize("path", ["../outside", "/tmp/outside", "a/../outside", "./run.json", ""])
def test_artifact_paths_cannot_escape_or_alias(tmp_path, path):
    with pytest.raises(RepositoryError):
        safe_artifact_path(tmp_path, path)


def test_symlink_escape_is_rejected(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "escape").symlink_to(tmp_path / "private")
    with pytest.raises(RepositoryError, match="escaped repository"):
        safe_artifact_path(root, "escape")


def test_fixture_detects_changed_source(tmp_path):
    fixture = json.loads((ROOT / FOUNDATION_FIXTURE).read_text())
    fixture["source"] += "corruption"
    path = tmp_path / FOUNDATION_FIXTURE
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(fixture))
    with pytest.raises(RepositoryError, match="did not reproduce"):
        reproduce_fixture(tmp_path)


def test_fixture_runs_from_unrelated_directory_without_credentials(tmp_path):
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_repository.py"), "--reproduce-fixture"],
        cwd=tmp_path, env={}, text=True, capture_output=True, check=True,
    )
    output = json.loads(completed.stdout)
    assert output["scope"] == "synthetic artifact identity only"
    assert output["sha256"] == reproduce_fixture()["sha256"]
