"""Single-run guard, append-only run ledger, and hash-verified sealed reads."""

from __future__ import annotations

import hashlib
import os
import signal
import time

import pytest

from bio_lab.campaign_kit import guards, runguard, seal
from bio_lab.campaign_kit.common import KitError, append_jsonl, file_lock, read_jsonl
from conftest import make_campaign, write

DATA = b"model_id,score\nM1,0.5\n"


def place_sealed(campaign, name="holdout.csv", data=DATA):
    """Put a synthetic sealed file and its receipt in place, then lock the directory."""
    with seal.writable(campaign) as directory:
        (directory / name).write_bytes(data)
        append_jsonl(directory / "receipts.jsonl",
                     {"file": name, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
    return campaign / "data" / "sealed" / name


def events(campaign):
    return [r["event"] for r in runguard.history(campaign)]


# ---------------------------------------------------------------- run guard

def test_first_run_is_recorded(frozen_campaign):
    campaign, lane_id, sha, _ = frozen_campaign
    with runguard.run(campaign, lane_id=lane_id) as active:
        out = write(campaign / "results" / "confirmation.summary.json", '{"label": "x"}\n')
        record = active.finish("SUPPORTED", outputs=["results/confirmation.summary.json"])
    assert record["outputs"] == {"results/confirmation.summary.json":
                                 hashlib.sha256(out.read_bytes()).hexdigest()}
    start = runguard.history(campaign)[0]
    assert start["freeze_sha256"] == sha and start["erratum"] is None and start["run"] == 1
    assert events(campaign) == ["start", "finish"]


def test_rerun_is_refused_without_an_erratum(frozen_campaign):
    campaign, lane_id, _, _ = frozen_campaign
    with runguard.run(campaign, lane_id=lane_id) as active:
        active.finish("SUPPORTED")
    with pytest.raises(runguard.RunGuardError, match="already run"):
        with runguard.run(campaign, lane_id=lane_id):
            pass
    assert events(campaign) == ["start", "finish"]


def test_rerun_is_refused_when_outputs_exist_without_a_ledger(frozen_campaign):
    campaign, lane_id, _, _ = frozen_campaign
    write(campaign / "results" / "confirmation.summary.json", "{}\n")
    with pytest.raises(runguard.RunGuardError, match="already run"):
        with runguard.run(campaign, lane_id=lane_id):
            pass


def test_rerun_with_an_erratum_once(frozen_campaign):
    campaign, lane_id, _, _ = frozen_campaign
    with runguard.run(campaign, lane_id=lane_id) as active:
        active.finish("SUPPORTED")
    with pytest.raises(runguard.RunGuardError, match="does not exist or is empty"):
        with runguard.run(campaign, lane_id=lane_id, erratum="errata/E1.md"):
            pass
    with pytest.raises(runguard.RunGuardError, match="under errata/"):
        with runguard.run(campaign, lane_id=lane_id, erratum="notes/E1.md"):
            pass
    write(campaign / "errata" / "E1.md", "The join key was wrong; rerun under the same rule.\n")
    with runguard.run(campaign, lane_id=lane_id, erratum="errata/E1.md") as active:
        active.finish("SUPPORTED")
    with pytest.raises(runguard.RunGuardError, match="already justified"):
        with runguard.run(campaign, lane_id=lane_id, erratum="errata/E1.md"):
            pass
    records = runguard.history(campaign)
    assert [r["run"] for r in records if r["event"] == "start"] == [1, 2]
    assert records[2]["erratum"] == "errata/E1.md" and records[2]["erratum_sha256"]


def test_erratum_on_a_first_run_is_refused(frozen_campaign):
    campaign, lane_id, _, _ = frozen_campaign
    write(campaign / "errata" / "E1.md", "early\n")
    with pytest.raises(runguard.RunGuardError, match="only for reruns"):
        with runguard.run(campaign, lane_id=lane_id, erratum="errata/E1.md"):
            pass
    assert runguard.history(campaign) == []


def test_crash_records_the_type_only_and_counts_as_a_run(frozen_campaign):
    campaign, lane_id, _, _ = frozen_campaign
    with pytest.raises(ValueError):
        with runguard.run(campaign, lane_id=lane_id):
            raise ValueError("sealed value 0.123 leaked into a message")
    crash = runguard.history(campaign)[-1]
    assert crash == {"event": "crash", "run": 1, "utc": crash["utc"], "error": "ValueError"}
    assert "0.123" not in (campaign / runguard.LEDGER).read_text()
    with pytest.raises(runguard.RunGuardError, match="already run"):
        with runguard.run(campaign, lane_id=lane_id):
            pass


def test_a_run_that_never_finishes_is_marked_incomplete(frozen_campaign):
    campaign, lane_id, _, _ = frozen_campaign
    with runguard.run(campaign, lane_id=lane_id):
        pass
    assert events(campaign) == ["start", "incomplete"]


def test_run_guard_requires_the_barrier_and_the_freeze(tmp_path, frozen_campaign):
    campaign = make_campaign(tmp_path / "x")
    with pytest.raises(KitError, match="freeze first"):
        with runguard.run(campaign, lane_id="S01"):
            pass
    campaign, lane_id, _, _ = frozen_campaign
    with pytest.raises(KitError, match="another group"):
        with runguard.run(campaign, lane_id="S05"):
            pass
    (campaign / "tests" / "test_demo.py").write_text("changed\n")
    with pytest.raises(KitError, match="freeze verify failed"):
        with runguard.run(campaign, lane_id=lane_id):
            pass
    assert runguard.history(campaign) == []


def test_only_one_process_holds_the_run(frozen_campaign):
    campaign, lane_id, _, _ = frozen_campaign
    with file_lock(campaign / runguard.LOCK):
        with pytest.raises(KitError, match="lock is held"):
            with runguard.run(campaign, lane_id=lane_id):
                pass


def test_the_ledger_is_never_rewritten(frozen_campaign):
    campaign, lane_id, _, _ = frozen_campaign
    with runguard.run(campaign, lane_id=lane_id) as active:
        active.finish("SUPPORTED")
    before = (campaign / runguard.LEDGER).read_bytes()
    write(campaign / "errata" / "E1.md", "reason\n")
    with runguard.run(campaign, lane_id=lane_id, erratum="errata/E1.md") as active:
        active.finish("SUPPORTED")
    assert (campaign / runguard.LEDGER).read_bytes().startswith(before)


# ---------------------------------------------------------------- seal

def test_seal_locks_and_reports_counts_only(frozen_campaign):
    campaign, _, _, _ = frozen_campaign
    path = place_sealed(campaign)
    state = seal.status(campaign)
    assert state["locked"] and state["sealed_files"] == 1 and state["files"] == 2
    assert "holdout.csv" not in repr(state)
    assert (path.stat().st_mode & 0o777) == 0
    assert ((campaign / "data" / "sealed").stat().st_mode & 0o777) == 0o500
    if os.geteuid() != 0:
        with pytest.raises(PermissionError):
            path.read_bytes()


def test_open_sealed_needs_an_active_run(frozen_campaign):
    campaign, lane_id, _, _ = frozen_campaign
    place_sealed(campaign)
    with pytest.raises(seal.SealError, match="active runguard run"):
        seal.open_sealed(campaign, "holdout.csv", None)
    with runguard.run(campaign, lane_id=lane_id) as active:
        with seal.open_sealed(campaign, "holdout.csv", active) as handle:
            assert handle.read() == DATA
        record = active.finish("SUPPORTED")
    assert record["sealed_opened"] == {"holdout.csv": hashlib.sha256(DATA).hexdigest()}
    assert (campaign / "data" / "sealed" / "holdout.csv").stat().st_mode & 0o777 == 0
    with pytest.raises(seal.SealError, match="active runguard run"):
        seal.open_sealed(campaign, "holdout.csv", active)


def test_open_sealed_refuses_a_changed_file(frozen_campaign):
    campaign, lane_id, _, _ = frozen_campaign
    path = place_sealed(campaign)
    seal.unlock(campaign)
    path.chmod(0o600)
    path.write_bytes(DATA.replace(b"0.5", b"0.7"))
    seal.lock(campaign)
    with runguard.run(campaign, lane_id=lane_id) as active:
        with pytest.raises(seal.SealError, match="does not match its receipt"):
            seal.open_sealed(campaign, "holdout.csv", active)
        with pytest.raises(seal.SealError, match="no single receipt"):
            seal.open_sealed(campaign, "missing.csv", active)
        with pytest.raises(seal.SealError, match="plain sealed file name"):
            seal.open_sealed(campaign, "receipts.jsonl", active)


def test_seal_cli(frozen_campaign, capsys):
    campaign, _, _, _ = frozen_campaign
    place_sealed(campaign)
    assert seal.main(["status", str(campaign)]) == 0
    assert "holdout" not in capsys.readouterr().out
    assert seal.main(["unlock", str(campaign)]) == 0
    assert seal.main(["lock", str(campaign)]) == 0
    assert read_jsonl(campaign / "data" / "sealed" / "receipts.jsonl")[0]["file"] == "holdout.csv"


# ---------------------------------------------------------------- signals

@pytest.fixture
def saved_handlers():
    saved = {s: signal.getsignal(s) for s in guards.INTERRUPT_SIGNALS}
    yield
    for s, handler in saved.items():
        signal.signal(s, handler)


def test_writable_locks_before_a_signal_is_sent_again(frozen_campaign, saved_handlers):
    campaign, _, _, _ = frozen_campaign
    seen = []
    signal.signal(signal.SIGTERM, lambda signum, frame: seen.append(seal.status(campaign)["locked"]))
    with pytest.raises(guards.Interrupted):
        with seal.writable(campaign) as directory:
            (directory / "holdout.csv").write_bytes(DATA)
            os.kill(os.getpid(), signal.SIGTERM)
            time.sleep(5)
    # the previous handler ran once, after the directory was locked again
    assert seen == [True]
    assert seal.status(campaign)["readable_sealed_files"] == 0


def test_open_sealed_restores_mode_000_before_a_signal_is_sent_again(frozen_campaign,
                                                                    saved_handlers, monkeypatch):
    campaign, lane_id, _, _ = frozen_campaign
    path = place_sealed(campaign)
    seen, opened = [], []
    signal.signal(signal.SIGTERM, lambda signum, frame: seen.append(path.stat().st_mode & 0o777))

    def signalled_open(*args, **kwargs):
        os.kill(os.getpid(), signal.SIGTERM)
        handle = open(*args, **kwargs)
        opened.append(handle)
        return handle

    monkeypatch.setattr(seal, "open", signalled_open, raising=False)
    with runguard.run(campaign, lane_id=lane_id) as active:
        with pytest.raises(guards.Interrupted):
            seal.open_sealed(campaign, "holdout.csv", active)
        active.finish("SUPPORTED")
    assert seen == [0] and path.stat().st_mode & 0o777 == 0
    assert len(opened) == 1 and opened[0].closed
