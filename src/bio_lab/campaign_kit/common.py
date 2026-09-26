"""Shared helpers: the kit error type, hashing, locks, JSON files and paths."""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import time
import unicodedata

MINING_ENV = "BIO_MINING_DIR"
RUN_ENV = "BIO_RUN_ID"
BUDGET_ENV = "BIO_DATA_BUDGET_GB"

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
NAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")

MAX_PUBLIC_BYTES = 4 * 1024 * 1024

# Personal path prefixes, assembled at runtime so no kit file contains them.
PERSONAL_PREFIXES = tuple("/" + part + "/" for part in ("Users", "home", "private"))
PERSONAL_RE = re.compile("|".join(re.escape(p) for p in PERSONAL_PREFIXES))


class KitError(RuntimeError):
    """A kit guard refused. The message says what failed and what to do next."""


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: os.PathLike | str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 22), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_fileobj(handle) -> str:
    digest = hashlib.sha256()
    for chunk in iter(lambda: handle.read(1 << 22), b""):
        digest.update(chunk)
    return digest.hexdigest()


def mining_dir(explicit: os.PathLike | str | None = None) -> Path:
    """The private mining dir, from an explicit argument or BIO_MINING_DIR."""
    value = explicit if explicit is not None else os.environ.get(MINING_ENV)
    if not value:
        raise KitError(f"no mining dir: pass it explicitly or set {MINING_ENV}")
    path = Path(value)
    if not path.is_dir():
        raise KitError(f"the mining dir does not exist: {path}")
    return path


@contextlib.contextmanager
def file_lock(lock_path: os.PathLike | str, *, blocking: bool = True,
              timeout: float | None = None, poll: float = 0.2):
    """Exclusive fcntl.flock on lock_path (created if missing).

    flock locks belong to the open file description, so two opens conflict
    even inside one process. With blocking=False the lock is tried once.
    """
    lock_path = Path(lock_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(lock_path, "a+")
    try:
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if not blocking or (deadline is not None and time.monotonic() >= deadline):
                    raise KitError(f"lock is held by another process: {lock_path.name}") from None
                time.sleep(poll)
        yield handle
    finally:
        handle.close()


def try_lock(lock_path: os.PathLike | str):
    """Open and lock without waiting. Returns the open handle or None."""
    handle = open(lock_path, "a+")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        return None
    return handle


def read_json(path: os.PathLike | str, what: str = "JSON file") -> dict:
    path = Path(path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise KitError(f"missing {what}: {path.name}") from None
    except json.JSONDecodeError as error:
        raise KitError(f"{what} is not valid JSON ({path.name}: {error})") from None
    if not isinstance(value, dict):
        raise KitError(f"{what} must hold a JSON object: {path.name}")
    return value


def write_json_atomic(path: os.PathLike | str, value, *, indent: int | None = 1,
                      sort_keys: bool = False) -> bytes:
    path = Path(path)
    data = (json.dumps(value, indent=indent, sort_keys=sort_keys, ensure_ascii=False) + "\n").encode()
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    with open(tmp, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)
    return data


def append_jsonl(path: os.PathLike | str, record: dict) -> None:
    """Append one JSON line and fsync. Never rewrites earlier lines."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n"
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())


def read_jsonl(path: os.PathLike | str) -> list[dict]:
    """Every line of a JSONL ledger. A malformed line is an error, not skipped."""
    path = Path(path)
    if not path.exists():
        return []
    records = []
    with open(path, encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                raise KitError(f"{path.name} line {number} is not valid JSON; "
                               "the ledger needs a manual look") from None
            if not isinstance(record, dict):
                raise KitError(f"{path.name} line {number} is not a JSON object")
            records.append(record)
    return records


def safe_relative(relative: str) -> PurePosixPath:
    """A canonical campaign-relative POSIX path, or a KitError."""
    if not isinstance(relative, str) or not relative:
        raise KitError("paths must be nonempty strings")
    path = PurePosixPath(relative)
    if path.is_absolute() or ".." in path.parts or str(path) != relative or relative.startswith("./"):
        raise KitError(f"not a canonical relative path: {relative!r}")
    return path


def rel_posix(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def fold(name: str) -> str:
    """Caseless form of a path part for comparisons.

    APFS and most macOS volumes ignore case and Unicode normalization, so
    Data/Sealed names the same directory as data/sealed. Every sealed-path
    comparison in the kit goes through this function.
    """
    return unicodedata.normalize("NFKD", unicodedata.normalize("NFKD", name).casefold())


SEALED_PARTS = ("sealed", "sanger_holdout")
PRIVATE_PARTS = SEALED_PARTS + ("discovery",)


def folded_parts(path: os.PathLike | str) -> list[str]:
    return [fold(part) for part in Path(os.path.abspath(path)).parts]


def _has_sealed_pair(parts: list[str]) -> bool:
    return any(parts[i] == "data" and parts[i + 1] in SEALED_PARTS for i in range(len(parts) - 1))


def is_sealed_path(path: os.PathLike | str) -> bool:
    """True for anything under a data/sealed/ or data/sanger_holdout/ directory.

    The comparison is caseless (see fold): data/Sealed and Data/sealed count too.
    """
    return _has_sealed_pair(folded_parts(path))


def is_sealed_relative(relative: str) -> bool:
    """is_sealed_path for a campaign-relative POSIX path (no filesystem lookup)."""
    return _has_sealed_pair([fold(p) for p in PurePosixPath(relative).parts])


def is_private_data_dir(path: os.PathLike | str) -> bool:
    """True for a directory under a sealed path, or whose path ends in
    data/sealed, data/sanger_holdout or data/discovery (caseless)."""
    parts = folded_parts(path)
    if len(parts) >= 2 and parts[-2] == "data" and parts[-1] in PRIVATE_PARTS:
        return True
    return _has_sealed_pair(parts)


def dir_has_files(path: Path) -> bool:
    """Whether a directory tree holds any regular file. Counts only; names stay unread."""
    if not path.is_dir():
        return False
    for _, _, files in os.walk(path):
        if files:
            return True
    return False


def die(error: BaseException, prefix: str = "refusing") -> int:
    import sys
    print(f"{prefix}: {error}", file=sys.stderr)
    return 2
