"""Standard-library statistics against hand-computed reference values."""

from __future__ import annotations

import math
import random

import pytest

from bio_lab.campaign_kit import stats

# Benjamini & Hochberg (1995), section 4: fifteen p-values, four rejected at q = 0.05.
BH_1995 = [0.0001, 0.0004, 0.0019, 0.0095, 0.0201, 0.0278, 0.0298, 0.0344, 0.0459, 0.3240,
           0.4262, 0.5719, 0.6528, 0.7590, 1.0000]


def reference_bh(p):
    """Direct definition: q_(i) = min over j >= i of p_(j) * n / j."""
    n = len(p)
    order = sorted(range(n), key=lambda i: p[i])
    q = [0.0] * n
    for rank, i in enumerate(order, 1):
        q[i] = min(1.0, min(p[order[j - 1]] * n / j for j in range(rank, n + 1)))
    return q


def test_bh_small_hand_example():
    # p.adjust(c(0.01, 0.04, 0.03, 0.005), "BH") = 0.02 0.04 0.04 0.02
    assert stats.bh_qvalues([0.01, 0.04, 0.03, 0.005]) == pytest.approx([0.02, 0.04, 0.04, 0.02])


def test_bh_1995_example():
    q = stats.bh_qvalues(BH_1995)
    assert q == pytest.approx(reference_bh(BH_1995))
    assert sum(v <= 0.05 for v in q) == 4
    shuffled = BH_1995[:]
    random.Random(7).shuffle(shuffled)
    assert stats.bh_qvalues(shuffled) == pytest.approx(reference_bh(shuffled))


def test_bh_edge_cases():
    assert stats.bh_qvalues([]) == []
    assert stats.bh_qvalues([0.5]) == [0.5]
    assert stats.bh_qvalues([0.9, 0.95]) == [0.95, 0.95]
    with pytest.raises(ValueError):
        stats.bh_qvalues([0.1, float("nan")])
    with pytest.raises(ValueError):
        stats.bh_qvalues([1.5])


def test_randomness_needs_a_seed():
    with pytest.raises(ValueError, match="seed"):
        stats.permute_within([1, 1, 2], None)
    with pytest.raises(ValueError, match="seed"):
        stats.bootstrap_ci([1.0, 2.0], seed=1.5)


def test_permute_within_keeps_strata():
    strata = ["a", "a", "a", "b", "b", "c"]
    index = stats.permute_within(strata, 11)
    assert sorted(index) == list(range(6))
    assert all(strata[index[i]] == strata[i] for i in range(6))
    assert index == stats.permute_within(strata, 11)


def test_permutation_pvalue_is_never_zero():
    assert stats.permutation_pvalue(5.0, [0.0] * 99) == pytest.approx(1 / 100)
    assert stats.permutation_pvalue(-5.0, [0.0, -6.0], alternative="less") == pytest.approx(2 / 3)
    assert stats.permutation_pvalue(-5.0, [4.0, 6.0], alternative="two-sided") == pytest.approx(2 / 3)
    with pytest.raises(ValueError):
        stats.permutation_pvalue(1.0, [])


def test_permutation_test_is_reproducible_and_detects_a_shift():
    values = [0.0] * 20 + [1.0] * 20
    labels = [0] * 20 + [1] * 20

    def mean_diff(v, lab):
        ones = [x for x, l in zip(v, lab) if l == 1]
        zeros = [x for x, l in zip(v, lab) if l == 0]
        return sum(ones) / len(ones) - sum(zeros) / len(zeros)

    first = stats.permutation_test(mean_diff, values, labels, n_perm=199, seed=3)
    assert first == stats.permutation_test(mean_diff, values, labels, n_perm=199, seed=3)
    assert first["observed"] == 1.0 and first["p"] == pytest.approx(1 / 200)
    strata = [0, 1] * 20
    within = stats.permutation_test(mean_diff, values, labels, n_perm=50, seed=3, strata=strata)
    assert within["n_perm"] == 50


def test_bootstrap_ci():
    est, low, high = stats.bootstrap_ci([2.0] * 10, seed=1, n_boot=100)
    assert est == low == high == 2.0
    values = [float(i) for i in range(100)]
    est, low, high = stats.bootstrap_ci(values, seed=5, n_boot=500)
    assert low < est < high and est == pytest.approx(49.5)
    assert (est, low, high) == stats.bootstrap_ci(values, seed=5, n_boot=500)


def test_binomial_and_sign_tests():
    assert stats.binom_sf(8, 10) == pytest.approx(56 / 1024)
    assert stats.binom_sf(0, 10) == 1.0 and stats.binom_sf(11, 10) == 0.0
    assert stats.sign_test(10, 10) == pytest.approx(1 / 1024)
    assert stats.sign_test(0, 10, "less") == pytest.approx(1 / 1024)
    big = stats.binom_sf(600, 1000)
    assert 0 < big < 1e-9 and math.isfinite(big)
    result = stats.sign_test_differences([0.5, 0.2, -0.1, 0.0, 0.3])
    assert (result["positive"], result["negative"], result["zeros"]) == (3, 1, 1)
    assert result["p"] == pytest.approx(5 / 16)


def test_wilson_interval():
    low, high = stats.wilson_interval(5, 10)
    assert low == pytest.approx(0.2366, abs=1e-4) and high == pytest.approx(0.7634, abs=1e-4)
    assert stats.wilson_interval(0, 10)[0] == 0.0
    with pytest.raises(ValueError):
        stats.wilson_interval(3, 0)
