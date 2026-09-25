"""Campaign C pure-function tests: the replication rule, label precedence,
and freeze guards. No sealed data, no network."""
import json, os, sys
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
import confirm as CF                       # noqa: E402


def res(beta=-0.5, p=0.01, sd=0.2, n=100):
    return {"beta": beta, "r": beta / 2, "p_two_sided": p, "se": 0.05,
            "df": n - 2, "n": n, "n_pos": 10, "n_neg": n - 10,
            "dep_sd": sd}


def test_replicated_rule():
    # same sign, p<0.05 one-sided, magnitude >= 0.5x shrunken discovery
    r = CF.replicated(-0.8, 0.5, 1.0, res(beta=-0.5, p=0.02, sd=0.5))
    # d_hold = 0.5/0.5 = 1.0 ; d_disc = 0.5/1.0 = 0.5 ; 1.0 >= 0.25 -> pass
    assert r["replicated"] and r["same_sign"] and r["magnitude_ok"]


def test_replicated_wrong_sign_fails():
    r = CF.replicated(-0.8, 0.5, 1.0, res(beta=+0.9, p=0.001))
    assert not r["replicated"] and not r["same_sign"]
    assert r["p_one_sided"] > 0.9  # one-sided p in the observed direction


def test_replicated_weak_magnitude_fails():
    r = CF.replicated(-0.8, 0.9, 1.0, res(beta=-0.10, p=0.001, sd=1.0))
    # d_hold = 0.1 < 0.5 * 0.9 = 0.45
    assert not r["replicated"] and not r["magnitude_ok"]


def test_replicated_untested_pair():
    assert CF.replicated(-0.5, 0.4, 1.0, None) is None


def test_freeze_refusal_without_freeze(tmp_path, monkeypatch):
    monkeypatch.setattr(CF, "ROOT", str(tmp_path))
    (tmp_path / "registration").mkdir()
    with pytest.raises(SystemExit):
        CF.check_freeze()


def test_freeze_refusal_on_changed_file(tmp_path, monkeypatch):
    monkeypatch.setattr(CF, "ROOT", str(tmp_path))
    (tmp_path / "registration").mkdir()
    (tmp_path / "a.txt").write_text("x")
    (tmp_path / "registration" / "freeze.json").write_text(json.dumps(
        {"frozen_utc": "2026-09-25T00:00:00Z",
         "sha256": {"a.txt": "wronghash"}}))
    with pytest.raises(SystemExit, match="changed"):
        CF.check_freeze()


def test_confirm_rerun_guard(tmp_path, monkeypatch):
    monkeypatch.setattr(CF, "ROOT", str(tmp_path))
    (tmp_path / "results").mkdir(parents=True)
    (tmp_path / "results" / "confirmation.summary.json").write_text("{}")
    with pytest.raises(SystemExit, match="already been opened"):
        CF.main()


def test_label_precedence_low_gold_is_underpowered():
    # exercises the real verdict() the run uses, not a reimplementation
    pr = {"tested": 70, "rate": 0.6, "replicated": 42}
    pl = {"tested": 10, "rate": 0.0, "replicated": 0}
    go = {"tested": 15, "rate": 0.2, "replicated": 3}
    nov = {"tested": 20, "rate": 0.5, "replicated": 10}
    label, flags = CF.verdict(pr, pl, go, nov)
    assert label == "UNDERPOWERED" and not flags["P5"]


def test_verdict_all_labels():
    nov = {"tested": 20, "rate": 0.5, "replicated": 10}
    go = {"tested": 15, "rate": 0.9, "replicated": 14}
    pl_ok = {"tested": 10, "rate": 0.0, "replicated": 0}
    pl_bad = {"tested": 10, "rate": 0.4, "replicated": 4}
    pr_hi = {"tested": 60, "rate": 0.5, "replicated": 30}
    pr_lo = {"tested": 60, "rate": 0.1, "replicated": 6}
    nov_lo = {"tested": 20, "rate": 0.1, "replicated": 1}
    assert CF.verdict(pr_hi, pl_ok, go, nov)[0] == "RNAI_REPLICATED"
    assert CF.verdict(pr_hi, pl_ok, go, nov_lo)[0] == "PARTIAL_REPLICATION"
    assert CF.verdict(pr_hi, pl_bad, go, nov)[0] == "PLACEBO_BREACH"
    assert CF.verdict(pr_lo, pl_ok, go, nov)[0] == "NO_TRANSFER"
    assert CF.verdict({"tested": 0, "rate": None, "replicated": 0},
                      pl_ok, go, nov)[0] == "NOT_EVALUABLE"


def test_replicated_fails_closed_on_missing_sd():
    r = CF.replicated(-0.8, 0.5, float("nan"), res(beta=-0.5, p=0.001))
    assert r is not None and not r["replicated"]
