"""Campaign B tests: replication rule, orientation guard, freeze guards.
No sealed data, no network."""
import json, os, sys
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
import confirm as CF                       # noqa: E402


def res(beta=-0.3, p=0.01, sd=0.4):
    return {"beta": beta, "r": 0.1, "p_two": p, "se": 0.05, "df": 90,
            "n": 90, "n_pos": 10, "n_neg": 80, "dep_sd": sd,
            "n_broad_ids": 1}


def test_replicated_rule():
    r = CF.replicated(-0.8, 1.0, res(beta=-0.4, p=0.02, sd=0.5))
    # d_hold = 0.4/0.5 = 0.8 ; d_disc = 0.8/1.0 ; 0.8 >= 0.4 -> pass
    assert r["replicated"]


def test_wrong_sign_fails():
    r = CF.replicated(-0.8, 1.0, res(beta=+0.5, p=0.001))
    assert not r["replicated"] and not r["same_sign"]


def test_missing_sd_fails_closed():
    r = CF.replicated(-0.8, float("nan"), res())
    assert r is not None and not r["replicated"]


def test_untested_returns_none():
    assert CF.replicated(-0.5, 1.0, None) is None


def test_freeze_refusal(tmp_path, monkeypatch):
    monkeypatch.setattr(CF, "ROOT", str(tmp_path))
    (tmp_path / "registration").mkdir()
    with pytest.raises(SystemExit):
        CF.check_freeze()


def test_rerun_guard(tmp_path, monkeypatch):
    monkeypatch.setattr(CF, "ROOT", str(tmp_path))
    (tmp_path / "results").mkdir(parents=True)
    (tmp_path / "results" / "confirmation.summary.json").write_text("{}")
    with pytest.raises(SystemExit, match="already been opened"):
        CF.main()


def test_prism_orientation_rejects_unrecognised(tmp_path, monkeypatch):
    monkeypatch.setattr(CF, "ROOT", str(tmp_path))
    sealed = tmp_path / "data" / "sealed"
    sealed.mkdir(parents=True)
    # neither rows nor cols carry '::' -> must refuse, not guess
    (sealed / "secondary-screen-replicate-collapsed-logfold-change.csv"
     ).write_text("x,y\nA,1\n")
    with pytest.raises(SystemExit, match="orientation"):
        CF.load_prism()


def test_prism_collapse_by_broad_id(tmp_path, monkeypatch):
    """B2 regression: dose/screen columns must collapse to broad_id."""
    import confirm as CF
    p = tmp_path / "data" / "sealed"
    p.mkdir(parents=True)
    (p / "secondary-screen-replicate-collapsed-logfold-change.csv"
     ).write_text("id,BRD-A::2.5::P1,BRD-A::10::P1,BRD-B::2.5::P1\n"
                  "ACH-1,1.0,3.0,0.5\nACH-2,2.0,4.0,1.5\n")
    monkeypatch.setattr(CF, "ROOT", str(tmp_path))
    out = CF.load_prism()
    assert list(sorted(out.columns)) == ["BRD-A", "BRD-B"]
    assert out.loc["ACH-1", "BRD-A"] == 2.0


def test_freeze_required_covers_confirm_inputs():
    """Every registration/prep artifact confirm.py opens must be frozen."""
    import freeze as FZ
    required = set(FZ.REQUIRED)
    assert "data/prep/gdsc2.npz" in required
    assert "data/prep/drug_crosswalk.json" in required
    assert "registration/selection.csv" in required
    assert "registration/gold_controls.json" in required


def test_gold_rows_use_discovery_beta():
    """B3 regression: eval path must not crash on gold rows lacking beta."""
    import confirm as CF
    res = {"beta": -1.0, "p_two": 0.01, "dep_sd": 2.0}
    rep = CF.replicated(-1.0, 2.0, res)
    assert rep["replicated"] is True
    rep2 = CF.replicated(float("nan"), 0.5, res)
    assert rep2["replicated"] is False


def test_placebo_glob_matches_files(tmp_path):
    """B1 regression: placebo files are selection.placebo*.csv."""
    reg = tmp_path / "registration"
    reg.mkdir()
    (reg / "selection.placebo20990101.csv").write_text(
        "context,drug,beta,r,se,beta_lb,p,n_models,df,q\n"
        "MUT_HOT:X,D, -1, -0.1, 0.1, 0.5, 0.001, 100, 90, 0.01\n")
    hits = [f for f in sorted(__import__('os').listdir(reg))
            if f.startswith("selection.placebo") and f.endswith(".csv")]
    assert hits == ["selection.placebo20990101.csv"]
