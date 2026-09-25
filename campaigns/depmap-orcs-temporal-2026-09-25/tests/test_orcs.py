"""Campaign D tests: freeze guards, BH, direction parsing, screen-file
parsing on the real ORCS schema, and an end-to-end run on a synthetic
tarball. No sealed data, no network."""
import io, json, os, sys, tarfile
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
import confirm as CF                       # noqa: E402
import campaign as C                       # noqa: E402


def test_bh():
    q = CF._bh(np.array([0.001, 0.5, 0.01, 0.9]))
    assert q[0] <= 0.01 and q[2] <= 0.02 and q[3] >= 0.9


def test_direction_from_criteria():
    assert CF.screen_direction("Score.1 (Z-score) < -2.17") == -1
    assert CF.screen_direction("Score.1 (Bayes Factor) > 15.47") == +1
    assert CF.screen_direction(
        "Score.1 > 2.17 OR Score.1 < -2.17") is None      # two-tailed
    assert CF.screen_direction("Score Significance") is None


def test_direction_from_score_type_fallback():
    assert CF.score_type_direction(["BAGEL BF"]) == 1
    assert CF.score_type_direction(["Log2 fold change"]) == -1
    assert CF.score_type_direction(["unknown metric"]) is None


def test_freeze_refusal(tmp_path, monkeypatch):
    monkeypatch.setattr(CF, "ROOT", str(tmp_path))
    (tmp_path / "registration").mkdir()
    with pytest.raises(SystemExit):
        CF.check_freeze()


def _screen_txt(sid, genes_scores):
    rows = "\n".join(f"{sid}\t100\tENTREZ_GENE\t{g}\t-\t9606\tHuman\t{v}\t"
                     f"-\t-\t-\t-\t-\tBioGRID ORCS"
                     for g, v in genes_scores)
    return ("#SCREEN_ID\tIDENTIFIER_ID\tIDENTIFIER_TYPE\tOFFICIAL_SYMBOL\t"
            "ALIASES\tORGANISM_ID\tORGANISM_OFFICIAL\tSCORE.1\tSCORE.2\t"
            "SCORE.3\tSCORE.4\tSCORE.5\tHIT\tSOURCE\n" + rows)


def test_screen_score_parse_real_schema():
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        body = _screen_txt(1614, [("TP53", -3.0), ("MDM2", -1.5),
                                  ("ALB", 0.1)])
        ti = tarfile.TarInfo("BIOGRID-ORCS-SCREEN_1614-2.0.18.screen.tab.txt")
        ti.size = len(body.encode())
        t.addfile(ti, io.BytesIO(body.encode()))
    buf.seek(0)
    with tarfile.open(fileobj=buf) as tf:
        s = CF.load_screen(tf, tf.getnames()[0], "SCORE.1")
    assert s is not None and s["TP53"] == -3.0 and len(s) == 3


def test_rerun_guard(tmp_path, monkeypatch):
    monkeypatch.setattr(CF, "ROOT", str(tmp_path))
    (tmp_path / "results").mkdir(parents=True)
    (tmp_path / "results" / "confirmation.summary.json").write_text("{}")
    with pytest.raises(SystemExit, match="already been opened"):
        CF.main()


def test_placebo_injection_refusal(tmp_path, monkeypatch):
    import hashlib
    monkeypatch.setattr(CF, "ROOT", str(tmp_path))
    (tmp_path / "registration").mkdir(parents=True)
    (tmp_path / "x.txt").write_text("x")
    fx = hashlib.sha256(b"x").hexdigest()
    fz = {"frozen_utc": "2999-01-01T00:00:00Z",
          "sha256": {"x.txt": fx}}
    h = hashlib.sha256()
    for f, v in sorted(fz["sha256"].items()):
        h.update(f"{f}\x00{v}\n".encode())
    fz["top_digest"] = h.hexdigest()
    (tmp_path / "registration" / "freeze.json").write_text(json.dumps(fz))
    (tmp_path / "registration" / "depmap_placebo_new.csv").write_text(
        "context,dep_gene\nE:G,G\n")
    with pytest.raises(SystemExit, match="post-freeze placebo"):
        CF.check_freeze()
