"""A fetch killed mid-transfer: the budget is charged what moved, not what was reserved.

A local server sends a fixed number of bytes with no size hint, then stalls,
so the fetch reserves the whole remaining budget and blocks mid-stream. The
fetch then gets SIGTERM (directly, or through the slot runner) or SIGKILL.
"""

from __future__ import annotations

import http.server
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time

import pytest

from bio_lab.campaign_kit import guards
from bio_lab.campaign_kit.common import read_jsonl
from conftest import kit_env

SERVED = 2 << 20          # two full 1 MiB reads, then the third read blocks
BUDGET_GB = 5
RUN = "signal-run"

CHILD = '''
import sys
from bio_lab.campaign_kit import receipts
from bio_lab.campaign_kit.receipts import Expect
receipts.fetch(sys.argv[1], sys.argv[2], Expect(first_line_prefix="model_id"), run_id="%s",
               budget_gb=%d, floor_gb=0, retries=0, timeout=120)
''' % (RUN, BUDGET_GB)


class StallingServer:
    """Serves SERVED bytes with no Content-Length, then holds the connection open."""

    def __init__(self):
        self.release = threading.Event()
        body = b"model_id,gene,score\n"
        body += b"x" * (SERVED - len(body))
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "text/csv")
                self.end_headers()
                try:
                    self.wfile.write(body)
                    self.wfile.flush()
                except OSError:
                    return
                outer.release.wait(60)

            def log_message(self, *args):
                pass

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}/stall.csv"

    def close(self):
        self.release.set()
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture
def stalling():
    server = StallingServer()
    yield server
    server.close()


def wait_for(predicate, timeout=60.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


def parts(mining):
    directory = mining / "cache" / "kit-tmp"
    return sorted(directory.glob("*.part")) if directory.is_dir() else []


def reservations(mining):
    directory = mining / guards.RESERVATIONS_DIR
    return sorted(directory.glob("*.json")) if directory.is_dir() else []


def charges(mining):
    path = mining / "data-budget.jsonl"
    return [(r["kind"], r["bytes"]) for r in read_jsonl(path)] if path.exists() else []


def mid_transfer(mining):
    """True once the fetch has written every byte served and blocks for more."""
    found = parts(mining)
    return len(found) == 1 and found[0].stat().st_size == SERVED


def start_fetch(tmp_path, url, slot_pidfile=None):
    script = tmp_path / "child_fetch.py"
    script.write_text(CHILD)
    cmd = [sys.executable, str(script), url, str(tmp_path / "lane" / "stall.csv")]
    if slot_pidfile is not None:
        cmd = [sys.executable, "-m", "bio_lab.campaign_kit.slot", "run", "--pidfile",
               str(slot_pidfile), "--", *cmd]
    return subprocess.Popen(cmd, env=kit_env(), stderr=subprocess.PIPE)


def stop(proc):
    if proc.poll() is None:
        proc.kill()
    proc.wait(timeout=30)
    proc.stderr.close()


def assert_mid_transfer(mining, proc):
    assert wait_for(lambda: mid_transfer(mining) or proc.poll() is not None), "no transfer"
    assert proc.poll() is None, proc.stderr.read().decode(errors="replace")
    # the probe's case: no size hint, so the fetch holds far more than it has moved
    assert guards.reserved_totals()[RUN] > 100 * SERVED


def assert_charged_what_moved(mining, kind):
    moved = charges(mining)
    assert [k for k, _ in moved] == [kind]
    assert SERVED - (1 << 16) <= moved[0][1] <= SERVED
    assert reservations(mining) == [] and parts(mining) == []
    assert guards.reserved_totals() == {}
    left = guards.budget_remaining(RUN, BUDGET_GB)
    assert left == BUDGET_GB * guards.GB - moved[0][1]


# ---------------------------------------------------------------- SIGTERM

def test_sigterm_settles_the_bytes_moved(stalling, tmp_path, mining):
    proc = start_fetch(tmp_path, stalling.url)
    try:
        assert_mid_transfer(mining, proc)
        proc.send_signal(signal.SIGTERM)
        # the signal is sent again after settling, so the process still ends by SIGTERM
        assert proc.wait(timeout=60) == -signal.SIGTERM
        assert_charged_what_moved(mining, "download_partial")
    finally:
        stop(proc)


def test_sigterm_to_the_slot_runner_settles_the_bytes_moved(stalling, tmp_path, mining):
    (mining / "slots").mkdir()
    (mining / "slots" / "slot-0.lock").touch()
    pidfile = tmp_path / "runner.pid"
    runner = start_fetch(tmp_path, stalling.url, slot_pidfile=pidfile)
    try:
        assert_mid_transfer(mining, runner)
        assert wait_for(pidfile.exists)
        os.kill(int(pidfile.read_text()), signal.SIGTERM)
        assert runner.wait(timeout=60) != 0
        assert_charged_what_moved(mining, "download_partial")
        assert guards.slot_status() == {"slot-0": "free"}
    finally:
        stop(runner)


# ---------------------------------------------------------------- SIGKILL

def test_sigkill_is_charged_the_metered_bytes_not_the_reservation(stalling, tmp_path, mining):
    proc = start_fetch(tmp_path, stalling.url)
    try:
        assert_mid_transfer(mining, proc)
        proc.kill()
        assert proc.wait(timeout=60) == -signal.SIGKILL
        assert len(reservations(mining)) == 1 and len(parts(mining)) == 1
        # the next budget check settles the dead fetch and removes its partial file
        guards.check_budget(0, run_id=RUN, budget_gb=BUDGET_GB)
        assert_charged_what_moved(mining, "download_unsettled")
        entry = read_jsonl(mining / "data-budget.jsonl")[0]
        assert entry["reserved"] > 100 * SERVED and "metered" in entry["note"]
    finally:
        stop(proc)


# ---------------------------------------------------------------- stale reservations

def dead_pid():
    done = subprocess.run([sys.executable, "-c", "import os; print(os.getpid())"],
                          capture_output=True, text=True, check=True)
    return int(done.stdout)


def stale(mining, name, **fields):
    directory = mining / guards.RESERVATIONS_DIR
    directory.mkdir(exist_ok=True)
    body = {"run": RUN, "bytes": 10 ** 9, "pid": dead_pid(), "host": socket.gethostname(),
            "utc": "2026-09-26T00:00:00Z", **fields}
    (directory / f"{name}.json").write_text(json.dumps(body))


def kit_part(mining, pid, size):
    directory = mining / "cache" / "kit-tmp"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{'ab' * 32}.{pid}.part"
    path.write_bytes(b"x" * size)
    return path


@pytest.mark.parametrize("fields, charged", [
    ({"moved": 12345, "earlier": 0}, 12345),                  # count only, no partial file
    ({}, 10 ** 9),                                            # neither: counted in full
    ({"moved": 0, "earlier": 0, "part": "/nowhere/x.part"}, 0),   # unknown path is not read
])
def test_a_stale_reservation_is_charged_from_what_it_recorded(mining, fields, charged):
    stale(mining, "r", **fields)
    guards.check_budget(0, run_id=RUN, budget_gb=BUDGET_GB)
    assert charges(mining) == [("download_unsettled", charged)]
    assert reservations(mining) == []


def test_a_stale_reservation_takes_the_larger_of_its_count_and_its_partial_file(mining):
    pid = dead_pid()
    part = kit_part(mining, pid, 700)
    stale(mining, "a", moved=500, earlier=300, part=str(part))
    guards.check_budget(0, run_id=RUN, budget_gb=BUDGET_GB)
    assert charges(mining) == [("download_unsettled", 1000)] and not part.exists()
    part = kit_part(mining, pid, 10)
    stale(mining, "b", moved=5000, earlier=0, part=str(part))
    guards.check_budget(0, run_id=RUN, budget_gb=BUDGET_GB)
    assert charges(mining)[1] == ("download_unsettled", 5000) and not part.exists()


def test_orphaned_partial_files_of_dead_processes_are_deleted(mining):
    orphan = kit_part(mining, dead_pid(), 10)
    mine = kit_part(mining, os.getpid(), 10)
    other = mining / "cache" / "kit-tmp" / "not-a-kit-file.part"
    other.write_bytes(b"x")
    directory = mining / guards.RESERVATIONS_DIR
    directory.mkdir()
    half_written = directory / f".{'0' * 32}.json.{dead_pid()}.tmp"
    being_written = directory / f".{'1' * 32}.json.{os.getpid()}.tmp"
    half_written.write_text('{"run": ')
    being_written.write_text('{"run": ')
    guards.check_budget(0, run_id=RUN, budget_gb=BUDGET_GB)
    assert not orphan.exists() and mine.exists() and other.exists()
    assert not half_written.exists() and being_written.exists()
    assert charges(mining) == []


def test_a_live_reservation_is_left_alone(mining):
    # its partial file's name carries a dead pid, but the reservation's process is alive
    pid = dead_pid()
    part = mining / "cache" / "kit-tmp" / f"{'ab' * 32}.{pid}.part"
    held = guards.reserve(1000, run_id=RUN, budget_gb=BUDGET_GB, part=part)
    kit_part(mining, pid, 10)
    held.progress(400, 0, force=True)
    guards.check_budget(0, run_id=RUN, budget_gb=BUDGET_GB)
    assert charges(mining) == [] and part.exists()
    assert json.loads(held.path.read_text())["moved"] == 400
    guards.settle(held, [("download_partial", 400, {})])
    assert charges(mining) == [("download_partial", 400)]


def test_progress_is_written_at_most_every_few_megabytes_unless_forced(mining, monkeypatch):
    held = guards.reserve(10 ** 9, run_id=RUN, budget_gb=BUDGET_GB)
    moved = lambda: json.loads(held.path.read_text())["moved"]  # noqa: E731
    held.progress(10, 0, force=True)
    assert moved() == 10
    held.progress(20, 0)
    assert moved() == 10
    held.progress(10 + guards.PROGRESS_BYTES, 0)
    assert moved() == 10 + guards.PROGRESS_BYTES
    monkeypatch.setattr(guards, "PROGRESS_SECONDS", 0.0)
    held.progress(guards.PROGRESS_BYTES + 11, 0)
    assert moved() == guards.PROGRESS_BYTES + 11
    guards.settle(held, [])
    held.progress(1, 0, force=True)
    assert not held.path.exists()
    assert list((mining / guards.RESERVATIONS_DIR).iterdir()) == []


# ---------------------------------------------------------------- interruptible()

@pytest.fixture
def handlers():
    saved = {s: signal.getsignal(s) for s in guards.INTERRUPT_SIGNALS}
    yield
    for s, handler in saved.items():
        signal.signal(s, handler)


def test_interruptible_raises_then_sends_the_signal_again(handlers):
    seen = []
    signal.signal(signal.SIGTERM, lambda signum, frame: seen.append(signum))
    previous = signal.getsignal(signal.SIGTERM)
    with pytest.raises(guards.Interrupted) as error:
        with guards.interruptible():
            os.kill(os.getpid(), signal.SIGTERM)
            time.sleep(5)
    assert error.value.signum == signal.SIGTERM
    assert seen == [signal.SIGTERM]            # delivered again to the previous handler
    assert signal.getsignal(signal.SIGTERM) is previous


def test_interruptible_defers_a_signal_while_settling(handlers):
    seen = []
    signal.signal(signal.SIGTERM, lambda signum, frame: seen.append(signum))
    steps = []
    with pytest.raises(guards.Interrupted):
        with guards.interruptible() as interrupt:
            with interrupt.hold():
                os.kill(os.getpid(), signal.SIGTERM)
                time.sleep(0.05)
                steps.append("settled")
            steps.append("not reached")
    assert steps == ["settled"] and seen == [signal.SIGTERM]


def test_interruptible_leaves_ignored_signals_ignored(handlers):
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    with guards.interruptible():
        assert signal.getsignal(signal.SIGHUP) == signal.SIG_IGN
        os.kill(os.getpid(), signal.SIGHUP)
        time.sleep(0.05)
    assert signal.getsignal(signal.SIGHUP) == signal.SIG_IGN


def test_interruptible_does_nothing_outside_the_main_thread(handlers):
    before = {s: signal.getsignal(s) for s in guards.INTERRUPT_SIGNALS}
    inside = []

    def body():
        with guards.interruptible():
            inside.append({s: signal.getsignal(s) for s in guards.INTERRUPT_SIGNALS})

    thread = threading.Thread(target=body)
    thread.start()
    thread.join()
    assert inside == [before]
