#!/usr/bin/env python3
"""A/B compartment eigenvector (PC1) at a fixed bin size from HiC-Pro outputs.

Method (in order; every step is a public function below):

1. **bin** -- cis, autosomal (chr1..chr22) contacts are binned at ``bin_size``
   (default 500 kb) into one symmetric dense count matrix per chromosome
   (``bin_valid_pairs`` from a HiC-Pro ``allValidPairs`` file, or
   ``read_hicpro_matrix`` from a HiC-Pro ``bins.bed`` + sparse matrix).
   Bin index of a 1-based position ``pos`` is ``(pos - 1) // bin_size``.
   For a pair with bins ``i != j`` the matrix gets +1 at ``[i, j]`` and at
   ``[j, i]``; a pair with ``i == j`` adds +1 at ``[i, i]`` once.
2. **ICE** -- iterative correction (Imakaev et al. 2012 style matrix
   balancing) of each cis matrix (``ice``).  Bins with fewer than
   ``min_nnz`` (default 10) non-zero entries in their raw row, or a zero raw
   row sum, are masked before balancing; the mask is enlarged if a row
   sum becomes zero after masking.  Balancing iterates
   ``W <- W / (s s^T)`` with ``s = rowsum(W) / mean(rowsum(W))`` until
   ``max |s - 1| < tol`` (default 1e-5) or ``max_iter`` (200) iterations.
   The main diagonal is kept; no final rescaling is applied (the overall
   scale cancels in the O/E step).
3. **O/E** -- observed over expected (``observed_over_expected``): each
   diagonal (fixed genomic separation) of the balanced matrix is divided by
   its arithmetic mean over entries whose two bins are both unmasked.
   Diagonals whose mean is zero (no signal at that separation) are set to
   1.0 (i.e. "as expected").
4. **Pearson** -- Pearson correlation matrix (``numpy.corrcoef``) of the O/E
   matrix restricted to unmasked bins.  Bins whose O/E column has zero
   variance (correlation undefined) are added to the mask.
5. **eigh** -- ``numpy.linalg.eigh`` on the (symmetric) correlation matrix;
   the eigenvector of the largest eigenvalue is taken
   (``compartment_eigenvector``), scaled to unit variance (population
   standard deviation, ``ddof=0``) over unmasked bins, with a deterministic
   provisional sign (sum of entries >= 0).  Masked bins are NaN.
6. **orient** -- the sign is flipped so that the Spearman correlation
   (``scipy.stats.spearmanr``, average ranks for ties) between the
   eigenvector and the gene density (number of RefSeq Select TSSs per bin,
   ``tss_density``) over unmasked bins is positive, so that positive values
   denote the gene-rich "A" compartment (``orient``).  If ``|rho|`` is
   below ``min_abs_rho`` (default 0.2), or fewer than three bins are
   available, the chromosome's vector is reported as all-NaN and is omitted
   from the bedGraph (the correlation is still reported in the stats).

The whole computation is deterministic and uses only numpy and scipy.
"""

from __future__ import annotations

import argparse
import gzip
import io
import json
import math
import sys
import warnings
from typing import Dict, Iterable, List, Optional, Sequence, TextIO, Tuple

import numpy as np
from scipy.stats import spearmanr

__all__ = [
    "AUTOSOMES",
    "normalise_chrom",
    "n_bins",
    "read_chrom_sizes",
    "bin_valid_pairs",
    "read_hicpro_matrix",
    "ice",
    "observed_over_expected",
    "compartment_eigenvector",
    "orient",
    "tss_density",
    "compute_pc1",
    "write_bedgraph",
    "read_bedgraph",
    "main",
]

#: Autosomes, in numeric order, with the ``chr`` prefix.
AUTOSOMES: Tuple[str, ...] = tuple(f"chr{i}" for i in range(1, 23))
_AUTOSOME_SET = frozenset(AUTOSOMES)
_AUTOSOME_ORDER = {c: i for i, c in enumerate(AUTOSOMES)}

_MAPQ_COL_1 = 10  # 0-based column of mapq1 in HiC-Pro allValidPairs
_MAPQ_COL_2 = 11


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------

def normalise_chrom(name: str) -> str:
    """Return ``name`` with exactly one ``chr`` prefix (case-insensitive).

    ``"1"`` -> ``"chr1"``, ``"chr1"`` -> ``"chr1"``, ``"Chr1"`` -> ``"chr1"``.
    Nothing else about the name is changed, so ``"1_random"`` becomes
    ``"chr1_random"`` and is *not* an autosome.
    """
    name = name.strip()
    if name[:3].lower() == "chr":
        name = name[3:]
    return "chr" + name


def is_autosome(name: str) -> bool:
    """True if the (normalised) chromosome name is one of chr1..chr22."""
    return name in _AUTOSOME_SET


def n_bins(chrom_size: int, bin_size: int) -> int:
    """Number of bins covering a chromosome: ``ceil(chrom_size / bin_size)``."""
    return -(-int(chrom_size) // int(bin_size))


def _sorted_chroms(chroms: Iterable[str]) -> List[str]:
    return sorted(chroms, key=lambda c: _AUTOSOME_ORDER.get(c, 10_000))


def _open_text(path: str) -> TextIO:
    """Open a plain or gzip-compressed text file for reading (text mode).

    Compression is detected from the gzip magic bytes, not the extension.
    """
    with open(path, "rb") as probe:
        magic = probe.read(2)
    if magic == b"\x1f\x8b":
        return io.TextIOWrapper(io.BufferedReader(gzip.open(path, "rb"), 1 << 20), encoding="utf-8", errors="replace")
    return open(path, "r", encoding="utf-8", errors="replace", buffering=1 << 20)


# --------------------------------------------------------------------------
# Inputs
# --------------------------------------------------------------------------

def read_chrom_sizes(path: str) -> Dict[str, int]:
    """Read a UCSC two-column ``chrom.sizes`` file, keeping only autosomes.

    Names with or without a ``chr`` prefix are accepted and normalised to
    the ``chr`` form.  Only ``chr1``..``chr22`` are returned; every other
    sequence (sex chromosomes, mitochondrion, unplaced/alt contigs) is
    dropped.  Blank lines and lines starting with ``#`` are ignored.
    """
    sizes: Dict[str, int] = {}
    with _open_text(path) as fh:
        for line in fh:
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            chrom = normalise_chrom(parts[0])
            if is_autosome(chrom):
                sizes[chrom] = int(parts[1])
    return {c: sizes[c] for c in _sorted_chroms(sizes)}


def _layout(chrom_sizes: Dict[str, int], bin_size: int):
    """Per-chromosome (n_bins, flat offset) for one global flat accumulator."""
    chroms = _sorted_chroms(c for c in chrom_sizes if is_autosome(c))
    nb = {c: n_bins(chrom_sizes[c], bin_size) for c in chroms}
    offsets: Dict[str, int] = {}
    total = 0
    for c in chroms:
        offsets[c] = total
        total += nb[c] * nb[c]
    return chroms, nb, offsets, total


def _symmetrise_upper(u: np.ndarray) -> np.ndarray:
    """``U + U^T - diag(U)``: mirror an upper-triangular accumulator."""
    return u + u.T - np.diag(np.diag(u))


def bin_valid_pairs(
    path: str,
    chrom_sizes: Dict[str, int],
    bin_size: int = 500_000,
    min_mapq: Optional[int] = None,
    chunk_size: int = 1_000_000,
) -> Tuple[Dict[str, np.ndarray], Dict[str, object]]:
    """Bin a HiC-Pro ``allValidPairs`` file into dense per-chromosome cis matrices.

    The file (gzip or plain text, detected by magic bytes) is streamed line
    by line.  Columns are whitespace separated.  Two layouts are
    auto-detected from the first data line and recorded in
    ``stats["format"]``: HiC-Pro ``read_name chr1 pos1 strand1 chr2 pos2
    strand2 [frag_size res_frag1 res_frag2 mapq1 mapq2 ...]`` (column 4 is
    a strand) or 4DN-style pairs ``read_name chr1 pos1 chr2 pos2 strand1
    strand2`` (columns 6 and 7 are strands); extra trailing columns are
    ignored.
    Lines starting with ``#`` and lines with fewer than 7 columns or
    non-integer positions are counted as ``malformed`` and skipped.

    Kept pairs are *cis* pairs whose (normalised) chromosome is an autosome
    present in ``chrom_sizes``, with both 1-based positions inside
    ``[1, chrom_size]`` (others are counted under ``out_of_range``).  With
    ``min_mapq`` set, both ``mapq1`` and ``mapq2`` (columns 11 and 12) must
    be ``>= min_mapq``; lines lacking those columns are dropped and counted
    under ``mapq_missing``.  Trans pairs and pairs involving a
    non-autosomal sequence are counted but not binned.

    Bin index is ``(pos - 1) // bin_size``.  The returned matrices are
    ``float64``, ``n_bins x n_bins`` (``n_bins = ceil(size / bin_size)``),
    symmetric: a pair with bins ``i != j`` contributes +1 to both ``[i, j]``
    and ``[j, i]``, a pair with ``i == j`` contributes +1 to ``[i, i]``.

    Memory: one global flat ``float64`` accumulator of ``sum(n_bins^2)``
    entries (about 20 MB for hg38 at 500 kb) plus a buffer of at most
    ``chunk_size`` pending flat indices that is flushed with
    ``numpy.bincount``; the input size is irrelevant.

    Returns ``(matrices, stats)`` where ``stats`` has ``total`` (data
    lines), ``kept``, ``cis`` (cis autosomal pairs, i.e. kept + out_of_range),
    ``trans``, ``non_autosomal``, ``mapq_filtered``, ``mapq_missing``,
    ``out_of_range``, ``malformed`` and ``per_chrom`` (kept pairs per
    chromosome).
    """
    bin_size = int(bin_size)
    chroms, nb, offsets, total_len = _layout(chrom_sizes, bin_size)
    sizes = {c: int(chrom_sizes[c]) for c in chroms}
    acc = np.zeros(total_len, dtype=np.float64)
    per_chrom = {c: 0 for c in chroms}
    stats: Dict[str, object] = {
        "total": 0, "kept": 0, "cis": 0, "trans": 0, "non_autosomal": 0,
        "mapq_filtered": 0, "mapq_missing": 0, "out_of_range": 0, "malformed": 0,
    }
    buf: List[int] = []
    # local aliases for speed
    norm_cache: Dict[str, str] = {}

    def norm(name: str) -> str:
        c = norm_cache.get(name)
        if c is None:
            c = normalise_chrom(name)
            if len(norm_cache) < 4096:  # bounded: a mis-parsed column must not grow memory
                norm_cache[name] = c
        return c

    def flush() -> None:
        if buf:
            acc[:] += np.bincount(np.asarray(buf, dtype=np.int64), minlength=total_len)
            buf.clear()

    c2_col, p2_col = 4, 5  # HiC-Pro layout until detected
    fmt = None
    with _open_text(path) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 7:
                if parts:
                    stats["malformed"] += 1
                continue
            if fmt is None:
                if parts[3] in ("+", "-"):
                    fmt = "hicpro"
                elif parts[5] in ("+", "-") and parts[6] in ("+", "-"):
                    fmt, c2_col, p2_col = "pairs", 3, 4
                else:
                    fmt = "hicpro"
                stats["format"] = fmt
            stats["total"] += 1
            if min_mapq is not None:
                if len(parts) <= _MAPQ_COL_2:
                    stats["mapq_missing"] += 1
                    continue
                try:
                    if int(parts[_MAPQ_COL_1]) < min_mapq or int(parts[_MAPQ_COL_2]) < min_mapq:
                        stats["mapq_filtered"] += 1
                        continue
                except ValueError:
                    stats["malformed"] += 1
                    continue
            c1 = norm(parts[1])
            c2 = norm(parts[c2_col])
            if c1 != c2:
                stats["trans"] += 1
                continue
            n = nb.get(c1)
            if n is None:
                stats["non_autosomal"] += 1
                continue
            try:
                p1 = int(parts[2])
                p2 = int(parts[p2_col])
            except ValueError:
                stats["malformed"] += 1
                continue
            stats["cis"] += 1
            size = sizes[c1]
            if p1 < 1 or p2 < 1 or p1 > size or p2 > size:
                stats["out_of_range"] += 1
                continue
            b1 = (p1 - 1) // bin_size
            b2 = (p2 - 1) // bin_size
            if b1 > b2:
                b1, b2 = b2, b1
            buf.append(offsets[c1] + b1 * n + b2)
            per_chrom[c1] += 1
            stats["kept"] += 1
            if len(buf) >= chunk_size:
                flush()
    flush()

    matrices: Dict[str, np.ndarray] = {}
    for c in chroms:
        n = nb[c]
        upper = acc[offsets[c]:offsets[c] + n * n].reshape(n, n)
        matrices[c] = _symmetrise_upper(upper)
    stats["per_chrom"] = per_chrom
    return matrices, stats


def read_hicpro_matrix(
    bins_bed: str,
    matrix_txt: str,
    chrom_sizes: Dict[str, int],
    bin_size: int = 500_000,
) -> Dict[str, np.ndarray]:
    """Read HiC-Pro ``*_abs.bed`` + sparse ``*.matrix`` into dense cis matrices.

    ``bins_bed`` has four columns ``chrom start end id`` (0-based
    half-open intervals, 1-based integer ids); ``matrix_txt`` (gzip or
    plain) has ``id1 id2 value``.  Chromosome names may lack ``chr``.
    Only bins on autosomes present in ``chrom_sizes`` are used, and every
    such bin must have ``start % bin_size == 0`` and
    ``start // bin_size < ceil(size / bin_size)`` (a ``ValueError`` is
    raised otherwise, i.e. the bed must be at the requested resolution).
    Entries whose two ids are on different chromosomes, or on
    non-autosomes, are ignored.  Lines starting with ``#`` are skipped.

    Values are accumulated at ``[bin1, bin2]`` exactly as listed; then, if
    the result is not already symmetric (HiC-Pro writes only the upper
    triangle, ``id1 <= id2``), it is mirrored as ``M + M^T - diag(M)``.
    The output therefore has the same convention as ``bin_valid_pairs``.
    """
    bin_size = int(bin_size)
    chroms, nb, _offsets, _total = _layout(chrom_sizes, bin_size)
    id_to_bin: Dict[int, Tuple[str, int]] = {}
    with _open_text(bins_bed) as fh:
        for line in fh:
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 4:
                continue
            chrom = normalise_chrom(parts[0])
            n = nb.get(chrom)
            if n is None:
                continue
            start = int(parts[1])
            if start % bin_size != 0:
                raise ValueError(
                    f"{bins_bed}: bin start {start} on {chrom} is not a multiple of bin_size={bin_size}")
            b = start // bin_size
            if b >= n:
                raise ValueError(
                    f"{bins_bed}: bin start {start} on {chrom} is beyond the chromosome size")
            id_to_bin[int(parts[3])] = (chrom, b)

    matrices: Dict[str, np.ndarray] = {c: np.zeros((nb[c], nb[c]), dtype=np.float64) for c in chroms}
    with _open_text(matrix_txt) as fh:
        for line in fh:
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 3:
                continue
            a = id_to_bin.get(int(parts[0]))
            b = id_to_bin.get(int(parts[1]))
            if a is None or b is None or a[0] != b[0]:
                continue
            matrices[a[0]][a[1], b[1]] += float(parts[2])
    for c, m in matrices.items():
        if not np.array_equal(m, m.T):
            matrices[c] = _symmetrise_upper(m)
    return matrices


def tss_density(
    refseq_select_txt_gz: str,
    chrom_sizes: Dict[str, int],
    bin_size: int = 500_000,
) -> Dict[str, np.ndarray]:
    """Count transcription start sites per bin from a UCSC ``ncbiRefSeqSelect`` dump.

    The table (gzip or plain, tab separated; ``#`` lines skipped) has the
    UCSC genePred-with-bin layout ``bin name chrom strand txStart txEnd
    ...``.  A dump without the leading ``bin`` column (``name chrom strand
    txStart txEnd ...``) is also accepted: the layout is chosen per line by
    which column holds the strand (``+``/``-``).  Coordinates are 0-based
    half-open as in UCSC tables.  The TSS is ``txStart`` on ``+`` and
    ``txEnd - 1`` on ``-``; its bin is ``tss // bin_size``.  One count per
    transcript row (RefSeq Select has one row per gene).  Only autosomes
    present in ``chrom_sizes`` are counted; TSSs beyond the chromosome end
    are ignored.  Returns ``{chrom: float64 vector of length n_bins}``.
    """
    bin_size = int(bin_size)
    chroms, nb, _offsets, _total = _layout(chrom_sizes, bin_size)
    out = {c: np.zeros(nb[c], dtype=np.float64) for c in chroms}
    with _open_text(refseq_select_txt_gz) as fh:
        for line in fh:
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 5:
                continue
            if len(parts) >= 6 and parts[3] in ("+", "-"):
                chrom, strand, tx_start, tx_end = parts[2], parts[3], parts[4], parts[5]
            elif parts[2] in ("+", "-"):
                chrom, strand, tx_start, tx_end = parts[1], parts[2], parts[3], parts[4]
            else:
                continue
            chrom = normalise_chrom(chrom)
            vec = out.get(chrom)
            if vec is None:
                continue
            try:
                tss = int(tx_start) if strand == "+" else int(tx_end) - 1
            except ValueError:
                continue
            b = tss // bin_size
            if 0 <= b < vec.shape[0]:
                vec[b] += 1.0
    return out


# --------------------------------------------------------------------------
# Core computation
# --------------------------------------------------------------------------

def ice(
    matrix: np.ndarray,
    max_iter: int = 200,
    tol: float = 1e-5,
    min_nnz: int = 10,
) -> Tuple[np.ndarray, np.ndarray]:
    """Iterative correction (Imakaev et al. 2012) of one symmetric cis matrix.

    Masking: bin ``i`` is masked if its raw row has fewer than ``min_nnz``
    non-zero entries or a zero (or non-finite) row sum.  After restricting
    to unmasked bins, any bin whose row sum over the *unmasked* columns is
    zero is masked as well, repeated until stable.

    Balancing on the unmasked submatrix ``W`` (main diagonal included):
    repeat ``s = rowsum(W); s = s / mean(s); W = W / (s s^T)`` until
    ``max |s - 1| < tol`` or ``max_iter`` iterations.  After convergence
    every unmasked row sums to (approximately) the same value; no final
    rescaling is applied (the scale cancels in the O/E step).  The bias
    vector is the product of the ``s`` factors, so the result equals
    ``M[i, j] / (b_i b_j)``.

    Returns ``(balanced, mask)``: ``balanced`` is a float64 matrix of the
    input's shape with NaN in masked rows and columns; ``mask`` is a boolean
    vector, True for bins that are *kept* (unmasked).
    """
    m = np.asarray(matrix, dtype=np.float64)
    if m.ndim != 2 or m.shape[0] != m.shape[1]:
        raise ValueError("ice expects a square matrix")
    n = m.shape[0]
    finite = np.isfinite(m)
    mz = np.where(finite, m, 0.0)
    nnz = np.count_nonzero(mz != 0.0, axis=1)
    rowsum = mz.sum(axis=1)
    mask = (nnz >= int(min_nnz)) & (rowsum > 0) & finite.all(axis=1)
    # enlarge the mask until every kept row has signal among kept columns
    while True:
        sub_sum = mz[np.ix_(mask, mask)].sum(axis=1) if mask.any() else np.zeros(0)
        bad = sub_sum <= 0
        if not bad.any():
            break
        idx = np.flatnonzero(mask)
        mask[idx[bad]] = False
    balanced = np.full((n, n), np.nan, dtype=np.float64)
    k = int(mask.sum())
    if k == 0:
        return balanced, mask
    w = mz[np.ix_(mask, mask)].copy()
    bias = np.ones(k, dtype=np.float64)
    for _ in range(int(max_iter)):
        s = w.sum(axis=1)
        s /= s.mean()
        w /= s[:, None]
        w /= s[None, :]
        bias *= s
        if np.max(np.abs(s - 1.0)) < tol:
            break
    balanced[np.ix_(mask, mask)] = w
    return balanced, mask


def observed_over_expected(matrix: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Divide each diagonal of ``matrix`` by its mean over unmasked bin pairs.

    For genomic separation ``d`` (``0 <= d < n``) the expected value is the
    arithmetic mean of ``matrix[i, i + d]`` over all ``i`` with both
    ``mask[i]`` and ``mask[i + d]`` True; non-finite entries among those are
    ignored.  Every entry on that diagonal (both triangles) is divided by
    the expected value.  If a diagonal has no unmasked pair or an expected
    value of zero, its entries are set to 1.0.  Masked rows and columns are
    NaN in the output.
    """
    m = np.asarray(matrix, dtype=np.float64)
    mask = np.asarray(mask, dtype=bool)
    n = m.shape[0]
    oe = np.full_like(m, np.nan)
    idx = np.arange(n)
    for d in range(n):
        i = idx[: n - d]
        j = i + d
        valid = mask[i] & mask[j]
        vals = m[i[valid], j[valid]]
        vals = vals[np.isfinite(vals)]
        expected = vals.mean() if vals.size else 0.0
        if not np.isfinite(expected) or expected <= 0.0:
            oe[i[valid], j[valid]] = 1.0
            oe[j[valid], i[valid]] = 1.0
        else:
            oe[i[valid], j[valid]] = m[i[valid], j[valid]] / expected
            oe[j[valid], i[valid]] = m[j[valid], i[valid]] / expected
    return oe


def compartment_eigenvector(
    matrix: np.ndarray,
    mask: np.ndarray,
    return_details: bool = False,
):
    """Leading eigenvector of the Pearson correlation matrix of O/E.

    ``matrix`` is a balanced cis matrix and ``mask`` its kept-bin vector
    (from ``ice``).  Steps: ``observed_over_expected`` -> restrict to kept
    bins -> ``numpy.corrcoef`` -> bins whose correlation row is not finite
    (zero-variance O/E column) are dropped from the mask -> the correlation
    matrix is symmetrised (``(C + C^T) / 2``) and decomposed with
    ``numpy.linalg.eigh`` -> the eigenvector belonging to the largest
    eigenvalue is taken.  It is scaled to unit population variance
    (``ddof=0``) over kept bins, and its provisional sign is fixed so that
    its sum over kept bins is ``>= 0`` (final sign comes from ``orient``).
    Bins not kept are NaN.  With fewer than 3 kept bins the vector is
    all-NaN.

    Returns the full-length vector, or with ``return_details=True`` a tuple
    ``(vector, eigenvalue, final_mask)``.
    """
    mask = np.asarray(mask, dtype=bool).copy()
    n = mask.shape[0]
    vec = np.full(n, np.nan, dtype=np.float64)
    eigval = float("nan")
    if int(mask.sum()) >= 3:
        oe = observed_over_expected(matrix, mask)
        sub = oe[np.ix_(mask, mask)]
        with np.errstate(invalid="ignore", divide="ignore"):
            corr = np.corrcoef(sub)
        good = np.isfinite(corr).all(axis=1)
        if good.sum() < corr.shape[0]:
            idx = np.flatnonzero(mask)
            mask[idx[~good]] = False
            corr = corr[np.ix_(good, good)]
        if corr.shape[0] >= 3:
            corr = 0.5 * (corr + corr.T)
            evals, evecs = np.linalg.eigh(corr)
            lead = evecs[:, -1]
            eigval = float(evals[-1])
            sd = lead.std()
            if sd > 0:
                lead = lead / sd
            if lead.sum() < 0:
                lead = -lead
            vec[mask] = lead
        else:
            mask[:] = False
    else:
        mask[:] = False
    if return_details:
        return vec, eigval, mask
    return vec


def orient(
    eigvec: np.ndarray,
    gene_density: np.ndarray,
    min_abs_rho: float = 0.2,
) -> Tuple[np.ndarray, float]:
    """Sign the eigenvector so that it correlates positively with gene density.

    ``rho`` is the Spearman rank correlation (``scipy.stats.spearmanr``;
    ties get average ranks) between ``eigvec`` and ``gene_density`` over the
    bins where both are finite.  If ``rho < 0`` the vector is negated.  If
    fewer than 3 such bins exist or ``rho`` is undefined (e.g. constant
    gene density) the result is an all-NaN vector and ``rho`` is NaN.  If
    ``|rho| < min_abs_rho`` the result is an all-NaN vector but the computed
    ``rho`` is still returned so the caller can report it.
    Returns ``(oriented_vector, rho)``.
    """
    v = np.asarray(eigvec, dtype=np.float64).copy()
    g = np.asarray(gene_density, dtype=np.float64)
    if v.shape != g.shape:
        raise ValueError("eigvec and gene_density must have the same length")
    valid = np.isfinite(v) & np.isfinite(g)
    nan_vec = np.full_like(v, np.nan)
    if valid.sum() < 3:
        return nan_vec, float("nan")
    with np.errstate(invalid="ignore", divide="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore")  # constant input -> NaN, handled below
        res = spearmanr(v[valid], g[valid])
    rho = float(res.statistic if hasattr(res, "statistic") else res[0])
    if not np.isfinite(rho):
        return nan_vec, float("nan")
    if abs(rho) < min_abs_rho:
        return nan_vec, rho
    if rho < 0:
        v = -v
    return v, rho


def compute_pc1(
    matrices: Dict[str, np.ndarray],
    chrom_sizes: Dict[str, int],
    tss: Dict[str, np.ndarray],
    bin_size: int = 500_000,
    min_abs_rho: float = 0.2,
    min_nnz: int = 10,
    stats: Optional[Dict[str, object]] = None,
) -> List[Tuple[str, int, int, float, float]]:
    """Run ICE -> O/E -> Pearson -> eigh -> orient for every chromosome.

    ``matrices`` maps chromosome (``chr`` form) to its raw symmetric cis
    matrix; ``tss`` maps chromosome to its TSS-per-bin vector (a missing
    chromosome counts as zero density, which yields an undefined
    orientation and an all-NaN vector).  Chromosomes are processed in
    numeric order.  Returns one record per bin,
    ``(chrom, start, end, value, rho)`` with ``end = min((i + 1) *
    bin_size, chrom_size)``; ``value`` is NaN for masked bins or for a
    chromosome whose orientation failed.  If ``stats`` is a dict, a
    ``per_chrom`` entry ``{chrom: {n_bins, n_masked, eigenvalue, rho,
    oriented}}`` is added to it.
    """
    bin_size = int(bin_size)
    records: List[Tuple[str, int, int, float, float]] = []
    per_chrom: Dict[str, Dict[str, object]] = {}
    for chrom in _sorted_chroms(c for c in matrices if is_autosome(c) and c in chrom_sizes):
        raw = matrices[chrom]
        n = raw.shape[0]
        size = int(chrom_sizes[chrom])
        balanced, mask = ice(raw, min_nnz=min_nnz)
        vec, eigval, mask = compartment_eigenvector(balanced, mask, return_details=True)
        density = tss.get(chrom)
        if density is None:
            density = np.zeros(n, dtype=np.float64)
        vec, rho = orient(vec, density, min_abs_rho=min_abs_rho)
        per_chrom[chrom] = {
            "n_bins": int(n),
            "n_masked": int(n - mask.sum()),
            "eigenvalue": None if not np.isfinite(eigval) else eigval,
            "rho": None if not np.isfinite(rho) else rho,
            "oriented": bool(np.isfinite(vec).any()),
        }
        for i in range(n):
            start = i * bin_size
            end = min(start + bin_size, size)
            records.append((chrom, start, end, float(vec[i]), rho))
    if stats is not None:
        stats["per_chrom"] = per_chrom
    return records


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------

def write_bedgraph(records: Sequence[Tuple[str, int, int, float, float]], path: str) -> int:
    """Write ``chrom start end value`` lines (tab separated, ``chr`` prefix).

    Records whose value is not finite are omitted.  Values are written with
    ``repr``-style shortest round-trip formatting (``%.17g`` is not needed:
    Python's ``float.__repr__`` round-trips exactly).  Returns the number of
    lines written.
    """
    n = 0
    with open(path, "w", encoding="utf-8") as fh:
        for chrom, start, end, value, _rho in records:
            if not math.isfinite(value):
                continue
            fh.write(f"{chrom}\t{start}\t{end}\t{value!r}\n")
            n += 1
    return n


def read_bedgraph(path: str) -> List[Tuple[str, int, int, float]]:
    """Read a bedGraph written by ``write_bedgraph`` (``track``/``#`` lines skipped)."""
    out: List[Tuple[str, int, int, float]] = []
    with _open_text(path) as fh:
        for line in fh:
            if not line.strip() or line.startswith("#") or line.startswith("track"):
                continue
            parts = line.split()
            out.append((normalise_chrom(parts[0]), int(parts[1]), int(parts[2]), float(parts[3])))
    return out


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pc1.py",
        description="A/B compartment eigenvector (PC1) from HiC-Pro outputs.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    def common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--chrom-sizes", required=True, help="UCSC chrom.sizes (autosomes are used)")
        sp.add_argument("--refseq", required=True, help="UCSC ncbiRefSeqSelect table (.txt.gz)")
        sp.add_argument("--out", required=True, help="output bedGraph")
        sp.add_argument("--bin-size", type=int, default=500_000)
        sp.add_argument("--stats", default=None, help="optional JSON stats output")
        sp.add_argument("--min-abs-rho", type=float, default=0.2,
                        help="minimum |Spearman rho| with TSS density to orient a chromosome")
        sp.add_argument("--min-nnz", type=int, default=10,
                        help="minimum non-zero entries for a bin to be kept in ICE")

    sp_pairs = sub.add_parser("pairs", help="from a HiC-Pro allValidPairs file")
    sp_pairs.add_argument("--pairs", required=True, help="allValidPairs (gz or plain)")
    sp_pairs.add_argument("--min-mapq", type=int, default=None)
    common(sp_pairs)

    sp_mat = sub.add_parser("matrix", help="from HiC-Pro bins bed + sparse matrix")
    sp_mat.add_argument("--bins", required=True, help="HiC-Pro *_abs.bed / bins.bed")
    sp_mat.add_argument("--matrix", required=True, help="HiC-Pro sparse matrix (id1 id2 value)")
    common(sp_mat)
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Command-line entry point; returns the process exit status."""
    args = _build_parser().parse_args(argv)
    chrom_sizes = read_chrom_sizes(args.chrom_sizes)
    if not chrom_sizes:
        print("no autosomes found in --chrom-sizes", file=sys.stderr)
        return 2
    stats: Dict[str, object] = {"bin_size": int(args.bin_size), "command": args.command}
    if args.command == "pairs":
        matrices, pair_stats = bin_valid_pairs(
            args.pairs, chrom_sizes, bin_size=args.bin_size, min_mapq=args.min_mapq)
        stats["pairs"] = pair_stats
        stats["min_mapq"] = args.min_mapq
    else:
        matrices = read_hicpro_matrix(args.bins, args.matrix, chrom_sizes, bin_size=args.bin_size)
    tss = tss_density(args.refseq, chrom_sizes, bin_size=args.bin_size)
    records = compute_pc1(
        matrices, chrom_sizes, tss, bin_size=args.bin_size,
        min_abs_rho=args.min_abs_rho, min_nnz=args.min_nnz, stats=stats)
    stats["n_written"] = write_bedgraph(records, args.out)
    if args.stats:
        with open(args.stats, "w", encoding="utf-8") as fh:
            json.dump(stats, fh, indent=2, sort_keys=True)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
