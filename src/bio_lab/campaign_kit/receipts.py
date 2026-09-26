"""Receipted downloads: content validation, a content-addressed cache, local imports.

fetch(url, dest, expect) downloads through $BIO_MINING_DIR/cache/ and clones
the cached blob into the lane's directory. It validates by content, never by
HTTP status: portals and archives serve error and login pages with status 200.
Every file gets a receipt line (url, bytes, sha256, UTC time) appended to
receipts.jsonl next to it.

Cache layout under $BIO_MINING_DIR/cache/ (kit-owned names only):
    kit-index/<sha256(url)>.json       url -> blob sha256, bytes, fetch time
    kit-blobs/<aa>/<sha256>            read-only blobs
    kit-locks/<sha256(url)>.lock       per-file lock while fetching
    kit-tmp/                           partial downloads
A cache hit costs no bandwidth and no budget: a cached file counts once.

import_local(name, dest, receipts_file=...) brings in an owner-downloaded
file that has no fetchable URL. It reads the expected SHA-256 and size from
the owner's receipts file, hashes $BIO_MINING_DIR/cache/<subdir>/<name>
in-process, refuses on any mismatch, clones it and writes the same receipt.

A destination under data/sealed/ needs the proof returned by barrier.require().
"""

from __future__ import annotations

import csv
import dataclasses
from dataclasses import dataclass, field
import gzip
import hashlib
import http.client
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

from . import KIT_VERSION
from .common import (KitError, SHA256_RE, append_jsonl, file_lock, is_sealed_path, mining_dir,
                     read_jsonl, sha256_file, utc_now, write_json_atomic)
from . import guards

USER_AGENT = (f"hraness-bio-campaign-kit/{KIT_VERSION} "
              "(research data fetch; +https://github.com/hraness/bio)")
RECEIPTS = "receipts.jsonl"
PORTAL_SUBDIR = "depmap-26q1-portal"
HEAD_BYTES = 1 << 16
JSON_PARSE_LIMIT = 16 << 20
GZIP_MAGIC = b"\x1f\x8b"


class ValidationError(KitError):
    pass


class FetchError(KitError):
    pass


@dataclass(frozen=True)
class Expect:
    """What a correct file looks like. At least one content check is required.

    first_line / first_line_prefix: the header line (BOM and line ending stripped;
    read through gzip when the file is gzip). magic: leading bytes.
    required_columns: names that must appear in the header (delimiter sniffed
    from comma or tab unless given). sha256 / bytes: provider-published values.
    allow_json: the file itself is JSON (it must still not be an error body).
    """
    first_line: str | None = None
    first_line_prefix: str | None = None
    magic: bytes | None = None
    required_columns: tuple = ()
    delimiter: str | None = None
    sha256: str | None = None
    bytes: int | None = None
    max_bytes: int | None = None
    allow_json: bool = False
    extra: dict = field(default_factory=dict)

    def has_content_check(self) -> bool:
        return bool(self.first_line is not None or self.first_line_prefix or self.magic
                    or self.required_columns or self.sha256)


# ---------------------------------------------------------------- validation

def _looks_like_html(head: bytes) -> bool:
    probe = head[:4096].lstrip(b"\xef\xbb\xbf \t\r\n").lower()
    if probe.startswith((b"<!doctype html", b"<html", b"<head", b"<body")):
        return True
    return b"<html" in probe[:1024] or (probe.startswith(b"<!doctype") and b"html" in probe[:64])


def _json_error(path: Path, head: bytes, allow_json: bool) -> str | None:
    probe = head.lstrip(b"\xef\xbb\xbf \t\r\n")
    if not probe.startswith((b"{", b"[")):
        return None
    if not allow_json:
        return "the body is JSON (an API error body?) where a data file was expected"
    if path.stat().st_size > JSON_PARSE_LIMIT:
        return None
    try:
        value = json.loads(path.read_bytes())
    except (json.JSONDecodeError, UnicodeDecodeError):
        return "the body is not valid JSON"
    if isinstance(value, dict) and ({"error", "errors", "fault"} & set(value)):
        return "the body is a JSON error object"
    return None


def _first_line(path: Path, head: bytes) -> str:
    if head.startswith(GZIP_MAGIC):
        with gzip.open(path, "rb") as handle:
            raw = handle.readline(1 << 20)
    else:
        with open(path, "rb") as handle:
            raw = handle.readline(1 << 20)
    return raw.decode("utf-8-sig", errors="replace").rstrip("\r\n")


def validate_content(path: os.PathLike | str, expect: Expect) -> list[str]:
    """Refuse unless the file matches expect. Returns the checks that passed.

    Error messages never echo file content.
    """
    if not isinstance(expect, Expect) or not expect.has_content_check():
        raise ValidationError("expect must declare a content check (first line, magic bytes, "
                              "required columns or a published sha256)")
    path = Path(path)
    size = path.stat().st_size
    checks = []
    if size == 0:
        raise ValidationError("the file is empty")
    if expect.bytes is not None and size != expect.bytes:
        raise ValidationError(f"size {size} differs from the expected {expect.bytes} bytes")
    if expect.max_bytes is not None and size > expect.max_bytes:
        raise ValidationError(f"size {size} passes the registered maximum")
    with open(path, "rb") as handle:
        head = handle.read(HEAD_BYTES)
    if _looks_like_html(head):
        raise ValidationError("the body is an HTML page (an error or login page, whatever the "
                              "HTTP status)")
    checks.append("not_html")
    problem = _json_error(path, head, expect.allow_json)
    if problem:
        raise ValidationError(problem)
    checks.append("not_json_error")
    if expect.magic:
        if not head.startswith(expect.magic):
            raise ValidationError("the leading bytes do not match the expected magic bytes")
        checks.append("magic")
    if expect.first_line is not None or expect.first_line_prefix or expect.required_columns:
        line = _first_line(path, head)
        if expect.first_line is not None:
            if line != expect.first_line:
                raise ValidationError("the first line differs from the expected header")
            checks.append("first_line")
        if expect.first_line_prefix:
            if not line.startswith(expect.first_line_prefix):
                raise ValidationError("the first line does not start with the expected prefix")
            checks.append("first_line_prefix")
        if expect.required_columns:
            delimiter = expect.delimiter or ("\t" if line.count("\t") > line.count(",") else ",")
            columns = next(csv.reader(io.StringIO(line), delimiter=delimiter), [])
            missing = [c for c in expect.required_columns if c not in columns]
            if missing:
                raise ValidationError(f"required columns missing from the header: {missing}")
            checks.append("required_columns")
    if expect.sha256:
        got = sha256_file(path)
        if got != expect.sha256:
            raise ValidationError(f"sha256 {got} differs from the published {expect.sha256}")
        checks.append("sha256")
    return checks


# ---------------------------------------------------------------- cloning

def clone_file(src: Path, dest: Path, *, floor_gb: float = guards.DEFAULT_FLOOR_GB) -> str:
    """Copy-on-write clone (cp -c on APFS, reflink elsewhere), else a checked copy."""
    tmp = dest.with_name(f".{dest.name}.part-{os.getpid()}")
    # BSD cp -c is a clonefile(2) clone; GNU cp -c means something else, so each OS gets its own.
    attempt = ((["cp", "-c", str(src), str(tmp)], "clone") if sys.platform == "darwin"
               else (["cp", "--reflink=always", str(src), str(tmp)], "reflink"))
    for cmd, method in (attempt,):
        try:
            done = subprocess.run(cmd, capture_output=True, check=False)
        except OSError:
            continue
        if done.returncode == 0:
            os.replace(tmp, dest)
            return method
        tmp.unlink(missing_ok=True)
    guards.require_disk_floor(dest.parent, src.stat().st_size, floor_gb)
    shutil.copyfile(src, tmp)
    os.replace(tmp, dest)
    return "copy"


# ---------------------------------------------------------------- receipts

def receipts_for(directory: os.PathLike | str) -> list[dict]:
    return read_jsonl(Path(directory) / RECEIPTS)


def _existing_receipt(dest: Path, sha: str) -> dict | None:
    """The receipt already recorded for dest, if it matches; refuse if it conflicts."""
    matches = [r for r in receipts_for(dest.parent) if r.get("file") == dest.name]
    for record in matches:
        if record.get("sha256") != sha:
            raise FetchError(f"{dest.name} already has a receipt with another sha256; "
                             "receipts are never rewritten")
    return matches[0] if matches else None


def _sealed_guard(dest: Path, barrier) -> None:
    if is_sealed_path(dest):
        from .barrier import require_proof
        require_proof(barrier, dest)


def _place(blob: Path, sha: str, size: int, dest: Path, floor_gb: float) -> tuple[str, dict | None]:
    """Clone blob to dest unless dest already holds it. Returns (method, prior receipt)."""
    prior = _existing_receipt(dest, sha)
    if dest.exists() or dest.is_symlink():
        if prior is not None:
            return "existing", prior
        raise FetchError(f"{dest.name} exists without a receipt; refusing to overwrite it")
    dest.parent.mkdir(parents=True, exist_ok=True)
    method = clone_file(blob, dest, floor_gb=floor_gb)
    got = sha256_file(dest)
    if got != sha or dest.stat().st_size != size:
        dest.unlink(missing_ok=True)
        raise FetchError(f"{dest.name} did not arrive intact (sha256 mismatch after {method})")
    os.chmod(dest, 0o444)
    return method, None


# ---------------------------------------------------------------- network

def _default_opener(request, timeout):
    return urllib.request.urlopen(request, timeout=timeout)


_TRANSIENT = (urllib.error.URLError, ConnectionError, TimeoutError, http.client.IncompleteRead,
              http.client.RemoteDisconnected)


def _download(url: str, part: Path, *, cap: int, opener, timeout: float, retries: int,
              sleep, user_agent: str) -> tuple[int, str]:
    """Stream url into part with at most cap bytes. Returns (bytes, sha256)."""
    attempt = 0
    while True:
        attempt += 1
        try:
            request = urllib.request.Request(url, headers={"User-Agent": user_agent,
                                                           "Accept-Encoding": "identity"})
            with opener(request, timeout) as response:
                length = response.headers.get("Content-Length") if response.headers else None
                if length is not None and length.isdigit() and int(length) > cap:
                    raise FetchError(f"the server announces {int(length)} bytes, over the "
                                     f"{cap} bytes this fetch may write (budget, disk floor or "
                                     "registered maximum)")
                digest, written = hashlib.sha256(), 0
                with open(part, "wb") as handle:
                    while True:
                        chunk = response.read(1 << 20)
                        if not chunk:
                            break
                        written += len(chunk)
                        if written > cap:
                            raise FetchError(f"the download passed the {cap} bytes this fetch "
                                             "may write; stopped")
                        digest.update(chunk)
                        handle.write(chunk)
                    handle.flush()
                    os.fsync(handle.fileno())
                if length is not None and length.isdigit() and written != int(length):
                    raise http.client.IncompleteRead(b"", int(length) - written)
                return written, digest.hexdigest()
        except urllib.error.HTTPError as error:
            part.unlink(missing_ok=True)
            if error.code not in (408, 425, 429, 500, 502, 503, 504) or attempt > retries:
                raise FetchError(f"HTTP {error.code} for {url}") from None
        except FetchError:
            part.unlink(missing_ok=True)
            raise
        except _TRANSIENT as error:
            part.unlink(missing_ok=True)
            if attempt > retries:
                raise FetchError(f"download failed after {attempt} attempts: "
                                 f"{type(error).__name__}") from None
        sleep(min(60.0, 2.0 ** attempt))


def _cache_paths(cache: Path, url: str):
    key = hashlib.sha256(url.encode()).hexdigest()
    return (cache / "kit-index" / f"{key}.json", cache / "kit-locks" / f"{key}.lock",
            cache / "kit-tmp")


def _blob_path(cache: Path, sha: str) -> Path:
    return cache / "kit-blobs" / sha[:2] / sha


def fetch(url: str, dest: os.PathLike | str, expect: Expect, *, run_id: str | None = None,
          budget_gb: float | None = None, mining=None, barrier=None,
          floor_gb: float = guards.DEFAULT_FLOOR_GB, retries: int = 3, timeout: float = 120.0,
          opener=None, sleep=time.sleep, user_agent: str = USER_AGENT) -> dict:
    """Download url to dest through the cache; validate; receipt. Returns the receipt."""
    if not isinstance(url, str) or not url.startswith(("https://", "http://")):
        raise FetchError("url must be an http(s) URL")
    if not isinstance(expect, Expect) or not expect.has_content_check():
        raise ValidationError("expect must declare a content check (first line, magic bytes, "
                              "required columns or a published sha256)")
    dest = Path(dest).resolve()
    _sealed_guard(dest, barrier)
    run_id = guards.run_id_from(run_id)
    guards.budget_bytes_from(budget_gb)
    cache = mining_dir(mining) / "cache"
    index_path, lock_path, tmp_dir = _cache_paths(cache, url)
    source, counted = "cache", False
    with file_lock(lock_path, timeout=3600):
        index = None
        if index_path.exists():
            try:
                index = json.loads(index_path.read_text(encoding="utf-8"))
                blob = _blob_path(cache, index["sha256"])
                if not SHA256_RE.match(index["sha256"]) or not isinstance(index["bytes"], int):
                    raise ValueError
            except (ValueError, KeyError, TypeError):
                raise FetchError("a cache index entry is malformed; the cache needs a manual "
                                 "look") from None
            if not blob.is_file() or blob.stat().st_size != index["bytes"]:
                raise FetchError("the cache index points at a missing or truncated blob; "
                                 "the cache needs a manual look")
            if sha256_file(blob) != index["sha256"]:
                raise FetchError("a cached blob no longer matches its sha256; the cache needs "
                                 "a manual look")
            checks = validate_content(blob, expect)
        else:
            tmp_dir.mkdir(parents=True, exist_ok=True)
            headroom = guards.require_disk_floor(tmp_dir, expect.bytes or 0, floor_gb)
            cap = min(headroom, guards.budget_remaining(run_id, budget_gb, mining))
            for limit in (expect.max_bytes, expect.bytes):
                if limit is not None:
                    cap = min(cap, limit)
            if cap <= 0:
                raise guards.BudgetError(f"no room left: run {run_id} has no data budget left "
                                         "or the disk is at its floor")
            part = tmp_dir / f"{index_path.stem}.{os.getpid()}.part"
            size, sha = _download(url, part, cap=cap, opener=opener or _default_opener,
                                  timeout=timeout, retries=retries, sleep=sleep,
                                  user_agent=user_agent)
            try:
                checks = validate_content(part, expect)
                guards.record_download(size, run_id=run_id, budget_gb=budget_gb, mining=mining,
                                       url=url, sha256=sha, file=dest.name)
            except KitError:
                part.unlink(missing_ok=True)
                raise
            blob = _blob_path(cache, sha)
            blob.parent.mkdir(parents=True, exist_ok=True)
            if blob.exists() and sha256_file(blob) == sha:
                part.unlink()
            else:
                os.replace(part, blob)
            os.chmod(blob, 0o444)
            index = {"url": url, "sha256": sha, "bytes": size, "fetched_utc": utc_now(),
                     "user_agent": user_agent}
            index_path.parent.mkdir(parents=True, exist_ok=True)
            write_json_atomic(index_path, index, sort_keys=True)
            source, counted = "network", True
        method, prior = _place(blob, index["sha256"], index["bytes"], dest, floor_gb)
    if prior is not None:
        return prior
    receipt = {"file": dest.name, "url": url, "bytes": index["bytes"], "sha256": index["sha256"],
               "fetched_utc": index["fetched_utc"], "received_utc": utc_now(), "source": source,
               "placed_by": method, "checks": checks, "user_agent": user_agent,
               "budget_run": run_id, "budget_counted": counted, "kit_version": KIT_VERSION}
    append_jsonl(dest.parent / RECEIPTS, receipt)
    return receipt


# ---------------------------------------------------------------- owner-downloaded files

_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def read_owner_receipts(receipts_file: os.PathLike | str) -> dict[str, dict]:
    """Parse lines '<sha256>  <name>  md5=<hex>  bytes=<n>'; '#' lines are comments."""
    path = Path(receipts_file)
    if not path.is_file():
        raise KitError("the owner receipts file does not exist")
    entries: dict[str, dict] = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        tokens = line.split()
        if len(tokens) < 3 or not SHA256_RE.match(tokens[0]):
            raise KitError(f"owner receipts line {number} is malformed")
        fields = dict(t.split("=", 1) for t in tokens[2:] if "=" in t)
        if not fields.get("bytes", "").isdigit():
            raise KitError(f"owner receipts line {number} has no byte count")
        if tokens[1] in entries:
            raise KitError(f"owner receipts list {tokens[1]} twice")
        entries[tokens[1]] = {"sha256": tokens[0], "bytes": int(fields["bytes"]),
                              "md5": fields.get("md5")}
    return entries


def import_local(name: str, dest: os.PathLike | str, *, receipts_file: os.PathLike | str,
                 mining=None, barrier=None, subdir: str = PORTAL_SUBDIR,
                 expect: Expect | None = None, floor_gb: float = guards.DEFAULT_FLOOR_GB) -> dict:
    """Clone an owner-downloaded cache file into dest after checking size and sha256."""
    if not isinstance(name, str) or not _NAME_RE.match(name):
        raise KitError("name must be a plain file name")
    if not _NAME_RE.match(subdir):
        raise KitError("subdir must be a plain directory name")
    wanted = read_owner_receipts(receipts_file).get(name)
    if wanted is None:
        raise KitError(f"{name} is not in the owner receipts file")
    dest = Path(dest).resolve()
    _sealed_guard(dest, barrier)
    src = mining_dir(mining) / "cache" / subdir / name
    if src.is_symlink() or not src.is_file():
        raise KitError(f"{name} is not in the cache as a regular file")
    if src.stat().st_size != wanted["bytes"]:
        raise ValidationError(f"{name} has {src.stat().st_size} bytes, the receipt says "
                              f"{wanted['bytes']}")
    if expect is None:
        expect = Expect(sha256=wanted["sha256"], bytes=wanted["bytes"])
    elif expect.sha256 not in (None, wanted["sha256"]) or expect.bytes not in (None, wanted["bytes"]):
        raise ValidationError(f"expect disagrees with the owner receipt for {name}")
    else:
        expect = dataclasses.replace(expect, sha256=wanted["sha256"], bytes=wanted["bytes"])
    checks = validate_content(src, expect)
    method, prior = _place(src, wanted["sha256"], wanted["bytes"], dest, floor_gb)
    if prior is not None:
        return prior
    receipt = {"file": dest.name, "url": f"local:{subdir}/{name}", "bytes": wanted["bytes"],
               "sha256": wanted["sha256"], "md5_published": wanted["md5"],
               "fetched_utc": None, "received_utc": utc_now(), "source": "import_local",
               "placed_by": method, "checks": checks, "user_agent": None,
               "budget_run": None, "budget_counted": False, "kit_version": KIT_VERSION}
    append_jsonl(dest.parent / RECEIPTS, receipt)
    return receipt
