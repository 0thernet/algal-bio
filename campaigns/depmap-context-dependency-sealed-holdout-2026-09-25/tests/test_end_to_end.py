"""A whole screen on synthetic data with a known answer.

Twelve associations are planted among 400,000 tested pairs. The pipeline must
find the planted ones, must not fill its list with the rest, and must find
almost nothing once the contexts are permuted within lineage.
"""
import numpy as np
import pytest

import stats as ST
import screen as SC

N_MODELS = 500
N_DEP = 400
N_CTX = 1000
PLANTED = [(3, 10, -1.2), (17, 44, -0.9), (55, 8, +0.8), (120, 200, -1.1),
           (300, 5, -0.75), (410, 310, +0.95), (640, 77, -1.4), (700, 150, -0.85),
           (810, 260, +1.05), (900, 33, -1.25), (950, 390, -0.7), (999, 111, +0.9)]


def build(seed=42):
    g = np.random.default_rng(seed)
    lineage = g.choice(["lung", "colon", "skin", "blood", "breast"], size=N_MODELS)
    aneu = g.normal(size=N_MODELS)
    tmb = g.poisson(70, size=N_MODELS).astype(float)
    wgd = g.integers(0, 2, size=N_MODELS).astype(float)
    sex = g.choice(["Male", "Female"], size=N_MODELS)
    Z = ST.design(lineage, tmb, aneu, wgd, sex=sex)

    X = (g.random((N_MODELS, N_CTX)) < g.uniform(0.15, 0.40, size=N_CTX)).astype(float)
    lineage_effect = g.normal(scale=0.3, size=(5, N_DEP))
    li = np.searchsorted(np.array(["blood", "breast", "colon", "lung", "skin"]), lineage)
    Y = lineage_effect[li] + 0.2 * aneu[:, None] * g.normal(size=(1, N_DEP)) \
        + g.normal(scale=0.35, size=(N_MODELS, N_DEP))
    for ci, di, b in PLANTED:
        Y[:, di] += b * X[:, ci]
    return Y, X, Z, lineage


def screen_once(Y, X, Z):
    beta, r, p, se, df = ST.associate(Y, X, Z)
    q = ST.bh_qvalues(p).reshape(p.shape)
    cand = ((np.abs(beta) >= SC.MIN_ABS_BETA)
            & (np.abs(beta) - SC.LB_Z * se >= SC.MIN_BETA_LB)
            & (q <= SC.MAX_Q))
    ci, di = np.where(cand)
    lb = np.abs(beta[ci, di]) - SC.LB_Z * se[ci, di]
    order = np.argsort(-lb, kind="stable")
    out, per_ctx, per_dep = [], {}, {}
    for k in order:
        c, d = int(ci[k]), int(di[k])
        if per_ctx.get(c, 0) >= SC.MAX_PER_CONTEXT or per_dep.get(d, 0) >= SC.MAX_PER_DEP:
            continue
        out.append((c, d))
        per_ctx[c] = per_ctx.get(c, 0) + 1
        per_dep[d] = per_dep.get(d, 0) + 1
        if len(out) >= sum(SC.STRATUM_N.values()):
            break
    return out, int(cand.sum()), beta, q


@pytest.fixture(scope="module")
def data():
    return build()


def test_the_screen_recovers_every_planted_association(data):
    Y, X, Z, _ = data
    sel, n_cand, beta, q = screen_once(Y, X, Z)
    found = set(sel)
    for ci, di, b in PLANTED:
        assert (ci, di) in found, f"missed the planted pair {ci}->{di} of size {b}"
        assert np.sign(beta[ci, di]) == np.sign(b)
        assert beta[ci, di] == pytest.approx(b, abs=0.2)
        assert q[ci, di] <= SC.MAX_Q


def test_the_planted_pairs_rank_at_the_top(data):
    Y, X, Z, _ = data
    sel, _, _, _ = screen_once(Y, X, Z)
    planted = {(c, d) for c, d, _ in PLANTED}
    assert set(sel[:len(PLANTED)]) == planted


def test_the_false_positives_stay_near_the_declared_error_rate(data):
    Y, X, Z, _ = data
    _, n_cand, _, _ = screen_once(Y, X, Z)
    assert len(PLANTED) <= n_cand <= len(PLANTED) + 5      # q <= 0.01 over 400k pairs


def test_permuting_the_contexts_destroys_the_signal(data):
    Y, X, Z, lineage = data
    perm = ST.permute_within(lineage, np.random.default_rng(20260925))
    sel, n_cand, _, _ = screen_once(Y, X[perm], Z)
    assert n_cand <= 3
    assert not set(sel) & {(c, d) for c, d, _ in PLANTED}


def test_permutation_keeps_the_lineage_structure_it_is_supposed_to_keep(data):
    _, X, _, lineage = data
    perm = ST.permute_within(lineage, np.random.default_rng(1))
    assert np.array_equal(lineage[perm], lineage)
    assert np.allclose(X[perm].mean(axis=0), X.mean(axis=0))


def test_a_screen_with_nothing_planted_finds_nothing():
    g = np.random.default_rng(99)
    lineage = g.choice(["a", "b", "c"], size=300)
    Z = ST.design(lineage, g.poisson(50, 300).astype(float), g.normal(size=300),
                  g.integers(0, 2, 300).astype(float))
    X = (g.random((300, 500)) < 0.3).astype(float)
    Y = g.normal(size=(300, 300))
    _, n_cand, _, _ = screen_once(Y, X, Z)
    assert n_cand == 0


def test_the_effect_size_floor_actually_bites():
    """Tiny-but-significant effects must not enter the candidate list."""
    g = np.random.default_rng(7)
    n = 4000
    lineage = np.array(["a"] * n)
    Z = ST.design(lineage, g.poisson(50, n).astype(float), g.normal(size=n),
                  g.integers(0, 2, n).astype(float))
    x = (g.random(n) < 0.3).astype(float)
    y = -0.10 * x + g.normal(scale=0.3, size=n)      # real, but a tenth of a copy
    beta, _, p, _, _ = ST.associate(y[:, None], x[:, None], Z)
    assert p[0, 0] < 1e-20                            # unmistakably significant
    assert abs(beta[0, 0]) < SC.MIN_ABS_BETA          # and correctly excluded
