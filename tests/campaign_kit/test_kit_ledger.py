"""Locked, additive holdout-ledger updates and the public export."""

from __future__ import annotations

import json

import pytest

from bio_lab.campaign_kit import ledger
from bio_lab.campaign_kit.common import sha256_file

BARRIER_A = "a" * 64
BARRIER_B = "b" * 64


@pytest.fixture
def ledger_path(tmp_path):
    doc = {
        "schema": "bio-holdout-ledger/1", "updated": "2026-09-25", "purpose": "synthetic",
        "statuses": {"FRESH": "never read"}, "rules": ["register before observing"],
        "entries": [
            {"id": "src-fresh", "kind": "table", "name": "Fresh source", "locator": "private-locator",
             "status": "FRESH", "opened_for": [], "campaigns": [], "verified": "2026-09-25",
             "notes": "private note"},
            {"id": "src-meta", "kind": "table", "name": "Metadata source", "locator": "x",
             "status": "METADATA", "opened_for": [], "campaigns": ["earlier"], "verified": None,
             "notes": ""},
            {"id": "src-used", "kind": "table", "name": "Used source", "locator": "y",
             "status": "DISCOVERY", "opened_for": [], "campaigns": ["earlier"], "verified": None,
             "notes": ""},
        ],
        "history": [{"date": "2026-09-25", "entry": "src-fresh", "change": "added"}],
    }
    path = tmp_path / "holdout-ledger.json"
    path.write_text(json.dumps(doc, indent=1) + "\n")
    return path


def load(path):
    return json.loads(path.read_text())


def entry(path, source):
    return next(e for e in load(path)["entries"] if e["id"] == source)


def test_record_discovery_is_idempotent(ledger_path):
    assert ledger.record_discovery(ledger_path, "src-meta", "lane-a", "2026-09-26") == "recorded"
    after = ledger_path.read_bytes()
    assert ledger.record_discovery(ledger_path, "src-meta", "lane-a", "2026-09-26") == "unchanged"
    assert ledger_path.read_bytes() == after
    record = entry(ledger_path, "src-meta")
    assert record["status"] == "DISCOVERY" and record["campaigns"] == ["earlier", "lane-a"]
    assert load(ledger_path)["history"][-1]["action"] == "discovery"


def test_record_open_group_then_members(ledger_path):
    frozen = ["lane-b", "lane-a"]
    assert ledger.record_open(ledger_path, "src-fresh", frozen, "lane-a", "2026-09-26",
                              BARRIER_A) == "opened"
    record = entry(ledger_path, "src-fresh")
    assert record["status"] == "OPENED" and record["opened_for"] == ["lane-a", "lane-b"]
    assert record["frozen_set_sha256"] == BARRIER_A and record["opened_on"] == "2026-09-26"
    snapshot = ledger_path.read_bytes()
    assert ledger.record_open(ledger_path, "src-fresh", frozen, "lane-a", "2026-09-26",
                              BARRIER_A) == "unchanged"
    assert ledger_path.read_bytes() == snapshot
    assert ledger.record_open(ledger_path, "src-fresh", frozen, "lane-b", "2026-09-27",
                              BARRIER_A) == "member"
    assert ledger.record_open(ledger_path, "src-fresh", frozen, "lane-b", "2026-09-27",
                              BARRIER_A) == "unchanged"
    actions = [h.get("action") for h in load(ledger_path)["history"]]
    assert actions == [None, "open", "group_member"]


def test_record_open_refuses_a_mismatched_group(ledger_path):
    ledger.record_open(ledger_path, "src-fresh", ["lane-a", "lane-b"], "lane-a", "2026-09-26",
                       BARRIER_A)
    with pytest.raises(ledger.LedgerError, match="another frozen set"):
        ledger.record_open(ledger_path, "src-fresh", ["lane-a"], "lane-a", "2026-09-26", BARRIER_A)
    with pytest.raises(ledger.LedgerError, match="not one of"):
        ledger.record_open(ledger_path, "src-fresh", ["lane-a"], "lane-z", "2026-09-26", BARRIER_B)


def test_a_later_group_reuses_disjointly_without_rewriting(ledger_path):
    ledger.record_open(ledger_path, "src-fresh", ["lane-a"], "lane-a", "2026-09-26", BARRIER_A)
    first = entry(ledger_path, "src-fresh")
    assert ledger.record_open(ledger_path, "src-fresh", ["lane-c"], "lane-c", "2026-09-28",
                              BARRIER_B) == "reused"
    second = entry(ledger_path, "src-fresh")
    assert second["opened_on"] == first["opened_on"] and second["campaign"] == "lane-a"
    assert second["frozen_set_sha256"] == BARRIER_A
    assert [o["usage"] for o in second["openings"]] == ["holdout", "reused_disjoint"]


def test_a_discovery_source_is_not_a_holdout(ledger_path):
    before = ledger_path.read_bytes()
    with pytest.raises(ledger.LedgerError, match="not a clean holdout"):
        ledger.record_open(ledger_path, "src-used", ["lane-a"], "lane-a", "2026-09-26", BARRIER_A)
    assert ledger_path.read_bytes() == before


def test_unknown_sources_and_bad_input_are_refused(ledger_path):
    with pytest.raises(ledger.LedgerError, match="missing"):
        ledger.record_discovery(ledger_path, "src-none", "lane-a", "2026-09-26")
    with pytest.raises(ledger.LedgerError, match="date"):
        ledger.record_discovery(ledger_path, "src-meta", "lane-a", "26/09/2026")
    with pytest.raises(ledger.LedgerError, match="SHA-256"):
        ledger.record_open(ledger_path, "src-fresh", ["lane-a"], "lane-a", "2026-09-26", "abc")


def test_additive_check_refuses_any_rewrite():
    before = {"entries": [{"id": "s", "status": "FRESH", "campaigns": ["a"]}],
              "history": [{"entry": "s", "change": "x"}], "rules": ["r"]}
    ok = json.loads(json.dumps(before))
    ok["entries"][0]["status"] = "OPENED"
    ok["entries"][0]["campaigns"].append("b")
    ok["history"].append({"entry": "s", "change": "y"})
    ledger._verify_additive(before, ok, "s")
    for mutate in (lambda d: d["history"].pop(0),
                   lambda d: d["history"][0].update(change="rewritten"),
                   lambda d: d["entries"][0]["campaigns"].insert(0, "z"),
                   lambda d: d.pop("rules"),
                   lambda d: d["entries"].append({"id": "t"})):
        bad = json.loads(json.dumps(before))
        mutate(bad)
        with pytest.raises(ledger.LedgerError):
            ledger._verify_additive(before, bad, "s")
    other = json.loads(json.dumps(before))
    other["entries"][0]["status"] = "OPENED"
    with pytest.raises(ledger.LedgerError):
        ledger._verify_additive(before, other, "another-source")


def test_export_public_drops_private_fields(ledger_path):
    ledger.record_open(ledger_path, "src-fresh", ["lane-a"], "lane-a", "2026-09-26", BARRIER_A)
    text = ledger.export_public(ledger_path)
    public = json.loads(text)
    assert public["schema"] == "bio-holdout-ledger-public/1"
    assert [e["id"] for e in public["entries"]] == ["src-fresh", "src-meta", "src-used"]
    assert set(public["entries"][0]) == set(ledger.PUBLIC_FIELDS)
    assert "private note" not in text and "private-locator" not in text
    assert ledger.export_public(ledger_path) == text


def test_cli_record_open_from_the_barrier_file(ledger_path, tmp_path, capsys):
    barrier_file = tmp_path / "group-barrier.json"
    barrier_file.write_text(json.dumps({
        "schema": "bio-group-barrier/1", "run_id": "r", "members": ["S01", "S02"],
        "frozen": [{"id": "S01", "campaign": "lane-a", "freeze_sha256": "c" * 64,
                    "merge_sha": "d" * 40}], "released": ["S02"]}, separators=(",", ":")))
    args = ["record-open", "--ledger", str(ledger_path), "--source", "src-fresh",
            "--campaign", "lane-a", "--barrier", str(barrier_file), "--date", "2026-09-26"]
    assert ledger.main(args) == 0
    assert capsys.readouterr().out.strip() == "opened"
    assert entry(ledger_path, "src-fresh")["frozen_set_sha256"] == sha256_file(barrier_file)
    assert ledger.main(args) == 0
    assert capsys.readouterr().out.strip() == "unchanged"
    assert ledger.main(["export-public", "--ledger", str(ledger_path)]) == 0
    assert json.loads(capsys.readouterr().out)["entries"][0]["status"] == "OPENED"
