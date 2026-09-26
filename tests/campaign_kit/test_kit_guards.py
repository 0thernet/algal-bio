"""Disk floor, data budget, compute slots, conflict markers and orientation guards."""

from __future__ import annotations

import json
import subprocess
import sys
from types import SimpleNamespace

import pytest

from bio_lab.campaign_kit import guards, slot
from bio_lab.campaign_kit.common import KitError, try_lock
from conftest import kit_env

GIB = guards.GIB


def fake_usage(free_bytes):
    return lambda _path: SimpleNamespace(free=free_bytes, total=free_bytes * 2, used=free_bytes)


# ---------------------------------------------------------------- disk floor

def test_disk_floor_passes_with_headroom(tmp_path):
    headroom = guards.require_disk_floor(tmp_path, 1 * GIB, 10, usage=fake_usage(20 * GIB))
    assert headroom == 10 * GIB


def test_disk_floor_refuses_when_the_write_would_cross_it(tmp_path):
    with pytest.raises(guards.DiskFloorError, match="disk floor"):
        guards.require_disk_floor(tmp_path, 3 * GIB, 10, usage=fake_usage(12 * GIB))


def test_disk_floor_refuses_when_already_under_it(tmp_path):
    with pytest.raises(guards.DiskFloorError):
        guards.require_disk_floor(tmp_path / "not" / "yet", 0, 10, usage=fake_usage(9 * GIB))


def test_disk_floor_rejects_negative_need(tmp_path):
    with pytest.raises(KitError):
        guards.require_disk_floor(tmp_path, -1, 10, usage=fake_usage(20 * GIB))


# ---------------------------------------------------------------- data budget

def test_budget_records_an_overrun_and_then_stops(mining):
    assert guards.record_download(600_000_000, run_id="r1", budget_gb=1) == 600_000_000
    # the bytes were spent: they are recorded, then the call says stop
    with pytest.raises(guards.BudgetExceeded, match="over its budget") as error:
        guards.record_download(500_000_000, run_id="r1", budget_gb=1)
    assert error.value.total == 1_100_000_000
    # another run's budget is separate
    assert guards.record_download(500_000_000, run_id="r2", budget_gb=1) == 500_000_000
    lines = (mining / "data-budget.jsonl").read_text().splitlines()
    assert [json.loads(line)["run"] for line in lines] == ["r1", "r1", "r2"]
    assert guards.budget_totals() == {"r1": 1_100_000_000, "r2": 500_000_000}
    with pytest.raises(guards.BudgetError, match="would pass"):
        guards.check_budget(1, run_id="r1", budget_gb=1)
    with pytest.raises(guards.BudgetError, match="would pass"):
        guards.check_budget(500_000_001, run_id="r2", budget_gb=1)
    assert guards.check_budget(500_000_000, run_id="r2", budget_gb=1) == 0


def test_check_counts_reservations_and_settles_stale_ones(mining):
    guards.record_download(100, run_id="r1", budget_gb=1)
    held = guards.reserve(10 ** 9 - 400, run_id="r1", budget_gb=1)
    assert guards.check_budget(300, run_id="r1", budget_gb=1) == 0
    with pytest.raises(guards.BudgetError, match="reserved by fetches in progress"):
        guards.check_budget(301, run_id="r1", budget_gb=1)
    guards.settle(held, [("download", 50, {})])
    assert guards.check_budget(301, run_id="r1", budget_gb=1) == 10 ** 9 - 451
    with pytest.raises(guards.BudgetError, match="nonnegative"):
        guards.check_budget(-1, run_id="r1", budget_gb=1)


def test_record_and_check_cli(mining, capsys):
    base = ["--run", "r1", "--budget-gb", "1"]
    assert guards.main(["check", *base, "--need-gb", "0.9"]) == 0
    assert guards.main(["record", *base, "--bytes", "900000000"]) == 0
    assert guards.main(["check", *base, "--need-bytes", "100000000"]) == 0
    assert guards.main(["check", *base, "--need-gb", "0.2"]) == 2
    assert "would pass" in capsys.readouterr().err
    # a download that happened anyway is recorded, and the exit status says stop
    assert guards.main(["record", *base, "--bytes", "200000000"]) == 3
    captured = capsys.readouterr()
    assert "run total 1.100 GB" in captured.out and "over budget" in captured.err
    assert guards.budget_totals() == {"r1": 1_100_000_000}
    assert guards.main(["budget", *base]) == 0
    assert "1.100 GB recorded" in capsys.readouterr().out
    assert guards.main(["check", *base, "--need-bytes", "0"]) == 2
    for bad in (["--need-gb", "nan"], ["--need-gb", "-1"], ["--need-bytes", "-5"]):
        assert guards.main(["check", *base, *bad]) == 2
    assert guards.budget_totals() == {"r1": 1_100_000_000}


def test_budget_needs_a_run_id_and_a_budget(monkeypatch):
    with pytest.raises(guards.BudgetError, match="run id"):
        guards.record_download(1, budget_gb=1)
    with pytest.raises(guards.BudgetError, match="budget"):
        guards.record_download(1, run_id="r1")
    monkeypatch.setenv("BIO_RUN_ID", "r9")
    monkeypatch.setenv("BIO_DATA_BUDGET_GB", "0.000001")
    assert guards.record_download(1000) == 1000
    with pytest.raises(guards.BudgetError):
        guards.record_download(1)


@pytest.mark.parametrize("value", ["abc", "0", "-1", "nan", "inf"])
def test_budget_env_must_be_a_positive_finite_number(monkeypatch, mining, value):
    monkeypatch.setenv("BIO_DATA_BUDGET_GB", value)
    with pytest.raises(guards.BudgetError, match="not a number|positive number"):
        guards.budget_bytes_from(None)
    with pytest.raises(guards.BudgetError):
        guards.reserve(1, run_id="r1")
    with pytest.raises(guards.BudgetError):
        guards.check_budget(1, run_id="r1")
    assert list(mining.iterdir()) in ([], [mining / "data-budget.jsonl.lock"])


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf"), 0.0, -0.5])
def test_budget_argument_must_be_a_positive_finite_number(mining, value):
    with pytest.raises(guards.BudgetError, match="positive number"):
        guards.budget_bytes_from(value)
    with pytest.raises(guards.BudgetError, match="positive number"):
        guards.reserve(1, run_id="r1", budget_gb=value)
    with pytest.raises(guards.BudgetError, match="positive number"):
        guards.check_budget(1, run_id="r1", budget_gb=value)
    # a download that happened is still recorded; the invalid budget is then reported
    with pytest.raises(guards.BudgetError, match="recorded, but the budget cannot be checked"):
        guards.record_download(1, run_id="r1", budget_gb=value)
    assert guards.budget_totals() == {"r1": 1}
    assert not (mining / guards.RESERVATIONS_DIR).exists()


@pytest.mark.parametrize("size", [-1, True, 1.5, "10"])
def test_negative_or_non_integer_sizes_are_refused(mining, size):
    with pytest.raises(guards.BudgetError, match="nonnegative integer"):
        guards.record_download(size, run_id="r1", budget_gb=1)
    assert not (mining / "data-budget.jsonl").exists()


@pytest.mark.parametrize("want", [0, -1, True, 2.0])
def test_a_reservation_must_be_positive(mining, want):
    with pytest.raises(guards.BudgetError, match="positive number of bytes"):
        guards.reserve(want, run_id="r1", budget_gb=1)
    assert not (mining / guards.RESERVATIONS_DIR).exists()


@pytest.mark.parametrize("size", [-1, True])
def test_settle_refuses_a_negative_transfer_and_records_nothing(mining, size):
    held = guards.reserve(100, run_id="r1", budget_gb=1)
    with pytest.raises(guards.BudgetError, match="nonnegative integer"):
        guards.settle(held, [("download", 10, {}), ("download_partial", size, {})])
    assert not (mining / "data-budget.jsonl").exists()
    assert not held.settled and held.path.exists()
    guards.settle(held, [("download", 10, {})])
    assert guards.budget_totals() == {"r1": 10} and not held.path.exists()


def test_budget_refuses_a_malformed_ledger(mining):
    (mining / "data-budget.jsonl").write_text('{"run": "r1"}\n')
    with pytest.raises(guards.BudgetError, match="entry 1"):
        guards.budget_totals()


def test_budget_needs_a_mining_dir(monkeypatch):
    monkeypatch.delenv("BIO_MINING_DIR")
    with pytest.raises(KitError, match="BIO_MINING_DIR"):
        guards.record_download(1, run_id="r1", budget_gb=1)


# ---------------------------------------------------------------- compute slots

def make_slots(mining, count=2):
    (mining / "slots").mkdir()
    for index in range(count):
        (mining / "slots" / f"slot-{index}.lock").touch()


def test_no_slots_is_a_refusal(mining):
    with pytest.raises(guards.SlotBusyError, match="no compute slots"):
        with guards.compute_slot(wait=False):
            pass


def test_slot_contention(mining):
    make_slots(mining, 2)
    with guards.compute_slot(wait=False) as first:
        with guards.compute_slot(wait=False) as second:
            assert {first, second} == {"slot-0", "slot-1"}
            assert set(guards.slot_status().values()) == {"busy"}
            with pytest.raises(guards.SlotBusyError, match="busy"):
                with guards.compute_slot(wait=False):
                    pass
            with pytest.raises(guards.SlotBusyError):
                with guards.compute_slot(timeout=0.05, poll=0.01):
                    pass
    assert set(guards.slot_status().values()) == {"free"}


def test_slot_runner_runs_the_command_inside_a_slot(mining, tmp_path):
    make_slots(mining, 1)
    out = tmp_path / "slot.txt"
    code = f"import os; open({str(out)!r}, 'w').write(os.environ['BIO_SLOT'])"
    assert slot.run([sys.executable, "-c", code]) == 0
    assert out.read_text() == "slot-0"


def test_slot_runner_refuses_when_busy(mining):
    make_slots(mining, 1)
    held = try_lock(mining / "slots" / "slot-0.lock")
    try:
        with pytest.raises(guards.SlotBusyError):
            slot.run([sys.executable, "-c", "pass"], wait=False)
        assert slot.main(["run", "--no-wait", "--", sys.executable, "-c", "pass"]) == 2
    finally:
        held.close()


def test_slot_runner_passes_the_exit_code(mining):
    make_slots(mining, 1)
    assert slot.main(["run", "--", sys.executable, "-c", "raise SystemExit(3)"]) == 3


# ---------------------------------------------------------------- conflict markers

def test_conflict_markers_found_and_markdown_rules_ignored(tmp_path):
    clean = tmp_path / "clean.md"
    clean.write_text("Title\n" + "=" * 7 + "\n\ntext\n")
    bad = tmp_path / "bad.py"
    bad.write_text("a = 1\n" + "<" * 7 + " HEAD\nb = 2\n" + "=" * 7 + "\nb = 3\n" + ">" * 7 + " x\n")
    assert guards.find_conflict_markers([clean]) == []
    assert guards.find_conflict_markers([tmp_path]) == [(str(bad), 2), (str(bad), 4), (str(bad), 6)]
    with pytest.raises(KitError, match="conflict markers"):
        guards.require_no_conflict_markers([tmp_path])
    assert guards.main(["markers", str(bad)]) == 1
    assert guards.main(["markers", str(clean)]) == 0


def test_marker_like_text_inside_a_line_is_fine(tmp_path):
    path = tmp_path / "ok.py"
    path.write_text("x = '" + "<" * 7 + "'\n" + "<" * 8 + "\n")
    assert guards.find_conflict_markers([path]) == []


# ---------------------------------------------------------------- orientation

def test_orientation_direction():
    assert guards.assert_direction("essential", [-1.2, -0.9, -1.0], [0.0, 0.1, -0.1]) > 0.8
    with pytest.raises(guards.OrientationError, match="orientation"):
        guards.assert_direction("essential", [0.0, 0.1], [-1.0, -1.2])
    with pytest.raises(guards.OrientationError):
        guards.assert_direction("essential", [-1.0], [0.0], min_gap=2.0)
    with pytest.raises(guards.OrientationError, match="non-finite"):
        guards.assert_direction("essential", [float("nan")], [0.0])


def test_orientation_sign_and_axis():
    guards.assert_sign("rho", 0.3, "positive")
    with pytest.raises(guards.OrientationError):
        guards.assert_sign("rho", -0.3, "positive")
    ids = [f"ACH-{i:06d}" for i in range(20)]
    assert guards.assert_axis("rows", ids, r"ACH-\d{6}") == 1.0
    with pytest.raises(guards.OrientationError, match="transposed"):
        guards.assert_axis("rows", ["TP53", "KRAS", *ids[:2]], r"ACH-\d{6}")


def test_guard_cli_reports_refusals(capsys):
    assert guards.main(["disk", "--floor-gb", "1e12"]) == 2
    assert "refusing: disk floor" in capsys.readouterr().err


def test_guard_cli_runs_as_a_module(mining):
    done = subprocess.run([sys.executable, "-m", "bio_lab.campaign_kit.guards", "record", "--run", "r1",
                           "--bytes", "5", "--budget-gb", "1"], capture_output=True, text=True,
                          env=kit_env())
    assert done.returncode == 0, done.stderr
    assert guards.budget_totals() == {"r1": 5}
