"""Write-once freeze and the holdout-group barrier."""

from __future__ import annotations

import json

import pytest

from bio_lab.campaign_kit import barrier, freeze
from bio_lab.campaign_kit.common import sha256_file
from conftest import barrier_doc, frozen_entry, make_campaign, write

PERSONAL = "/" + "Users" + "/someone/research"


# ---------------------------------------------------------------- freeze

def test_freeze_build_and_verify(tmp_path):
    campaign = make_campaign(tmp_path)
    manifest, sha = freeze.build(campaign)
    assert sha == sha256_file(campaign / freeze.FREEZE) == freeze.freeze_sha256(campaign)
    assert sorted(manifest["sha256"]) == ["code/confirm.py", "lane.json",
                                          "registration/protocol.json", "tests/test_demo.py"]
    assert manifest["top_digest"] == freeze.top_digest(manifest["sha256"])
    result = freeze.verify(campaign)
    assert result["ok"] and result["files"] == 4 and result["lane_id"] == "S01"


def test_freeze_refuses_a_second_freeze(tmp_path):
    campaign = make_campaign(tmp_path)
    freeze.build(campaign)
    before = (campaign / freeze.FREEZE).read_bytes()
    with pytest.raises(freeze.FreezeError, match="write-once"):
        freeze.build(campaign)
    assert (campaign / freeze.FREEZE).read_bytes() == before


def test_freeze_refuses_after_results_or_sealed_files(tmp_path):
    campaign = make_campaign(tmp_path / "a")
    write(campaign / "results" / "early.json", "{}\n")
    with pytest.raises(freeze.FreezeError, match="results/"):
        freeze.build(campaign)
    campaign = make_campaign(tmp_path / "b")
    write(campaign / "data" / "sealed" / "holdout.csv", "synthetic\n")
    with pytest.raises(freeze.FreezeError, match="nothing may be fetched"):
        freeze.build(campaign)
    assert not (campaign / freeze.FREEZE).exists()


def test_freeze_refuses_missing_lane_or_protocol(tmp_path):
    campaign = make_campaign(tmp_path / "a")
    (campaign / "lane.json").write_text('{"slug": "x"}\n')
    with pytest.raises(freeze.FreezeError, match="lane id"):
        freeze.build(campaign)
    campaign = make_campaign(tmp_path / "b")
    (campaign / "registration" / "protocol.json").unlink()
    with pytest.raises(freeze.FreezeError, match="protocol.json"):
        freeze.build(campaign)


def test_freeze_refuses_personal_paths_symlinks_and_sealed_roots(tmp_path):
    campaign = make_campaign(tmp_path / "a")
    write(campaign / "code" / "paths.py", f"DATA = {PERSONAL!r}\n")
    with pytest.raises(freeze.FreezeError, match="personal path"):
        freeze.build(campaign)
    campaign = make_campaign(tmp_path / "b")
    (campaign / "code" / "link.py").symlink_to(campaign / "code" / "confirm.py")
    with pytest.raises(freeze.FreezeError, match="symlink"):
        freeze.build(campaign)
    campaign = make_campaign(tmp_path / "c")
    for root in ("results", "data/sealed", "data/discovery", "code/sealed"):
        with pytest.raises(freeze.FreezeError, match="never frozen"):
            freeze.build(campaign, include=[root])


def test_freeze_refuses_oversized_registered_files(tmp_path):
    campaign = make_campaign(tmp_path)
    write(campaign / "registration" / "big.txt", "x" * (4 * 1024 * 1024 + 1))
    with pytest.raises(freeze.FreezeError, match="over 4 MB"):
        freeze.build(campaign)


def test_freeze_verify_reports_changed_missing_and_added(tmp_path):
    campaign = make_campaign(tmp_path)
    freeze.build(campaign)
    (campaign / "code" / "confirm.py").write_text("changed\n")
    (campaign / "tests" / "test_demo.py").unlink()
    write(campaign / "code" / "late.py", "late = True\n")
    with pytest.raises(freeze.FreezeError) as error:
        freeze.verify(campaign)
    message = str(error.value)
    assert "changed: code/confirm.py" in message
    assert "missing: tests/test_demo.py" in message
    assert "added: code/late.py" in message


def test_freeze_verify_refuses_an_edited_manifest(tmp_path):
    campaign = make_campaign(tmp_path)
    freeze.build(campaign)
    path = campaign / freeze.FREEZE
    manifest = json.loads(path.read_text())
    manifest["sha256"]["code/confirm.py"] = "0" * 64
    path.write_text(json.dumps(manifest))
    with pytest.raises(freeze.FreezeError, match="top digest"):
        freeze.verify(campaign)


@pytest.mark.parametrize("edit, message", [
    (lambda m: m.update(schema="other"), "not a kit freeze manifest"),
    (lambda m: m.pop("schema"), "not a kit freeze manifest"),
    (lambda m: m.update(sha256={}), "lacks its file list"),
    (lambda m: m.update(sha256=[]), "lacks its file list"),
    (lambda m: m.pop("sha256"), "lacks its file list"),
    (lambda m: m.update(declared="code"), "lacks its file list"),
    (lambda m: m.pop("declared"), "lacks its file list"),
])
def test_freeze_verify_refuses_a_manifest_that_is_not_a_kit_freeze(tmp_path, edit, message):
    campaign = make_campaign(tmp_path)
    freeze.build(campaign)
    assert freeze.verify(campaign)["ok"]
    path = campaign / freeze.FREEZE
    manifest = json.loads(path.read_text())
    edit(manifest)
    path.write_text(json.dumps(manifest))
    with pytest.raises(freeze.FreezeError, match=message):
        freeze.verify(campaign)


@pytest.mark.parametrize("root", ["code", "tests", "registration"])
def test_freeze_refuses_a_symlinked_registered_root(tmp_path, root):
    campaign = make_campaign(tmp_path / "lane")
    real = tmp_path / f"real-{root}"
    (campaign / root).rename(real)
    (campaign / root).symlink_to(real, target_is_directory=True)
    with pytest.raises(freeze.FreezeError, match=f"{root} is a symlink"):
        freeze.build(campaign)
    assert not (campaign / freeze.FREEZE).exists() and not (real / "freeze.json").exists()


def test_freeze_ignores_bytecode_caches(tmp_path):
    campaign = make_campaign(tmp_path)
    freeze.build(campaign)
    write(campaign / "code" / "__pycache__" / "confirm.cpython-312.pyc", "bytecode")
    assert freeze.verify(campaign)["ok"]


def test_freeze_cli(tmp_path, capsys):
    campaign = make_campaign(tmp_path)
    assert freeze.main(["build", str(campaign)]) == 0
    assert freeze.main(["build", str(campaign)]) == 2
    assert "write-once" in capsys.readouterr().err
    assert freeze.main(["verify", str(campaign)]) == 0


# ---------------------------------------------------------------- barrier

def test_barrier_is_compact_json_in_the_workflow_key_order(frozen_campaign):
    campaign, lane_id, sha, name = frozen_campaign
    raw = (campaign / barrier.BARRIER).read_text()
    expected = ('{"schema":"bio-group-barrier/1","run_id":"2026-09-26-campaigns",'
                '"members":["S01","S02"],"frozen":[{"id":"S01","campaign":"' + name + '",'
                '"freeze_sha256":"' + sha + '","merge_sha":"' + "a" * 40 + '"}],"released":["S02"]}')
    assert raw == expected


def test_barrier_require_returns_a_proof(frozen_campaign):
    campaign, lane_id, sha, name = frozen_campaign
    proof = barrier.require(campaign, lane_id, sha)
    assert proof.lane_id == "S01" and proof.campaign == name
    assert proof.barrier_sha256 == sha256_file(campaign / barrier.BARRIER)
    assert proof.frozen_campaigns == (name,)


def test_barrier_write_is_idempotent_and_never_rewritten(frozen_campaign):
    campaign, lane_id, sha, name = frozen_campaign
    doc = barrier_doc(["S01", "S02"], [frozen_entry("S01", name, sha)], released=["S02"])
    before = (campaign / barrier.BARRIER).read_bytes()
    assert barrier.write(campaign, doc) == sha256_file(campaign / barrier.BARRIER)
    other = barrier_doc(["S01"], [frozen_entry("S01", name, sha)])
    with pytest.raises(barrier.BarrierError, match="never rewritten"):
        barrier.write(campaign, other)
    assert (campaign / barrier.BARRIER).read_bytes() == before


def test_barrier_missing_refuses(tmp_path):
    campaign = make_campaign(tmp_path)
    _, sha = freeze.build(campaign)
    with pytest.raises(barrier.BarrierError, match="missing"):
        barrier.require(campaign, "S01", sha)


def test_barrier_of_another_group_refuses(tmp_path):
    campaign = make_campaign(tmp_path)
    _, sha = freeze.build(campaign)
    doc = barrier_doc(["S07"], [frozen_entry("S07", "other-lane-2026-09-26", "b" * 64)])
    barrier.write(campaign, doc)
    with pytest.raises(barrier.BarrierError, match="another group"):
        barrier.require(campaign, "S01", sha)


def test_barrier_released_lane_refuses(tmp_path):
    campaign = make_campaign(tmp_path)
    _, sha = freeze.build(campaign)
    doc = barrier_doc(["S01", "S02"], [frozen_entry("S02", "other-lane-2026-09-26", "b" * 64)],
                      released=["S01"])
    barrier.write(campaign, doc)
    with pytest.raises(barrier.BarrierError, match="released"):
        barrier.require(campaign, "S01", sha)


def test_barrier_refuses_wrong_sha_wrong_dir_or_changed_freeze(frozen_campaign, tmp_path):
    campaign, lane_id, sha, name = frozen_campaign
    with pytest.raises(barrier.BarrierError, match="another freeze sha"):
        barrier.require(campaign, lane_id, "c" * 64)
    with pytest.raises(barrier.BarrierError, match="SHA-256"):
        barrier.require(campaign, lane_id, "short")
    (campaign / "code" / "confirm.py").write_text("edited after the freeze\n")
    with pytest.raises(barrier.BarrierError, match="freeze verify failed"):
        barrier.require(campaign, lane_id, sha)
    elsewhere = make_campaign(tmp_path / "x", name="another-lane-2026-09-26")
    _, sha2 = freeze.build(elsewhere)
    barrier.write(elsewhere, barrier_doc(["S01"], [frozen_entry("S01", name, sha2)]))
    with pytest.raises(barrier.BarrierError, match="not this directory"):
        barrier.require(elsewhere, "S01", sha2)


@pytest.mark.parametrize("mutate, message", [
    (lambda d: d.update(schema="other"), "schema"),
    (lambda d: d.update(extra=1), "exactly the keys"),
    (lambda d: d["frozen"][0].update(merge_sha="pending"), "merge_sha"),
    (lambda d: d["frozen"][0].update(freeze_sha256="x"), "freeze_sha256"),
    (lambda d: d.update(released=[]), "every member"),
    (lambda d: d.update(released=["S01", "S02"]), "both frozen and released"),
    (lambda d: d.update(members=["S01", "S01", "S02"]), "duplicates"),
])
def test_barrier_validation(mutate, message):
    doc = barrier_doc(["S01", "S02"], [frozen_entry("S01", "demo", "b" * 64)], released=["S02"])
    mutate(doc)
    with pytest.raises(barrier.BarrierError, match=message):
        barrier.canonical(doc)


def _entry(**changes):
    item = frozen_entry("S01", "demo", "b" * 64)
    item.update(changes)
    return item


@pytest.mark.parametrize("mutate, message", [
    (lambda d: d.update(run_id=""), "run_id must be a nonempty string"),
    (lambda d: d.update(run_id=None), "run_id must be a nonempty string"),
    (lambda d: d.update(run_id=20260926), "run_id must be a nonempty string"),
    (lambda d: d.update(members=[]), "lists no members"),
    (lambda d: d.update(frozen=_entry()), "frozen must be a list"),
    (lambda d: d.update(frozen=None), "frozen must be a list"),
    (lambda d: d.update(frozen=["S01"]), "each frozen member needs exactly"),
    (lambda d: d["frozen"][0].pop("merge_sha"), "each frozen member needs exactly"),
    (lambda d: d["frozen"][0].update(note="x"), "each frozen member needs exactly"),
    (lambda d: d["frozen"][0].update(id=""), "id and campaign must be nonempty"),
    (lambda d: d["frozen"][0].update(campaign=""), "id and campaign must be nonempty"),
    (lambda d: d["frozen"][0].update(id=1), "id and campaign must be nonempty"),
    (lambda d: d.update(frozen=[_entry(), _entry()]), "frozen member twice"),
    (lambda d: d.update(frozen=[], released=["S01", "S02"]), "no frozen member"),
])
def test_a_malformed_barrier_is_never_written(tmp_path, mutate, message):
    campaign = make_campaign(tmp_path)
    doc = barrier_doc(["S01", "S02"], [frozen_entry("S01", "demo", "b" * 64)], released=["S02"])
    barrier.canonical(doc)                 # the unmutated document is valid
    mutate(doc)
    with pytest.raises(barrier.BarrierError, match=message):
        barrier.write(campaign, doc)
    assert not (campaign / barrier.BARRIER).exists()
    assert not (campaign / "audit").exists()


def test_barrier_cli(frozen_campaign, capsys):
    campaign, lane_id, sha, name = frozen_campaign
    assert barrier.main(["require", str(campaign), "--lane", lane_id, "--freeze-sha256", sha]) == 0
    assert barrier.main(["require", str(campaign), "--lane", "S09", "--freeze-sha256", sha]) == 2
    assert "refusing" in capsys.readouterr().err
