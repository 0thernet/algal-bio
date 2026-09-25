"""The replication rule is the whole outcome, so it gets a truth table.

Rule, from registration/protocol.json: same sign as discovery, one-sided p
below 0.05, and a STANDARDISED effect at least half the standardised shrunken
discovery effect. Standardised, because ScreenGeneEffect is scaled per library
run, so a raw Chronos difference is not transferable from Avana to KY.
Shrunken, because discovery effects are selected on their magnitude.
""" 
import numpy as np
import pytest

import confirm as CF


def res(beta, p_two, dep_sd=1.0):
    return {"beta": beta, "p_two_sided": p_two, "se": 0.1, "df": 100,
            "n": 150, "n_pos": 20, "n_neg": 130, "r": 0.2, "dep_sd": dep_sd}


def rep(disc_beta, r, disc_lb=None, disc_sd=1.0):
    """The rule with the discovery side supplied. By default the shrunken
    discovery effect equals |beta|, which makes the truth table read the same
    way it did when the rule compared raw betas."""
    return CF.replicated(disc_beta, abs(disc_beta) if disc_lb is None else disc_lb,
                         disc_sd, r)


def test_the_constants_are_the_registered_ones():
    assert (CF.REP_P, CF.REP_FRAC, CF.MIN_TIER_POS, CF.MIN_TIER_N) == (0.05, 0.5, 3, 30)


def test_a_clean_replication_passes():
    r = rep(-0.8, res(-0.7, 0.001))
    assert r["replicated"] and r["same_sign"] and r["magnitude_ok"]
    assert r["p_one_sided"] == pytest.approx(0.0005)


def test_the_opposite_sign_never_replicates_however_small_the_p_value():
    r = rep(-0.8, res(+0.9, 1e-12))
    assert not r["replicated"] and not r["same_sign"]
    assert r["p_one_sided"] > 0.99      # a strong effect the wrong way


def test_a_weak_p_value_fails_even_with_the_right_sign_and_size():
    r = rep(-0.8, res(-0.8, 0.2))
    assert r["same_sign"] and r["magnitude_ok"] and not r["replicated"]
    assert r["p_one_sided"] == pytest.approx(0.1)


def test_a_shrunken_effect_fails_even_when_highly_significant():
    """Sign and significance alone would let a tenth-sized effect count."""
    r = rep(-0.8, res(-0.08, 1e-9))
    assert r["same_sign"] and not r["magnitude_ok"] and not r["replicated"]


@pytest.mark.parametrize("disc,rep_beta,p,expect", [
    (-0.8, -0.40, 0.04, True),    # exactly half the discovery effect
    (-0.8, -0.39, 0.04, False),   # just under half
    (-0.8, -0.70, 0.10, True),    # two-sided 0.10 is one-sided 0.05... not below
    (+0.5, +0.60, 0.02, True),
    (+0.5, -0.60, 0.02, False),
])
def test_boundaries(disc, rep_beta, p, expect):
    got = globals()["rep"](disc, res(rep_beta, p))["replicated"]
    if (disc, rep_beta, p) == (-0.8, -0.70, 0.10):
        assert got is False       # p_one_sided == 0.05 is not < 0.05
    else:
        assert got is expect


def test_an_untested_pair_returns_nothing_rather_than_a_verdict():
    assert rep(-0.8, None) is None


def test_the_magnitude_test_is_scale_free_across_libraries():
    """The holdout library's gene effects can be on a different scale. The same
    biological effect, expressed in a matrix whose spread is half as wide, must
    still count; a raw comparison would fail it."""
    shrunk = rep(-0.8, res(-0.30, 0.001, dep_sd=0.5))      # d = 0.60 against d_disc 0.80
    assert shrunk["replicated"], "a scaled-down library was scored as a non-replication"
    raw_equivalent = rep(-0.8, res(-0.30, 0.001, dep_sd=1.0))
    assert not raw_equivalent["magnitude_ok"]


def test_the_discovery_side_is_shrunken_not_the_selected_estimate():
    """Discovery betas are selected at |beta| >= 0.30 and ranked on their lower
    bound, so they are inflated. The rule compares against the lower bound."""
    on_point = rep(-1.0, res(-0.40, 0.001), disc_lb=1.0)
    on_bound = rep(-1.0, res(-0.40, 0.001), disc_lb=0.6)
    assert not on_point["magnitude_ok"] and on_bound["magnitude_ok"]
    assert on_bound["d_discovery_shrunken"] == pytest.approx(0.6)


def test_the_rule_is_applied_identically_to_placebos_and_controls():
    """One function, so a placebo cannot be judged on a softer rule."""
    import inspect
    src = inspect.getsource(CF.evaluate)
    assert src.count("replicated(") == 1
    assert "label" in inspect.signature(CF.evaluate).parameters


def test_a_tier_with_too_few_positives_is_not_tested():
    rngen = np.random.default_rng(0)
    y = rngen.normal(size=100)
    Z = np.column_stack([np.ones(100), rngen.normal(size=100)])
    x = np.zeros(100)
    x[:2] = 1.0                            # only two context-positive models
    assert CF.test_pair(y, x, Z) is None


def test_a_tier_with_too_few_models_is_not_tested():
    rngen = np.random.default_rng(0)
    y = rngen.normal(size=20)
    Z = np.column_stack([np.ones(20), rngen.normal(size=20)])
    x = (rngen.random(20) < 0.5).astype(float)
    assert CF.test_pair(y, x, Z) is None


def test_missing_values_are_dropped_pairwise_and_counted():
    rngen = np.random.default_rng(1)
    n = 200
    x = (rngen.random(n) < 0.3).astype(float)
    y = -1.0 * x + rngen.normal(scale=0.3, size=n)
    Z = np.column_stack([np.ones(n), rngen.normal(size=n)])
    y[:20] = np.nan
    x[20:30] = np.nan
    out = CF.test_pair(y, x, Z)
    assert out["n"] == n - 30
    assert out["n_pos"] + out["n_neg"] == out["n"]
    assert out["beta"] == pytest.approx(-1.0, abs=0.15)


def test_an_unidentified_context_is_not_tested_rather_than_failed():
    """A context perfectly explained by the covariates carries no independent
    information. Scoring it as tested-and-not-replicated would let the covariate
    design manufacture non-replications and push the rate down for a reason that
    has nothing to do with the holdout."""
    n = 120
    g = np.random.default_rng(3)
    grp = np.array([1.0] * 5 + [0.0] * (n - 5))
    Z = np.column_stack([np.ones(n), grp, g.normal(size=n)])
    x = grp.copy()
    y = g.normal(size=n)
    assert CF.test_pair(y, x, Z) is None
    assert rep(-0.8, None) is None


def test_a_placebo_screen_that_selected_nothing_does_not_crash_the_run(tmp_path):
    """One of the three placebo seeds selected no pairs; the file has no header."""
    import pandas as pd
    (tmp_path / "selection.placebo20260927.csv").write_text("\n")
    with pytest.raises(pd.errors.EmptyDataError):
        pd.read_csv(tmp_path / "selection.placebo20260927.csv")
    import inspect
    src = inspect.getsource(CF.main)
    assert "EmptyDataError" in src, "confirm.main would crash on an empty placebo selection"
    assert "selected_nothing" in src, "an empty placebo seed must still be reported"
