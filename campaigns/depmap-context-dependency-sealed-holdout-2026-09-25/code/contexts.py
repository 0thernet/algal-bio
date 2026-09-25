#!/usr/bin/env python3
"""Context definitions, shared by discovery and confirmation.

Both arms import the binarisation from here, so the meaning of a context cannot
drift between the screen and the holdout test. Two properties matter and are
enforced by construction:

  per-column coverage   a model that was not measured for THIS gene is missing,
                        never context-negative, regardless of which other genes
                        were requested in the same call.
  no data-dependent cuts  every threshold is a fixed constant. Median splits are
                        not used, because a median taken over one model set and
                        applied to another silently changes the definition.
"""
import csv, os, re
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = f"{ROOT}/data/depmap24q4"

# frozen thresholds
EXPR_LOW = 1.0          # log2(TPM+1) below this is loss of expression
DEEP_DEL_CN = 0.5       # absolute copy number below this is a deep deletion
MSI_HI = 20.0           # MSIScore above this is MSI-high

SRC = {"MUT_DAM": ("OmicsSomaticMutationsMatrixDamaging.csv", lambda a: a > 0),
       "MUT_HOT": ("OmicsSomaticMutationsMatrixHotspot.csv", lambda a: a > 0),
       "DEL": ("OmicsAbsoluteCNGene.csv", lambda a: a < DEEP_DEL_CN),
       "EXPR_LOW": ("OmicsExpressionProteinCodingGenesTPMLogp1.csv", lambda a: a < EXPR_LOW)}

# SIG features are whole-genome states with no context gene. Only states with a
# fixed, published cut are offered: a median split would make the definition
# depend on which models happen to be in the set.
SIG_DEF = {"MSI_HIGH": ("MSIScore", lambda v: v > MSI_HI),
           "WGD": ("WGD", lambda v: v > 0)}


def strip_entrez(cols):
    """'TP53 (7157)' -> 'TP53'"""
    return [re.sub(r"\s*\(\d+\)$", "", str(c)) for c in cols]


def binarise(values, kind):
    """Numeric column -> float 0/1 with NaN preserved as NaN.

    This is the single definition of "context positive". prep.py and build()
    both call it, so discovery and confirmation cannot disagree.
    """
    v = np.asarray(values, dtype=float)
    out = np.where(SRC[kind][1](v), 1.0, 0.0)
    return np.where(np.isfinite(v), out, np.nan)


_READ_CACHE = {}
_FRAME_CACHE = {}


def _read_cols(fn, want):
    """Read each file once per data dir, then select columns from the cached frame.

    Caching per column set re-read the whole file for every single-feature lookup
    (the annotation proxies do one lookup per candidate context), which made a
    238 MB copy-number read happen hundreds of times. The values are identical."""
    key = (D, fn)
    if key not in _READ_CACHE:
        _READ_CACHE[key] = pd.read_csv(f"{D}/{fn}", index_col=0)
    return _READ_CACHE[key][list(want)]


def _colmap(fn):
    """Gene symbol -> column name for one file, built once per data dir (the files have
    ~20k columns, so re-parsing the header per lookup dominated the annotation run)."""
    def load():
        with open(f"{D}/{fn}") as fh:
            header = next(csv.reader(fh))
        colmap = {}
        for c in header[1:]:
            colmap.setdefault(re.sub(r"\s*\(\d+\)$", "", c), c)
        return colmap
    return _cached(("colmap", fn), load)


def _cached(name, load):
    key = (D, name)
    if key not in _FRAME_CACHE:
        _FRAME_CACHE[key] = load()
    return _FRAME_CACHE[key]


def signatures():
    return _cached("sig", lambda: pd.read_csv(f"{D}/OmicsSignatures.csv", index_col=0))


def sig_binary(names, models):
    sig = signatures()
    out = pd.DataFrame(index=list(models))
    for g in names:
        col, pos = SIG_DEF[g]
        v = sig[col]
        b = pd.Series(np.where(pos(v.to_numpy(dtype=float)), 1.0, 0.0),
                      index=sig.index).where(v.notna())
        out[f"SIG:{g}"] = b.reindex(out.index)
    return out


def build(keys, models):
    """keys: iterable of 'KIND:GENE'. Returns DataFrame models x keys.

    The value for one key never depends on which other keys were requested.
    """
    keys = list(dict.fromkeys(keys))
    by_kind = {}
    for k in keys:
        kind, gene = k.split(":", 1)
        by_kind.setdefault(kind, []).append(gene)
    index = pd.Index(list(models))
    cols = {}
    for kind, genes in by_kind.items():
        if kind == "SIG":
            sb = sig_binary(genes, index)
            for c in sb.columns:
                cols[c] = sb[c]
            continue
        fn, _ = SRC[kind]
        colmap = _colmap(fn)
        want = [colmap[g] for g in genes if g in colmap]
        df = _read_cols(fn, want)
        for g in genes:
            if g not in colmap:
                cols[f"{kind}:{g}"] = pd.Series(np.nan, index=index)
                continue
            col = df[colmap[g]]
            # coverage is per column: a model measured for another gene in the
            # same file but null for this one is missing, not context-negative
            v = pd.Series(binarise(col.to_numpy(dtype=float), kind), index=df.index)
            cols[f"{kind}:{g}"] = v.reindex(index)
    return pd.concat([cols[k] for k in keys], axis=1, keys=keys)


def model_table():
    return _cached("model", lambda: pd.read_csv(f"{D}/Model.csv", index_col=0))


def tmb_series():
    def load():
        dam = pd.read_csv(f"{D}/OmicsSomaticMutationsMatrixDamaging.csv", index_col=0)
        s = dam.sum(axis=1)
        del dam
        return s
    return _cached("tmb", load)


def tp53_series():
    """Damaging TP53 mutation status per model, the covariate form."""
    def load():
        head = pd.read_csv(f"{D}/OmicsSomaticMutationsMatrixDamaging.csv", nrows=0)
        col = next(c for c in head.columns[1:] if re.sub(r"\s*\(\d+\)$", "", c) == "TP53")
        df = pd.read_csv(f"{D}/OmicsSomaticMutationsMatrixDamaging.csv", index_col=0,
                         usecols=[head.columns[0], col])
        return (df[col] > 0).astype(float).where(df[col].notna())
    return _cached("tp53", load)


def covariates_for(models):
    """Covariate design for an arbitrary model list, same terms as discovery."""
    import stats as ST
    models = list(models)
    tmb = tmb_series().reindex(models).to_numpy(dtype=float)
    sig = signatures().reindex(models)
    mod = model_table().reindex(models)
    tp53 = tp53_series().reindex(models).to_numpy(dtype=float)
    return ST.design(mod.OncotreeLineage.fillna("UNKNOWN").to_numpy(dtype=str), tmb,
                     sig.Aneuploidy.to_numpy(dtype=float), sig.WGD.to_numpy(dtype=float),
                     sex=mod.Sex.to_numpy(dtype=object),
                     disease=mod.OncotreePrimaryDisease.fillna("UNKNOWN").to_numpy(dtype=object),
                     tp53=tp53)
