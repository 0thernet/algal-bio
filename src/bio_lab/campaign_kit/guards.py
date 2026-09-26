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
import signal
import socket
import statistics
import sys
import threading
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
# A reservation file carries the fetch's metered byte count, rewritten at least
# every PROGRESS_BYTES or PROGRESS_SECONDS, and the path of its partial file.
PROGRESS_BYTES = 1 << 22
PROGRESS_SECONDS = 2.0
# partial downloads live in <mining>/cache/kit-tmp/<key>.<pid>.part
PART_DIR = ("cache", "kit-tmp")
PART_RE = re.compile(r"^[0-9a-f]{64}\.([0-9]+)\.part$")
INTERRUPT_SIGNALS = (signal.SIGTERM, signal.SIGHUP, signal.SIGINT)
# a reservation file being rewritten: .<name>.json.<pid>.tmp
RESERVATION_TMP_RE = re.compile(r"^\.[0-9a-f]{32}\.json\.([0-9]+)\.tmp$")


class DiskFloorError(KitError):
    pass


class BudgetError(KitError):
    pass


class SlotBusyError(KitError):
    pass


class OrientationError(KitError):
    pass


class BudgetExceeded(BudgetError):
    """A download was recorded, and the run's total now passes its budget."""

    def __init__(self, message: str, total: int):
        super().__init__(message)
        self.total = total


class Interrupted(BaseException):
    """SIGTERM, SIGHUP or SIGINT arrived while a budget reservation was held.

    A BaseException, like KeyboardInterrupt, so no `except KitError` or
    `except Exception` mistakes it for a refusal or a failed download.
    """

    def __init__(self, signum: int):
        super().__init__(f"interrupted by signal {signum}")
        self.signum = signum


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
                or not _count(size) \
                or any(key in record and not _count(record[key]) for key in ("moved", "earlier")) \
                or ("part" in record and not isinstance(record["part"], str)):
            raise BudgetError(f"budget reservation {path.name} is malformed; the budget needs "
                              "a manual look")
        out.append((path, record))
    return out


def _count(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _part_file(mining, record: dict) -> Path | None:
    """The reservation's partial file, only when it is a kit partial in the mining dir."""
    part = record.get("part")
    if not isinstance(part, str):
        return None
    path = Path(part)
    if not PART_RE.match(path.name) \
            or path.parent.resolve() != mining_dir(mining).joinpath(*PART_DIR).resolve():
        return None
    return path


def _stale_charge(mining, record: dict) -> tuple[int, str]:
    """Bytes to charge for a reservation whose fetch died, and how they were counted.

    The larger of the metered count last written to the reservation and the
    bytes of earlier attempts plus the partial file's size; the whole
    reservation only when neither can be read.
    """
    counts = []
    if _count(record.get("moved")):
        counts.append(record["moved"])
    part = _part_file(mining, record)
    if part is not None:
        try:
            counts.append(record.get("earlier", 0) + part.stat().st_size)
        except OSError:
            pass
    if not counts:
        return record["bytes"], "reservation of a fetch that exited without settling; counted in full"
    return max(counts), ("reservation of a fetch that exited without settling; counted from "
                         "its metered bytes and partial file")


def _settle_stale(mining) -> None:
    """Charge, then drop, the reservations of processes on this host that exited
    without settling (a killed fetch), and delete partial files whose process is
    gone. Caller holds the budget lock. See _stale_charge for the amount."""
    host = socket.gethostname()
    held_parts = set()
    for path, record in _read_reservations(mining):
        if record.get("host") == host and not _pid_alive(record.get("pid")):
            charge, note = _stale_charge(mining, record)
            entry = {"run": record["run"], "bytes": charge, "utc": utc_now(),
                     "kind": "download_unsettled", "note": note, "reserved": record["bytes"]}
            if isinstance(record.get("url"), str):
                entry["url"] = record["url"]
            append_jsonl(_budget_path(mining), entry)
            part = _part_file(mining, record)
            if part is not None:
                part.unlink(missing_ok=True)
            path.unlink()
        elif isinstance(record.get("part"), str):
            held_parts.add(str(Path(record["part"]).resolve()))
    _sweep_parts(mining, held_parts)
    directory = _reservations_dir(mining)
    if directory.is_dir():
        for path in directory.iterdir():
            match = RESERVATION_TMP_RE.match(path.name)
            if match and not _pid_alive(int(match.group(1))):
                path.unlink(missing_ok=True)


def _sweep_parts(mining, held: set) -> None:
    """Delete kit partial files whose process on this host is gone and that no open
    reservation names; their bytes were settled already or just now."""
    directory = mining_dir(mining).joinpath(*PART_DIR)
    if not directory.is_dir():
        return
    for path in directory.iterdir():
        match = PART_RE.match(path.name)
        if match is None or str(path.resolve()) in held or path.is_symlink() \
                or not path.is_file():
            continue
        if not _pid_alive(int(match.group(1))):
            path.unlink(missing_ok=True)


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
    """Refuse when add_bytes more would pass this run's budget, counting the recorded
    bytes and the reservations of fetches in progress (stale ones are settled first).
    Run it before a download made outside the kit. Returns the bytes left after."""
    if not _count(add_bytes):
        raise BudgetError("a download size must be a nonnegative integer")
    run_id = run_id_from(run_id)
    budget = budget_bytes_from(budget_gb)
    with _budget_lock(mining):
        _settle_stale(mining)
        total = budget_totals(mining).get(run_id, 0)
        reserved = reserved_totals(mining).get(run_id, 0)
    left = budget - total - reserved - add_bytes
    if left < 0:
        raise BudgetError(f"data budget: run {run_id} has {total / GB:.3f} GB recorded and "
                          f"{reserved / GB:.3f} GB reserved by fetches in progress; "
                          f"{add_bytes / GB:.3f} GB more would pass its budget of "
                          f"{budget / GB:.3f} GB by {-left / GB:.3f} GB; stop and report")
    return left


def record_download(nbytes: int, *, run_id: str | None = None, budget_gb: float | None = None,
                    mining=None, url: str | None = None, sha256: str | None = None,
                    file: str | None = None, note: str | None = None) -> int:
    """Append one download that has already happened to the data-budget ledger.

    The bytes were spent, so they are always recorded, under the budget lock.
    Afterwards it raises BudgetExceeded when the run's recorded total passes
    its budget (stop downloading), or BudgetError when no valid budget is set.
    Returns the run's total after the append. Check before downloading with
    check_budget.
    """
    if not _count(nbytes):
        raise BudgetError("a download size must be a nonnegative integer")
    run_id = run_id_from(run_id)
    path = _budget_path(mining)
    with _budget_lock(mining):
        _settle_stale(mining)
        append_jsonl(path, _record(run_id, nbytes, "download", url=url, sha256=sha256,
                                   file=file, note=note))
        total = budget_totals(mining).get(run_id, 0)
    try:
        budget = budget_bytes_from(budget_gb)
    except BudgetError as error:
        raise BudgetError(f"recorded, but the budget cannot be checked: {error}") from None
    if total > budget:
        raise BudgetExceeded(f"data budget: recorded, but run {run_id} now has {total / GB:.3f} GB "
                             f"recorded, over its budget of {budget / GB:.3f} GB; stop "
                             "downloading and report", total)
    return total


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
    record: dict = dataclasses.field(default_factory=dict)
    _written: tuple = (0, 0.0)

    def progress(self, moved: int, earlier: int, force: bool = False) -> None:
        """Write the metered byte count (moved: all attempts so far; earlier: attempts
        already ended) into the reservation file, at most every PROGRESS_BYTES or
        PROGRESS_SECONDS unless forced, so a killed fetch is charged what it moved."""
        if self.settled:
            return
        last_bytes, last_time = self._written
        now = time.monotonic()
        if not force and moved - last_bytes < PROGRESS_BYTES and now - last_time < PROGRESS_SECONDS:
            return
        self.record = dict(self.record, moved=moved, earlier=earlier)
        _write_reservation(self.path, self.record, create=False)
        self._written = (moved, now)


def _write_reservation(path: Path, body: dict, *, create: bool) -> None:
    """Write a reservation file whole (temporary file, then rename), so a reader or a
    kill never sees half of one."""
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(body, handle, sort_keys=True)
            handle.flush()
            if create:
                os.fsync(handle.fileno())
        if create and path.exists():
            raise BudgetError("a reservation file with this name exists already")
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def reserve(want: int, *, run_id: str | None = None, budget_gb: float | None = None,
            mining=None, url: str | None = None, part: os.PathLike | str | None = None,
            wait: float = 0.0, poll: float = 1.0) -> Reservation:
    """Hold up to want bytes of the run's budget before a transfer starts.

    Concurrent fetches see each other's reservations, so two of them cannot
    both stream into the same remaining budget. When the recorded bytes leave
    no budget the call refuses at once. When only other fetches' reservations
    stand in the way it waits up to wait seconds for them to settle, then takes
    what is left, or refuses when nothing is. Every reservation must end in
    settle(). part names the fetch's partial file; Reservation.progress keeps
    a metered byte count in the file. One left by a process that died is
    charged the larger of that count and the partial file's size (plus
    earlier attempts), or in full when neither can be read.
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
                        "host": socket.gethostname(), "utc": utc_now(), "moved": 0, "earlier": 0}
                if url is not None:
                    body["url"] = url
                if part is not None:
                    body["part"] = str(Path(part).resolve())
                _write_reservation(path, body, create=True)
                return Reservation(run_id, grant, path, mining, record=body)
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
    transfers = list(transfers)
    for _kind, nbytes, _fields in transfers:
        if not _count(nbytes):
            raise BudgetError("a transfer size must be a nonnegative integer")
    path = _budget_path(reservation.mining)
    with _budget_lock(reservation.mining):
        for kind, nbytes, fields in transfers:
            if nbytes:
                append_jsonl(path, _record(reservation.run_id, nbytes, kind, **fields))
        reservation.path.unlink(missing_ok=True)
        reservation.settled = True


class _SignalGuard:
    """State of interruptible(): the first signal raises Interrupted, unless held."""

    def __init__(self):
        self.previous: dict = {}
        self.pending: int | None = None
        self.raised = False
        self.holding = 0

    def _handler(self, signum, _frame):
        if self.pending is None:
            self.pending = signum
        if not self.raised and not self.holding:
            self.raised = True
            raise Interrupted(signum)

    @contextlib.contextmanager
    def hold(self):
        """Defer a signal until the block ends (use it around settle)."""
        self.holding += 1
        try:
            yield
        finally:
            self.holding -= 1
        if self.pending is not None and not self.raised and not self.holding:
            self.raised = True
            raise Interrupted(self.pending)


@contextlib.contextmanager
def interruptible():
    """While a reservation is held: turn SIGTERM, SIGHUP and SIGINT into Interrupted.

    A killed Python process runs no finally, so a fetch killed by SIGTERM
    would never settle its reservation. Inside this block the first of these
    signals raises Interrupted instead, so the fetch's finally records the
    bytes it moved. On exit the previous handlers are restored and the signal
    is sent again, so the process ends (or not) as it would have without the
    block. Signals set to be ignored (nohup's SIGHUP) stay ignored. It works in
    the main thread only; elsewhere it changes nothing.
    """
    guard = _SignalGuard()
    if threading.current_thread() is not threading.main_thread():
        yield guard
        return
    try:
        for signum in INTERRUPT_SIGNALS:
            current = signal.getsignal(signum)
            if current is None or current == signal.SIG_IGN:
                continue
            guard.previous[signum] = current
            signal.signal(signum, guard._handler)
        yield guard
    finally:
        for signum, handler in guard.previous.items():
            signal.signal(signum, handler)
        if guard.pending is not None and guard.pending in guard.previous:
            os.kill(os.getpid(), guard.pending)


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
    check = sub.add_parser("check", help="before a download made outside the kit: refuse "
                           "when it would pass the run's budget, counting reservations")
    check.add_argument("--run")
    need = check.add_mutually_exclusive_group(required=True)
    need.add_argument("--need-bytes", type=int)
    need.add_argument("--need-gb", type=float)
    check.add_argument("--budget-gb", type=float)
    check.add_argument("--mining-dir")
    record = sub.add_parser("record", help="append a download made outside the kit; it is "
                            "always recorded, and exits 3 when the run is then over its budget")
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
        elif args.cmd == "check":
            if args.need_gb is not None:
                if not (math.isfinite(args.need_gb) and args.need_gb >= 0):
                    raise BudgetError("--need-gb must be a nonnegative number")
                need_bytes = math.ceil(args.need_gb * GB)
            else:
                need_bytes = args.need_bytes
            left = check_budget(need_bytes, run_id=args.run, budget_gb=args.budget_gb,
                                mining=args.mining_dir)
            print(f"ok: {left / GB:.3f} GB of the budget left after this download")
        elif args.cmd == "record":
            try:
                total = record_download(args.bytes, run_id=args.run, budget_gb=args.budget_gb,
                                        mining=args.mining_dir, url=args.url, sha256=args.sha256,
                                        file=args.file)
            except BudgetExceeded as error:
                print(f"recorded; run total {error.total / GB:.3f} GB")
                print(f"over budget: {error}", file=sys.stderr)
                return 3
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
