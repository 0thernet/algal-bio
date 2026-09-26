"""Run a command inside a compute slot.

    python -m bio_lab.campaign_kit.slot run [--no-wait] [--timeout S] [--pidfile P] -- <cmd> ...
    python -m bio_lab.campaign_kit.slot status

From a vendored copy: PYTHONPATH=<campaign>/code python -m campaign_kit.slot run -- ...
The slot is an fcntl lock over $BIO_MINING_DIR/slots/slot-*.lock, held until
the command exits. SIGTERM, SIGINT and SIGHUP are forwarded to the command, so
killing the runner (its pid is in --pidfile) stops the job too.
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys

from .common import KitError, die
from .guards import compute_slot, slot_status


def run(cmd: list[str], *, mining=None, wait: bool = True, timeout: float | None = None,
        pidfile: str | None = None) -> int:
    if not cmd:
        raise KitError("no command given after --")
    with compute_slot(mining, wait=wait, timeout=timeout) as slot:
        env = dict(os.environ, BIO_SLOT=slot)
        child = subprocess.Popen(cmd, env=env)
        if pidfile:
            with open(pidfile, "w") as handle:
                handle.write(f"{os.getpid()}\n")

        def forward(signum, _frame):
            if child.poll() is None:
                child.send_signal(signum)

        previous = {s: signal.signal(s, forward) for s in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP)}
        try:
            return child.wait()
        finally:
            for s, handler in previous.items():
                signal.signal(s, handler)


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
    parser.add_argument("--pidfile", help="write the runner's pid here")
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
