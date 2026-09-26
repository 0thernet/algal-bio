"""Machine guards: disk floor, data budget, compute slots, conflict markers, orientation.

Units: the disk floor is in GiB (2**30 bytes), matching df -g; the data budget
is in GB (10**9 bytes), so both round toward refusing.
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import json
import math
import os
from pathlib import Path
import re
import shutil
import socket
import statistics
import sys
import time
import uuid

from .common import (KitError, append_jsonl, die, file_lock, mining_dir, read_jsonl,
                     try_lock, utc_now, RUN_ENV, BUDGET_ENV)

GIB = 1 << 30
GB = 10 ** 9
DEFAULT_FLOOR_GB = 10.0
BUDGET_FILE = "data-budget.jsonl"
RESERVATIONS_DIR = "data-budget.reservations"
SLOTS_DIR = "slots"
# download: a validated file; download_rejected: a body that failed validation;
# download_partial: bytes of a transfer that dropped or passed its cap;
# download_unsettled: a reservation whose fetch died before recording.
TRANSFER_KINDS = ("download", "download_rejected", "download_partial", "download_unsettled")


class DiskFloorError(KitError):
    pass


class BudgetError(KitError):
    pass


class SlotBusyError(KitError):
    pass


class OrientationError(KitError):
    pass


# ---------------------------------------------------------------- disk floor

def disk_free_bytes(path: os.PathLike | str, usage=shutil.disk_usage) -> int:
    probe = Path(os.path.abspath(path))
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    return int(usage(probe).free)


def require_disk_floor(path: os.PathLike | str, need_bytes: int = 0,
                       floor_gb: float = DEFAULT_FLOOR_GB, usage=shutil.disk_usage) -> int:
    """Refuse unless free space stays above the floor after writing need_bytes.

    Returns the number of bytes that may still be written above the floor.
    """
    if need_bytes < 0:
        raise KitError("need_bytes must not be negative")
    free = disk_free_bytes(path, usage)
    floor = int(floor_gb * GIB)
    headroom = free - floor
    if headroom < need_bytes:
        raise DiskFloorError(
            f"disk floor: {free / GIB:.1f} GiB free, {need_bytes / GIB:.2f} GiB needed, "
            f"floor {floor_gb:g} GiB; free space first")
    return headroom


# ---------------------------------------------------------------- data budget

def _budget_path(mining) -> Path:
    return mining_dir(mining) / BUDGET_FILE


def budget_bytes_from(budget_gb: float | None) -> int:
    if budget_gb is None:
        value = os.environ.get(BUDGET_ENV)
        if not value:
            raise BudgetError(f"no data budget: pass budget_gb or set {BUDGET_ENV}")
        try:
            budget_gb = float(value)
        except ValueError:
            raise BudgetError(f"{BUDGET_ENV} is not a number") from None
    if not (budget_gb > 0 and math.isfinite(budget_gb)):
        raise BudgetError("the data budget must be a positive number of GB")
    return int(budget_gb * GB)


def run_id_from(run_id: str | None) -> str:
    run_id = run_id or os.environ.get(RUN_ENV)
    if not run_id or not isinstance(run_id, str):
        raise BudgetError(f"no run id: pass run_id or set {RUN_ENV}")
    return run_id


def budget_totals(mining=None) -> dict[str, int]:
    """Bytes recorded per run id. A malformed entry is an error."""
    totals: dict[str, int] = {}
    for number, record in enumerate(read_jsonl(_budget_path(mining)), 1):
        run, size = record.get("run"), record.get("bytes")
        if not isinstance(run, str) or not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise BudgetError(f"{BUDGET_FILE} entry {number} lacks a run id or a byte count")
        totals[run] = totals.get(run, 0) + size
    return totals


def _reservations_dir(mining) -> Path:
    return mining_dir(mining) / RESERVATIONS_DIR


def _pid_alive(pid) -> bool:
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _read_reservations(mining) -> list[tuple[Path, dict]]:
    directory = _reservations_dir(mining)
    out = []
    if not directory.is_dir():
        return out
    for path in sorted(directory.glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raise BudgetError(f"budget reservation {path.name} is unreadable; the budget needs "
                              "a manual look") from None
        size = record.get("bytes") if isinstance(record, dict) else None
        if not isinstance(record, dict) or not isinstance(record.get("run"), str) \
                or not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise BudgetError(f"budget reservation {path.name} is malformed; the budget needs "
                              "a manual look")
        out.append((path, record))
    return out


def _settle_stale(mining) -> None:
    """Charge in full, then drop, the reservations of processes on this host that exited
    without settling (a killed fetch). Caller holds the budget lock."""
    host = socket.gethostname()
    for path, record in _read_reservations(mining):
        if record.get("host") == host and not _pid_alive(record.get("pid")):
            entry = {"run": record["run"], "bytes": record["bytes"], "utc": utc_now(),
                     "kind": "download_unsettled",
                     "note": "reservation of a fetch that exited without settling; counted in full"}
            if isinstance(record.get("url"), str):
                entry["url"] = record["url"]
            append_jsonl(_budget_path(mining), entry)
            path.unlink()


def reserved_totals(mining=None) -> dict[str, int]:
    """Bytes held by fetches in progress, per run id."""
    totals: dict[str, int] = {}
    for _, record in _read_reservations(mining):
        totals[record["run"]] = totals.get(record["run"], 0) + record["bytes"]
    return totals


def budget_remaining(run_id: str | None = None, budget_gb: float | None = None, mining=None) -> int:
    """Budget left after the recorded bytes and the reservations of fetches in progress."""
    run_id = run_id_from(run_id)
    return (budget_bytes_from(budget_gb) - budget_totals(mining).get(run_id, 0)
            - reserved_totals(mining).get(run_id, 0))


def check_budget(add_bytes: int, run_id: str | None = None, budget_gb: float | None = None,
                 mining=None) -> int:
    """Refuse when this run's total would pass its budget. Returns the bytes left after."""
    left = budget_remaining(run_id, budget_gb, mining) - add_bytes
    if left < 0:
        raise BudgetError(f"data budget: run {run_id_from(run_id)} would pass its budget by "
                          f"{-left / GB:.2f} GB; stop and report")
    return left


def record_download(nbytes: int, *, run_id: str | None = None, budget_gb: float | None = None,
                    mining=None, url: str | None = None, sha256: str | None = None,
                    file: str | None = None, note: str | None = None) -> int:
    """Append one download to the data-budget ledger under its lock.

    The check and the append happen under one lock, so two lanes cannot both
    squeeze under the limit. Returns the run's total after the append.
    """
    if not isinstance(nbytes, int) or isinstance(nbytes, bool) or nbytes < 0:
        raise BudgetError("a download size must be a nonnegative integer")
    run_id = run_id_from(run_id)
    budget = budget_bytes_from(budget_gb)
    path = _budget_path(mining)
    with _budget_lock(mining):
        _settle_stale(mining)
        total = budget_totals(mining).get(run_id, 0)
        reserved = reserved_totals(mining).get(run_id, 0)
        if total + reserved + nbytes > budget:
            raise BudgetError(f"data budget: run {run_id} has {total / GB:.2f} GB recorded and "
                              f"{reserved / GB:.2f} GB reserved by fetches in progress; "
                              f"{nbytes / GB:.2f} GB more would pass {budget / GB:.2f} GB")
        append_jsonl(path, _record(run_id, nbytes, "download", url=url, sha256=sha256,
                                   file=file, note=note))
    return total + nbytes


def _budget_lock(mining):
    path = _budget_path(mining)
    return file_lock(path.with_name(path.name + ".lock"), timeout=120)


def _record(run_id: str, nbytes: int, kind: str, **fields) -> dict:
    if kind not in TRANSFER_KINDS:
        raise BudgetError(f"unknown budget record kind {kind}")
    record = {"run": run_id, "bytes": nbytes, "utc": utc_now(), "kind": kind}
    for key, value in fields.items():
        if value is not None:
            record[key] = value
    return record


@dataclasses.dataclass
class Reservation:
    """Bytes a fetch in progress holds against its run's budget (see reserve)."""
    run_id: str
    bytes: int
    path: Path
    mining: object
    settled: bool = False


def reserve(want: int, *, run_id: str | None = None, budget_gb: float | None = None,
            mining=None, url: str | None = None, wait: float = 0.0,
            poll: float = 1.0) -> Reservation:
    """Hold up to want bytes of the run's budget before a transfer starts.

    Concurrent fetches see each other's reservations, so two of them cannot
    both stream into the same remaining budget. When the recorded bytes leave
    no budget the call refuses at once. When only other fetches' reservations
    stand in the way it waits up to wait seconds for them to settle, then takes
    what is left, or refuses when nothing is. Every reservation must end in
    settle(); one left by a process that died is charged in full.
    """
    if not isinstance(want, int) or isinstance(want, bool) or want <= 0:
        raise BudgetError("a reservation must be a positive number of bytes")
    run_id = run_id_from(run_id)
    budget = budget_bytes_from(budget_gb)
    deadline = time.monotonic() + max(0.0, wait)
    directory = _reservations_dir(mining)
    while True:
        with _budget_lock(mining):
            _settle_stale(mining)
            ledger_left = budget - budget_totals(mining).get(run_id, 0)
            if ledger_left <= 0:
                raise BudgetError(f"no room left: run {run_id} has no data budget left")
            others = reserved_totals(mining).get(run_id, 0)
            full = min(want, ledger_left)
            available = ledger_left - others
            if available >= full or (time.monotonic() >= deadline and available > 0):
                grant = min(full, available)
                directory.mkdir(parents=True, exist_ok=True)
                path = directory / f"{uuid.uuid4().hex}.json"
                body = {"run": run_id, "bytes": grant, "pid": os.getpid(),
                        "host": socket.gethostname(), "utc": utc_now()}
                if url is not None:
                    body["url"] = url
                with open(path, "x", encoding="utf-8") as handle:
                    json.dump(body, handle, sort_keys=True)
                    handle.flush()
                    os.fsync(handle.fileno())
                return Reservation(run_id, grant, path, mining)
            if time.monotonic() >= deadline:
                raise BudgetError(f"no room left: run {run_id} has no data budget left beyond "
                                  f"{others} bytes reserved by fetches in progress")
        time.sleep(poll)


def settle(reservation: Reservation, transfers) -> None:
    """Record every transfer of a reserved fetch, then release the reservation.

    transfers: (kind, bytes, fields) items. Every byte moved is recorded,
    whatever the outcome and even past the budget, because it was spent.
    """
    if reservation.settled:
        raise BudgetError("this reservation is already settled")
    path = _budget_path(reservation.mining)
    with _budget_lock(reservation.mining):
        for kind, nbytes, fields in transfers:
            if not isinstance(nbytes, int) or nbytes < 0:
                raise BudgetError("a transfer size must be a nonnegative integer")
            if nbytes:
                append_jsonl(path, _record(reservation.run_id, nbytes, kind, **fields))
        reservation.path.unlink(missing_ok=True)
        reservation.settled = True


# ---------------------------------------------------------------- compute slots

def slot_files(mining=None) -> list[Path]:
    directory = mining_dir(mining) / SLOTS_DIR
    files = sorted(directory.glob("slot-*.lock")) if directory.is_dir() else []
    if not files:
        raise SlotBusyError("no compute slots: the mining dir has no slots/slot-*.lock files")
    return files


@contextlib.contextmanager
def hold_slot(mining=None, *, wait: bool = True, timeout: float | None = None,
              poll: float = 2.0):
    """Hold one compute slot; yields (slot name, the open locked handle).

    The lock is an fcntl.flock on the open file description, so it lasts while
    any process holds a descriptor for it: pass handle.fileno() to a child
    (Popen(..., pass_fds=...)) and the slot stays busy until both have exited.
    """
    files = slot_files(mining)
    deadline = None if timeout is None else time.monotonic() + timeout
    while True:
        for path in files:
            handle = try_lock(path)
            if handle is not None:
                try:
                    yield path.stem, handle
                finally:
                    handle.close()
                return
        if not wait or (deadline is not None and time.monotonic() >= deadline):
            raise SlotBusyError(f"all {len(files)} compute slots are busy")
        time.sleep(poll)


@contextlib.contextmanager
def compute_slot(mining=None, *, wait: bool = True, timeout: float | None = None,
                 poll: float = 2.0):
    """Hold one compute slot (an fcntl lock) for the duration of the block; yields its name."""
    with hold_slot(mining, wait=wait, timeout=timeout, poll=poll) as (name, _handle):
        yield name


def slot_status(mining=None) -> dict[str, str]:
    status = {}
    for path in slot_files(mining):
        handle = try_lock(path)
        status[path.stem] = "free" if handle is not None else "busy"
        if handle is not None:
            handle.close()
    return status


# ---------------------------------------------------------------- conflict markers

_MARK = {c * 7 for c in "<>|"}
_SEP = "=" * 7


def _marker_kind(line: str) -> str | None:
    stripped = line.rstrip("\r\n")
    head = stripped[:7]
    if head in _MARK and (len(stripped) == 7 or stripped[7] == " "):
        return head
    if stripped == _SEP:
        return _SEP
    return None


def _iter_files(paths):
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            for root, dirs, files in os.walk(path):
                dirs[:] = sorted(d for d in dirs if d not in (".git", "__pycache__", ".pytest_cache"))
                for name in sorted(files):
                    yield Path(root) / name
        elif path.is_file():
            yield path
        else:
            raise KitError(f"no such file or directory: {raw}")


def find_conflict_markers(paths) -> list[tuple[str, int]]:
    """(file, line) of every merge-conflict marker in the given files or trees.

    A bare separator line counts only in a file that also has an open or
    close marker, so Markdown underlines do not trip it.
    """
    hits = []
    for path in _iter_files(paths):
        try:
            data = path.read_bytes()
        except OSError as error:
            raise KitError(f"cannot read {path}: {error.strerror}") from None
        if b"\0" in data[:8192]:
            continue
        found, separators = [], []
        for number, line in enumerate(data.decode("utf-8", errors="replace").splitlines(), 1):
            kind = _marker_kind(line)
            if kind == _SEP:
                separators.append(number)
            elif kind:
                found.append(number)
        if found:
            hits.extend((str(path), n) for n in sorted(found + separators))
    return hits


def require_no_conflict_markers(paths) -> None:
    hits = find_conflict_markers(paths)
    if hits:
        where = ", ".join(f"{p}:{n}" for p, n in hits[:20])
        raise KitError(f"conflict markers found: {where}")


# ---------------------------------------------------------------- orientation

def _finite(label, values):
    out = [float(v) for v in values]
    if not out:
        raise OrientationError(f"{label}: no values to check")
    if not all(math.isfinite(v) for v in out):
        raise OrientationError(f"{label}: non-finite values")
    return out


def assert_direction(label: str, lower, higher, *, min_gap: float = 0.0) -> float:
    """Refuse unless median(lower) + min_gap < median(higher). Returns the gap.

    Use it with registered references, for example common-essential genes
    (lower gene effect) against non-essential genes, before any comparison
    relies on the sign of a score.
    """
    gap = statistics.median(_finite(label, higher)) - statistics.median(_finite(label, lower))
    if not gap > min_gap:
        raise OrientationError(f"{label}: expected the first group below the second by more than "
                               f"{min_gap:g}, got a gap of {gap:.4g}; check the score orientation")
    return gap


def assert_sign(label: str, value: float, expected: str) -> None:
    if expected not in ("positive", "negative"):
        raise KitError("expected must be 'positive' or 'negative'")
    value = float(value)
    ok = value > 0 if expected == "positive" else value < 0
    if not (math.isfinite(value) and ok):
        raise OrientationError(f"{label}: expected a {expected} value, got {value:.4g}")


def assert_axis(label: str, ids, pattern: str, *, min_fraction: float = 0.95) -> float:
    """Refuse unless most ids match pattern (for example ACH-\\d{6} for models).

    Catches a transposed matrix before rows and columns are confused.
    """
    ids = [str(i) for i in ids]
    if not ids:
        raise OrientationError(f"{label}: no identifiers")
    regex = re.compile(pattern)
    fraction = sum(1 for i in ids if regex.fullmatch(i)) / len(ids)
    if fraction < min_fraction:
        raise OrientationError(f"{label}: only {fraction:.0%} of identifiers match the expected "
                               f"pattern; the matrix may be transposed")
    return fraction


# ---------------------------------------------------------------- CLI

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="campaign_kit.guards", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    disk = sub.add_parser("disk", help="refuse when free space would drop under the floor")
    disk.add_argument("--path", default=".")
    disk.add_argument("--need-gb", type=float, default=0.0)
    disk.add_argument("--floor-gb", type=float, default=DEFAULT_FLOOR_GB)
    budget = sub.add_parser("budget", help="show this run's recorded bytes")
    budget.add_argument("--run")
    budget.add_argument("--budget-gb", type=float)
    budget.add_argument("--mining-dir")
    record = sub.add_parser("record", help="append a download made outside the kit")
    record.add_argument("--run")
    record.add_argument("--bytes", type=int, required=True)
    record.add_argument("--budget-gb", type=float)
    record.add_argument("--url")
    record.add_argument("--sha256")
    record.add_argument("--file")
    record.add_argument("--mining-dir")
    markers = sub.add_parser("markers", help="conflict-marker check scoped to paths")
    markers.add_argument("paths", nargs="+")
    args = parser.parse_args(argv)
    try:
        if args.cmd == "disk":
            headroom = require_disk_floor(args.path, int(args.need_gb * GIB), args.floor_gb)
            print(f"ok: {headroom / GIB:.1f} GiB above the floor after this write")
        elif args.cmd == "budget":
            run = run_id_from(args.run)
            used = budget_totals(args.mining_dir).get(run, 0)
            held = reserved_totals(args.mining_dir).get(run, 0)
            line = f"run {run}: {used / GB:.3f} GB recorded, {held / GB:.3f} GB reserved"
            if args.budget_gb is not None or os.environ.get(BUDGET_ENV):
                line += f" of {budget_bytes_from(args.budget_gb) / GB:.3f} GB"
            print(line)
        elif args.cmd == "record":
            total = record_download(args.bytes, run_id=args.run, budget_gb=args.budget_gb,
                                    mining=args.mining_dir, url=args.url, sha256=args.sha256,
                                    file=args.file)
            print(f"recorded; run total {total / GB:.3f} GB")
        elif args.cmd == "markers":
            hits = find_conflict_markers(args.paths)
            for path, line in hits:
                print(f"{path}:{line}: conflict marker")
            return 1 if hits else 0
    except KitError as error:
        return die(error)
    return 0


if __name__ == "__main__":
    sys.exit(main())
