"""The slot runner under signals: SIGKILL of the runner, SIGTERM forwarding, the pidfile."""

from __future__ import annotations

import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest

from bio_lab.campaign_kit import guards, slot
from conftest import kit_env

CHILD = r'''
import os, signal, sys, time
ready, release, marker = sys.argv[1:4]
def on_term(signum, frame):
    open(marker, "w").write("term")
    sys.exit(7)
signal.signal(signal.SIGTERM, on_term)
open(ready + ".tmp", "w").write(str(os.getpid()))
os.replace(ready + ".tmp", ready)
deadline = time.monotonic() + 30
while not os.path.exists(release) and time.monotonic() < deadline:
    time.sleep(0.02)
'''


def wait_for(predicate, timeout=15.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


@pytest.fixture
def one_slot(mining):
    (mining / "slots").mkdir()
    (mining / "slots" / "slot-0.lock").touch()
    return mining


def start_runner(tmp_path):
    ready, release, marker = (tmp_path / n for n in ("ready", "release", "marker"))
    pidfile = tmp_path / "runner.pid"
    runner = subprocess.Popen(
        [sys.executable, "-m", "bio_lab.campaign_kit.slot", "run", "--pidfile", str(pidfile),
         "--", sys.executable, "-c", CHILD, str(ready), str(release), str(marker)],
        env=kit_env())
    assert wait_for(ready.exists), "the command never started"
    return runner, int(ready.read_text()), pidfile, release, marker


def test_sigkill_of_the_runner_keeps_the_slot_until_the_command_exits(one_slot, tmp_path):
    runner, child, pidfile, release, _ = start_runner(tmp_path)
    try:
        assert pidfile.read_text().strip() == str(runner.pid)
        runner.kill()
        runner.wait(timeout=10)
        assert alive(child)
        # the command still holds the inherited lock descriptor
        assert guards.slot_status() == {"slot-0": "busy"}
        with pytest.raises(guards.SlotBusyError):
            with guards.compute_slot(wait=False):
                pass
        release.write_text("go")
        assert wait_for(lambda: guards.slot_status() == {"slot-0": "free"})
    finally:
        release.write_text("go")
        if alive(child):
            os.kill(child, signal.SIGKILL)
        if runner.poll() is None:
            runner.kill()
            runner.wait(timeout=10)


def test_sigterm_is_forwarded_and_the_pidfile_is_removed(one_slot, tmp_path):
    runner, child, pidfile, release, marker = start_runner(tmp_path)
    try:
        assert pidfile.read_text().strip() == str(runner.pid)
        runner.send_signal(signal.SIGTERM)
        assert runner.wait(timeout=20) == 7
        assert marker.read_text() == "term"
        assert not pidfile.exists()
        assert wait_for(lambda: not alive(child))
        assert guards.slot_status() == {"slot-0": "free"}
    finally:
        release.write_text("go")
        if alive(child):
            os.kill(child, signal.SIGKILL)
        if runner.poll() is None:
            runner.kill()
            runner.wait(timeout=10)


def test_the_pidfile_is_left_alone_when_it_names_another_process(one_slot, tmp_path):
    pidfile = tmp_path / "runner.pid"
    code = f"open({str(pidfile)!r}, 'w').write('1\\n')"
    assert slot.run([sys.executable, "-c", code], pidfile=str(pidfile)) == 0
    assert pidfile.read_text() == "1\n"
    pidfile.unlink()
    assert slot.run([sys.executable, "-c", "pass"], pidfile=str(pidfile)) == 0
    assert not pidfile.exists()
    assert not any(Path(tmp_path).glob(".runner.pid.tmp-*"))


def test_the_command_sees_its_slot_and_an_empty_command_is_refused(one_slot, tmp_path):
    out = tmp_path / "env.txt"
    code = f"import os; open({str(out)!r}, 'w').write(os.environ['BIO_SLOT'])"
    assert slot.run([sys.executable, "-c", code]) == 0
    assert out.read_text() == "slot-0"
    assert slot.main(["run"]) == 2
