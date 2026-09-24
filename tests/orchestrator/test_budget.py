import importlib.util
import json
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("budget_checker", ROOT / "scripts/check_budget.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


@pytest.mark.parametrize("value", [-1, 0.5, True, "1", float("inf"), 1_000_000_000_001])
def test_independent_accounting_rejects_unsafe_money(value):
    with pytest.raises(ValueError):
        MODULE.money(value)


def test_accounting_requires_all_components_including_recovery():
    with pytest.raises(ValueError, match="Every cost component"):
        MODULE.cost({"computeMicros": 1})


def test_independent_accounting_agrees_after_crash_recovery_and_denied_followup(tmp_path):
    fixture = subprocess.run(
        ["bun", str(ROOT / "orchestrator/fixtures.ts"), str(tmp_path)],
        capture_output=True, text=True, check=True,
    )
    expected = json.loads(fixture.stdout)
    report = MODULE.audit(tmp_path / expected["journal"])
    assert expected["submissionCount"] == 1
    assert expected["unknownSpendBlocked"] and expected["exhaustionBlocked"]
    assert report["spentMicros"] == expected["spentMicros"] == 100
    assert report["reservedMicros"] == 0
    assert not report["uncertain"] and not report["breached"]
