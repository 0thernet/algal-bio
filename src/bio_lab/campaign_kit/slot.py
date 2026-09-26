"""Run a command inside a compute slot.

    python -m bio_lab.campaign_kit.slot run [--no-wait] [--timeout S] [--pidfile P] -- <cmd> ...
    python -m bio_lab.campaign_kit.slot status

From a vendored copy: PYTHONPATH=<campaign>/code python -m campaign_kit.slot run -- ...
The slot is an fcntl lock over $BIO_MINING_DIR/slots/slot-*.lock. The command
inherits the locked descriptor, so the slot stays busy until both the runner
and the command have exited: killing the runner, even with SIGKILL, never
frees the slot while the command still runs. SIGTERM, SIGINT and SIGHUP sent
to the runner (its pid is in --pidfile) are forwarded to the command. The
pidfile is written once the command has started and removed when the runner
exits normally.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import signal
import subprocess
import sys

from .common import KitError, die
from .guards import hold_slot, slot_status

FORWARDED = (signal.SIGTERM, signal.SIGINT, signal.SIGHUP)


def _write_pidfile(pidfile: Path) -> None:
    tmp = pidfile.with_name(f".{pidfile.name}.tmp-{os.getpid()}")
    tmp.write_text(f"{os.getpid()}\n", encoding="utf-8")
    os.replace(tmp, pidfile)


def _remove_pidfile(pidfile: Path) -> None:
    try:
        if pidfile.read_text(encoding="utf-8").strip() == str(os.getpid()):
            pidfile.unlink()
    except OSError:
        pass


def run(cmd: list[str], *, mining=None, wait: bool = True, timeout: float | None = None,
        pidfile: str | None = None) -> int:
    if not cmd:
        raise KitError("no command given after --")
    with hold_slot(mining, wait=wait, timeout=timeout) as (slot, handle):
        env = dict(os.environ, BIO_SLOT=slot)
        state = {"child": None, "pending": []}

        def forward(signum, _frame):
            child = state["child"]
            if child is None:
                state["pending"].append(signum)
            elif child.poll() is None:
                child.send_signal(signum)

        previous = {s: signal.signal(s, forward) for s in FORWARDED}
        path = Path(pidfile) if pidfile else None
        try:
            # the child keeps the locked descriptor: the slot frees only when both exit
            child = subprocess.Popen(cmd, env=env, pass_fds=(handle.fileno(),))
            state["child"] = child
            for signum in state["pending"]:
                if child.poll() is None:
                    child.send_signal(signum)
            if path is not None:
                _write_pidfile(path)
            return child.wait()
        finally:
            for s, handler in previous.items():
                signal.signal(s, handler)
            if path is not None:
                _remove_pidfile(path)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd: list[str] = []
    if "--" in argv:
        split = argv.index("--")
        argv, cmd = argv[:split], argv[split + 1:]
    parser = argparse.ArgumentParser(prog="campaign_kit.slot", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=("run", "status"))
    parser.add_argument("--mining-dir")
    parser.add_argument("--no-wait", action="store_true", help="fail at once when every slot is busy")
    parser.add_argument("--timeout", type=float, help="seconds to wait for a slot")
    parser.add_argument("--pidfile", help="write the runner's pid here while the command runs")
    args = parser.parse_args(argv)
    try:
        if args.action == "status":
            for name, state in slot_status(args.mining_dir).items():
                print(f"{name}: {state}")
            return 0
        return run(cmd, mining=args.mining_dir, wait=not args.no_wait, timeout=args.timeout,
                   pidfile=args.pidfile)
    except KitError as error:
        return die(error)


if __name__ == "__main__":
    sys.exit(main())
