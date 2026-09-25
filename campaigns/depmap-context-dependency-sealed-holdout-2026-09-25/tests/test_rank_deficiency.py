"""The covariate design is rank deficient in about half of the per-pair model
subsets of the real tier A, because a lineage indicator and a sex or disease
indicator routinely coincide once the model list is restricted to one pair's
finite values. A non-pivoted QR silently returns the wrong projector in exactly
that case, leaving a real covariate in the residual and manufacturing an effect
above the study's own 0.30 floor. These tests are the guard.
"""
import numpy as np
import pytest

import stats as ST


def deficient_design(n=200, seed=0):
    g = np.random.default_rng(seed)
    a = (g.random(n) < 0.3).astype(float)
    b = g.normal(size=n)
    # the deficiency is at columns 1 and 2, EARLIER than the last column, which
    # is the case a non-pivoted QR gets wrong
    return np.column_stack([np.ones(n), a, a, b]), a, b


def test_the_basis_spans_a_rank_deficient_design():
    Z, _, _ = deficient_design()
    Q, rank = ST.basis(Z)
    assert rank == 3
    assert np.abs(Z - Q @ (Q.T @ Z)).max() < 1e-8


def test_the_residualiser_annihilates_every_column_of_a_rank_deficient_design():
    Z, _, _ = deficient_design()
    R, rank = ST.residualiser(Z)
    assert rank == 3
    assert np.abs(R @ Z).max() < 1e-8, "a covariate survived the projection"


def test_a_covariate_driven_outcome_produces_no_effect_when_the_design_is_deficient():
    """y is generated entirely by a covariate. Any non-trivial beta is the bug."""
    Z, a, _ = deficient_design(seed=1)
    g = np.random.default_rng(2)
    n = Z.shape[0]
    y = 3.0 * a + g.normal(scale=0.1, size=n)
    x = (g.random(n) < 0.4).astype(float)
    b, r, p, se, df = ST.associate(y[:, None], x[:, None], Z)
    # the screen's own candidate floor is |beta| >= 0.30; the buggy projector
    # produced 0.356 on the real tier A design, above that floor
    assert abs(float(b[0, 0])) < 0.10, \
        f"a rank-deficient design leaked a covariate into beta: {b[0, 0]}"


def test_a_duplicated_column_does_not_change_the_answer():
    """Adding a copy of an existing covariate must not move beta at all."""
    g = np.random.default_rng(3)
    n = 300
    a = (g.random(n) < 0.4).astype(float)
    b_ = g.normal(size=n)
    Z1 = np.column_stack([np.ones(n), a, b_])
    Z2 = np.column_stack([np.ones(n), a, a, b_, b_])
    x = (g.random(n) < 0.3).astype(float)
    y = 0.8 * x + 1.5 * a + g.normal(scale=0.5, size=n)
    r1 = ST.associate(y[:, None], x[:, None], Z1)
    r2 = ST.associate(y[:, None], x[:, None], Z2)
    assert np.isclose(float(r1[0][0, 0]), float(r2[0][0, 0]), atol=1e-9)
    assert r1[4] == r2[4], "duplicated columns must not consume degrees of freedom"


def test_the_assertion_fires_if_the_basis_ever_stops_spanning():
    """associate asserts its own basis. The guard must be live, not decorative."""
    Z = np.column_stack([np.ones(50), np.arange(50.0)])
    y = np.random.default_rng(4).normal(size=50)
    x = (np.arange(50) % 2).astype(float)
    ST.associate(y[:, None], x[:, None], Z)      # no assertion error on a good design
    src = open(ST.__file__).read()
    assert "does not span the design" in src, "the spanning assertion was removed"
