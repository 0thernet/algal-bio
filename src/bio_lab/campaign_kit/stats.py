"""Standard-library statistics shared by campaigns.

bh_qvalues keeps the name the completed campaigns used (helper-name drift
caused an erratum once). Randomness always comes from an explicit seed or a
random.Random, so every placebo and interval is reproducible.
"""

from __future__ import annotations

import math
import random
from typing import Callable, Sequence


def _check_p(p) -> list[float]:
    out = []
    for value in p:
        value = float(value)
        if not (0.0 <= value <= 1.0):
            raise ValueError("p-values must lie in [0, 1] (NaN is not allowed)")
        out.append(value)
    return out


def bh_qvalues(p: Sequence[float]) -> list[float]:
    """Benjamini-Hochberg q-values, in the input order (R: p.adjust(p, "BH"))."""
    values = _check_p(p)
    n = len(values)
    order = sorted(range(n), key=lambda i: values[i])
    q = [0.0] * n
    running = 1.0
    for rank in range(n, 0, -1):
        i = order[rank - 1]
        running = min(running, values[i] * n / rank)
        q[i] = min(1.0, running)
    return q


def _rng(seed) -> random.Random:
    if isinstance(seed, random.Random):
        return seed
    if seed is None or isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("pass an integer seed or a random.Random; unseeded randomness is not "
                         "reproducible")
    return random.Random(seed)


def permute_within(labels: Sequence, seed) -> list[int]:
    """An index permutation that shuffles positions only inside each label group."""
    rng = _rng(seed)
    groups: dict = {}
    for index, label in enumerate(labels):
        groups.setdefault(label, []).append(index)
    out = list(range(len(labels)))
    for key in sorted(groups, key=repr):
        members = groups[key]
        shuffled = members[:]
        rng.shuffle(shuffled)
        for target, source in zip(members, shuffled):
            out[target] = source
    return out


def permutation_pvalue(observed: float, null: Sequence[float], alternative: str = "greater") -> float:
    """(1 + #null at least as extreme) / (1 + len(null)); never zero."""
    if not null:
        raise ValueError("the null distribution is empty")
    if alternative == "greater":
        extreme = sum(1 for v in null if v >= observed)
    elif alternative == "less":
        extreme = sum(1 for v in null if v <= observed)
    elif alternative == "two-sided":
        extreme = sum(1 for v in null if abs(v) >= abs(observed))
    else:
        raise ValueError("alternative must be greater, less or two-sided")
    return (1 + extreme) / (1 + len(null))


def permutation_test(statistic: Callable[[Sequence], float], values: Sequence, labels: Sequence,
                     *, n_perm: int, seed, strata: Sequence | None = None,
                     alternative: str = "greater") -> dict:
    """Permute labels (within strata if given) and compare statistic(values, labels)."""
    if n_perm < 1:
        raise ValueError("n_perm must be positive")
    if len(values) != len(labels) or (strata is not None and len(strata) != len(labels)):
        raise ValueError("values, labels and strata must have the same length")
    rng = _rng(seed)
    observed = statistic(values, labels)
    null = []
    groups = strata if strata is not None else [0] * len(labels)
    for _ in range(n_perm):
        index = permute_within(groups, rng)
        null.append(statistic(values, [labels[i] for i in index]))
    return {"observed": observed, "p": permutation_pvalue(observed, null, alternative),
            "n_perm": n_perm}


def bootstrap_ci(values: Sequence[float], statistic: Callable[[Sequence[float]], float] | None = None,
                 *, n_boot: int = 2000, alpha: float = 0.05, seed) -> tuple[float, float, float]:
    """Percentile bootstrap: (estimate, low, high)."""
    values = list(values)
    if not values:
        raise ValueError("no values to bootstrap")
    if not (0 < alpha < 1) or n_boot < 1:
        raise ValueError("alpha must lie in (0, 1) and n_boot must be positive")
    statistic = statistic or (lambda xs: sum(xs) / len(xs))
    rng = _rng(seed)
    n = len(values)
    draws = sorted(statistic([values[rng.randrange(n)] for _ in range(n)]) for _ in range(n_boot))
    low = draws[max(0, math.floor(alpha / 2 * n_boot))]
    high = draws[min(n_boot - 1, math.ceil((1 - alpha / 2) * n_boot) - 1)]
    return statistic(values), low, high


def binom_sf(k: int, n: int, p: float = 0.5) -> float:
    """P(X >= k) for X ~ Binomial(n, p), exact (log-space terms)."""
    if not (0 <= p <= 1) or n < 0:
        raise ValueError("need 0 <= p <= 1 and n >= 0")
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    if p in (0.0, 1.0):
        return 1.0 if p == 1.0 else 0.0
    logs = [math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1)
            + i * math.log(p) + (n - i) * math.log1p(-p) for i in range(k, n + 1)]
    top = max(logs)
    return min(1.0, math.exp(top) * sum(math.exp(v - top) for v in logs))


def sign_test(successes: int, trials: int, alternative: str = "greater") -> float:
    """One-sided exact sign test of successes out of trials against p = 0.5."""
    if not (0 <= successes <= trials):
        raise ValueError("need 0 <= successes <= trials")
    if alternative == "greater":
        return binom_sf(successes, trials, 0.5)
    if alternative == "less":
        return binom_sf(trials - successes, trials, 0.5)
    raise ValueError("alternative must be greater or less")


def sign_test_differences(differences: Sequence[float], alternative: str = "greater") -> dict:
    """Sign test on paired differences; exact zeros are dropped and counted."""
    positive = sum(1 for d in differences if d > 0)
    negative = sum(1 for d in differences if d < 0)
    zeros = len(differences) - positive - negative
    return {"positive": positive, "negative": negative, "zeros": zeros,
            "p": sign_test(positive, positive + negative, alternative) if positive + negative else 1.0}


def wilson_interval(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    """Wilson score interval for a proportion k/n."""
    if n <= 0 or not (0 <= k <= n):
        raise ValueError("need n > 0 and 0 <= k <= n")
    phat = k / n
    denom = 1 + z * z / n
    centre = (phat + z * z / (2 * n)) / denom
    half = z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)
