#!/usr/bin/env python3
"""Registered cross-study concordance test: acute LMNA-depletion lamina change
(GSE300197 LMNB1 CUT&RUN z-score, exposed predictor) versus chronic LMNA R225X
Hi-C compartment change (GSE126459 HOMER 500 kb Active.PC1, untouched outcome).

Two commands:

  predictor  build the per-tile predictor table from the exposed bigWigs and the
             RefSeq annotation (may run before the freeze; its hash is bound).
  run        evaluate the frozen registration against the six PC1 bedGraphs.

All thresholds, permutation counts, seeds and file roles come from the
registration JSON. The code never reads the registration's pass criteria from
the outcome data.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from scipy import stats

TILE = 500_000
AUTOSOMES = [f"chr{i}" for i in range(1, 23)]


# ----------------------------------------------------------------------------
# hashing / io helpers
# ----------------------------------------------------------------------------
def sha256_path(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: str | Path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def dump_json(obj, path: str | Path) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, sort_keys=True)
        fh.write("\n")


# ----------------------------------------------------------------------------
# tiles and interval aggregation
# ----------------------------------------------------------------------------
def tiles_for(chrom_sizes: dict, chroms=AUTOSOMES, tile: int = TILE):
    """Fixed tiles [k*tile, min((k+1)*tile, L)) for each chromosome in order."""
    rows = []
    for c in chroms:
        length = int(chrom_sizes[c])
        for s in range(0, length, tile):
            rows.append((c, s, min(s + tile, length)))
    return rows


def interval_tile_means(starts, ends, vals, tiles):
    """Coverage-weighted mean of piecewise-constant intervals over each tile.

    starts/ends/vals: sorted, non-overlapping half-open intervals on one
    chromosome. tiles: list of (start, end). Returns (means, coverage) where
    coverage is the fraction of tile bases covered by finite values; the mean is
    NaN when nothing finite covers the tile.
    """
    starts = np.asarray(starts, dtype=np.int64)
    ends = np.asarray(ends, dtype=np.int64)
    vals = np.asarray(vals, dtype=np.float64)
    if len(starts) > 1:
        if np.any(np.diff(starts) < 0) or np.any(starts[1:] < ends[:-1]):
            raise ValueError("intervals must be sorted and non-overlapping")
    means = np.full(len(tiles), np.nan)
    cov = np.zeros(len(tiles))
    for i, (s, e) in enumerate(tiles):
        lo = np.searchsorted(ends, s, side="right")
        hi = np.searchsorted(starts, e, side="left")
        if hi <= lo:
            continue
        seg_s = np.maximum(starts[lo:hi], s)
        seg_e = np.minimum(ends[lo:hi], e)
        w = (seg_e - seg_s).astype(np.float64)
        v = vals[lo:hi]
        ok = np.isfinite(v) & (w > 0)
        covered = float(w[ok].sum())
        cov[i] = covered / float(e - s)
        if covered > 0:
            means[i] = float((w[ok] * v[ok]).sum() / covered)
    return means, cov


def bigwig_tile_means(bw_path, tiles, min_coverage: float):
    import pyBigWig  # local import: only needed for real inputs

    bw = pyBigWig.open(str(bw_path))
    try:
        chroms = bw.chroms()
        means = np.full(len(tiles), np.nan)
        cov = np.zeros(len(tiles))
        for c, idxs in _group_by_chrom(tiles).items():
            if c not in chroms:
                continue
            iv = bw.intervals(c) or ()
            if not iv:
                continue
            st = [x[0] for x in iv]
            en = [x[1] for x in iv]
            va = [x[2] for x in iv]
            m, cv = interval_tile_means(st, en, va, [(tiles[i][1], tiles[i][2]) for i in idxs])
            means[idxs] = m
            cov[idxs] = cv
    finally:
        bw.close()
    means[cov < min_coverage] = np.nan
    return means, cov


def read_bedgraph(path):
    """Read a (gzipped) bedGraph into {chrom: (starts, ends, vals)} sorted."""
    opener = gzip.open if str(path).endswith(".gz") else open
    per = {}
    with opener(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip() or line.startswith(("track", "#", "browser")):
                continue
            parts = line.split()
            if len(parts) < 4:
                continue
            c, s, e = parts[0], int(parts[1]), int(parts[2])
            if not c.startswith("chr"):
                c = "chr" + c  # HOMER/HiC-Pro tracks use Ensembl-style names (1..22, X, Y)
            try:
                v = float(parts[3])
            except ValueError:
                v = float("nan")
            per.setdefault(c, []).append((s, e, v))
    out = {}
    for c, rows in per.items():
        rows.sort()
        out[c] = (
            np.array([r[0] for r in rows], dtype=np.int64),
            np.array([r[1] for r in rows], dtype=np.int64),
            np.array([r[2] for r in rows], dtype=np.float64),
        )
    return out


def bedgraph_tile_means(path, tiles, min_coverage: float):
    per = read_bedgraph(path)
    means = np.full(len(tiles), np.nan)
    cov = np.zeros(len(tiles))
    for c, idxs in _group_by_chrom(tiles).items():
        if c not in per:
            continue
        st, en, va = per[c]
        m, cv = interval_tile_means(st, en, va, [(tiles[i][1], tiles[i][2]) for i in idxs])
        means[idxs] = m
        cov[idxs] = cv
    means[cov < min_coverage] = np.nan
    return means, cov


def _group_by_chrom(tiles):
    g = {}
    for i, t in enumerate(tiles):
        g.setdefault(t[0], []).append(i)
    return {c: np.array(v, dtype=np.int64) for c, v in g.items()}


def tss_density(refseq_gz, tiles, chroms=AUTOSOMES, tile: int = TILE):
    """Count unique RefSeq Select TSS positions per tile (UCSC refGene format)."""
    index = {(c, s): i for i, (c, s, _e) in enumerate(tiles)}
    counts = np.zeros(len(tiles))
    seen = set()
    opener = gzip.open if str(refseq_gz).endswith(".gz") else open
    with opener(refseq_gz, "rt", encoding="utf-8") as fh:
        for line in fh:
            p = line.rstrip("\n").split("\t")
            if len(p) < 13:
                continue
            chrom, strand, tx_start, tx_end, symbol = p[2], p[3], int(p[4]), int(p[5]), p[12]
            if chrom not in chroms:
                continue
            tss = tx_start if strand == "+" else tx_end
            key = (symbol, chrom, tss)
            if key in seen:
                continue
            seen.add(key)
            i = index.get((chrom, (tss // tile) * tile))
            if i is not None:
                counts[i] += 1
    return counts


# ----------------------------------------------------------------------------
# statistics
# ----------------------------------------------------------------------------
def rank(a):
    return stats.rankdata(np.asarray(a, dtype=np.float64))


def pearson(x, y):
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    xc = x - x.mean()
    yc = y - y.mean()
    d = np.sqrt((xc * xc).sum() * (yc * yc).sum())
    return float((xc * yc).sum() / d) if d > 0 else float("nan")


def spearman(x, y):
    return pearson(rank(x), rank(y))


def residualise(rank_target, rank_covs):
    """Residuals of rank_target after OLS on [1, rank_covs...]."""
    n = len(rank_target)
    X = np.column_stack([np.ones(n)] + [np.asarray(c, dtype=np.float64) for c in rank_covs])
    beta, *_ = np.linalg.lstsq(X, np.asarray(rank_target, dtype=np.float64), rcond=None)
    return np.asarray(rank_target, dtype=np.float64) - X @ beta


def partial_spearman(x, y, covs):
    """Rank-based partial correlation of x and y given covariates."""
    rc = [rank(c) for c in covs]
    return pearson(residualise(rank(x), rc), residualise(rank(y), rc))


def circular_shift_index(chrom_labels, rng):
    """Permutation index that rolls positions within each chromosome by a random
    non-zero offset. Chromosomes with a single element are left in place."""
    chrom_labels = np.asarray(chrom_labels)
    perm = np.arange(len(chrom_labels))
    for c in np.unique(chrom_labels):
        idx = np.flatnonzero(chrom_labels == c)
        if len(idx) < 2:
            continue
        k = int(rng.integers(1, len(idx)))
        perm[idx] = np.roll(idx, k)
    return perm


def permutation_test(observed_fn, chrom_labels, n_perm: int, seed: int):
    """One-sided (negative direction) circular-shift p-value.

    observed_fn(perm) must return the statistic when the predictor block is
    permuted by index array perm. The identity permutation gives the observed
    statistic.
    """
    n = len(chrom_labels)
    obs = observed_fn(np.arange(n))
    rng = np.random.default_rng(seed)
    null = np.empty(n_perm)
    for i in range(n_perm):
        null[i] = observed_fn(circular_shift_index(chrom_labels, rng))
    p_neg = (1.0 + float(np.sum(null <= obs))) / (1.0 + n_perm)
    p_pos = (1.0 + float(np.sum(null >= obs))) / (1.0 + n_perm)
    return obs, p_neg, p_pos, null


def evaluate_contrast(dlam, base_lam, dpc1, base_pc1, chrom_labels, n_perm, seed):
    """Unadjusted and adjusted Spearman with circular-shift nulls.

    The predictor block (dlam, base_lam) is shifted jointly; the outcome block
    (dpc1, base_pc1) stays fixed.
    """
    r_dlam = rank(dlam)
    r_base_lam = rank(base_lam)
    r_dpc1 = rank(dpc1)
    r_base_pc1 = rank(base_pc1)

    def unadj(perm):
        return pearson(r_dlam[perm], r_dpc1)

    def adj(perm):
        covs = [r_base_pc1, r_base_lam[perm]]
        return pearson(residualise(r_dlam[perm], covs), residualise(r_dpc1, covs))

    u_obs, u_pneg, u_ppos, _ = permutation_test(unadj, chrom_labels, n_perm, seed)
    a_obs, a_pneg, a_ppos, _ = permutation_test(adj, chrom_labels, n_perm, seed + 1)
    return {
        "unadjusted_rho": u_obs,
        "unadjusted_p_negative": u_pneg,
        "unadjusted_p_positive": u_ppos,
        "adjusted_rho": a_obs,
        "adjusted_p_negative": a_pneg,
        "adjusted_p_positive": a_ppos,
    }


def decile_contrast(dlam, dpc1):
    lo_cut, hi_cut = np.quantile(dlam, [0.1, 0.9])
    lo = dpc1[dlam <= lo_cut]
    hi = dpc1[dlam >= hi_cut]
    return {
        "n_bottom_decile": int(len(lo)),
        "n_top_decile": int(len(hi)),
        "mean_dpc1_bottom_decile_dlam": float(lo.mean()),
        "mean_dpc1_top_decile_dlam": float(hi.mean()),
        "top_minus_bottom": float(hi.mean() - lo.mean()),
    }


# ----------------------------------------------------------------------------
# predictor command
# ----------------------------------------------------------------------------
def build_predictor(reg, data_dir: Path, out_dir: Path) -> dict:
    import pyBigWig

    files = reg["predictor"]["files"]
    paths = {k: data_dir / v["name"] for k, v in files.items()}
    hashes = {}
    for k, p in paths.items():
        h = sha256_path(p)
        hashes[k] = h
        if h != files[k]["sha256"]:
            raise SystemExit(f"predictor input {k} hash mismatch: {h} != {files[k]['sha256']}")
    bw = pyBigWig.open(str(paths["siScr_mCh"]))
    chrom_sizes = bw.chroms()
    bw.close()
    tiles = tiles_for(chrom_sizes, reg["tiles"]["chromosomes"], reg["tiles"]["size"])
    mc = reg["tiles"]["min_coverage"]
    cols = {}
    for k in ("siScr_mCh", "siLMNA_mCh", "siScr_DNK", "siLMNA_DNK"):
        cols[k], cols[k + "_cov"] = bigwig_tile_means(paths[k], tiles, mc)
    density = tss_density(paths["refseq"], tiles, reg["tiles"]["chromosomes"], reg["tiles"]["size"])
    out_dir.mkdir(parents=True, exist_ok=True)
    tsv = out_dir / "predictor.tsv"
    with open(tsv, "w", encoding="utf-8") as fh:
        fh.write(
            "tile_id\tchrom\tstart\tend\tsiScr_mCh\tsiLMNA_mCh\tdlam_mCh\tsiScr_DNK\tsiLMNA_DNK\tdlam_DNK\tcov_min\ttss_count\n"
        )
        for i, (c, s, e) in enumerate(tiles):
            cov_min = min(cols["siScr_mCh_cov"][i], cols["siLMNA_mCh_cov"][i], cols["siScr_DNK_cov"][i], cols["siLMNA_DNK_cov"][i])
            dl = cols["siLMNA_mCh"][i] - cols["siScr_mCh"][i]
            dd = cols["siLMNA_DNK"][i] - cols["siScr_DNK"][i]
            fh.write(
                f"{c}:{s}-{e}\t{c}\t{s}\t{e}\t{cols['siScr_mCh'][i]:.6g}\t{cols['siLMNA_mCh'][i]:.6g}\t{dl:.6g}\t"
                f"{cols['siScr_DNK'][i]:.6g}\t{cols['siLMNA_DNK'][i]:.6g}\t{dd:.6g}\t{cov_min:.4f}\t{int(density[i])}\n"
            )
    eligible = int(np.sum(np.isfinite(cols["siLMNA_mCh"] - cols["siScr_mCh"])))
    manifest = {
        "schema": "bio.compartment-predictor.v1",
        "campaign_id": reg["campaign_id"],
        "input_sha256": hashes,
        "n_tiles": len(tiles),
        "n_tiles_predictor_finite": eligible,
        "predictor_tsv_sha256": sha256_path(tsv),
        "numpy": np.__version__,
        "pybigwig": pyBigWig.__version__,
        "python": sys.version.split()[0],
    }
    dump_json(manifest, out_dir / "predictor.manifest.json")
    return manifest


def read_predictor(tsv: Path):
    rows = []
    with open(tsv, encoding="utf-8") as fh:
        header = fh.readline().rstrip("\n").split("\t")
        for line in fh:
            rows.append(line.rstrip("\n").split("\t"))
    col = {h: i for i, h in enumerate(header)}
    def fcol(name):
        return np.array([float(r[col[name]]) for r in rows], dtype=np.float64)
    return {
        "tiles": [(r[col["chrom"]], int(r[col["start"]]), int(r[col["end"]])) for r in rows],
        "chrom": np.array([r[col["chrom"]] for r in rows]),
        "siScr_mCh": fcol("siScr_mCh"),
        "dlam_mCh": fcol("dlam_mCh"),
        "siScr_DNK": fcol("siScr_DNK"),
        "dlam_DNK": fcol("dlam_DNK"),
        "tss_count": fcol("tss_count"),
    }


# ----------------------------------------------------------------------------
# run command
# ----------------------------------------------------------------------------
def orient_tracks(P, chrom, density, corrected_gsms, chromosomes, min_rho_per_chrom, min_tiles_per_chrom=10):
    """Per-chromosome PC1 orientation against TSS density using corrected baselines.

    Returns (P_oriented, keep_mask, per_chrom, flipped, excluded). Input arrays
    are not mutated.
    """
    P = {g: np.array(v, dtype=np.float64, copy=True) for g, v in P.items()}
    base_all = np.mean([P[g] for g in corrected_gsms], axis=0)
    per_chrom, flipped, excluded = {}, [], []
    keep = np.ones(len(chrom), dtype=bool)
    for c in chromosomes:
        idx = np.flatnonzero(chrom == c)
        if len(idx) < min_tiles_per_chrom:
            if len(idx):
                excluded.append(c)
                keep[idx] = False
            per_chrom[c] = {"n": int(len(idx)), "rho": None, "flipped": False, "excluded": True}
            continue
        r = spearman(density[idx], base_all[idx])
        f = bool(r < 0)
        if f:
            for g in P:
                P[g][idx] = -P[g][idx]
            base_all[idx] = -base_all[idx]
            r = -r
            flipped.append(c)
        ex = bool(r < min_rho_per_chrom)
        if ex:
            excluded.append(c)
            keep[idx] = False
        per_chrom[c] = {"n": int(len(idx)), "rho": float(r), "flipped": f, "excluded": ex}
    return P, keep, per_chrom, flipped, excluded


def standardise_per_chromosome(P, chrom):
    """Return tracks centred and scaled to unit SD within each chromosome (scale-artefact sensitivity)."""
    out = {}
    for g, v in P.items():
        z = np.array(v, dtype=np.float64, copy=True)
        for c in np.unique(chrom):
            idx = np.flatnonzero(chrom == c)
            sd = z[idx].std()
            z[idx] = (z[idx] - z[idx].mean()) / sd if sd > 0 else 0.0
        out[g] = z
    return out


def scale_diagnostic(P, chrom, mut, corrected):
    """Per-chromosome SD(mean mutant PC1) / SD(mean corrected PC1) for each clone."""
    mut_mean = np.mean([P[g] for g in mut], axis=0)
    out = {}
    for cname, reps in corrected.items():
        base = np.mean([P[g] for g in reps], axis=0)
        ratios = {}
        for c in np.unique(chrom):
            idx = np.flatnonzero(chrom == c)
            sd_b = base[idx].std()
            ratios[str(c)] = float(mut_mean[idx].std() / sd_b) if sd_b > 0 else None
        vals = [v for v in ratios.values() if v is not None]
        out[cname] = {"per_chromosome": ratios, "genome_sd_ratio": float(mut_mean.std() / base.std()), "median_chromosome_sd_ratio": float(np.median(vals)) if vals else None}
    return out


def clone_contrast(P, dlam, base_lam, dlam_dnk, chrom, mut, reps, n_perm, seed, thr, with_secondary=True):
    mut_mean = np.mean([P[g] for g in mut], axis=0)
    base_c = np.mean([P[g] for g in reps], axis=0)
    dpc1 = mut_mean - base_c
    res = evaluate_contrast(dlam, base_lam, dpc1, base_c, chrom, n_perm, seed)
    pairs = {}
    for mg, cg in zip(mut, reps):
        pairs[f"{mg}-{cg}"] = spearman(dlam, P[mg] - P[cg])
    res["replicate_pair_rho"] = pairs
    res["replicate_pairs_all_negative"] = bool(all(v < 0 for v in pairs.values()))
    if with_secondary:
        a_mask = base_c > 0
        b_mask = base_c < 0
        dk = np.isfinite(dlam_dnk)
        res["secondary"] = {
            "stratum_A_baseline": {"n": int(a_mask.sum()), "unadjusted_rho": spearman(dlam[a_mask], dpc1[a_mask]) if a_mask.sum() > 10 else None},
            "stratum_B_baseline": {"n": int(b_mask.sum()), "unadjusted_rho": spearman(dlam[b_mask], dpc1[b_mask]) if b_mask.sum() > 10 else None},
            "dnk_arm_unadjusted_rho": spearman(dlam_dnk[dk], dpc1[dk]) if dk.sum() > 10 else None,
            "decile_contrast": decile_contrast(dlam, dpc1),
            "baseline_pc1_vs_baseline_lamina_rho": spearman(base_lam, base_c),
        }
    return res


def run_registered(reg, predictor_tsv: Path, outcome_dir: Path, out_dir: Path, registration_sha256: str, freeze_sha256: str | None, intake_hashes: dict | None = None, allow_unfrozen: bool = False):
    """Evaluate the registered test. Refuses to run without a freeze receipt unless
    allow_unfrozen=True is passed explicitly (synthetic tests only); such runs are
    labelled in summary.json and cannot be mistaken for registered outcomes."""
    if freeze_sha256 is None and not allow_unfrozen:
        raise SystemExit("refusing to run without a freeze receipt (pass --freeze and --intake)")
    pred = read_predictor(predictor_tsv)
    tiles = pred["tiles"]
    mc = reg["tiles"]["min_coverage"]
    samples = reg["outcome"]["samples"]
    pc1 = {}
    outcome_hashes = {}
    for gsm, meta in samples.items():
        p = outcome_dir / meta["filename"]
        h = sha256_path(p)
        if intake_hashes is not None and intake_hashes.get(meta["filename"]) != h:
            raise SystemExit(f"outcome file {meta['filename']} hash {h} does not match the intake receipt")
        outcome_hashes[gsm] = h
        pc1[gsm], _cov = bedgraph_tile_means(p, tiles, mc)

    def line_reps(line):
        return sorted([g for g, m in samples.items() if m["line"] == line], key=lambda g: samples[g]["replicate"])

    mut = line_reps("mutant")
    corrected = {c: line_reps(c) for c in reg["outcome"]["corrected_lines"]}
    all_corrected = [g for c in corrected.values() for g in c]

    finite = np.isfinite(pred["dlam_mCh"]) & np.isfinite(pred["siScr_mCh"])
    for g in samples:
        finite &= np.isfinite(pc1[g])
    chrom0 = pred["chrom"][finite]
    dlam0 = pred["dlam_mCh"][finite]
    base_lam0 = pred["siScr_mCh"][finite]
    dlam_dnk0 = pred["dlam_DNK"][finite]
    density0 = pred["tss_count"][finite]
    P0 = {g: pc1[g][finite] for g in samples}
    ids0 = [f"{c}:{s}-{e}" for (c, s, e), f in zip(tiles, finite) if f]

    chromosomes = reg["tiles"]["chromosomes"]
    min_chrom = float(reg["orientation"]["min_rho_per_chromosome"])
    floors = reg["orientation"]["floor_sensitivity"]
    P1, keep, per_chrom, flipped_chroms, excluded_chroms = orient_tracks(P0, chrom0, density0, all_corrected, chromosomes, min_chrom)
    chrom, dlam, base_lam, dlam_dnk, density = (a[keep] for a in (chrom0, dlam0, base_lam0, dlam_dnk0, density0))
    P = {g: v[keep] for g, v in P1.items()}
    ids = [i for i, k in zip(ids0, keep) if k]
    n_elig = int(keep.sum())
    base_all = np.mean([P[g] for g in all_corrected], axis=0)
    orient_rho = spearman(density, base_all)
    orientation_ok = bool(orient_rho >= reg["orientation"]["min_abs_rho_gene_density"])

    n_perm = int(reg["null"]["permutations"])
    seed = int(reg["null"]["seed"])
    thr = reg["pass_criteria"]
    ratio_min = float(thr["adjusted_to_unadjusted_ratio_min"])
    std_rho_max = float(thr["standardised_unadjusted_rho_max"])

    scale = scale_diagnostic(P, chrom, mut, corrected)
    P_std = standardise_per_chromosome(P, chrom)

    contrasts = {}
    for cname, reps in corrected.items():
        res = clone_contrast(P, dlam, base_lam, dlam_dnk, chrom, mut, reps, n_perm, seed, thr)
        std = clone_contrast(P_std, dlam, base_lam, dlam_dnk, chrom, mut, reps, n_perm, seed + 2, thr, with_secondary=False)
        res["standardised"] = {k: std[k] for k in ("unadjusted_rho", "unadjusted_p_negative", "unadjusted_p_positive", "adjusted_rho", "adjusted_p_negative", "adjusted_p_positive", "replicate_pairs_all_negative")}
        u, a = res["unadjusted_rho"], res["adjusted_rho"]
        res["component_pass"] = {
            "unadjusted_effect": bool(u <= thr["unadjusted_rho_max"]),
            "unadjusted_p": bool(res["unadjusted_p_negative"] <= thr["p_max"]),
            "adjusted_effect": bool(a <= thr["adjusted_rho_max"]),
            "adjusted_p": bool(res["adjusted_p_negative"] <= thr["p_max"]),
            "adjusted_to_unadjusted_ratio": bool(a < 0 and u < 0 and abs(a) >= ratio_min * abs(u)),
            "standardised_effect": bool(std["unadjusted_rho"] <= std_rho_max),
            "standardised_p": bool(std["unadjusted_p_negative"] <= thr["p_max"]),
            "replicate_pairs": res["replicate_pairs_all_negative"],
        }
        res["clone_pass"] = bool(all(res["component_pass"].values()))
        contrasts[cname] = res

    # Orientation-floor sensitivity (reported only; no permutation p-values)
    sensitivity = {}
    for floor in floors:
        Pf, keepf, _pc, _fl, exf = orient_tracks(P0, chrom0, density0, all_corrected, chromosomes, float(floor))
        Pf = {g: v[keepf] for g, v in Pf.items()}
        ch_f = chrom0[keepf]
        d_f, bl_f, dk_f = dlam0[keepf], base_lam0[keepf], dlam_dnk0[keepf]
        entry = {"n_tiles": int(keepf.sum()), "excluded_chromosomes": exf, "clones": {}}
        for cname, reps in corrected.items():
            mm = np.mean([Pf[g] for g in mut], axis=0)
            bc = np.mean([Pf[g] for g in reps], axis=0)
            entry["clones"][cname] = {"unadjusted_rho": spearman(d_f, mm - bc), "adjusted_rho": partial_spearman(d_f, mm - bc, [bc, bl_f])}
        sensitivity[str(floor)] = entry

    passed = bool(orientation_ok and n_elig >= thr["min_eligible_tiles"] and all(r["clone_pass"] for r in contrasts.values()))
    opposite = bool(orientation_ok and all(r["unadjusted_p_positive"] <= thr["p_max"] and r["unadjusted_rho"] >= -thr["unadjusted_rho_max"] for r in contrasts.values()))

    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "tiles.tsv", "w", encoding="utf-8") as fh:
        cols = ["tile_id", "chrom", "dlam_mCh", "siScr_mCh", "dlam_DNK", "tss_count"] + [f"pc1_{g}" for g in samples]
        fh.write("\t".join(cols) + "\n")
        for i in range(n_elig):
            row = [ids[i], chrom[i], f"{dlam[i]:.6g}", f"{base_lam[i]:.6g}", f"{dlam_dnk[i]:.6g}", f"{int(density[i])}"] + [f"{P[g][i]:.6g}" for g in samples]
            fh.write("\t".join(row) + "\n")

    summary = {
        "schema": "bio.compartment-concordance-result.v2",
        "campaign_id": reg["campaign_id"],
        "registered_run": freeze_sha256 is not None,
        "unfrozen_synthetic_run": freeze_sha256 is None,
        "registration_sha256": registration_sha256,
        "freeze_sha256": freeze_sha256,
        "code_sha256": sha256_path(Path(__file__)),
        "predictor_tsv_sha256": sha256_path(predictor_tsv),
        "outcome_sha256": outcome_hashes,
        "outcome_hashes_verified_against_intake": intake_hashes is not None,
        "n_tiles_total": len(tiles),
        "n_tiles_eligible": n_elig,
        "orientation": {
            "gene_density_rho_after_orientation": orient_rho,
            "flipped": bool(flipped_chroms),
            "flipped_chromosomes": flipped_chroms,
            "excluded_chromosomes": excluded_chroms,
            "per_chromosome": per_chrom,
            "ok": orientation_ok,
        },
        "scale_diagnostic": scale,
        "orientation_floor_sensitivity": sensitivity,
        "contrasts": contrasts,
        "registered_pass": passed,
        "registered_opposite_direction": opposite,
        "numpy": np.__version__,
        "scipy": __import__("scipy").__version__,
        "python": sys.version.split()[0],
    }
    dump_json(summary, out_dir / "summary.json")
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("predictor")
    p1.add_argument("--registration", required=True)
    p1.add_argument("--data-dir", required=True)
    p1.add_argument("--out-dir", required=True)
    p2 = sub.add_parser("run")
    p2.add_argument("--registration", required=True)
    p2.add_argument("--freeze", required=True)
    p2.add_argument("--intake", required=True)
    p2.add_argument("--predictor", required=True)
    p2.add_argument("--outcome-dir", required=True)
    p2.add_argument("--out-dir", required=True)
    a = ap.parse_args(argv)
    reg = load_json(a.registration)
    if a.cmd == "predictor":
        m = build_predictor(reg, Path(a.data_dir), Path(a.out_dir))
        print(json.dumps(m, indent=2))
        return 0
    here = Path(__file__).resolve().parent
    reg_sha = sha256_path(a.registration)
    fz = load_json(a.freeze)
    checks = {
        "registration_sha256": reg_sha,
        "code_sha256": sha256_path(Path(__file__)),
        "test_sha256": sha256_path(here / "test_compartment.py"),
        "requirements_lock_sha256": sha256_path(here / "requirements.lock"),
        "predictor_tsv_sha256": sha256_path(a.predictor),
    }
    for k, v in checks.items():
        if fz.get(k) != v:
            raise SystemExit(f"{k} does not match the freeze receipt")
    freeze_sha = sha256_path(a.freeze)
    intake = load_json(a.intake)
    if intake.get("freeze_sha256") != freeze_sha:
        raise SystemExit("intake receipt does not bind this freeze receipt")
    intake_hashes = {f["filename"]: f["sha256"] for f in intake["files"]}
    s = run_registered(reg, Path(a.predictor), Path(a.outcome_dir), Path(a.out_dir), reg_sha, freeze_sha, intake_hashes)
    print(json.dumps({k: s[k] for k in ("n_tiles_eligible", "registered_pass", "registered_opposite_direction")}, indent=2))
    print(json.dumps({k: s["orientation"][k] for k in ("gene_density_rho_after_orientation", "flipped_chromosomes", "excluded_chromosomes", "ok")}, indent=2))
    for c, r in s["contrasts"].items():
        print(c, json.dumps({k: r[k] for k in ("unadjusted_rho", "unadjusted_p_negative", "adjusted_rho", "adjusted_p_negative", "replicate_pairs_all_negative", "clone_pass")}))
        print(c, "standardised", json.dumps(r["standardised"]))
        print(c, "components", json.dumps(r["component_pass"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
