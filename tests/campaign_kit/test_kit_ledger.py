"""Locked, additive holdout-ledger updates and the public export."""

from __future__ import annotations

import json

import pytest

from bio_lab.campaign_kit import ledger
from bio_lab.campaign_kit.common import sha256_file

BARRIER_A = "a" * 64
BARRIER_B = "b" * 64
BARRIER_C = "c" * 64
STATUSES = {name: "synthetic" for name in ("FRESH", "METADATA", "UNOBSERVED_SUBSET", "FUTURE",
                                            "DISCOVERY", "OPENED", "ANNOTATION", "RETIRED")}


@pytest.fixture
def ledger_path(tmp_path):
    doc = {
        "schema": "bio-holdout-ledger/1", "updated": "2026-09-25", "purpose": "synthetic",
        "statuses": dict(STATUSES), "rules": ["register before observing"],
        "entries": [
            {"id": "src-fresh", "kind": "table", "name": "Fresh source", "locator": "private-locator",
             "status": "FRESH", "opened_for": [], "campaigns": [], "verified": True,
             "notes": "private note"},
            {"id": "src-meta", "kind": "table", "name": "Metadata source", "locator": "x",
             "status": "METADATA", "opened_for": [], "campaigns": ["earlier"], "verified": None,
             "notes": ""},
            {"id": "src-used", "kind": "table", "name": "Used source", "locator": "y",
             "status": "DISCOVERY", "opened_for": [], "campaigns": ["earlier"], "verified": False,
             "notes": ""},
            {"id": "src-future", "kind": "table", "name": "Future source", "locator": "z",
             "status": "FUTURE", "opened_for": [], "campaigns": [], "verified": None, "notes": ""},
            {"id": "src-retired", "kind": "table", "name": "Retired source", "locator": "w",
             "status": "RETIRED", "opened_for": [], "campaigns": [], "verified": None, "notes": ""},
        ],
        "history": [{"date": "2026-09-25", "entry": "src-fresh", "change": "added"}],
    }
    path = tmp_path / "holdout-ledger.json"
    path.write_text(json.dumps(doc, indent=1) + "\n")
    return path


@pytest.fixture
def deny_file(tmp_path):
    path = tmp_path / "deny.txt"
    path.write_text("# synthetic\nQuillon Vantree\nzorblat\n", encoding="utf-8")
    return path


def load(path):
    return json.loads(path.read_text())


def entry(path, source):
    return next(e for e in load(path)["entries"] if e["id"] == source)


def edit(path, source, **fields):
    doc = load(path)
    for item in doc["entries"]:
        if item["id"] == source:
            item.update(fields)
    path.write_text(json.dumps(doc, indent=1) + "\n")


def test_record_discovery_is_idempotent(ledger_path):
    assert ledger.record_discovery(ledger_path, "src-meta", "lane-a", "2026-09-26") == "recorded"
    after = ledger_path.read_bytes()
    assert ledger.record_discovery(ledger_path, "src-meta", "lane-a", "2026-09-26") == "unchanged"
    assert ledger_path.read_bytes() == after
    record = entry(ledger_path, "src-meta")
    assert record["status"] == "DISCOVERY" and record["campaigns"] == ["earlier", "lane-a"]
    assert load(ledger_path)["history"][-1]["action"] == "discovery"
    assert ledger.discovery_recorded(ledger_path, "src-meta", "lane-a")
    assert not ledger.discovery_recorded(ledger_path, "src-meta", "lane-b")
    # listed in campaigns but with no discovery history item: not a recorded use
    assert not ledger.discovery_recorded(ledger_path, "src-used", "earlier")


@pytest.mark.parametrize("source", ["src-future", "src-retired"])
def test_record_discovery_refuses_future_and_retired_sources(ledger_path, source):
    before = ledger_path.read_bytes()
    with pytest.raises(ledger.LedgerError, match="cannot serve as discovery data"):
        ledger.record_discovery(ledger_path, source, "lane-a", "2026-09-26")
    assert ledger_path.read_bytes() == before


def test_record_discovery_refuses_a_duplicated_id(ledger_path):
    doc = load(ledger_path)
    doc["entries"].append(dict(doc["entries"][1]))
    ledger_path.write_text(json.dumps(doc, indent=1) + "\n")
    before = ledger_path.read_bytes()
    with pytest.raises(ledger.LedgerError, match="duplicated"):
        ledger.record_discovery(ledger_path, "src-meta", "lane-a", "2026-09-26")
    assert ledger_path.read_bytes() == before


def test_record_open_group_then_members(ledger_path):
    frozen = ["lane-b", "lane-a"]
    assert ledger.record_open(ledger_path, "src-fresh", frozen, "lane-a", "2026-09-26",
                              BARRIER_A, usage="holdout") == "opened"
    record = entry(ledger_path, "src-fresh")
    assert record["status"] == "OPENED" and record["opened_for"] == ["lane-a", "lane-b"]
    assert record["frozen_set_sha256"] == BARRIER_A and record["opened_on"] == "2026-09-26"
    snapshot = ledger_path.read_bytes()
    assert ledger.record_open(ledger_path, "src-fresh", frozen, "lane-a", "2026-09-26",
                              BARRIER_A, usage="holdout") == "unchanged"
    assert ledger_path.read_bytes() == snapshot
    assert ledger.record_open(ledger_path, "src-fresh", frozen, "lane-b", "2026-09-27",
                              BARRIER_A, usage="holdout") == "member"
    assert ledger.record_open(ledger_path, "src-fresh", frozen, "lane-b", "2026-09-27",
                              BARRIER_A, usage="holdout") == "unchanged"
    actions = [h.get("action") for h in load(ledger_path)["history"]]
    assert actions == [None, "open", "group_member"]


def test_record_open_refuses_a_mismatched_group(ledger_path):
    ledger.record_open(ledger_path, "src-fresh", ["lane-a", "lane-b"], "lane-a", "2026-09-26",
                       BARRIER_A, usage="holdout")
    with pytest.raises(ledger.LedgerError, match="another frozen set"):
        ledger.record_open(ledger_path, "src-fresh", ["lane-a"], "lane-a", "2026-09-26", BARRIER_A,
                           usage="holdout")
    with pytest.raises(ledger.LedgerError, match="not one of"):
        ledger.record_open(ledger_path, "src-fresh", ["lane-a"], "lane-z", "2026-09-26", BARRIER_B,
                           usage="holdout")


def test_a_later_group_reuses_disjointly_without_rewriting(ledger_path):
    ledger.record_open(ledger_path, "src-fresh", ["lane-a"], "lane-a", "2026-09-26", BARRIER_A,
                       usage="holdout")
    first = entry(ledger_path, "src-fresh")
    assert ledger.record_open(ledger_path, "src-fresh", ["lane-c"], "lane-c", "2026-09-28",
                              BARRIER_B, usage="reused_disjoint") == "reused"
    second = entry(ledger_path, "src-fresh")
    assert second["opened_on"] == first["opened_on"] and second["campaign"] == "lane-a"
    assert second["frozen_set_sha256"] == BARRIER_A
    assert [o["usage"] for o in second["openings"]] == ["holdout", "reused_disjoint"]


def test_a_reuse_that_overlaps_an_earlier_group_is_refused(ledger_path):
    ledger.record_open(ledger_path, "src-fresh", ["lane-a", "lane-b"], "lane-a", "2026-09-26",
                       BARRIER_A, usage="holdout")
    ledger.record_open(ledger_path, "src-fresh", ["lane-c"], "lane-c", "2026-09-27", BARRIER_B,
                       usage="reused_disjoint")
    before = ledger_path.read_bytes()
    # lane-b was in the first opening, lane-c in the second (an earlier reuse)
    for group, recorder in ((["lane-b", "lane-d"], "lane-d"), (["lane-c", "lane-e"], "lane-e")):
        with pytest.raises(ledger.LedgerError, match="a reuse needs a disjoint group"):
            ledger.record_open(ledger_path, "src-fresh", group, recorder, "2026-09-28", BARRIER_C,
                               usage="reused_disjoint")
    assert ledger_path.read_bytes() == before


def test_an_opening_by_a_discovery_user_is_refused(ledger_path):
    # "earlier" read src-meta as discovery data: its group may not open it as a holdout
    before = ledger_path.read_bytes()
    with pytest.raises(ledger.LedgerError, match="already used src-meta"):
        ledger.record_open(ledger_path, "src-meta", ["earlier", "lane-x"], "lane-x", "2026-09-26",
                           BARRIER_A, usage="holdout")
    assert ledger_path.read_bytes() == before


def test_a_reuse_by_a_campaign_in_the_entry_campaigns_is_refused(ledger_path):
    ledger.record_discovery(ledger_path, "src-fresh", "lane-q", "2026-09-25")
    edit(ledger_path, "src-fresh", status="FRESH")      # simulate a clean-looking entry
    before = ledger_path.read_bytes()
    with pytest.raises(ledger.LedgerError, match="lane-q already used src-fresh"):
        ledger.record_open(ledger_path, "src-fresh", ["lane-q"], "lane-q", "2026-09-26", BARRIER_A,
                           usage="holdout")
    assert ledger_path.read_bytes() == before


def test_the_registered_usage_must_match_the_ledger(ledger_path):
    before = ledger_path.read_bytes()
    with pytest.raises(ledger.LedgerError, match="registration and the ledger disagree"):
        ledger.record_open(ledger_path, "src-fresh", ["lane-a"], "lane-a", "2026-09-26", BARRIER_A,
                           usage="reused_disjoint")
    assert ledger_path.read_bytes() == before
    ledger.record_open(ledger_path, "src-fresh", ["lane-a"], "lane-a", "2026-09-26", BARRIER_A,
                       usage="holdout")
    opened = ledger_path.read_bytes()
    with pytest.raises(ledger.LedgerError, match="registration and the ledger disagree"):
        ledger.record_open(ledger_path, "src-fresh", ["lane-c"], "lane-c", "2026-09-27", BARRIER_B,
                           usage="holdout")
    # a member of a recorded group must register the same usage as the group
    with pytest.raises(ledger.LedgerError, match="recorded as holdout"):
        ledger.record_open(ledger_path, "src-fresh", ["lane-a"], "lane-a", "2026-09-26", BARRIER_A,
                           usage="reused_disjoint")
    with pytest.raises(ledger.LedgerError, match="usage must be one of"):
        ledger.record_open(ledger_path, "src-fresh", ["lane-c"], "lane-c", "2026-09-27", BARRIER_B,
                           usage="reuse")
    assert ledger_path.read_bytes() == opened


def test_a_discovery_source_is_not_a_holdout(ledger_path):
    before = ledger_path.read_bytes()
    with pytest.raises(ledger.LedgerError, match="not a clean holdout"):
        ledger.record_open(ledger_path, "src-used", ["lane-a"], "lane-a", "2026-09-26", BARRIER_A,
                           usage="holdout")
    assert ledger_path.read_bytes() == before


def test_unknown_sources_and_bad_input_are_refused(ledger_path):
    with pytest.raises(ledger.LedgerError, match="missing"):
        ledger.record_discovery(ledger_path, "src-none", "lane-a", "2026-09-26")
    with pytest.raises(ledger.LedgerError, match="date"):
        ledger.record_discovery(ledger_path, "src-meta", "lane-a", "26/09/2026")
    with pytest.raises(ledger.LedgerError, match="SHA-256"):
        ledger.record_open(ledger_path, "src-fresh", ["lane-a"], "lane-a", "2026-09-26", "abc",
                           usage="holdout")


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


def test_export_public_keeps_checked_fields_only(ledger_path, deny_file):
    ledger.record_open(ledger_path, "src-fresh", ["lane-a"], "lane-a", "2026-09-26", BARRIER_A,
                       usage="holdout")
    edit(ledger_path, "src-meta", campaigns=["earlier", "a free-text note, not a token"])
    text = ledger.export_public(ledger_path, deny_file=deny_file)
    public = json.loads(text)
    assert public["schema"] == "bio-holdout-ledger-public/2"
    assert [e["id"] for e in public["entries"]] == ["src-fresh", "src-future", "src-meta",
                                                    "src-retired", "src-used"]
    assert all(set(e) == set(ledger.PUBLIC_FIELDS) for e in public["entries"])
    assert "name" not in ledger.PUBLIC_FIELDS
    for private in ("private note", "private-locator", "Fresh source", "free-text note"):
        assert private not in text
    meta = next(e for e in public["entries"] if e["id"] == "src-meta")
    assert meta["campaigns"] == ["earlier", ledger.PLACEHOLDER]
    assert public["free_text_items_withheld"] == 1
    assert ledger.export_public(ledger_path, deny_file=deny_file) == text


@pytest.mark.parametrize("field, value, message", [
    ("id", "has space", "id is not a plain token"),
    ("kind", "table/with/slash", "kind is not a plain token"),
    ("status", "Not A Token", "status is not a plain token"),
    ("status", "INVENTED", "not one of the ledger's statuses"),
    ("opened_on", "26/09/2026", "opened_on must be YYYY-MM-DD"),
    ("opened_on", "2026-02-30", "date must be YYYY-MM-DD"),
    ("opened_on", 20260926, "opened_on must be YYYY-MM-DD"),
    ("verified", "2026-09-25", "verified must be"),
    ("opened_for", "lane-a", "opened_for must be a list"),
])
def test_export_public_refuses_an_unchecked_field(ledger_path, deny_file, field, value, message):
    edit(ledger_path, "src-meta", **{field: value})
    with pytest.raises(ledger.LedgerError, match=message):
        ledger.export_public(ledger_path, deny_file=deny_file)


def test_export_public_refuses_duplicates_and_a_missing_statuses_object(ledger_path, deny_file):
    doc = load(ledger_path)
    doc["entries"].append(dict(doc["entries"][0]))
    ledger_path.write_text(json.dumps(doc, indent=1) + "\n")
    with pytest.raises(ledger.LedgerError, match="lists an id twice"):
        ledger.export_public(ledger_path, deny_file=deny_file)
    doc["entries"].pop()
    doc.pop("statuses")
    ledger_path.write_text(json.dumps(doc, indent=1) + "\n")
    with pytest.raises(ledger.LedgerError, match="no statuses object"):
        ledger.export_public(ledger_path, deny_file=deny_file)


@pytest.mark.parametrize("item", ["quillon-vantree", "quillon_vantree", "Quillon.Vantree",
                                  "zorblat_draft"])
def test_export_public_refuses_deny_names_joined_by_separators(ledger_path, deny_file, capsys,
                                                               item):
    # plain tokens, so they reach the public copy unless the deny scan catches them
    edit(ledger_path, "src-meta", opened_for=[item], campaigns=[f"lane-{item}"])
    with pytest.raises(ledger.LedgerError, match="hygiene check") as caught:
        ledger.export_public(ledger_path, deny_file=deny_file)
    assert ledger.main(["export-public", "--ledger", str(ledger_path),
                        "--deny-file", str(deny_file)]) == 2
    out = capsys.readouterr()
    for part in ("quillon", "vantree", "zorblat"):
        assert part not in (str(caught.value) + out.out + out.err).lower()


def test_export_public_needs_a_deny_file_and_refuses_a_deny_list_hit(ledger_path, deny_file,
                                                                     capsys):
    with pytest.raises(ledger.LedgerError, match="needs --deny-file"):
        ledger.export_public(ledger_path, deny_file=None)
    assert ledger.main(["export-public", "--ledger", str(ledger_path)]) == 2
    edit(ledger_path, "src-meta", campaigns=["zorblat-lane"])
    with pytest.raises(ledger.LedgerError, match="hygiene check") as caught:
        ledger.export_public(ledger_path, deny_file=deny_file)
    assert "zorblat" not in str(caught.value).lower()
    assert ledger.main(["export-public", "--ledger", str(ledger_path),
                        "--deny-file", str(deny_file)]) == 2
    assert "zorblat" not in capsys.readouterr().err.lower()


def _barrier_file(tmp_path, campaign="lane-a"):
    path = tmp_path / "group-barrier.json"
    path.write_text(json.dumps({
        "schema": "bio-group-barrier/1", "run_id": "r", "members": ["S01", "S02"],
        "frozen": [{"id": "S01", "campaign": campaign, "freeze_sha256": "c" * 64,
                    "merge_sha": "d" * 40}], "released": ["S02"]}, separators=(",", ":")))
    return path


def test_cli_record_open_from_the_barrier_file(ledger_path, tmp_path, capsys, deny_file):
    barrier_file = _barrier_file(tmp_path)
    args = ["record-open", "--ledger", str(ledger_path), "--source", "src-fresh",
            "--campaign", "lane-a", "--barrier", str(barrier_file), "--date", "2026-09-26",
            "--usage", "holdout"]
    assert ledger.main(args) == 0
    assert capsys.readouterr().out.strip() == "opened"
    assert entry(ledger_path, "src-fresh")["frozen_set_sha256"] == sha256_file(barrier_file)
    assert ledger.main(args) == 0
    assert capsys.readouterr().out.strip() == "unchanged"
    assert ledger.main(["export-public", "--ledger", str(ledger_path),
                        "--deny-file", str(deny_file)]) == 0
    public = json.loads(capsys.readouterr().out)
    assert next(e for e in public["entries"] if e["id"] == "src-fresh")["status"] == "OPENED"


def test_cli_record_open_needs_a_usage_that_matches(ledger_path, tmp_path, capsys):
    barrier_file = _barrier_file(tmp_path)
    base = ["record-open", "--ledger", str(ledger_path), "--source", "src-fresh",
            "--campaign", "lane-a", "--barrier", str(barrier_file), "--date", "2026-09-26"]
    before = ledger_path.read_bytes()
    assert ledger.main(base) == 2
    assert "--usage" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        ledger.main(base + ["--usage", "whatever"])
    assert ledger.main(base + ["--usage", "reused_disjoint"]) == 2
    assert "disagree" in capsys.readouterr().err
    assert ledger_path.read_bytes() == before


def test_cli_flags_that_disagree_with_the_barrier_file_are_refused(ledger_path, tmp_path, capsys):
    barrier_file = _barrier_file(tmp_path)
    base = ["record-open", "--ledger", str(ledger_path), "--source", "src-fresh",
            "--campaign", "lane-a", "--barrier", str(barrier_file), "--date", "2026-09-26",
            "--usage", "holdout"]
    before = ledger_path.read_bytes()
    assert ledger.main(base + ["--frozen-campaign", "lane-z"]) == 2
    assert "--frozen-campaign disagrees" in capsys.readouterr().err
    assert ledger.main(base + ["--barrier-sha256", "e" * 64]) == 2
    assert "--barrier-sha256 disagrees" in capsys.readouterr().err
    assert ledger_path.read_bytes() == before
