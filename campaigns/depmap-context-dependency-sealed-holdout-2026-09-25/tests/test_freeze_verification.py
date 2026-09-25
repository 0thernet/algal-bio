"""confirm.check_freeze is the gate between the registration and the holdout.

Every one of these was a real gap: the manifest was trusted verbatim so editing
one hash defeated the seal; the sealed matrices were never hashed at all, so
the abort rule in the protocol had no implementation; and the omics files that
define every context vector and the whole covariate design were unbound, so
editing one after the freeze changed every number undetected.
"""
import hashlib, json, os
import pytest

import confirm as CF


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


@pytest.fixture
def frozen_tree(tmp_path, monkeypatch):
    """A minimal tree that check_freeze should accept."""
    (tmp_path / "registration").mkdir()
    (tmp_path / "data" / "sealed").mkdir(parents=True)
    (tmp_path / "data" / "depmap24q4").mkdir(parents=True)
    (tmp_path / "code").mkdir()

    (tmp_path / "code" / "stats.py").write_text("# analysis code\n")
    (tmp_path / "data" / "sealed" / "ScreenGeneEffect.KY.csv").write_text("sealed,rows\n")
    (tmp_path / "data" / "depmap24q4" / "Model.csv").write_text("ModelID,OncotreeLineage\n")

    def sha(rel):
        return sha_bytes((tmp_path / rel).read_bytes())

    json.dump({"parts": {"KY": {"path": "data/sealed/ScreenGeneEffect.KY.csv",
                                "sha256": sha("data/sealed/ScreenGeneEffect.KY.csv")}}},
              open(tmp_path / "data" / "split.receipt.json", "w"))
    json.dump({"files": {"Model.csv": {"sha256": sha("data/depmap24q4/Model.csv")}}},
              open(tmp_path / "data" / "depmap24q4.receipt.json", "w"))

    manifest = {rel: sha(rel) for rel in ["code/stats.py", "data/split.receipt.json",
                                          "data/depmap24q4.receipt.json"]}
    json.dump({"frozen_utc": "2026-09-25T00:00:00Z",
               "top_digest": CF.top_digest(manifest),
               "sha256": manifest,
               "sealed_unopened": {"sha256": {
                   "data/sealed/ScreenGeneEffect.KY.csv":
                       sha("data/sealed/ScreenGeneEffect.KY.csv")}}},
              open(tmp_path / "registration" / "freeze.json", "w"))
    monkeypatch.setattr(CF, "ROOT", str(tmp_path))
    return tmp_path


def edit(path, text):
    path.write_text(text)


def test_a_clean_tree_passes(frozen_tree, capsys):
    frozen = CF.check_freeze()
    assert frozen["top_digest"]
    assert "freeze verified" in capsys.readouterr().out


def test_a_missing_freeze_refuses(frozen_tree):
    os.remove(frozen_tree / "registration" / "freeze.json")
    with pytest.raises(SystemExit, match="does not exist"):
        CF.check_freeze()


def test_editing_one_hash_in_the_manifest_is_detected(frozen_tree):
    """Without the top digest the manifest is self-attesting: change the hash
    to match the edited file and nothing notices."""
    fz = json.load(open(frozen_tree / "registration" / "freeze.json"))
    edit(frozen_tree / "code" / "stats.py", "# tampered\n")
    fz["sha256"]["code/stats.py"] = sha_bytes(b"# tampered\n")
    json.dump(fz, open(frozen_tree / "registration" / "freeze.json", "w"))
    with pytest.raises(SystemExit, match="top_digest"):
        CF.check_freeze()


def test_editing_a_frozen_file_is_detected(frozen_tree):
    edit(frozen_tree / "code" / "stats.py", "# changed after the freeze\n")
    with pytest.raises(SystemExit, match="frozen files changed"):
        CF.check_freeze()


def test_a_changed_sealed_matrix_is_detected(frozen_tree):
    """The sealed files are deliberately not in the checked manifest, so before
    this check nothing hashed them at confirmation time at all."""
    edit(frozen_tree / "data" / "sealed" / "ScreenGeneEffect.KY.csv", "different,rows\n")
    with pytest.raises(SystemExit, match="does not match the freeze"):
        CF.check_freeze()


def test_a_sealed_matrix_that_disagrees_with_the_split_receipt_is_detected(frozen_tree):
    body = "swapped,rows\n"
    edit(frozen_tree / "data" / "sealed" / "ScreenGeneEffect.KY.csv", body)
    fz = json.load(open(frozen_tree / "registration" / "freeze.json"))
    fz["sealed_unopened"]["sha256"]["data/sealed/ScreenGeneEffect.KY.csv"] = sha_bytes(body.encode())
    json.dump(fz, open(frozen_tree / "registration" / "freeze.json", "w"))
    with pytest.raises(SystemExit, match="split.receipt.json"):
        CF.check_freeze()


def test_editing_an_omics_file_named_only_in_a_receipt_is_detected(frozen_tree):
    """Model.csv is in no manifest. It supplies lineage, disease and sex for
    every covariate design in both arms. Editing it changes every number."""
    edit(frozen_tree / "data" / "depmap24q4" / "Model.csv", "ModelID,OncotreeLineage\nX,Lung\n")
    with pytest.raises(SystemExit, match="changed since the freeze"):
        CF.check_freeze()


def test_a_receipted_input_that_went_missing_is_refused_not_skipped(frozen_tree):
    """Skipping it would let the run fall back to whatever pandas does with a
    missing file; the gate has to fail closed."""
    (frozen_tree / "data" / "depmap24q4" / "Model.csv").unlink()
    with pytest.raises(SystemExit, match="is missing"):
        CF.check_freeze()


def test_the_top_digest_is_order_independent_and_collision_resistant():
    a = {"x": "1", "y": "2"}
    b = {"y": "2", "x": "1"}
    assert CF.top_digest(a) == CF.top_digest(b)
    assert CF.top_digest({"xy": "12"}) != CF.top_digest({"x": "y12"})
