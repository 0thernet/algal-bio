"""The seal must actually refuse.

A pre-registration is worth nothing if the confirmation step will run anyway
after the protocol or the selection has been edited.
"""
import json, os, shutil, subprocess, sys
import pytest

import confirm as CF

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def build_tree(tmp_path):
    """A minimal campaign tree that code/freeze.py will accept."""
    shutil.copytree(f"{ROOT}/code", tmp_path / "code",
                    ignore=shutil.ignore_patterns("__pycache__"))
    for sub in ("registration", "prior-art", "results", "data/prep", "data/refs",
                "data/sealed", "data/other", "tests"):
        (tmp_path / sub).mkdir(parents=True, exist_ok=True)
    (tmp_path / "prior-art/prior-art-context-dependency.md").write_text("survey\n")
    (tmp_path / "README.campaign.md").write_text("# campaign\n")
    (tmp_path / "data/sanger_holdout.sha256").write_text("0" * 64 + "  archive.zip\n")
    json.dump({"campaign_id": "test-campaign",
               "data": {"second_sealed_resource": {"sha256": "0" * 64}}},
              open(tmp_path / "registration/protocol.json", "w"))
    json.dump({"pairs": []}, open(tmp_path / "registration/gold_controls.json", "w"))
    json.dump({"verdict": "PASS"}, open(tmp_path / "registration/prefreeze-review-3.json", "w"))
    for f in ("data/prep/prep.receipt.json", "data/refs/refs.receipt.json",
              "data/prep/dep_genes.json", "data/prep/ctx_names.json",
              "data/prep/ctx_group.json", "data/prep/ctx_duplicates.json",
              "results/screen.real.json", "results/annotation.summary.json",
              "results/tier_testability.json"):
        json.dump({}, open(tmp_path / f, "w"))
    for f in ("results/candidates.real.csv", "results/selection.real.csv",
              "results/selection.annotated.csv"):
        (tmp_path / f).write_text("context,dep_gene,beta\n")
    (tmp_path / "tests/test_x.py").write_text("def test_x():\n    assert True\n")
    ky = tmp_path / "data/sealed/ScreenGeneEffect.KY.csv"
    cd = tmp_path / "data/other/ScreenGeneEffect.CD.csv"
    joint = tmp_path / "data/sealed/CRISPRGeneEffect.csv"
    ky.write_text("sealed KY\n")
    cd.write_text("sealed CD\n")
    joint.write_text("sealed joint fit\n")
    unsplit = tmp_path / "data/sealed/ScreenGeneEffect.csv"
    unsplit.write_text("unsplit release file, carries the KY rows\n")
    import hashlib
    h = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
    json.dump({"source_sha256": h(unsplit),
               "parts": {"KY": {"path": "data/sealed/ScreenGeneEffect.KY.csv", "sha256": h(ky)},
                         "CD": {"path": "data/other/ScreenGeneEffect.CD.csv", "sha256": h(cd)}}},
              open(tmp_path / "data/split.receipt.json", "w"))
    # the joint-fit matrix and the unsplit matrix are downloaded release files, so
    # they are pinned against the release receipt rather than the split
    json.dump({"files": {"CRISPRGeneEffect.csv": {"sha256": h(joint)},
                         "ScreenGeneEffect.csv": {"sha256": h(unsplit)}}},
              open(tmp_path / "data/depmap24q4.receipt.json", "w"))
    return tmp_path


def run_freeze(tree):
    return subprocess.run([sys.executable, str(tree / "code/freeze.py")],
                          capture_output=True, text=True)


def test_a_clean_tree_freezes_and_records_a_digest_over_every_bound_file(tmp_path):
    tree = build_tree(tmp_path)
    r = run_freeze(tree)
    assert r.returncode == 0, r.stderr
    fz = json.load(open(tree / "registration/freeze.json"))
    assert fz["file_count"] == len(fz["sha256"]) >= 20
    assert len(fz["top_digest"]) == 64
    assert "registration/protocol.json" in fz["sha256"]
    assert "code/stats.py" in fz["sha256"] and "code/screen.py" in fz["sha256"]
    assert "results/selection.real.csv" in fz["sha256"]
    assert "tests/test_x.py" in fz["sha256"]
    # the sealed matrix is hashed but is not part of the frozen-code set
    assert "data/sealed/ScreenGeneEffect.KY.csv" in fz["sealed_unopened"]["sha256"]
    assert "data/sealed/ScreenGeneEffect.KY.csv" not in fz["sha256"]


def test_the_freeze_is_write_once(tmp_path):
    tree = build_tree(tmp_path)
    assert run_freeze(tree).returncode == 0
    second = run_freeze(tree)
    assert second.returncode != 0
    assert "write-once" in second.stderr


def test_freezing_is_refused_once_confirmation_output_exists(tmp_path):
    tree = build_tree(tmp_path)
    (tree / "results/confirmation.csv").write_text("x\n")
    r = run_freeze(tree)
    assert r.returncode != 0 and "already been opened" in r.stderr


def test_freezing_is_refused_if_the_sealed_matrix_no_longer_matches(tmp_path):
    tree = build_tree(tmp_path)
    (tree / "data/sealed/ScreenGeneEffect.KY.csv").write_text("tampered\n")
    r = run_freeze(tree)
    assert r.returncode != 0 and "does not match the split receipt" in r.stderr


def test_freezing_is_refused_when_a_required_file_is_missing(tmp_path):
    tree = build_tree(tmp_path)
    os.remove(tree / "results/selection.real.csv")
    r = run_freeze(tree)
    assert r.returncode != 0 and "missing required files" in r.stderr


def test_the_top_digest_changes_if_any_bound_byte_changes(tmp_path):
    tree = build_tree(tmp_path)
    run_freeze(tree)
    first = json.load(open(tree / "registration/freeze.json"))["top_digest"]
    os.remove(tree / "registration/freeze.json")
    (tree / "results/selection.real.csv").write_text("context,dep_gene,beta\nA,B,1\n")
    run_freeze(tree)
    assert json.load(open(tree / "registration/freeze.json"))["top_digest"] != first


def test_confirmation_refuses_without_a_freeze(tmp_path, monkeypatch):
    monkeypatch.setattr(CF, "ROOT", str(tmp_path))
    (tmp_path / "registration").mkdir()
    with pytest.raises(SystemExit) as e:
        CF.check_freeze()
    assert "does not exist" in str(e.value)


def frozen_tree(tmp_path):
    """A minimal tree that CF.check_freeze() accepts, plus its manifest."""
    import hashlib
    h = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
    (tmp_path / "registration").mkdir()
    (tmp_path / "data/sealed").mkdir(parents=True)
    (tmp_path / "data/depmap24q4").mkdir(parents=True)
    target = tmp_path / "registration/protocol.json"
    target.write_text('{"P1": "at least 0.40"}')
    ky = tmp_path / "data/sealed/ScreenGeneEffect.KY.csv"
    ky.write_text("sealed KY\n")
    omic = tmp_path / "data/depmap24q4/Model.csv"
    omic.write_text("ModelID\nACH-1\n")
    receipt = tmp_path / "data/depmap24q4.receipt.json"
    json.dump({"files": {"Model.csv": {"sha256": h(omic)}}}, open(receipt, "w"))
    json.dump({"parts": {"KY": {"path": "data/sealed/ScreenGeneEffect.KY.csv",
                                "sha256": h(ky)}}},
              open(tmp_path / "data/split.receipt.json", "w"))
    shas = {"registration/protocol.json": h(target),
            "data/depmap24q4.receipt.json": h(receipt)}
    manifest = {"frozen_utc": "now", "sha256": shas,
                "top_digest": CF.top_digest(shas),
                "sealed_unopened": {"sha256": {"data/sealed/ScreenGeneEffect.KY.csv": h(ky)}}}
    json.dump(manifest, open(tmp_path / "registration/freeze.json", "w"))
    return target, ky, omic


def test_confirmation_refuses_when_a_frozen_file_was_edited(tmp_path, monkeypatch):
    monkeypatch.setattr(CF, "ROOT", str(tmp_path))
    target, _, _ = frozen_tree(tmp_path)
    assert CF.check_freeze()["sha256"]["registration/protocol.json"]

    target.write_text('{"P1": "at least 0.10"}')     # move the goalposts
    with pytest.raises(SystemExit) as e:
        CF.check_freeze()
    assert "changed since the freeze" in str(e.value)


def test_confirmation_refuses_when_the_manifest_itself_was_edited(tmp_path, monkeypatch):
    """Rewriting one hash to match an edited file must not go unnoticed: the
    manifest attests to itself through the top digest."""
    monkeypatch.setattr(CF, "ROOT", str(tmp_path))
    target, _, _ = frozen_tree(tmp_path)
    import hashlib
    target.write_text('{"P1": "at least 0.10"}')
    fz = tmp_path / "registration/freeze.json"
    m = json.load(open(fz))
    m["sha256"]["registration/protocol.json"] = hashlib.sha256(target.read_bytes()).hexdigest()
    json.dump(m, open(fz, "w"))
    with pytest.raises(SystemExit) as e:
        CF.check_freeze()
    assert "top_digest" in str(e.value)


def test_confirmation_refuses_when_a_sealed_resource_changed(tmp_path, monkeypatch):
    monkeypatch.setattr(CF, "ROOT", str(tmp_path))
    _, ky, _ = frozen_tree(tmp_path)
    ky.write_text("a different holdout\n")
    with pytest.raises(SystemExit) as e:
        CF.check_freeze()
    assert "sealed resource" in str(e.value)


def test_confirmation_refuses_when_a_receipted_input_changed(tmp_path, monkeypatch):
    """The omics files are not in the manifest one by one; they are bound through
    their receipt. Swapping one underneath a frozen receipt must still refuse."""
    monkeypatch.setattr(CF, "ROOT", str(tmp_path))
    _, _, omic = frozen_tree(tmp_path)
    omic.write_text("ModelID\nACH-2\n")
    with pytest.raises(SystemExit) as e:
        CF.check_freeze()
    assert "Model.csv changed since the freeze" in str(e.value)
