"""Sealed files: permission lock and unlock of data/sealed, hash-verified opens.

    python -m bio_lab.campaign_kit.seal lock|unlock|status <campaign_dir>

lock() makes every sealed file unreadable (mode 000) and the directory
read-only (500); receipts.jsonl stays readable because it holds only urls,
sizes and hashes. writable() opens the directory for a fetch and locks it
again afterwards. open_sealed() is the only reader: it needs the active run
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

from .common import KitError, die, sha256_fileobj
from .receipts import RECEIPTS, receipts_for

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


def lock(campaign_dir) -> int:
    """Mode 000 for sealed files, 444 for receipts, 500 for directories. Returns the file count."""
    directory = _sealed_dir(campaign_dir)
    if not directory.is_dir():
        raise SealError("data/sealed/ does not exist")
    os.chmod(directory, 0o700)
    files = _files(directory)
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
    directory.mkdir(parents=True, exist_ok=True)
    os.chmod(directory, 0o700)
    receipts = directory / RECEIPTS
    if receipts.exists():
        os.chmod(receipts, 0o644)
    try:
        yield directory
    finally:
        lock(campaign_dir)


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
    os.chmod(path, 0o400)
    try:
        handle = open(path, "rb")
    finally:
        os.chmod(path, 0o000)
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
