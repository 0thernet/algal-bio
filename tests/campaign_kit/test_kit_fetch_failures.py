"""Fetch failure paths: budget accounting of every byte moved, reservations, gzip error
pages, cache damage, conflicting receipts and case-variant sealed destinations."""

from __future__ import annotations

import gzip
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error

import pytest

from bio_lab.campaign_kit import barrier, guards, receipts, seal
from bio_lab.campaign_kit.common import read_jsonl
from bio_lab.campaign_kit.receipts import Expect
from conftest import make_campaign
from test_kit_receipts import CSV, HTML, fetch, owner_file, server  # noqa: F401


class FakeResponse:
    """A response that hands out chunks, then fails or ends."""

    def __init__(self, chunks, length=None, fail=None):
        self.chunks = list(chunks)
        self.headers = {} if length is None else {"Content-Length": str(length)}
        self.fail = fail

    def read(self, n):
        if not self.chunks:
            if self.fail is not None:
                raise self.fail
            return b""
        chunk = self.chunks.pop(0)
        if len(chunk) > n:
            self.chunks.insert(0, chunk[n:])
            chunk = chunk[:n]
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def kinds(mining):
    return [(r["kind"], r["bytes"]) for r in read_jsonl(mining / "data-budget.jsonl")]


def tmp_files(mining):
    tmp = mining / "cache" / "kit-tmp"
    return sorted(p.name for p in tmp.iterdir()) if tmp.is_dir() else []


def reservations(mining):
    directory = mining / guards.RESERVATIONS_DIR
    return sorted(directory.glob("*.json")) if directory.is_dir() else []


# ---------------------------------------------------------------- every byte is charged

def test_every_rejected_body_is_charged(server, tmp_path, mining):
    for i in range(5):
        with pytest.raises(receipts.ValidationError, match="HTML"):
            fetch(server.url("/login"), tmp_path / f"out{i}.csv")
    assert len(server.requests) == 5
    assert kinds(mining) == [("download_rejected", len(HTML))] * 5
    assert guards.budget_totals() == {"test-run": 5 * len(HTML)}
    assert reservations(mining) == [] and tmp_files(mining) == []


def test_dropped_attempts_are_charged_as_partial(tmp_path, mining):
    attempts, held = [], []

    def opener(request, timeout):
        attempts.append(1)
        held.append(len(reservations(mining)))
        if len(attempts) < 3:
            return FakeResponse([CSV[:10]], fail=ConnectionResetError())
        return FakeResponse([CSV], length=len(CSV))

    receipt = fetch("https://example.invalid/data.csv", tmp_path / "data.csv", opener=opener,
                    retries=2, sleep=lambda s: None)
    assert receipt["bytes"] == len(CSV)
    # the reservation existed before any byte moved, and is gone once settled
    assert held == [1, 1, 1] and reservations(mining) == []
    assert kinds(mining) == [("download_partial", 20), ("download", len(CSV))]
    assert tmp_files(mining) == []


def test_the_metered_count_reaches_the_reservation_before_each_retry(tmp_path, mining):
    # a fetch killed in a backoff is charged from this count (see guards._stale_charge)
    moved = []

    def opener(request, timeout):
        if len(moved) < 2:
            return FakeResponse([CSV[:10]], fail=ConnectionResetError())
        return FakeResponse([CSV], length=len(CSV))

    def sleep(_seconds):
        (path,) = reservations(mining)
        moved.append(json.loads(path.read_text())["moved"])

    fetch("https://example.invalid/data.csv", tmp_path / "data.csv", opener=opener, retries=2,
          sleep=sleep)
    assert moved == [10, 20]
    assert kinds(mining) == [("download_partial", 20), ("download", len(CSV))]


@pytest.fixture
def saved_sigterm():
    saved = signal.getsignal(signal.SIGTERM)
    yield
    signal.signal(signal.SIGTERM, saved)


def test_a_signal_during_settle_waits_until_the_bytes_are_recorded(tmp_path, mining, monkeypatch,
                                                                   saved_sigterm):
    seen = []
    signal.signal(signal.SIGTERM, lambda signum, frame: seen.append(signum))
    real_settle = guards.settle

    def settle(reservation, transfers):
        os.kill(os.getpid(), signal.SIGTERM)
        time.sleep(0.05)
        return real_settle(reservation, transfers)

    monkeypatch.setattr(guards, "settle", settle)

    def opener(request, timeout):
        return FakeResponse([CSV], length=len(CSV))

    with pytest.raises(guards.Interrupted):
        fetch("https://example.invalid/data.csv", tmp_path / "data.csv", opener=opener)
    assert kinds(mining) == [("download", len(CSV))]
    assert reservations(mining) == [] and seen == [signal.SIGTERM]


def test_a_stream_without_length_past_the_cap_leaves_no_partial_file(tmp_path, mining):
    def opener(request, timeout):
        return FakeResponse([CSV] * 50)

    with pytest.raises(receipts.FetchError, match="passed the 100 bytes"):
        fetch("https://example.invalid/big.csv", tmp_path / "big.csv", opener=opener,
              expect=Expect(first_line="model_id,gene,score", max_bytes=100))
    assert not (tmp_path / "big.csv").exists() and tmp_files(mining) == []
    assert kinds(mining) == [("download_partial", 101)]


def test_a_truncated_body_is_refused(tmp_path, mining):
    def opener(request, timeout):
        return FakeResponse([CSV[:10]], length=len(CSV))

    with pytest.raises(receipts.FetchError, match="after 1 attempts"):
        fetch("https://example.invalid/data.csv", tmp_path / "data.csv", opener=opener)
    assert not (tmp_path / "data.csv").exists() and tmp_files(mining) == []
    assert kinds(mining) == [("download_partial", 10)]


def test_retries_that_run_out_are_refused(tmp_path, mining):
    calls = []

    def opener(request, timeout):
        calls.append(1)
        raise urllib.error.URLError("reset")

    with pytest.raises(receipts.FetchError, match="after 3 attempts"):
        fetch("https://example.invalid/data.csv", tmp_path / "data.csv", opener=opener, retries=2,
              sleep=lambda s: None)
    assert len(calls) == 3 and kinds(mining) == [] and reservations(mining) == []


def test_retries_stop_when_the_reserved_bytes_are_used(tmp_path, mining):
    guards.record_download(10 ** 9 - 150, run_id="test-run", budget_gb=1)
    calls = []

    def opener(request, timeout):
        calls.append(1)
        return FakeResponse([b"x" * 75], fail=ConnectionResetError())

    with pytest.raises(receipts.FetchError, match="used up the bytes reserved"):
        fetch("https://example.invalid/data.csv", tmp_path / "data.csv", opener=opener, retries=5,
              sleep=lambda s: None)
    assert len(calls) == 2
    assert kinds(mining)[1:] == [("download_partial", 150)]
    assert guards.budget_totals() == {"test-run": 10 ** 9}


def test_a_concurrent_fetch_is_refused_by_a_reservation(server, tmp_path, mining):
    held = guards.reserve(10 ** 9, run_id="test-run", budget_gb=1, mining=mining)
    assert guards.budget_remaining("test-run", 1) == 0
    with pytest.raises(guards.BudgetError, match="reserved by fetches in progress"):
        fetch(server.url("/data.csv"), tmp_path / "data.csv", budget_wait=0)
    assert server.requests == []
    guards.settle(held, [])
    assert fetch(server.url("/data.csv"), tmp_path / "data.csv")["bytes"] == len(CSV)
    with pytest.raises(guards.BudgetError, match="already settled"):
        guards.settle(held, [])


def test_a_stale_reservation_is_charged_as_unsettled(server, tmp_path, mining):
    done = subprocess.run([sys.executable, "-c", "import os; print(os.getpid())"],
                          capture_output=True, text=True, check=True)
    dead = int(done.stdout)
    directory = mining / guards.RESERVATIONS_DIR
    directory.mkdir()
    (directory / "stale.json").write_text(json.dumps({
        "run": "test-run", "bytes": 1234, "pid": dead, "host": socket.gethostname(),
        "utc": "2026-09-26T00:00:00Z", "url": "https://example.invalid/killed"}))
    fetch(server.url("/data.csv"), tmp_path / "data.csv")
    assert kinds(mining) == [("download_unsettled", 1234), ("download", len(CSV))]
    assert reservations(mining) == []


def test_a_malformed_reservation_stops_the_budget(tmp_path, mining):
    directory = mining / guards.RESERVATIONS_DIR
    directory.mkdir()
    (directory / "bad.json").write_text("{not json")
    with pytest.raises(guards.BudgetError, match="needs a manual look"):
        guards.record_download(1, run_id="test-run", budget_gb=1)


# ---------------------------------------------------------------- gzip error pages

def test_gzip_compressed_error_pages_are_refused(server, tmp_path, mining):
    gz = Expect(magic=b"\x1f\x8b", first_line="model_id,gene,score")
    with pytest.raises(receipts.ValidationError, match="HTML"):
        fetch(server.url("/login.gz"), tmp_path / "a.csv.gz", expect=gz)
    # a server that compresses anyway (Content-Encoding: gzip, which urllib leaves encoded)
    with pytest.raises(receipts.ValidationError, match="HTML"):
        fetch(server.url("/login.gz"), tmp_path / "b.csv")
    with pytest.raises(receipts.ValidationError, match="JSON"):
        fetch(server.url("/error.json.gz"), tmp_path / "c.csv.gz", expect=gz)
    assert all(k == "download_rejected" for k, _ in kinds(mining))
    page = tmp_path / "page.gz"
    page.write_bytes(gzip.compress(b"\n\n  " + HTML))
    with pytest.raises(receipts.ValidationError, match="HTML"):
        receipts.validate_content(page, gz)
    corrupt = tmp_path / "corrupt.gz"
    corrupt.write_bytes(b"\x1f\x8b\x08\x00" + b"\xff" * 64)
    with pytest.raises(receipts.ValidationError, match="corrupt"):
        receipts.validate_content(corrupt, gz)


# ---------------------------------------------------------------- receipts and cache damage

def test_an_existing_receipt_with_another_sha_is_refused(server, tmp_path):
    dest = tmp_path / "lane" / "data.csv"
    fetch(server.url("/data.csv"), dest)
    with pytest.raises(receipts.FetchError, match="another sha256"):
        fetch(server.url("/other.csv"), dest)
    assert dest.read_bytes() == CSV
    assert len(read_jsonl(dest.parent / "receipts.jsonl")) == 1


def test_a_malformed_cache_index_is_refused(server, tmp_path, mining):
    url = server.url("/data.csv")
    fetch(url, tmp_path / "a" / "data.csv")
    index_path = receipts._cache_paths(mining / "cache", url)[0]
    for body in ("{not json", json.dumps({"sha256": "zz", "bytes": 1}), json.dumps({"bytes": 1})):
        index_path.write_text(body)
        with pytest.raises(receipts.FetchError, match="malformed"):
            fetch(url, tmp_path / "b" / "data.csv")
    assert not (tmp_path / "b" / "data.csv").exists() and len(server.requests) == 1


def test_a_missing_or_truncated_blob_is_refused(server, tmp_path, mining):
    url = server.url("/data.csv")
    receipt = fetch(url, tmp_path / "a" / "data.csv")
    blob = mining / "cache" / "kit-blobs" / receipt["sha256"][:2] / receipt["sha256"]
    blob.chmod(0o644)
    blob.write_bytes(CSV[:5])
    with pytest.raises(receipts.FetchError, match="missing or truncated"):
        fetch(url, tmp_path / "b" / "data.csv")
    blob.unlink()
    with pytest.raises(receipts.FetchError, match="missing or truncated"):
        fetch(url, tmp_path / "c" / "data.csv")
    assert len(server.requests) == 1


def test_a_cache_hit_is_checked_against_the_new_expectation(server, tmp_path):
    url = server.url("/data.csv")
    fetch(url, tmp_path / "a" / "data.csv")
    with pytest.raises(receipts.ValidationError, match="first line"):
        fetch(url, tmp_path / "b" / "data.csv", expect=Expect(first_line="other,header"))
    assert not (tmp_path / "b" / "data.csv").exists() and len(server.requests) == 1


@pytest.mark.parametrize("url", ["ftp://example.invalid/x.csv", "file:///x.csv", "example.invalid/x",
                                 None])
def test_only_http_urls_are_fetched(tmp_path, url):
    with pytest.raises(receipts.FetchError, match="http"):
        fetch(url, tmp_path / "x.csv")


# ---------------------------------------------------------------- caseless sealed paths

SEALED_VARIANTS = ["Data/sealed", "data/Sealed", "DATA/SEALED", "data/Sanger_Holdout",
                   "data/sealed/Nested"]


@pytest.mark.parametrize("variant", SEALED_VARIANTS)
def test_case_variant_sealed_destinations_need_the_barrier(server, tmp_path, mining, variant):
    campaign = make_campaign(tmp_path)
    dest = campaign.joinpath(*variant.split("/"), "data.csv")
    with pytest.raises(barrier.BarrierError, match="barrier.require"):
        fetch(server.url("/data.csv"), dest)
    receipts_file = tmp_path / "owner-receipts.txt"
    receipts_file.write_text(owner_file(mining, "data.csv", CSV))
    with pytest.raises(barrier.BarrierError, match="barrier.require"):
        receipts.import_local("data.csv", dest, receipts_file=receipts_file, floor_gb=0)
    assert server.requests == []


def test_sealed_receipts_are_mirrored_outside_the_sealed_directory(server, frozen_campaign):
    campaign, lane_id, sha, name = frozen_campaign
    proof = barrier.require(campaign, lane_id, sha)
    dest = campaign / "data" / "sealed" / "data.csv"
    with seal.writable(campaign):
        receipt = fetch(server.url("/data.csv"), dest, barrier=proof)
        again = fetch(server.url("/data.csv"), dest, barrier=proof)
    assert again == receipt
    mirrored = read_jsonl(campaign / receipts.SEALED_RECEIPTS)
    assert mirrored == [dict(receipt, path="data/sealed/data.csv")]
