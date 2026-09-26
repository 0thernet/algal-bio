"""Synthetic fixtures for the campaign kit tests. Nothing here touches real data.

Every test gets its own mining dir under tmp_path (BIO_MINING_DIR), with no
run id or budget in the environment, so a guard that forgets an argument
fails instead of reading the machine's real settings.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from bio_lab.campaign_kit import barrier, freeze, seal

SRC = Path(__file__).resolve().parents[2] / "src"


def kit_env(**extra) -> dict:
    """Environment for a subprocess that imports bio_lab from this checkout."""
    env = dict(os.environ, **extra)
    env["PYTHONPATH"] = os.pathsep.join(p for p in (str(SRC), env.get("PYTHONPATH")) if p)
    return env


CONFIRM = '''import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

K = load_constants(ROOT)
ALPHA = K["ALPHA"]
'''


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    mining = tmp_path / "mining"
    mining.mkdir()
    monkeypatch.setenv("BIO_MINING_DIR", str(mining))
    for name in ("BIO_RUN_ID", "BIO_DATA_BUDGET_GB", "BIO_SLOT"):
        monkeypatch.delenv(name, raising=False)
    return mining


@pytest.fixture
def mining(isolated_env):
    return isolated_env


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def make_campaign(root: Path, name: str = "demo-lane-2026-09-26", lane_id: str = "S01",
                  constants: dict | None = None) -> Path:
    """A minimal registered campaign directory (not yet frozen)."""
    campaign = root / f"biology-{name}"
    write(campaign / "lane.json", json.dumps({"id": lane_id, "slug": name}) + "\n")
    protocol = {"schema": "bio.protocol.v1", "constants": constants or {"ALPHA": 0.05}}
    write(campaign / "registration" / "protocol.json", json.dumps(protocol, indent=1) + "\n")
    write(campaign / "code" / "confirm.py", CONFIRM)
    write(campaign / "tests" / "test_demo.py", "def test_ok():\n    assert True\n")
    (campaign / "results").mkdir()
    (campaign / "data" / "sealed").mkdir(parents=True)
    return campaign


def barrier_doc(members, frozen, released=(), run_id="2026-09-26-campaigns") -> dict:
    return {"schema": barrier.SCHEMA, "run_id": run_id, "members": list(members),
            "frozen": [dict(f) for f in frozen], "released": list(released)}


def frozen_entry(lane_id: str, campaign: str, freeze_sha: str, merge_sha: str = "a" * 40) -> dict:
    return {"id": lane_id, "campaign": campaign, "freeze_sha256": freeze_sha, "merge_sha": merge_sha}


@pytest.fixture
def frozen_campaign(tmp_path):
    """(campaign_dir, lane_id, freeze_sha256, name) with a group barrier that clears this lane."""
    name, lane_id = "demo-lane-2026-09-26", "S01"
    campaign = make_campaign(tmp_path / "research", name, lane_id)
    _, sha = freeze.build(campaign)
    doc = barrier_doc(["S01", "S02"], [frozen_entry("S01", name, sha)], released=["S02"])
    barrier.write(campaign, doc)
    yield campaign, lane_id, sha, name
    seal.unlock(campaign)          # let pytest remove the synthetic tree
