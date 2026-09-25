"""The statistic must be the thing the protocol says it is.

Every test here is deterministic, needs no network and needs no DepMap data.
"""
import numpy as np
import pytest
import statsmodels.api as sm

import stats as ST


def rng():
    return np.random.default_rng(11)


def synthetic(n=200, planted=0.0):
    g = rng()
    lineage = g.choice(["lung", "colon", "skin", "blood"], size=n)
    tmb = g.poisson(80, size=n).astype(float)
    aneu = g.normal(size=n)
    wgd = g.integers(0, 2, size=n).astype(float)
    sex = g.choice(["Male", "Female"], size=n)
    Z = ST.design(lineage, tmb, aneu, wgd, sex=sex)
    x = (g.random(n) < 0.3).astype(float)
    y = planted * x + 0.4 * aneu + g.normal(scale=0.5, size=n)
    return Z, x, y, lineage


def test_beta_se_and_p_match_ols_exactly():
    """associate() must equal ordinary least squares on [context | covariates]."""
    Z, x, y, _ = synthetic(planted=-0.8)
    b, r, p, se, df = ST.associate(y[:, None], x[:, None], Z)
    fit = sm.OLS(y, np.column_stack([x, Z])).fit()
    assert df == int(fit.df_resid)
    assert b[0, 0] == pytest.approx(fit.params[0], rel=1e-5)
    assert se[0, 0] == pytest.approx(fit.bse[0], rel=1e-4)
    assert p[0, 0] == pytest.approx(fit.pvalues[0], rel=1e-5, abs=1e-12)


def test_recovers_a_planted_effect_and_finds_none_when_there_is_none():
    Z, x, y, _ = synthetic(planted=-0.8)
    b, _, p, _, _ = ST.associate(y[:, None], x[:, None], Z)
    assert b[0, 0] == pytest.approx(-0.8, abs=0.2)
    assert p[0, 0] < 1e-6

    Z, x, y, _ = synthetic(planted=0.0)
    b, _, p, _, _ = ST.associate(y[:, None], x[:, None], Z)
    assert abs(b[0, 0]) < 0.3
    assert p[0, 0] > 0.01


def test_many_columns_give_the_same_answer_as_one_at_a_time():
    """The vectorised path is what the screen runs; it must not drift."""
    Z, x, y, _ = synthetic(planted=0.5)
    g = rng()
    Y = np.column_stack([y] + [g.normal(size=y.size) for _ in range(4)])
    X = np.column_stack([x] + [(g.random(y.size) < 0.25).astype(float) for _ in range(3)])
    B, _, P, SE, _ = ST.associate(Y, X, Z)
    for i in range(X.shape[1]):
        for j in range(Y.shape[1]):
            b1, _, p1, se1, _ = ST.associate(Y[:, [j]], X[:, [i]], Z)
            assert B[i, j] == pytest.approx(b1[0, 0], rel=1e-4, abs=1e-6)
            assert SE[i, j] == pytest.approx(se1[0, 0], rel=1e-4, abs=1e-6)
            assert P[i, j] == pytest.approx(p1[0, 0], rel=1e-4, abs=1e-12)


def test_refuses_when_degrees_of_freedom_are_too_small():
    Z, x, y, _ = synthetic(n=25)
    assert y.size - np.linalg.matrix_rank(Z) - 1 < 20
    with pytest.raises(ValueError):
        ST.associate(y[:, None], x[:, None], Z, min_df=20)


def test_accepts_the_same_data_when_the_floor_is_lowered():
    Z, x, y, _ = synthetic(n=25)
    b, _, _, _, df = ST.associate(y[:, None], x[:, None], Z, min_df=10)
    assert np.isfinite(b[0, 0]) and df >= 10


def test_covariate_adjustment_actually_removes_a_lineage_confound():
    """A context that only tracks lineage must not produce an effect."""
    g = rng()
    n = 400
    lineage = g.choice(["lung", "colon", "skin", "blood"], size=n)
    x = (lineage == "colon").astype(float)
    y = 1.5 * (lineage == "colon") + g.normal(scale=0.3, size=n)
    Z = ST.design(lineage, np.zeros(n), g.normal(size=n), np.zeros(n))
    b, _, p, se, _ = ST.associate(y[:, None], x[:, None], Z)
    assert abs(b[0, 0]) < 1e-6          # perfectly collinear with a covariate
    unadjusted = np.corrcoef(x, y)[0, 1]
    assert unadjusted > 0.8             # and it would have looked huge unadjusted


def test_zero_variance_context_does_not_produce_a_finite_effect():
    Z, x, y, _ = synthetic()
    b, r, p, se, _ = ST.associate(y[:, None], np.zeros_like(x)[:, None], Z)
    assert r[0, 0] == 0.0
    assert p[0, 0] == pytest.approx(1.0)
    assert not np.isfinite(se[0, 0])


def test_residualiser_is_a_projection_and_reports_the_right_rank():
    Z, _, _, _ = synthetic()
    R, rank = ST.residualiser(Z)
    assert rank == np.linalg.matrix_rank(Z)
    assert np.allclose(R @ R, R, atol=1e-8)
    assert np.allclose(R @ Z, 0.0, atol=1e-8)


def test_design_drops_one_level_per_categorical_block():
    n = 12
    lineage = np.array(["a", "b", "c"] * 4)                  # 4 models each
    sex = np.array(["Male", "Female"] * 6)                   # 6 models each
    Z = ST.design(lineage, np.arange(float(n)), np.arange(float(n)), np.zeros(n), sex=sex)
    # intercept + 2 of 3 lineages + 1 of 2 sexes + tmb + aneuploidy;
    # wgd is constant and is dropped
    assert Z.shape == (n, 6)
    assert np.linalg.matrix_rank(Z) == 6


def test_design_treats_a_missing_sex_value_as_its_own_level():
    n = 12
    lineage = np.array(["a"] * n)
    sex = np.array(["Male", "Female", None] * 4, dtype=object)
    Z = ST.design(lineage, np.arange(float(n)), np.arange(float(n)), np.zeros(n), sex=sex)
    # intercept + 2 of 3 sex levels (UNKNOWN is a level) + tmb + aneuploidy
    assert Z.shape[1] == 1 + 2 + 2


def test_a_categorical_level_below_the_floor_is_carried_by_the_intercept():
    """A 96-level disease one-hot would otherwise consume most of the residual
    degrees of freedom in a 119-model tier. Levels with fewer than MIN_LEVEL_N
    models get no indicator; those models are described by the intercept."""
    n = 20
    lineage = np.array(["big"] * 16 + ["rare"] * 2 + ["alsorare"] * 2)
    Z = ST.design(lineage, np.arange(float(n)), np.zeros(n), np.zeros(n))
    assert ST.MIN_LEVEL_N == 3
    assert Z.shape[1] == 1 + 1          # intercept + tmb; no lineage level qualifies twice
    lineage2 = np.array(["big"] * 14 + ["small"] * 3 + ["rare"] * 3)
    Z2 = ST.design(lineage2, np.arange(float(n)), np.zeros(n), np.zeros(n))
    assert Z2.shape[1] == 1 + 2 + 1     # intercept + 2 of 3 qualifying levels + tmb


def test_an_imputed_covariate_is_flagged_rather_than_described_as_typical():
    n = 30
    aneu = np.concatenate([np.arange(24.0), np.full(6, np.nan)])
    Z = ST.design(np.array(["a"] * n), np.arange(float(n)), aneu, np.zeros(n))
    # intercept + tmb + aneuploidy + the "this value was imputed" indicator
    assert Z.shape[1] == 4
    assert set(np.unique(Z[:, -1])) == {0.0, 1.0}
    assert Z[:, -1].sum() == 6


def test_bh_qvalues_match_a_direct_reference_implementation():
    g = rng()
    p = np.concatenate([g.random(500) * 1e-4, g.random(4500)])
    q = ST.bh_qvalues(p)
    n = p.size
    order = np.argsort(p)
    ref = np.empty(n)
    running = 1.0
    for k in range(n - 1, -1, -1):
        running = min(running, p[order[k]] * n / (k + 1))
        ref[order[k]] = running
    assert np.allclose(q, np.clip(ref, 0, 1))


def test_bh_qvalues_are_monotone_in_p_and_bounded():
    g = rng()
    p = g.random(2000)
    q = ST.bh_qvalues(p)
    o = np.argsort(p)
    assert np.all(np.diff(q[o]) >= -1e-12)
    assert q.min() >= 0.0 and q.max() <= 1.0
    assert np.all(q >= p - 1e-12)


def test_bh_on_pure_noise_yields_almost_no_discoveries():
    """The FDR ceiling in the protocol has to mean something."""
    g = np.random.default_rng(3)
    p = g.random(200000)
    assert (ST.bh_qvalues(p) <= 0.01).sum() == 0


def test_permute_within_stays_inside_each_group_and_is_a_permutation():
    g = np.random.default_rng(7)
    labels = np.array(["x"] * 50 + ["y"] * 30 + ["z"] * 20)
    perm = ST.permute_within(labels, g)
    assert sorted(perm.tolist()) == list(range(labels.size))
    assert np.array_equal(labels[perm], labels)


def test_permute_within_is_seed_deterministic_and_seed_sensitive():
    labels = np.array(["x"] * 40 + ["y"] * 40)
    a = ST.permute_within(labels, np.random.default_rng(20260925))
    b = ST.permute_within(labels, np.random.default_rng(20260925))
    c = ST.permute_within(labels, np.random.default_rng(20260926))
    assert np.array_equal(a, b)
    assert not np.array_equal(a, c)


def test_permute_within_destroys_a_real_association_but_keeps_the_lineage_effect():
    g = np.random.default_rng(5)
    n = 600
    lineage = g.choice(["lung", "colon"], size=n)
    x = (g.random(n) < 0.4).astype(float)
    y = -1.0 * x + 0.8 * (lineage == "colon") + g.normal(scale=0.3, size=n)
    Z = ST.design(lineage, np.zeros(n), g.normal(size=n), np.zeros(n))
    b0, _, p0, _, _ = ST.associate(y[:, None], x[:, None], Z)
    assert p0[0, 0] < 1e-20
    perm = ST.permute_within(lineage, np.random.default_rng(1))
    b1, _, p1, _, _ = ST.associate(y[:, None], x[perm][:, None], Z)
    assert p1[0, 0] > 0.01
    assert abs(b1[0, 0]) < abs(b0[0, 0]) / 3


def test_a_nearly_collinear_context_is_dropped_rather_than_amplified():
    """The failure mode this guards: a rare context confined to one lineage."""
    g = np.random.default_rng(13)
    n = 120
    lineage = np.array(["rare"] * 4 + ["common"] * (n - 4))
    x = (lineage == "rare").astype(float)
    y = g.normal(size=n)
    Z = ST.design(lineage, np.zeros(n), g.normal(size=n), np.zeros(n))
    b, r, p, se, _ = ST.associate(y[:, None], x[:, None], Z, min_df=10)
    assert b[0, 0] == 0.0 and r[0, 0] == 0.0
    assert p[0, 0] == pytest.approx(1.0)
    assert not np.isfinite(se[0, 0])


def test_a_context_only_partly_explained_by_lineage_survives():
    """The guard must not throw away ordinary, partly confounded contexts."""
    g = np.random.default_rng(17)
    n = 400
    lineage = g.choice(["lung", "colon", "skin"], size=n)
    x = np.where(lineage == "colon", (g.random(n) < 0.7), (g.random(n) < 0.2)).astype(float)
    y = -0.9 * x + 0.5 * (lineage == "colon") + g.normal(scale=0.4, size=n)
    Z = ST.design(lineage, np.zeros(n), g.normal(size=n), np.zeros(n))
    b, _, p, se, _ = ST.associate(y[:, None], x[:, None], Z)
    assert b[0, 0] == pytest.approx(-0.9, abs=0.15)
    assert np.isfinite(se[0, 0]) and p[0, 0] < 1e-10


def test_the_identifiability_guard_leaves_ordinary_columns_bit_identical():
    """Adding the guard must not silently change any real result."""
    Z, x, y, _ = synthetic(planted=-0.6)
    g = np.random.default_rng(23)
    X = np.column_stack([x] + [(g.random(y.size) < 0.3).astype(float) for _ in range(3)])
    B, _, P, SE, _ = ST.associate(y[:, None], X, Z)
    # recompute the textbook way, column by column, with no guard at all
    R, rank = ST.residualiser(Z)
    yc = R @ y
    for i in range(X.shape[1]):
        xc = R @ X[:, i]
        beta = float(xc @ yc / (xc @ xc))
        assert B[i, 0] == pytest.approx(beta, rel=1e-5)
        assert np.isfinite(SE[i, 0])
