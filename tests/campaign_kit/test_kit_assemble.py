"""Public assembly: byte-identical registered files, path scrubbing, private data kept out."""

from __future__ import annotations

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


def test_private_data_is_never_walked_and_sealed_receipts_come_from_audit(tmp_path, repo):
    campaign = make_campaign(tmp_path / "research", NAME)
    write(campaign / "data" / "discovery" / "table.csv", "a,b\n1,2\n")
    append_jsonl(campaign / "data" / "discovery" / "receipts.jsonl", {"file": "table.csv"})
    freeze.build(campaign)
    write(campaign / "data" / "sealed" / "holdout.csv", "synthetic\n")
    append_jsonl(campaign / "data" / "sealed" / "receipts.jsonl", {"file": "holdout.csv"})
    append_jsonl(campaign / "audit" / "sealed-receipts.jsonl",
                 {"file": "holdout.csv", "path": "data/sealed/holdout.csv", "sha256": "0" * 64})
    manifest = assemble_public.assemble(campaign, repo, NAME, "prereg")
    out = repo / "campaigns" / NAME
    assert not (out / "data" / "sealed").exists()
    assert (out / "data" / "discovery" / "receipts.jsonl").is_file()
    assert not (out / "data" / "discovery" / "table.csv").exists()
    assert (out / "audit" / "sealed-receipts.jsonl").read_bytes() == (
        campaign / "audit" / "sealed-receipts.jsonl").read_bytes()
    skipped = {s["source"]: s["reason"] for s in manifest["skipped"]}
    assert skipped["data/sealed/"] == "sealed data" and skipped["data/discovery/"] == "private data"
    assert not any(s.startswith("data/sealed/") and s != "data/sealed/" for s in skipped)


@pytest.fixture
def spy(monkeypatch):
    """Record every directory listed and every file opened during the assembly."""
    import builtins
    import io
    import os as _os

    seen = []
    real_scandir, real_open, real_io_open = _os.scandir, builtins.open, io.open

    def scandir(path="."):
        seen.append(str(path))
        return real_scandir(path)

    def opener(real):
        def wrapped(file, *args, **kwargs):
            seen.append(str(file))
            return real(file, *args, **kwargs)
        return wrapped

    monkeypatch.setattr(_os, "scandir", scandir)
    monkeypatch.setattr(builtins, "open", opener(real_open))
    monkeypatch.setattr(io, "open", opener(real_io_open))
    return seen


SEALED_DIRS = ["data/sealed", "Data/Sealed/inner", "data/sanger_holdout", "sub/data/sealed",
               "results/sealed", "deep/x/data/Sanger_Holdout", "misc/SEALED"]


def test_nested_and_case_variant_sealed_dirs_are_never_listed_or_read(tmp_path, repo, spy):
    campaign = make_campaign(tmp_path / "research", NAME)
    freeze.build(campaign)
    for rel in SEALED_DIRS:
        target = campaign.joinpath(*rel.split("/"))
        write(target / "values.csv", "synthetic\n")
        append_jsonl(target / "receipts.jsonl", {"file": "values.csv"})
    write(campaign / "deep" / "x" / "data" / "discovery" / "t.csv", "a\n")
    append_jsonl(campaign / "deep" / "x" / "data" / "discovery" / "receipts.jsonl", {"file": "t.csv"})
    write(campaign / "results" / "confirmation.summary.json", '{"label": "SUPPORTED"}\n')
    write(campaign / "report.md", "# Report\n")
    spy.clear()
    manifest = assemble_public.assemble(campaign, repo, NAME, "outcome")
    from bio_lab.campaign_kit.common import folded_parts, is_sealed_path
    touched = [p for p in spy if is_sealed_path(p) or "sealed" in folded_parts(p)]
    assert touched == []
    # the spy does see the walk and the reads of everything else
    assert any(p.endswith("registration") for p in spy) and any(p.endswith("report.md") for p in spy)
    out = repo / "campaigns" / NAME
    published = {f["source"] for f in manifest["files"]}
    assert "deep/x/data/discovery/receipts.jsonl" in published
    assert not any("values.csv" in p or "sealed" in p.lower() or "holdout" in p.lower()
                   for p in published)
    assert not (out / "results" / "sealed").exists() and not (out / "misc").exists()
    reasons = {s["source"]: s["reason"] for s in manifest["skipped"]}
    for rel in ("data/sealed/", "data/sanger_holdout/", "sub/data/sealed/", "results/sealed/",
                "deep/x/data/Sanger_Holdout/", "misc/SEALED/"):
        assert reasons[rel] == "sealed data", rel
    assert reasons["deep/x/data/discovery/"] == "private data"


def test_receipted_files_are_skipped_in_any_directory(campaign, repo):
    write(campaign / "downloads" / "table.csv", "a,b\n1,2\n")
    write(campaign / "downloads" / "notes.md", "our notes\n")
    append_jsonl(campaign / "downloads" / "receipts.jsonl", {"file": "table.csv", "sha256": "x"})
    write(campaign / "deep" / "er" / "raw.tsv", "a\tb\n")
    append_jsonl(campaign / "deep" / "er" / "receipts.jsonl", {"file": "raw.tsv"})
    manifest = assemble_public.assemble(campaign, repo, NAME, "prereg")
    out = repo / "campaigns" / NAME
    assert not (out / "downloads" / "table.csv").exists()
    assert not (out / "deep" / "er" / "raw.tsv").exists()
    assert (out / "downloads" / "receipts.jsonl").is_file()
    assert (out / "deep" / "er" / "receipts.jsonl").is_file()
    assert (out / "downloads" / "notes.md").is_file()
    reasons = {s["source"]: s["reason"] for s in manifest["skipped"]}
    assert reasons["downloads/table.csv"] == "receipted third-party data"
    assert reasons["deep/er/raw.tsv"] == "receipted third-party data"


@pytest.mark.parametrize("body", ["{not json\n", '{"file": "../escape.csv"}\n', '{"url": "x"}\n',
                                  "[1]\n"])
def test_a_malformed_receipts_file_refuses(campaign, repo, body):
    write(campaign / "downloads" / "receipts.jsonl", body)
    with pytest.raises(assemble_public.AssemblyError, match="receipts.jsonl"):
        assemble_public.plan(campaign, repo, NAME, "prereg")


def test_a_personal_path_that_survives_scrubbing_refuses(campaign, repo):
    write(campaign / "audit" / "env.md", "hosts at " + "/" + "private" + "/etc/hosts\n")
    with pytest.raises(assemble_public.AssemblyError, match="survives scrubbing"):
        assemble_public.plan(campaign, repo, NAME, "prereg")
    assert not (repo / "campaigns").exists()


def test_prereg_refuses_once_a_report_exists(campaign, repo):
    write(campaign / "report.md", "# Report\n")
    with pytest.raises(assemble_public.AssemblyError, match="report.md exists"):
        assemble_public.plan(campaign, repo, NAME, "prereg")


def test_a_worktree_inside_the_campaign_refuses(campaign):
    inner = campaign / "public"
    inner.mkdir()
    subprocess.run(["git", "init", "-q", str(inner)], check=True)
    with pytest.raises(assemble_public.AssemblyError, match="separate trees"):
        assemble_public.plan(campaign, inner, NAME, "prereg")


def test_assembly_hygiene_checks_file_and_directory_names(campaign, repo, tmp_path):
    name = "Zorb" + "lax"
    deny = tmp_path / "deny.txt"
    deny.write_text(name + "\n")
    for target in (campaign / "review" / f"{name.lower()}-notes.md",
                   campaign / f"{name}_dir" / "notes.md",
                   campaign / "fanout" / f"{name}.npz"):
        write(target, "nothing personal\n")
        with pytest.raises(assemble_public.AssemblyError, match="deny-list name") as error:
            assemble_public.plan(campaign, repo, NAME, "prereg", deny_file=deny)
        assert name.lower() not in str(error.value).lower()
        target.unlink()
        if target.parent != campaign and not any(target.parent.iterdir()):
            target.parent.rmdir()
    assemble_public.plan(campaign, repo, NAME, "prereg", deny_file=deny)


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


# ---------------------------------------------------------------- registered files kept whole

def repo_files(repo):
    return sorted(p.relative_to(repo).as_posix() for p in repo.rglob("*")
                  if p.is_file() and ".git" not in p.relative_to(repo).parts)


@pytest.mark.parametrize("layout", ["receipted", "skipped dir", "lock name"])
def test_registered_files_that_would_not_be_published_refuse(tmp_path, repo, layout):
    campaign = make_campaign(tmp_path / "research", NAME)
    if layout == "receipted":
        # a registered file that its directory's receipts.jsonl lists as third-party data
        write(campaign / "code" / "table.csv", "a,b\n1,2\n")
        append_jsonl(campaign / "code" / "receipts.jsonl", {"file": "table.csv"})
        missing = "code/table.csv"
    elif layout == "skipped dir":
        # the freeze registers it, but the assembly never walks a .git directory
        write(campaign / "code" / ".git" / "notes.txt", "registered\n")
        missing = "code/.git/notes.txt"
    else:
        write(campaign / "tests" / ".confirmation.lock", "")
        missing = "tests/.confirmation.lock"
    manifest, _ = freeze.build(campaign)
    assert missing in manifest["sha256"]
    with pytest.raises(assemble_public.AssemblyError,
                       match=f"registered files would not be published: {missing}"):
        assemble_public.assemble(campaign, repo, NAME, "prereg")
    assert repo_files(repo) == []


def test_a_registered_file_that_scrubbing_would_change_refuses(tmp_path, repo, monkeypatch):
    campaign = make_campaign(tmp_path / "research", NAME)
    write(campaign / "code" / "paths.py", "ROOT = 'synthetic-private-root/lane'\n")
    freeze.build(campaign)
    monkeypatch.setattr(assemble_public, "scrub_rules",
                        lambda _campaign: [("synthetic-private-root", "<research-root>")])
    with pytest.raises(assemble_public.AssemblyError,
                       match="registered file code/paths.py would change in the public copy"):
        assemble_public.assemble(campaign, repo, NAME, "prereg")
    assert repo_files(repo) == []
    monkeypatch.undo()                     # without the synthetic rule the same tree publishes
    assemble_public.assemble(campaign, repo, NAME, "prereg")
    assert (repo / "campaigns" / NAME / "code" / "paths.py").read_bytes() == (
        campaign / "code" / "paths.py").read_bytes()
