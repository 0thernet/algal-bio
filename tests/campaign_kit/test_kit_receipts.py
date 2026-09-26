"""Receipted downloads: content validation, cache reuse, budget, barrier and disk guards."""

from __future__ import annotations

import gzip
import hashlib
import http.server
import io
import json
import threading
import urllib.error

import pytest

from bio_lab.campaign_kit import barrier, guards, ledger, receipts, seal
from bio_lab.campaign_kit.common import read_jsonl
from bio_lab.campaign_kit.receipts import Expect
from conftest import make_campaign

CSV = b"model_id,gene,score\nM1,G1,0.5\nM2,G2,-0.25\n"
HTML = b"<!DOCTYPE html>\n<html><body>Please sign in</body></html>\n"
CSV_EXPECT = Expect(first_line="model_id,gene,score", required_columns=("model_id", "score"))


class Server:
    """A local HTTP server with fixed bodies; every one is served with status 200."""

    def __init__(self, routes):
        self.routes = routes
        self.requests = []
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                outer.requests.append({"path": self.path,
                                       "user_agent": self.headers.get("User-Agent")})
                body = outer.routes.get(self.path)
                if body is None:
                    self.send_response(404)
                    self.end_headers()
                    return
                headers = {}
                if isinstance(body, tuple):
                    body, headers = body
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                for key, value in headers.items():
                    self.send_header(key, value)
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, args=(0.02,), daemon=True)
        self.thread.start()

    def url(self, path):
        return f"http://127.0.0.1:{self.httpd.server_address[1]}{path}"

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)


@pytest.fixture
def server():
    srv = Server({"/data.csv": CSV, "/login": HTML, "/error.json": b'{"error": "quota"}\n',
                  "/big.csv": CSV * 100, "/other.csv": CSV + b"M3,G3,1.0\n",
                  "/login.gz": (gzip.compress(HTML), {"Content-Encoding": "gzip"}),
                  "/error.json.gz": gzip.compress(b'{"error": "quota"}\n')})
    yield srv
    srv.close()


def fetch(url, dest, expect=CSV_EXPECT, **kwargs):
    kwargs.setdefault("run_id", "test-run")
    kwargs.setdefault("budget_gb", 1)
    kwargs.setdefault("floor_gb", 0)
    kwargs.setdefault("retries", 0)
    return receipts.fetch(url, dest, expect, **kwargs)


# ---------------------------------------------------------------- content validation

def test_html_served_with_status_200_is_refused(server, tmp_path, mining):
    with pytest.raises(receipts.ValidationError, match="HTML"):
        fetch(server.url("/login"), tmp_path / "out" / "data.csv")
    assert not (tmp_path / "out" / "data.csv").exists()
    # the rejected body was transferred, so it is charged
    assert guards.budget_totals() == {"test-run": len(HTML)}
    assert [r["kind"] for r in read_jsonl(mining / "data-budget.jsonl")] == ["download_rejected"]
    assert server.requests[0]["user_agent"] == receipts.USER_AGENT
    assert "hraness-bio-campaign-kit" in receipts.USER_AGENT


def test_json_error_body_is_refused(server, tmp_path):
    with pytest.raises(receipts.ValidationError, match="JSON"):
        fetch(server.url("/error.json"), tmp_path / "out.csv")
    with pytest.raises(receipts.ValidationError, match="error object"):
        fetch(server.url("/error.json"), tmp_path / "out.json",
              Expect(first_line_prefix="{", allow_json=True))


def test_expect_needs_a_content_check(tmp_path):
    with pytest.raises(receipts.ValidationError, match="content check"):
        fetch("https://example.invalid/x", tmp_path / "x", Expect(bytes=5))


def test_validate_content_checks(tmp_path):
    path = tmp_path / "f.tsv"
    path.write_bytes(b"\xef\xbb\xbfa\tb\tc\r\n1\t2\t3\n")
    assert "required_columns" in receipts.validate_content(path, Expect(required_columns=("a", "c")))
    with pytest.raises(receipts.ValidationError, match="missing"):
        receipts.validate_content(path, Expect(required_columns=("d",)))
    with pytest.raises(receipts.ValidationError, match="first line"):
        receipts.validate_content(path, Expect(first_line="a,b,c"))
    with pytest.raises(receipts.ValidationError, match="magic"):
        receipts.validate_content(path, Expect(magic=b"PK"))
    with pytest.raises(receipts.ValidationError, match="published"):
        receipts.validate_content(path, Expect(sha256="0" * 64))
    with pytest.raises(receipts.ValidationError, match="size"):
        receipts.validate_content(path, Expect(first_line_prefix="a", bytes=3))
    gz = tmp_path / "f.csv.gz"
    gz.write_bytes(gzip.compress(CSV))
    assert "first_line" in receipts.validate_content(gz, Expect(magic=b"\x1f\x8b",
                                                                first_line="model_id,gene,score"))
    empty = tmp_path / "empty"
    empty.write_bytes(b"")
    with pytest.raises(receipts.ValidationError, match="empty"):
        receipts.validate_content(empty, CSV_EXPECT)


def test_first_line_prefix_is_checked(tmp_path):
    path = tmp_path / "f.csv"
    path.write_bytes(b"\xef\xbb\xbfmodel_id,gene,score\r\nM1,G1,0.5\n")
    checks = receipts.validate_content(path, Expect(first_line_prefix="model_id,"))
    assert checks == ["not_html", "not_json_error", "first_line_prefix"]
    for prefix in ("gene", "model_id,score", "MODEL_ID", "model_id,gene,score,extra"):
        with pytest.raises(receipts.ValidationError, match="expected prefix"):
            receipts.validate_content(path, Expect(first_line_prefix=prefix))
    gz = tmp_path / "f.csv.gz"
    gz.write_bytes(gzip.compress(CSV))
    assert "first_line_prefix" in receipts.validate_content(gz, Expect(first_line_prefix="model_id"))
    with pytest.raises(receipts.ValidationError, match="expected prefix"):
        receipts.validate_content(gz, Expect(first_line_prefix="\x1f"))


def test_allow_json_accepts_a_well_formed_body_and_refuses_a_broken_one(tmp_path):
    good = tmp_path / "list.json"
    good.write_bytes(b'[{"gene": "G1", "score": 0.5}, {"gene": "G2", "score": -0.25}]\n')
    expect = Expect(first_line_prefix="[", allow_json=True)
    assert receipts.validate_content(good, expect) == ["not_html", "not_json_error",
                                                       "first_line_prefix"]
    obj = tmp_path / "obj.json"
    obj.write_bytes(b'{"genes": ["G1", "G2"]}')
    assert "not_json_error" in receipts.validate_content(obj, Expect(first_line_prefix="{",
                                                                     allow_json=True))
    truncated = tmp_path / "truncated.json"
    truncated.write_bytes(b'[{"gene": "G1", "score": 0.5}, {"gene": "G2", "sc')
    with pytest.raises(receipts.ValidationError, match="not valid JSON"):
        receipts.validate_content(truncated, expect)
    # without allow_json the same well-formed body is refused as a probable API error
    with pytest.raises(receipts.ValidationError, match="API error"):
        receipts.validate_content(good, Expect(first_line_prefix="["))


def test_validation_errors_never_echo_content(tmp_path):
    path = tmp_path / "f.csv"
    path.write_bytes(b"secret_column_value,other\n")
    with pytest.raises(receipts.ValidationError) as error:
        receipts.validate_content(path, Expect(first_line="model_id"))
    assert "secret_column_value" not in str(error.value)


# ---------------------------------------------------------------- download, receipt, cache

def test_fetch_writes_a_receipt_and_counts_the_budget(server, tmp_path, mining):
    dest = tmp_path / "lane" / "data" / "discovery" / "data.csv"
    receipt = fetch(server.url("/data.csv"), dest)
    assert dest.read_bytes() == CSV
    assert receipt["sha256"] == hashlib.sha256(CSV).hexdigest()
    assert receipt["bytes"] == len(CSV) and receipt["source"] == "network"
    assert receipt["budget_counted"] is True and "first_line" in receipt["checks"]
    assert read_jsonl(dest.parent / "receipts.jsonl") == [receipt]
    budget = read_jsonl(mining / "data-budget.jsonl")
    assert [(b["run"], b["bytes"], b["kind"]) for b in budget] == [("test-run", len(CSV), "download")]


def test_cache_reuse_costs_no_bandwidth_and_no_budget(server, tmp_path, mining):
    first = fetch(server.url("/data.csv"), tmp_path / "a" / "data.csv")
    second = fetch(server.url("/data.csv"), tmp_path / "b" / "data.csv")
    assert len(server.requests) == 1
    assert second["source"] == "cache" and second["budget_counted"] is False
    assert second["sha256"] == first["sha256"]
    assert guards.budget_totals() == {"test-run": len(CSV)}
    # the same destination again returns the recorded receipt and adds nothing
    again = fetch(server.url("/data.csv"), tmp_path / "a" / "data.csv")
    assert again == first
    assert len(read_jsonl(tmp_path / "a" / "receipts.jsonl")) == 1


def test_cache_blob_that_changed_is_refused(server, tmp_path, mining):
    receipt = fetch(server.url("/data.csv"), tmp_path / "a" / "data.csv")
    blob = mining / "cache" / "kit-blobs" / receipt["sha256"][:2] / receipt["sha256"]
    blob.chmod(0o644)
    blob.write_bytes(CSV.replace(b"0.5", b"0.9"))
    with pytest.raises(receipts.FetchError, match="no longer matches"):
        fetch(server.url("/data.csv"), tmp_path / "b" / "data.csv")


def test_existing_file_without_receipt_is_not_overwritten(server, tmp_path):
    dest = tmp_path / "data.csv"
    dest.write_bytes(b"model_id,gene,score\nlocal\n")
    with pytest.raises(receipts.FetchError, match="without a receipt"):
        fetch(server.url("/data.csv"), dest)
    assert dest.read_bytes() == b"model_id,gene,score\nlocal\n"


def test_budget_overrun_stops_the_download(server, tmp_path, mining):
    guards.record_download(999_999_000, run_id="test-run", budget_gb=1)
    with pytest.raises(receipts.FetchError, match="bytes this fetch may write"):
        fetch(server.url("/big.csv"), tmp_path / "big.csv")
    assert not (tmp_path / "big.csv").exists()
    assert guards.budget_totals() == {"test-run": 999_999_000}
    guards.record_download(1000, run_id="test-run", budget_gb=1)
    with pytest.raises(guards.BudgetError, match="no data budget left"):
        fetch(server.url("/data.csv"), tmp_path / "data.csv")


def test_disk_floor_refuses_before_downloading(server, tmp_path):
    with pytest.raises(guards.DiskFloorError):
        fetch(server.url("/data.csv"), tmp_path / "data.csv", floor_gb=1e9)
    assert server.requests == []


def test_http_error_is_not_retried_but_throttling_is(tmp_path):
    calls = []

    def opener(status):
        def open_(request, timeout):
            calls.append(request.get_header("User-agent"))
            raise urllib.error.HTTPError(request.full_url, status, "x", {}, io.BytesIO(b""))
        return open_

    with pytest.raises(receipts.FetchError, match="HTTP 404"):
        fetch("https://example.invalid/x.csv", tmp_path / "x.csv", opener=opener(404), retries=3,
              sleep=lambda s: None)
    assert len(calls) == 1
    calls.clear()
    with pytest.raises(receipts.FetchError, match="HTTP 429"):
        fetch("https://example.invalid/x.csv", tmp_path / "x.csv", opener=opener(429), retries=2,
              sleep=lambda s: None)
    assert len(calls) == 3 and calls[0] == receipts.USER_AGENT


def test_transient_failure_then_success(tmp_path):
    attempts = []

    class Response(io.BytesIO):
        headers = {"Content-Length": str(len(CSV))}

    def opener(request, timeout):
        attempts.append(1)
        if len(attempts) == 1:
            raise urllib.error.URLError("reset")
        return Response(CSV)

    sleeps = []
    receipt = fetch("https://example.invalid/data.csv", tmp_path / "data.csv", opener=opener,
                    retries=2, sleep=sleeps.append)
    assert receipt["source"] == "network" and len(attempts) == 2 and sleeps == [2.0]


# ---------------------------------------------------------------- sealed destinations

def test_sealed_fetch_without_a_barrier_is_refused(server, tmp_path):
    campaign = make_campaign(tmp_path)
    with pytest.raises(barrier.BarrierError, match="barrier.require"):
        fetch(server.url("/data.csv"), campaign / "data" / "sealed" / "data.csv")
    assert server.requests == []


def test_sealed_fetch_with_another_lanes_barrier_is_refused(server, frozen_campaign, tmp_path):
    campaign, lane_id, sha, name = frozen_campaign
    proof = barrier.require(campaign, lane_id, sha)
    other = make_campaign(tmp_path / "other", name="other-lane-2026-09-26", lane_id="S02")
    with pytest.raises(barrier.BarrierError, match="another campaign"):
        fetch(server.url("/data.csv"), other / "data" / "sealed" / "data.csv", barrier=proof)
    with pytest.raises(barrier.BarrierError, match="another group"):
        barrier.require(campaign, "S03", sha)
    assert server.requests == []


def test_sealed_fetch_with_the_proof_is_receipted_and_locked(server, frozen_campaign):
    campaign, lane_id, sha, name = frozen_campaign
    proof = barrier.require(campaign, lane_id, sha)
    with seal.writable(campaign):
        receipt = fetch(server.url("/data.csv"), campaign / "data" / "sealed" / "data.csv",
                        barrier=proof)
    assert receipt["bytes"] == len(CSV)
    state = seal.status(campaign)
    assert state["sealed_files"] == 1 and state["files"] == 2
    assert state["locked"] is True


# ---------------------------------------------------------------- owner-downloaded files

def owner_file(mining, name, data):
    portal = mining / "cache" / receipts.PORTAL_SUBDIR
    portal.mkdir(parents=True, exist_ok=True)
    (portal / name).write_bytes(data)
    sha = hashlib.sha256(data).hexdigest()
    md5 = hashlib.md5(data).hexdigest()
    return f"{sha}  {name}  md5={md5}  bytes={len(data)}\n"


PORTAL_SOURCE = receipts.SUBDIR_SOURCES[receipts.PORTAL_SUBDIR]
LANE = "demo-lane-2026-09-26"


def portal_ledger(tmp_path, *, discovery_by=None):
    """A synthetic holdout ledger whose portal entry records discovery use by discovery_by."""
    path = tmp_path / "holdout-ledger.json"
    doc = {"schema": "bio-holdout-ledger/1", "statuses": {"METADATA": "x", "DISCOVERY": "x"},
           "entries": [{"id": PORTAL_SOURCE, "kind": "table", "status": "METADATA",
                        "opened_for": [], "campaigns": []}],
           "history": []}
    path.write_text(json.dumps(doc) + "\n")
    if discovery_by:
        ledger.record_discovery(path, PORTAL_SOURCE, discovery_by, "2026-09-26")
    return path


def test_import_local_checks_size_and_hash(tmp_path, mining):
    line = owner_file(mining, "Model.csv", CSV)
    receipts_file = tmp_path / "owner-receipts.txt"
    receipts_file.write_text("# owner receipts\n" + line)
    ledger_path = portal_ledger(tmp_path, discovery_by=LANE)
    lane = tmp_path / f"biology-{LANE}"
    route = {"ledger": ledger_path, "campaign": LANE}
    dest = lane / "prep" / "Model.csv"
    receipt = receipts.import_local("Model.csv", dest, receipts_file=receipts_file, floor_gb=0,
                                    **route)
    assert dest.read_bytes() == CSV and receipt["source"] == "import_local"
    assert receipt["url"] == f"local:{receipts.PORTAL_SUBDIR}/Model.csv"
    assert guards.budget_totals() == {}
    # a changed cache file is refused
    (mining / "cache" / receipts.PORTAL_SUBDIR / "Model.csv").write_bytes(CSV.replace(b"M1", b"M9"))
    with pytest.raises(receipts.ValidationError, match="published"):
        receipts.import_local("Model.csv", lane / "other" / "Model.csv",
                              receipts_file=receipts_file, floor_gb=0, **route)
    with pytest.raises(receipts.KitError, match="not in the owner receipts"):
        receipts.import_local("Other.csv", lane / "o.csv", receipts_file=receipts_file, **route)
    with pytest.raises(receipts.ValidationError, match="disagrees"):
        receipts.import_local("Model.csv", lane / "x.csv", receipts_file=receipts_file,
                              expect=Expect(sha256="1" * 64), **route)


def test_import_local_needs_a_barrier_or_a_recorded_discovery_use(tmp_path, mining):
    receipts_file = tmp_path / "owner-receipts.txt"
    receipts_file.write_text(owner_file(mining, "Model.csv", CSV))
    lane = tmp_path / f"biology-{LANE}"
    dest = lane / "prep" / "Model.csv"
    with pytest.raises(receipts.KitError, match="needs the barrier proof"):
        receipts.import_local("Model.csv", dest, receipts_file=receipts_file, floor_gb=0)
    unrecorded = portal_ledger(tmp_path)
    with pytest.raises(receipts.KitError, match="records no discovery use"):
        receipts.import_local("Model.csv", dest, receipts_file=receipts_file, floor_gb=0,
                              ledger=unrecorded, campaign=LANE)
    ledger.record_discovery(unrecorded, PORTAL_SOURCE, "another-lane", "2026-09-26")
    with pytest.raises(receipts.KitError, match="records no discovery use"):
        receipts.import_local("Model.csv", dest, receipts_file=receipts_file, floor_gb=0,
                              ledger=unrecorded, campaign=LANE)
    ledger.record_discovery(unrecorded, PORTAL_SOURCE, LANE, "2026-09-26")
    # the named source must be the one the subdirectory holds
    with pytest.raises(receipts.KitError, match="holds ledger source"):
        receipts.import_local("Model.csv", dest, receipts_file=receipts_file, floor_gb=0,
                              ledger=unrecorded, campaign=LANE, source="some-other-source")
    # the destination must be inside that campaign's directory
    with pytest.raises(receipts.KitError, match="not inside campaign"):
        receipts.import_local("Model.csv", tmp_path / "elsewhere" / "Model.csv",
                              receipts_file=receipts_file, floor_gb=0, ledger=unrecorded,
                              campaign=LANE)
    assert not dest.exists()
    receipt = receipts.import_local("Model.csv", dest, receipts_file=receipts_file, floor_gb=0,
                                    ledger=unrecorded, campaign=LANE)
    assert receipt["sha256"] == hashlib.sha256(CSV).hexdigest()


def test_import_local_refusals(tmp_path, mining, frozen_campaign):
    campaign, lane_id, sha, name = frozen_campaign
    proof = barrier.require(campaign, lane_id, sha)
    receipts_file = tmp_path / "owner-receipts.txt"
    line = owner_file(mining, "Model.csv", CSV)
    dest = campaign / "data" / "prep" / "Model.csv"
    # a size that disagrees with the owner receipt
    receipts_file.write_text(line.replace(f"bytes={len(CSV)}", f"bytes={len(CSV) + 1}"))
    with pytest.raises(receipts.ValidationError, match="the receipt says"):
        receipts.import_local("Model.csv", dest, receipts_file=receipts_file, floor_gb=0,
                              barrier=proof)
    receipts_file.write_text(line)
    # traversal in the name or the subdirectory
    for bad in ("../Model.csv", "a/Model.csv", ".hidden"):
        with pytest.raises(receipts.KitError, match="plain file name"):
            receipts.import_local(bad, dest, receipts_file=receipts_file, barrier=proof)
    for bad in ("..", "../cache", "a/b"):
        with pytest.raises(receipts.KitError, match="plain directory name"):
            receipts.import_local("Model.csv", dest, receipts_file=receipts_file, barrier=proof,
                                  subdir=bad)
    # a symlinked cache file
    portal = mining / "cache" / receipts.PORTAL_SUBDIR
    (portal / "Link.csv").symlink_to(portal / "Model.csv")
    receipts_file.write_text(line + line.replace("Model.csv", "Link.csv"))
    with pytest.raises(receipts.KitError, match="not in the cache as a regular file"):
        receipts.import_local("Link.csv", campaign / "data" / "prep" / "Link.csv",
                              receipts_file=receipts_file, floor_gb=0, barrier=proof)
    # a missing receipts file
    with pytest.raises(receipts.KitError, match="does not exist"):
        receipts.import_local("Model.csv", dest, receipts_file=tmp_path / "missing.txt",
                              barrier=proof)
    assert not dest.exists()


def test_import_local_into_sealed_needs_the_barrier(tmp_path, mining, frozen_campaign):
    campaign, lane_id, sha, name = frozen_campaign
    receipts_file = tmp_path / "owner-receipts.txt"
    receipts_file.write_text(owner_file(mining, "Gene.csv", CSV))
    dest = campaign / "data" / "sealed" / "Gene.csv"
    with pytest.raises(barrier.BarrierError):
        receipts.import_local("Gene.csv", dest, receipts_file=receipts_file, floor_gb=0)
    proof = barrier.require(campaign, lane_id, sha)
    with seal.writable(campaign):
        receipt = receipts.import_local("Gene.csv", dest, receipts_file=receipts_file,
                                        barrier=proof, floor_gb=0,
                                        expect=Expect(required_columns=("gene",)))
    assert "required_columns" in receipt["checks"] and "sha256" in receipt["checks"]


def test_owner_receipts_parse_errors(tmp_path):
    path = tmp_path / "r.txt"
    path.write_text("nothex  a.csv  bytes=1\n")
    with pytest.raises(receipts.KitError, match="malformed"):
        receipts.read_owner_receipts(path)
    path.write_text(f"{'a' * 64}  a.csv  md5=x\n")
    with pytest.raises(receipts.KitError, match="byte count"):
        receipts.read_owner_receipts(path)
    path.write_text(f"{'a' * 64}  a.csv  bytes=1\n{'b' * 64}  a.csv  bytes=2\n")
    with pytest.raises(receipts.KitError, match="twice"):
        receipts.read_owner_receipts(path)


def test_clone_falls_back_to_a_checked_copy(tmp_path, monkeypatch):
    src = tmp_path / "blob"
    src.write_bytes(CSV)

    def no_clone(cmd, **kwargs):
        return receipts.subprocess.CompletedProcess(cmd, 1, b"", b"")

    monkeypatch.setattr(receipts.subprocess, "run", no_clone)
    assert receipts.clone_file(src, tmp_path / "copy", floor_gb=0) == "copy"
    assert (tmp_path / "copy").read_bytes() == CSV
    with pytest.raises(guards.DiskFloorError):
        receipts.clone_file(src, tmp_path / "copy2", floor_gb=1e9)
    assert not (tmp_path / "copy2").exists()
