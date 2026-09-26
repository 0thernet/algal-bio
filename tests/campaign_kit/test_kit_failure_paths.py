"""Failure paths of the barrier, the freeze, the seal and the run guard."""

from __future__ import annotations

import hashlib
import json
import os

import pytest

from bio_lab.campaign_kit import barrier, freeze, runguard, seal
from bio_lab.campaign_kit.common import KitError, append_jsonl
from conftest import barrier_doc, frozen_entry, make_campaign, write

DATA = b"model_id,score\nM1,0.5\n"
NAME = "Zorb" + "lax"          # a synthetic deny-list name, never whole in a file


@pytest.fixture
def deny_file(tmp_path):
    path = tmp_path / "deny.txt"
    path.write_text(NAME + "\n")
    return path


def frozen(root, name, lane_id):
    campaign = make_campaign(root, name, lane_id)
    _, sha = freeze.build(campaign)
    barrier.write(campaign, barrier_doc([lane_id], [frozen_entry(lane_id, name, sha)]))
    return campaign, sha


# ---------------------------------------------------------------- barrier.require

def test_barrier_refuses_a_lane_json_that_names_another_lane(frozen_campaign):
    campaign, lane_id, sha, name = frozen_campaign
    (campaign / "lane.json").write_text(json.dumps({"id": "S09", "slug": name}) + "\n")
    with pytest.raises(barrier.BarrierError, match="lane.json names another lane"):
        barrier.require(campaign, lane_id, sha)


def test_barrier_refuses_a_freeze_replaced_after_the_barrier(frozen_campaign):
    campaign, lane_id, sha, name = frozen_campaign
    path = campaign / freeze.FREEZE
    path.chmod(0o644)
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(barrier.BarrierError, match="does not hash to the barrier's freeze sha"):
        barrier.require(campaign, lane_id, sha)


def test_barrier_refuses_an_invalid_barrier_file(frozen_campaign):
    campaign, lane_id, sha, name = frozen_campaign
    path = campaign / "audit" / "group-barrier.json"
    path.chmod(0o644)
    path.write_text("{not json")
    with pytest.raises(barrier.BarrierError, match="not valid JSON"):
        barrier.require(campaign, lane_id, sha)
    path.write_text(json.dumps({"schema": barrier.SCHEMA}))
    with pytest.raises(barrier.BarrierError, match="exactly the keys"):
        barrier.require(campaign, lane_id, sha)


# ---------------------------------------------------------------- freeze

def test_freeze_refuses_a_deny_list_hit_in_content_or_a_file_name(tmp_path, deny_file):
    campaign = make_campaign(tmp_path)
    write(campaign / "registration" / "notes.md", f"reviewed with {NAME}\n")
    with pytest.raises(freeze.FreezeError, match="deny-list name") as error:
        freeze.build(campaign, deny_file=deny_file)
    assert NAME.lower() not in str(error.value).lower()
    (campaign / "registration" / "notes.md").unlink()
    write(campaign / "registration" / f"{NAME.lower()}-notes.md", "clean\n")
    with pytest.raises(freeze.FreezeError, match="deny-list name") as error:
        freeze.build(campaign, deny_file=deny_file)
    assert NAME.lower() not in str(error.value).lower()
    assert not (campaign / freeze.FREEZE).exists()


def test_freeze_refuses_a_symlinked_directory(tmp_path):
    campaign = make_campaign(tmp_path)
    (tmp_path / "elsewhere").mkdir()
    (campaign / "code" / "lib").symlink_to(tmp_path / "elsewhere", target_is_directory=True)
    with pytest.raises(freeze.FreezeError, match="symlink"):
        freeze.build(campaign)


@pytest.mark.parametrize("include, message", [
    ("audit/missing.md", "missing"),
    ("../outside.md", "relative"),
    ("/abs/path.md", "relative"),
    ("Data/Sealed/x.csv", "never frozen"),
    ("data/SANGER_HOLDOUT/x.csv", "never frozen"),
])
def test_freeze_refuses_missing_escaping_or_sealed_includes(tmp_path, include, message):
    campaign = make_campaign(tmp_path)
    write(tmp_path / "outside.md", "x\n")
    with pytest.raises(KitError, match=message):
        freeze.build(campaign, include=[include])
    assert not (campaign / freeze.FREEZE).exists()


def test_freeze_refuses_sealed_files_in_any_letter_case(tmp_path):
    campaign = make_campaign(tmp_path)
    write(campaign / "data" / "Sanger_Holdout" / "values.csv", "synthetic\n")
    with pytest.raises(freeze.FreezeError, match="already holds files"):
        freeze.build(campaign)


def test_freeze_verify_refuses_a_symlink_added_later(tmp_path):
    campaign = make_campaign(tmp_path)
    freeze.build(campaign)
    (campaign / "code" / "extra.py").symlink_to(campaign / "code" / "confirm.py")
    with pytest.raises(KitError, match="symlink"):
        freeze.verify(campaign)


# ---------------------------------------------------------------- seal

def place_sealed(campaign, name="holdout.csv", data=DATA):
    with seal.writable(campaign) as directory:
        (directory / name).write_bytes(data)
        append_jsonl(directory / "receipts.jsonl",
                     {"file": name, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})


def test_writable_locks_again_after_an_exception(frozen_campaign):
    campaign, _, _, _ = frozen_campaign
    with pytest.raises(RuntimeError):
        with seal.writable(campaign) as directory:
            (directory / "partial.csv").write_bytes(b"x")
            raise RuntimeError("fetch failed")
    directory = campaign / "data" / "sealed"
    assert (directory.stat().st_mode & 0o777) == 0o500
    assert ((directory / "partial.csv").stat().st_mode & 0o777) == 0
    assert seal.status(campaign)["locked"] is True


def test_open_sealed_refuses_another_campaigns_run_and_a_symlink(tmp_path):
    first, _ = frozen(tmp_path / "a", "first-lane-2026-09-26", "S01")
    second, _ = frozen(tmp_path / "b", "second-lane-2026-09-26", "S02")
    place_sealed(first)
    outside = tmp_path / "outside.csv"
    outside.write_bytes(DATA)
    # seal.lock refuses to lock through a symlink, so plant one in an unlocked directory
    seal.unlock(first)
    link = first / "data" / "sealed" / "link.csv"
    link.symlink_to(outside)
    append_jsonl(link.parent / "receipts.jsonl",
                 {"file": "link.csv", "sha256": hashlib.sha256(DATA).hexdigest()})
    with pytest.raises(seal.SealError, match="symlink"):
        seal.lock(first)
    # a run relocks the sealed directory on entry, so it refuses one with a symlink
    with pytest.raises(seal.SealError, match="symlink"):
        with runguard.run(first, lane_id="S01"):
            pass
    assert runguard.history(first) == []
    try:
        with runguard.run(second, lane_id="S02") as other:
            with pytest.raises(seal.SealError, match="this campaign's active runguard run"):
                seal.open_sealed(first, "holdout.csv", other)
            other.finish("NOT_RUN")
        link.unlink()
        with runguard.run(first, lane_id="S01") as active:
            # planted after the run started
            seal.unlock(first)
            link.symlink_to(outside)
            with pytest.raises(seal.SealError, match="not a regular sealed file"):
                seal.open_sealed(first, "link.csv", active)
            active.finish("NOT_RUN")
    finally:
        link.unlink(missing_ok=True)
        seal.unlock(first)
        seal.unlock(second)


# ---------------------------------------------------------------- run guard

def test_finish_refuses_bad_outputs_labels_and_a_second_call(frozen_campaign):
    campaign, lane_id, _, _ = frozen_campaign
    with runguard.run(campaign, lane_id=lane_id) as active:
        write(campaign / "results" / "confirmation.summary.json", "{}\n")
        with pytest.raises(runguard.RunGuardError, match="does not exist"):
            active.finish("SUPPORTED", outputs=["results/missing.json"])
        with pytest.raises(runguard.RunGuardError, match="outcome label"):
            active.finish("", outputs=[])
        with pytest.raises(KitError, match="canonical relative path"):
            active.finish("SUPPORTED", outputs=["../outside.json"])
        with pytest.raises(KitError, match="canonical relative path"):
            active.finish("SUPPORTED", outputs=["/abs.json"])
        active.finish("SUPPORTED", outputs=["results/confirmation.summary.json"])
        with pytest.raises(runguard.RunGuardError, match="not active"):
            active.finish("SUPPORTED")
    assert [r["event"] for r in runguard.history(campaign)] == ["start", "finish"]


@pytest.mark.parametrize("erratum, message", [
    ("errata/E1.md", "does not exist or is empty"),
    ("errata/blank.md", "does not exist or is empty"),
    ("../errata/E1.md", "canonical relative path"),
    ("errata/../lane.json", "canonical relative path"),
    ("notes/E1.md", "under errata/"),
])
def test_a_blank_missing_or_escaping_erratum_is_refused(frozen_campaign, erratum, message):
    campaign, lane_id, _, _ = frozen_campaign
    with runguard.run(campaign, lane_id=lane_id) as active:
        active.finish("SUPPORTED")
    write(campaign / "errata" / "blank.md", "  \n\t\n")
    write(campaign / "notes" / "E1.md", "a reason\n")
    before = (campaign / runguard.LEDGER).read_bytes()
    with pytest.raises(KitError, match=message):
        with runguard.run(campaign, lane_id=lane_id, erratum=erratum):
            pass
    assert (campaign / runguard.LEDGER).read_bytes() == before
    assert not os.path.exists(campaign / "errata" / "E1.md")
