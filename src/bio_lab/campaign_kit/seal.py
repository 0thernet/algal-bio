"""Sealed files: permission lock and unlock of data/sealed, hash-verified opens.

    python -m bio_lab.campaign_kit.seal lock|unlock|status <campaign_dir>

lock() makes every sealed file unreadable (mode 000) and the directory
read-only (500); receipts.jsonl stays readable because it holds only urls,
sizes and hashes. writable() opens the directory for a fetch and locks it
again afterwards, also when SIGTERM, SIGHUP or SIGINT stops the fetch.
fetch and import_local write a sealed file through a temporary file created
with mode 000, so it never has a read bit, even under SIGKILL. One SIGKILL
window remains: open_sealed's brief mode 400. writable() and runguard.run()
therefore lock the directory again on entry, so a file left readable there is
locked before the next fetch or run; lock() also deletes the temporary files
of dead processes. open_sealed() is the only reader: it needs the active run
handle from runguard (so only a guarded confirm.py run can call it), checks
the file against its receipt, opens it, restores mode 000 at once and
verifies the sha256 on the open descriptor before returning it.

Permissions are a speed bump against accidental reads by the same user, not
access control; the freeze, the barrier and the run ledger are the evidence.
"""

from __future__ import annotations

import argparse
import contextlib
import os
from pathlib import Path
import stat
import sys

from . import guards
from .common import KitError, die, sha256_fileobj
from .receipts import RECEIPTS, SEALED_PART_RE, receipts_for

SEALED = "data/sealed"


class SealError(KitError):
    pass


def _sealed_dir(campaign_dir) -> Path:
    return Path(campaign_dir).resolve() / SEALED


def _files(directory: Path) -> list[Path]:
    out = []
    for root, dirs, names in os.walk(directory):
        for d in dirs:
            os.chmod(Path(root) / d, 0o700)
        out.extend(Path(root) / n for n in names)
    return out


def _drop_stale_parts(files: list[Path]) -> list[Path]:
    """Delete the temporary files of sealed copies whose process is gone."""
    kept = []
    for path in files:
        match = SEALED_PART_RE.match(path.name)
        if match and not path.is_symlink() and not guards._pid_alive(int(match.group(1))):
            path.unlink(missing_ok=True)
        else:
            kept.append(path)
    return kept


def lock(campaign_dir) -> int:
    """Mode 000 for sealed files, 444 for receipts, 500 for directories. Returns the file count.

    Temporary files of sealed copies left by dead processes are deleted first."""
    directory = _sealed_dir(campaign_dir)
    if not directory.is_dir():
        raise SealError("data/sealed/ does not exist")
    os.chmod(directory, 0o700)
    files = _drop_stale_parts(_files(directory))
    for path in files:
        if path.is_symlink():
            raise SealError("data/sealed/ holds a symlink; refusing to lock through it")
        os.chmod(path, 0o444 if path.name == RECEIPTS else 0o000)
    for root, dirs, _ in os.walk(directory, topdown=False):
        for d in dirs:
            os.chmod(Path(root) / d, 0o500)
    os.chmod(directory, 0o500)
    return len(files)


def unlock(campaign_dir) -> int:
    """Owner read access again (files 400, directories 700), for cleanup only."""
    directory = _sealed_dir(campaign_dir)
    if not directory.is_dir():
        raise SealError("data/sealed/ does not exist")
    os.chmod(directory, 0o700)
    files = _files(directory)
    for path in files:
        os.chmod(path, 0o644 if path.name == RECEIPTS else 0o400)
    return len(files)


@contextlib.contextmanager
def writable(campaign_dir):
    """Let a fetch add files to data/sealed/, then lock it again whatever happens."""
    directory = _sealed_dir(campaign_dir)
    # SIGTERM, SIGHUP or SIGINT inside the block raises guards.Interrupted, so this
    # finally locks the directory before the signal is sent again (see
    # guards.interruptible); the lock itself is never cut short by a signal.
    with guards.interruptible() as interrupt:
        with interrupt.hold():
            directory.mkdir(parents=True, exist_ok=True)
            # a process killed while a sealed file was readable (open_sealed's
            # mode 400) left it so; lock everything before opening the directory
            lock(campaign_dir)
        try:
            with interrupt.hold():
                os.chmod(directory, 0o700)
                receipts = directory / RECEIPTS
                if receipts.exists():
                    os.chmod(receipts, 0o644)
            yield directory
        finally:
            with interrupt.hold():
                lock(campaign_dir)


def relock_if_open(campaign_dir) -> bool:
    """Lock data/sealed/ again when it exists and is not locked. True if it relocked."""
    directory = _sealed_dir(campaign_dir)
    if not directory.is_dir() or status(campaign_dir)["locked"]:
        return False
    lock(campaign_dir)
    return True


def status(campaign_dir) -> dict:
    """Counts and modes only; never names or contents."""
    directory = _sealed_dir(campaign_dir)
    if not directory.is_dir():
        return {"exists": False}
    mode = stat.S_IMODE(directory.stat().st_mode)
    files = sealed_files = open_files = 0
    for root, _, names in os.walk(directory):
        for name in names:
            files += 1
            if name == RECEIPTS:
                continue
            sealed_files += 1
            if stat.S_IMODE((Path(root) / name).lstat().st_mode) & 0o444:
                open_files += 1
    return {"exists": True, "dir_mode": oct(mode), "files": files, "sealed_files": sealed_files,
            "readable_sealed_files": open_files, "locked": mode & 0o200 == 0 and open_files == 0}


def open_sealed(campaign_dir, name: str, run):
    """Open data/sealed/<name> for a guarded confirm run, verified against its receipt.

    Returns a binary file object positioned at the start.
    """
    from .runguard import ActiveRun
    campaign_dir = Path(campaign_dir).resolve()
    if not isinstance(run, ActiveRun) or not run.active or run.campaign_dir != campaign_dir:
        raise SealError("sealed files open only inside this campaign's active runguard run")
    if not isinstance(name, str) or "/" in name or name.startswith(".") or name == RECEIPTS:
        raise SealError("name must be a plain sealed file name")
    directory = campaign_dir / SEALED
    matches = [r for r in receipts_for(directory) if r.get("file") == name]
    shas = {r.get("sha256") for r in matches}
    if len(shas) != 1:
        raise SealError(f"{name} has no single receipt in data/sealed/receipts.jsonl")
    want = shas.pop()
    path = directory / name
    if path.is_symlink() or not path.is_file():
        raise SealError(f"{name} is not a regular sealed file")
    handle = None
    try:
        # a signal here is deferred until mode 000 is back (see guards.interruptible)
        with guards.interruptible() as interrupt, interrupt.hold():
            os.chmod(path, 0o400)
            try:
                handle = open(path, "rb")
            finally:
                os.chmod(path, 0o000)
    except BaseException:
        if handle is not None:
            handle.close()
        raise
    try:
        if sha256_fileobj(handle) != want:
            raise SealError(f"{name} does not match its receipt; the sealed copy changed")
        handle.seek(0)
    except BaseException:
        handle.close()
        raise
    run.note_open(name, want)
    return handle


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="campaign_kit.seal", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=("lock", "unlock", "status"))
    parser.add_argument("campaign_dir")
    args = parser.parse_args(argv)
    try:
        if args.action == "lock":
            print(f"locked {lock(args.campaign_dir)} files")
        elif args.action == "unlock":
            print(f"unlocked {unlock(args.campaign_dir)} files")
        else:
            print(status(args.campaign_dir))
    except KitError as error:
        return die(error)
    return 0


if __name__ == "__main__":
    sys.exit(main())
