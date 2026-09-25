#!/usr/bin/env python3
"""Shared statistics for the context-dependency study.

One routine, used identically in discovery, placebo and confirmation:
residualise dependency and context on a covariate design, then report the
regression slope of dependency on the binary context and its correlation and
two-sided p-value.

The design is intercept + lineage one-hot + primary-disease one-hot + sex
one-hot + standardised log1p(damaging mutation burden) + aneuploidy +
whole-genome doubling + TP53 damaging status. Disease is in the design because
lineage does not separate cell identity inside a lineage: 87 discovery models
are "Lymphoid", spanning mature B-cell neoplasms, B-ALL, mature T/NK and T-ALL,
and the canonical B-cell identity factors (EBF1, IRF4, POU2AF1, PAX5) are
otherwise free to appear as context-specific dependencies when they are only
cell identity. TP53 is in the design because residual copy-number proximity
bias after the release's own arm correction is larger in TP53-mutant lines
(Vinceti 2024); the cost is that TP53 mutation is then unidentified as a
context, and it is excluded from the context universe a priori rather than
silently zeroed.
"""
import numpy as np
from scipy import stats as sps


# A one-hot level with fewer than this many models carries almost no information
# and costs a degree of freedom. Such levels are folded into the intercept. This
# matters in the small confirmation tiers, where a 96-level disease one-hot would
# otherwise consume most of the residual degrees of freedom.
MIN_LEVEL_N = 3


def _onehot(v, out):
    """Append one-hot columns for the levels of v with at least MIN_LEVEL_N models.

    The most common qualifying level is dropped and carried by the intercept.
    Models whose level does not qualify get all-zero indicators, so they too are
    described by the intercept.
    """
    v = np.asarray(["UNKNOWN" if not isinstance(x, str) else x for x in v])
    levels = [lv for lv in sorted(set(v.tolist())) if (v == lv).sum() >= MIN_LEVEL_N]
    if len(levels) < 2:
        return
    drop = max(levels, key=lambda lv: ((v == lv).sum(), lv))
    for lv in levels:
        if lv != drop:
            out.append((v == lv).astype(np.float64))


def design(lineage, tmb, aneu, wgd, sex=None, disease=None, tp53=None):
    """Covariate matrix. Rows are models, in the caller's order.

    Lineage, primary disease and sex enter as one-hot blocks; mutational burden,
    aneuploidy and whole-genome doubling enter standardised; TP53 damaging status
    enters as a 0/1 indicator. Sex is a covariate because sex-chromosome copy
    number and X-linked dependencies (for example DDX3X, buffered by DDX3Y)
    track it.
    """
    n = len(np.asarray(lineage))
    Z = [np.ones(n, dtype=np.float64)]
    _onehot(np.asarray(lineage), Z)
    if disease is not None:
        _onehot(np.asarray(disease, dtype=object), Z)
    if sex is not None:
        _onehot(np.asarray(sex, dtype=object), Z)
    for v in (np.log1p(np.asarray(tmb, dtype=np.float64)),
              np.asarray(aneu, dtype=np.float64),
              np.asarray(wgd, dtype=np.float64)):
        v = v.copy()
        bad = ~np.isfinite(v)
        if bad.all():
            continue
        v[bad] = np.median(v[~bad])
        if np.std(v) > 0:
            Z.append((v - v.mean()) / np.std(v))
        if MIN_LEVEL_N <= bad.sum() <= n - MIN_LEVEL_N:
            Z.append(bad.astype(np.float64))   # "this value was imputed"
    if tp53 is not None:
        t = np.asarray(tp53, dtype=np.float64)
        t = np.where(np.isfinite(t), t, 0.0)
        if 0 < t.sum() < n:
            Z.append(t)
    return np.column_stack(Z)


def basis(Z):
    """Orthonormal basis for the column space of Z, and its rank.

    An SVD, not a QR. numpy's QR is not pivoted, so when Z is rank deficient
    its leading `rank` columns need not span col(Z): if the deficiency is at an
    earlier column, Q[:, :rank] contains an arbitrary Householder direction and
    omits a real covariate direction, leaving that covariate in the residual.
    The covariate designs here are rank deficient in about half of the tier A
    per-pair subsets, because a lineage indicator and a sex or disease indicator
    routinely coincide once the model list is restricted to one pair's finite
    values. An SVD basis is correct in every case.
    """
    Z = np.asarray(Z, dtype=np.float64)
    U, sv, _ = np.linalg.svd(Z, full_matrices=False)
    if sv.size == 0 or sv[0] <= 0:
        return U[:, :0], 0
    rank = int((sv > sv[0] * max(Z.shape) * np.finfo(np.float64).eps).sum())
    return U[:, :rank], rank


def residualiser(Z):
    """Return (R, rank) where R @ v removes the column space of Z from v."""
    Q, rank = basis(Z)
    return np.eye(np.asarray(Z).shape[0]) - Q @ Q.T, rank


# A context that is (near-)perfectly explained by the covariates carries no
# independent information, and dividing by its vanishing residual variance
# manufactures an arbitrarily large slope. Such a column is unidentified and is
# reported as no effect rather than as a huge one. The test fails closed: an
# unidentified pair can never replicate, because its |beta| is zero.
IDENT_FRAC = 1e-6
IDENT_ABS = 1e-12


def associate(Y, X, Z, min_df=20):
    """Y: models x dep genes. X: models x context features (0/1). Z: covariates.

    Returns beta (context features x dep genes), r, p, se, df.
    beta is the covariate-adjusted change in gene effect for context-positive
    models, in Chronos gene-effect units; se is its standard error.

    Context columns with no residual variance left after covariate adjustment
    are unidentified and come back as beta 0, r 0, p 1, se infinite.
    """
    Y = np.asarray(Y, dtype=np.float64)
    X = np.asarray(X, dtype=np.float64)
    Zf = np.asarray(Z, dtype=np.float64)
    Q, rank = basis(Zf)
    assert np.abs(Zf - Q @ (Q.T @ Zf)).max() < 1e-8 * max(1.0, np.abs(Zf).max()), \
        "the covariate basis does not span the design"
    Yc = Y - Q @ (Q.T @ Y)
    Xc = X - Q @ (Q.T @ X)
    df = Y.shape[0] - rank - 1
    if df < min_df:
        raise ValueError(f"df too small: {df}")
    sxx = np.einsum("ij,ij->j", Xc, Xc)
    syy = np.einsum("ij,ij->j", Yc, Yc)
    sxy = Xc.T @ Yc
    Xd = X - X.mean(axis=0, keepdims=True)
    sxx_raw = np.einsum("ij,ij->j", Xd, Xd)
    ident = sxx > np.maximum(IDENT_FRAC * sxx_raw, IDENT_ABS)
    with np.errstate(divide="ignore", invalid="ignore"):
        beta = sxy / sxx[:, None]
        r = sxy / np.sqrt(np.outer(sxx, syy))
    r = np.clip(np.nan_to_num(r, nan=0.0), -0.999999, 0.999999)
    beta = np.where(ident[:, None], beta, 0.0)
    r = np.where(ident[:, None], r, 0.0)
    t = r * np.sqrt(df / (1.0 - r ** 2))
    p = 2.0 * sps.t.sf(np.abs(t), df)
    with np.errstate(divide="ignore", invalid="ignore"):
        resvar = np.maximum(syy[None, :] - (beta ** 2) * sxx[:, None], 0.0) / df
        se = np.sqrt(resvar / sxx[:, None])
    se = np.nan_to_num(se, nan=np.inf, posinf=np.inf)
    se = np.where(ident[:, None], se, np.inf)
    return beta, r, p, se, df


def bh_qvalues(p):
    """Benjamini-Hochberg q-values over a flat array of p-values."""
    p = np.asarray(p, dtype=np.float64).ravel()
    n = p.size
    order = np.argsort(p, kind="stable")
    q = np.empty(n, dtype=np.float64)
    ranked = p[order] * n / np.arange(1, n + 1)
    q[order] = np.minimum.accumulate(ranked[::-1])[::-1]
    return np.clip(q, 0.0, 1.0)


def permute_within(labels, rng):
    """Index permutation that shuffles rows only inside each label group."""
    labels = np.asarray(labels)
    idx = np.arange(labels.size)
    out = idx.copy()
    for lv in np.unique(labels):
        w = idx[labels == lv]
        out[w] = rng.permutation(w)
    return out
