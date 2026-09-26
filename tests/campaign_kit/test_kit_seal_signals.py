"""An interrupted holdout fetch never leaves a readable sealed file behind.

A scaffolded campaign's fetch_holdout.py (the template, unchanged apart from
its SOURCES) fetches two sealed files from a local server. The first arrives
whole; the second stalls mid-stream. The fetch is then stopped by SIGTERM,
by SIGTERM to the slot runner's pidfile pid (the documented cleanup) or by
SIGKILL. seal.status must report no readable sealed file, and, when the
signal could be caught, a locked directory.
"""

from __future__ import annotations

import http.server
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

import pytest

from bio_lab.campaign_kit import barrier, freeze, guards, receipts, seal
from bio_lab.campaign_kit.common import read_jsonl
from conftest import barrier_doc, frozen_entry, kit_env, make_campaign

REPO = Path(__file__).resolve().parents[2]
NAME = "demo-lane-2026-09-26"
SERVED = 2 << 20
FIRST = b"model_id,gene,score\nM1,G1,0.5\n"
RUN = "seal-signal-run"

SOURCES = '''SOURCES = {
    "a-first.csv": (os.environ["KIT_TEST_URL"] + "/first.csv",
                    Expect(first_line_prefix="model_id")),
    "b-second.csv": (os.environ["KIT_TEST_URL"] + "/second.csv",
                     Expect(first_line_prefix="model_id")),
}
'''

# Runs the template as __main__ with the disk floor at 0, so the test does not
# depend on the free space of the machine; nothing else is changed.
LAUNCHER = '''import runpy
import sys

sys.path.insert(0, sys.argv[1])
from campaign_kit import receipts

_fetch = receipts.fetch
receipts.fetch = lambda *args, **kwargs: _fetch(*args, floor_gb=0, **kwargs)
script = sys.argv[1] + "/fetch_holdout.py"
sys.argv = [script, *sys.argv[2:]]
runpy.run_path(script, run_name="__main__")
'''


class TwoFileServer:
    """/first.csv whole, with a Content-Length; /second.csv: SERVED bytes, then a stall."""

    def __init__(self):
        self.release = threading.Event()
        second = b"model_id,gene,score\n" + b"x" * (SERVED - 20)
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "text/csv")
                if self.path == "/first.csv":
                    self.send_header("Content-Length", str(len(FIRST)))
                    self.end_headers()
                    self.wfile.write(FIRST)
                    return
                self.end_headers()
                try:
                    self.wfile.write(second)
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
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def close(self):
        self.release.set()
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture
def server():
    started = TwoFileServer()
    yield started
    started.close()


def load_new_campaign():
    spec = importlib.util.spec_from_file_location("new_campaign", REPO / "scripts" / "new_campaign.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def lane(tmp_path):
    """(campaign dir, freeze sha): scaffolded, SOURCES filled, frozen, barrier cleared."""
    card = tmp_path / "lane-card.json"
    card.write_text(json.dumps({"id": "S01", "slug": NAME}) + "\n")
    target = tmp_path / "research" / f"biology-{NAME}"
    load_new_campaign().scaffold(NAME, target, card)
    (target / "registration" / "protocol.json").write_text(
        json.dumps({"schema": "bio.protocol.v1", "constants": {"ALPHA": 0.05}}) + "\n")
    script = target / "code" / "fetch_holdout.py"
    text = script.read_text()
    assert text.count("SOURCES = {}\n") == 1
    script.write_text(text.replace("SOURCES = {}\n", SOURCES))
    _, sha = freeze.build(target)
    barrier.write(target, barrier_doc(["S01", "S02"], [frozen_entry("S01", NAME, sha)],
                                      released=["S02"]))
    yield target, sha
    if (target / seal.SEALED).is_dir():
        seal.unlock(target)            # let pytest remove the synthetic tree


def start(tmp_path, target, sha, url, mining, pidfile=None):
    launcher = tmp_path / "launch_fetch.py"
    launcher.write_text(LAUNCHER)
    cmd = [sys.executable, str(launcher), str(target / "code"), "--freeze-sha256", sha]
    if pidfile is not None:
        cmd = [sys.executable, "-m", "campaign_kit.slot", "run", "--pidfile", str(pidfile),
               "--", *cmd]
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env.update(PYTHONDONTWRITEBYTECODE="1", KIT_TEST_URL=url, BIO_MINING_DIR=str(mining),
               BIO_RUN_ID=RUN, BIO_DATA_BUDGET_GB="5")
    if pidfile is not None:
        env["PYTHONPATH"] = str(target / "code")        # the vendored slot runner
    return subprocess.Popen(cmd, env=env, cwd=target, stderr=subprocess.PIPE)


def wait_for(predicate, timeout=60.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


def second_file_mid_transfer(mining):
    directory = mining / "cache" / "kit-tmp"
    found = sorted(directory.glob("*.part")) if directory.is_dir() else []
    return len(found) == 1 and found[0].stat().st_size == SERVED


def assert_mid_second_file(target, mining, proc):
    assert wait_for(lambda: second_file_mid_transfer(mining) or proc.poll() is not None)
    assert proc.poll() is None, proc.stderr.read().decode(errors="replace")
    # the first file is placed and receipted; the second is still streaming
    state = seal.status(target)
    assert state["sealed_files"] == 1 and state["readable_sealed_files"] == 0, state


def stop(proc):
    if proc.poll() is None:
        proc.kill()
    proc.wait(timeout=30)
    proc.stderr.close()


def assert_sealed_and_settled(target, mining, locked):
    state = seal.status(target)
    assert state["sealed_files"] == 1 and state["readable_sealed_files"] == 0, state
    if locked:
        assert state["locked"] is True and state["dir_mode"] == "0o500", state
    guards.check_budget(0, run_id=RUN, budget_gb=5)
    assert guards.reserved_totals() == {}
    kinds = [r["kind"] for r in read_jsonl(mining / "data-budget.jsonl")]
    assert kinds[0] == "download" and len(kinds) == 2


def test_sigterm_during_the_second_file_leaves_data_sealed_locked(server, lane, tmp_path, mining):
    target, sha = lane
    proc = start(tmp_path, target, sha, server.url, mining)
    try:
        assert_mid_second_file(target, mining, proc)
        proc.send_signal(signal.SIGTERM)
        assert proc.wait(timeout=60) == -signal.SIGTERM
        assert_sealed_and_settled(target, mining, locked=True)
    finally:
        stop(proc)


def test_sigterm_to_the_slot_runner_leaves_data_sealed_locked(server, lane, tmp_path, mining):
    target, sha = lane
    (mining / "slots").mkdir()
    (mining / "slots" / "slot-0.lock").touch()
    pidfile = tmp_path / "runner.pid"
    runner = start(tmp_path, target, sha, server.url, mining, pidfile=pidfile)
    try:
        assert_mid_second_file(target, mining, runner)
        assert wait_for(pidfile.exists)
        os.kill(int(pidfile.read_text()), signal.SIGTERM)
        assert runner.wait(timeout=60) != 0
        assert_sealed_and_settled(target, mining, locked=True)
    finally:
        stop(runner)


def test_sigkill_during_the_second_file_leaves_no_readable_sealed_file(server, lane, tmp_path,
                                                                       mining):
    target, sha = lane
    proc = start(tmp_path, target, sha, server.url, mining)
    try:
        assert_mid_second_file(target, mining, proc)
        proc.kill()
        assert proc.wait(timeout=60) == -signal.SIGKILL
        assert_sealed_and_settled(target, mining, locked=False)
    finally:
        stop(proc)


# ---------------------------------------------------------------- SIGKILL around a sealed copy

PLACE = '''
import hashlib
import os
import signal
import sys
from pathlib import Path

from bio_lab.campaign_kit import receipts

blob, dest, point = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
data = blob.read_bytes()


def die():
    os.kill(os.getpid(), signal.SIGKILL)


if point == "mid-copy":
    receipts.COPY_CHUNK = 1 << 16
    real = hashlib.sha256

    class Dying:
        def __init__(self):
            self.inner, self.calls = real(), 0

        def update(self, chunk):
            self.calls += 1
            if self.calls == 3:
                die()
            self.inner.update(chunk)

        def hexdigest(self):
            return self.inner.hexdigest()

    receipts.hashlib = type("hashlib", (), {"sha256": staticmethod(Dying)})
elif point == "before-rename":
    os.replace = lambda *args, **kwargs: die()
elif point == "after-rename":
    real_replace = os.replace

    def replace(*args, **kwargs):
        real_replace(*args, **kwargs)
        die()

    os.replace = replace
receipts._place(blob, hashlib.sha256(data).hexdigest(), len(data), dest, 0)
'''


@pytest.mark.parametrize("point, placed", [("mid-copy", 0), ("before-rename", 0),
                                           ("after-rename", 1)])
def test_sigkill_during_a_sealed_copy_leaves_no_readable_file(tmp_path, point, placed):
    campaign = make_campaign(tmp_path / "research")
    blob = tmp_path / "blob.csv"
    blob.write_bytes(b"model_id,gene,score\n" + b"x" * (1 << 18))
    os.chmod(blob, 0o444)                     # like a cache blob, which a clone would copy
    script = tmp_path / "place.py"
    script.write_text(PLACE)
    dest = campaign / "data" / "sealed" / "holdout.csv"
    done = subprocess.run([sys.executable, str(script), str(blob), str(dest), point],
                          env=kit_env(), capture_output=True, timeout=120)
    assert done.returncode == -signal.SIGKILL, done.stderr.decode(errors="replace")
    state = seal.status(campaign)
    # the temporary file (or the placed file) exists, and nothing has a read bit
    assert state["sealed_files"] == 1 and state["readable_sealed_files"] == 0, state
    # the next lock deletes the dead process's temporary file
    seal.lock(campaign)
    state = seal.status(campaign)
    assert state["sealed_files"] == placed and state["locked"] is True, state
    seal.unlock(campaign)


def test_a_sealed_copy_is_never_readable_while_written(tmp_path, monkeypatch):
    campaign = make_campaign(tmp_path / "research")
    blob = tmp_path / "blob.csv"
    blob.write_bytes(b"model_id,gene,score\n" + b"x" * (1 << 18))
    dest = campaign / "data" / "sealed" / "holdout.csv"
    modes = []
    monkeypatch.setattr(receipts, "COPY_CHUNK", 1 << 16)
    real = receipts.hashlib.sha256

    class Watching:
        def __init__(self):
            self.inner = real()

        def update(self, chunk):
            modes.append(receipts.sealed_part_path(dest).stat().st_mode & 0o777)
            self.inner.update(chunk)

        def hexdigest(self):
            return self.inner.hexdigest()

    monkeypatch.setattr(receipts, "hashlib", type("hashlib", (), {"sha256": staticmethod(Watching)}))
    data = blob.read_bytes()
    method, prior = receipts._place(blob, real(data).hexdigest(), len(data), dest, 0)
    assert method == "sealed-copy" and prior is None
    assert len(modes) == 5 and set(modes) == {0}
    assert dest.stat().st_mode & 0o777 == 0 and seal.status(campaign)["readable_sealed_files"] == 0
    seal.unlock(campaign)


def test_a_sealed_copy_that_does_not_match_is_removed(tmp_path):
    campaign = make_campaign(tmp_path / "research")
    blob = tmp_path / "blob.csv"
    blob.write_bytes(b"model_id\n1\n")
    dest = campaign / "data" / "sealed" / "holdout.csv"
    with pytest.raises(receipts.FetchError, match="did not arrive intact"):
        receipts._place(blob, "0" * 64, 11, dest, 0)
    assert list(dest.parent.iterdir()) == []
