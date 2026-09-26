"""Public assembly: byte-identical registered files, path scrubbing, private data kept out."""

from __future__ import annotations

import json
import subprocess

import pytest

from bio_lab.campaign_kit import assemble_public, freeze
from bio_lab.campaign_kit.common import append_jsonl, sha256_file
from conftest import make_campaign, write

NAME = "demo-lane-2026-09-26"


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / "public-repo"
    path.mkdir()
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    return path


@pytest.fixture
def campaign(tmp_path):
    campaign = make_campaign(tmp_path / "research", NAME)
    freeze.build(campaign)
    return campaign


def test_prereg_publishes_registered_files_byte_identical(campaign, repo):
    manifest = assemble_public.assemble(campaign, repo, NAME, "prereg")
    out = repo / "campaigns" / NAME
    for rel in ("lane.json", "registration/protocol.json", "registration/freeze.json",
                "code/confirm.py", "tests/test_demo.py"):
        assert (out / rel).read_bytes() == (campaign / rel).read_bytes()
    assert freeze.verify(out)["ok"]
    assert (out / "assembly.manifest.json").is_file()
    assert manifest["schema"] == "bio.assembly-manifest.v2"
    assert all(f["registered"] and not f["path_prefix_redacted"] for f in manifest["files"])


def test_unregistered_files_are_scrubbed(campaign, repo, tmp_path):
    private_tmp = "/" + "private" + "/var/folders/xy/T/run-1/out.txt"
    home = "/" + "Users" + "/someone/Documents/notes.md"
    parent = str(campaign.parent)
    write(campaign / "audit" / "metadata.md",
          f"cache at {parent}/other-lane/x.csv\nlog {private_tmp}\nsee {home}\n")
    manifest = assemble_public.assemble(campaign, repo, NAME, "prereg")
    text = (repo / "campaigns" / NAME / "audit" / "metadata.md").read_text()
    assert text == "cache at <research-root>/other-lane/x.csv\nlog <tmp>\nsee <home>/Documents/notes.md\n"
    entry = next(f for f in manifest["files"] if f["source"] == "audit/metadata.md")
    assert entry["path_prefix_redacted"] and entry["sha256_original"] == sha256_file(
        campaign / "audit" / "metadata.md")


def test_private_data_is_never_walked_but_receipts_are_published(tmp_path, repo):
    campaign = make_campaign(tmp_path / "research", NAME)
    write(campaign / "data" / "discovery" / "table.csv", "a,b\n1,2\n")
    append_jsonl(campaign / "data" / "discovery" / "receipts.jsonl", {"file": "table.csv"})
    freeze.build(campaign)
    write(campaign / "data" / "sealed" / "holdout.csv", "synthetic\n")
    append_jsonl(campaign / "data" / "sealed" / "receipts.jsonl", {"file": "holdout.csv"})
    manifest = assemble_public.assemble(campaign, repo, NAME, "prereg")
    out = repo / "campaigns" / NAME / "data"
    assert (out / "sealed" / "receipts.jsonl").is_file()
    assert (out / "discovery" / "receipts.jsonl").is_file()
    assert not (out / "sealed" / "holdout.csv").exists()
    assert not (out / "discovery" / "table.csv").exists()
    skipped = {s["source"]: s["reason"] for s in manifest["skipped"]}
    assert skipped["data/sealed/"] == "private data" and skipped["data/discovery/"] == "private data"
    assert "holdout.csv" not in json.dumps(manifest)


def test_prereg_refuses_once_results_exist(campaign, repo):
    write(campaign / "results" / "confirmation.summary.json", "{}\n")
    with pytest.raises(assemble_public.AssemblyError, match="results/"):
        assemble_public.plan(campaign, repo, NAME, "prereg")


def test_outcome_puts_the_report_under_reports(campaign, repo):
    assemble_public.assemble(campaign, repo, NAME, "prereg")
    write(campaign / "results" / "confirmation.summary.json", '{"label": "SUPPORTED"}\n')
    write(campaign / "report.md", "# Report\n\nAn association, not a cause.\n")
    assemble_public.assemble(campaign, repo, NAME, "outcome")
    assert (repo / "reports" / NAME / "report.md").is_file()
    assert (repo / "reports" / NAME / "assembly.manifest.json").is_file()
    assert (repo / "campaigns" / NAME / "results" / "confirmation.summary.json").is_file()


def test_assembly_refuses_changed_or_conflicting_registered_files(campaign, repo):
    (campaign / "code" / "confirm.py").write_text("edited\n")
    with pytest.raises(assemble_public.AssemblyError, match="freeze verify failed"):
        assemble_public.plan(campaign, repo, NAME, "prereg")


def test_assembly_refuses_a_different_copy_already_in_the_worktree(campaign, repo):
    write(repo / "campaigns" / NAME / "code" / "confirm.py", "someone else's copy\n")
    with pytest.raises(assemble_public.AssemblyError, match="differs from the copy"):
        assemble_public.plan(campaign, repo, NAME, "prereg")


def test_assembly_refuses_bad_names_symlinks_and_excluding_registered(campaign, repo, tmp_path):
    with pytest.raises(assemble_public.AssemblyError, match="lowercase"):
        assemble_public.plan(campaign, repo, "Bad Name", "prereg")
    with pytest.raises(assemble_public.AssemblyError, match="git worktree"):
        assemble_public.plan(campaign, tmp_path, NAME, "prereg")
    with pytest.raises(assemble_public.AssemblyError, match="registered file"):
        assemble_public.plan(campaign, repo, NAME, "prereg", exclude=["code"])
    (campaign / "audit").mkdir()
    (campaign / "audit" / "link.md").symlink_to(campaign / "lane.json")
    with pytest.raises(assemble_public.AssemblyError, match="symlink"):
        assemble_public.plan(campaign, repo, NAME, "prereg")


def test_assembly_hygiene_refuses_a_deny_hit(campaign, repo, tmp_path):
    name = "Zorb" + "lax"
    deny = tmp_path / "deny.txt"
    deny.write_text(name + "\n")
    write(campaign / "review" / "notes.md", f"reviewed with {name}\n")
    with pytest.raises(assemble_public.AssemblyError) as error:
        assemble_public.plan(campaign, repo, NAME, "prereg", deny_file=deny)
    assert "deny-list name" in str(error.value) and name not in str(error.value)
    assert not (repo / "campaigns").exists()


def test_large_unregistered_files_are_skipped_with_their_hash(campaign, repo):
    big = write(campaign / "fanout" / "big.txt", "x" * (4 * 1024 * 1024 + 10))
    write(campaign / "fanout" / "matrix.npz", "binary")
    manifest = assemble_public.assemble(campaign, repo, NAME, "prereg")
    skipped = {s["source"]: s for s in manifest["skipped"]}
    assert skipped["fanout/big.txt"]["reason"] == "over 4 MB"
    assert skipped["fanout/big.txt"]["sha256"] == sha256_file(big)
    assert skipped["fanout/matrix.npz"]["reason"] == "binary data format"
