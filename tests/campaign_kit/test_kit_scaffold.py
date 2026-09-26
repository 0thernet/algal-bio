"""scripts/new_campaign.py: layout, no overwrite, and a vendored kit that works standalone."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from bio_lab.campaign_kit import lint

REPO = Path(__file__).resolve().parents[2]
NAME = "demo-lane-2026-09-26"


def load_script():
    spec = importlib.util.spec_from_file_location("new_campaign", REPO / "scripts" / "new_campaign.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def new_campaign():
    return load_script()


def plain_env():
    """A subprocess environment without this checkout on the path: the vendored kit must suffice."""
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def scaffolded(new_campaign, tmp_path):
    lane = tmp_path / "lane-card.json"
    lane.write_text(json.dumps({"id": "S01", "slug": NAME}) + "\n")
    target = tmp_path / "research" / f"biology-{NAME}"
    new_campaign.scaffold(NAME, target, lane)
    return target


def test_scaffold_layout(new_campaign, tmp_path):
    target = scaffolded(new_campaign, tmp_path)
    for rel in ("code/campaign_kit/__init__.py", "code/campaign_kit/VENDORED.json", "code/freeze.py",
                "code/fetch_holdout.py", "code/confirm.py", "tests/conftest.py",
                "tests/test_demo_lane_2026_09_26_scaffold.py", "README.md", "lane.json"):
        assert (target / rel).is_file(), rel
    for rel in ("registration", "data/discovery", "data/prep", "data/sealed", "results", "review",
                "audit", "errata", "prior-art", "fanout"):
        assert (target / rel).is_dir(), rel
    vendored = json.loads((target / "code" / "campaign_kit" / "VENDORED.json").read_text())
    kit = REPO / "src" / "bio_lab" / "campaign_kit"
    assert vendored["files"] == {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in sorted(kit.glob("*.py"))}


def test_scaffold_never_overwrites(new_campaign, tmp_path):
    target = scaffolded(new_campaign, tmp_path)
    (target / "code" / "confirm.py").write_text("# my registered code\n")
    (target / "lane.json").write_text('{"id": "S01", "edited": true}\n')
    other = tmp_path / "other-card.json"
    other.write_text('{"id": "S99"}\n')
    created = new_campaign.scaffold(NAME, target, other)
    assert created == []
    assert (target / "code" / "confirm.py").read_text() == "# my registered code\n"
    assert json.loads((target / "lane.json").read_text())["id"] == "S01"


def test_scaffold_refuses_bad_names_and_directories(new_campaign, tmp_path):
    with pytest.raises(SystemExit, match="lowercase"):
        new_campaign.scaffold("Bad_Name", tmp_path / "Bad_Name")
    with pytest.raises(SystemExit, match="must be named"):
        new_campaign.scaffold(NAME, tmp_path / "somewhere-else")
    with pytest.raises(SystemExit, match="lane-json"):
        new_campaign.scaffold(NAME, tmp_path / NAME, tmp_path / "absent.json")


def test_vendored_kit_freezes_and_its_own_tests_pass(new_campaign, tmp_path):
    target = scaffolded(new_campaign, tmp_path)
    (target / "registration" / "protocol.json").write_text(
        json.dumps({"schema": "bio.protocol.v1", "constants": {"ALPHA": 0.05}}) + "\n")
    assert lint.lint_protocol(target) == []
    tests = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                            "--rootdir", str(target), str(target / "tests")],
                           capture_output=True, text=True, env=plain_env(), cwd=target)
    assert tests.returncode == 0, tests.stdout + tests.stderr
    built = subprocess.run([sys.executable, "code/freeze.py", "build"], capture_output=True,
                           text=True, env=plain_env(), cwd=target)
    assert built.returncode == 0, built.stderr
    sha = json.loads(built.stdout)["freeze_sha256"]
    manifest = json.loads((target / "registration" / "freeze.json").read_text())
    assert "code/campaign_kit/receipts.py" in manifest["sha256"]
    verified = subprocess.run([sys.executable, "code/freeze.py", "verify"], capture_output=True,
                              text=True, env=plain_env(), cwd=target)
    assert verified.returncode == 0, verified.stderr
    # the fetch template refuses before any network access: no barrier yet
    fetch = subprocess.run([sys.executable, "code/fetch_holdout.py", "--freeze-sha256", sha],
                           capture_output=True, text=True, env=plain_env(), cwd=target)
    assert fetch.returncode != 0 and "refusing:" in fetch.stderr and "barrier" in fetch.stderr
    confirm = subprocess.run([sys.executable, "code/confirm.py"], capture_output=True, text=True,
                             env=plain_env(), cwd=target)
    assert confirm.returncode != 0 and "refusing:" in confirm.stderr
    assert not any((target / "results").iterdir()) or \
        {p.name for p in (target / "results").iterdir()} <= {".confirmation.lock"}


def test_cli(tmp_path):
    target = tmp_path / NAME
    done = subprocess.run([sys.executable, str(REPO / "scripts" / "new_campaign.py"), NAME, str(target)],
                          capture_output=True, text=True, env=plain_env())
    assert done.returncode == 0, done.stderr
    assert "created code/campaign_kit/freeze.py" in done.stdout
    again = subprocess.run([sys.executable, str(REPO / "scripts" / "new_campaign.py"), NAME, str(target)],
                           capture_output=True, text=True, env=plain_env())
    assert "nothing to create" in again.stdout
