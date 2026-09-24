#!/usr/bin/env python3
"""Frozen, descriptive GSE300197 analysis. No network or external-study access."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import platform
from pathlib import Path
from typing import Any

import numpy as np
import pyBigWig
import scipy
from scipy.stats import rankdata

REGISTRATION_SHA = "201e24b9870349bd5a2234fd40f52dbfd7a618fb37b700feb0eb474c0b128efa"
MANIFEST_SHA = "0eb7d5c82a3f0419ea7cac24e59119c89ef173cf8c45eafc6329b2c12cdbc775"
LOCK_SHA = "b3b8f376548d81e1ab9f8a430112e1e84f13ac7de0cc064dac2340e44c2b0865"
SEED = 20260924
TRACKS = ("siScr.mCh", "siLMNA.mCh", "siScr.DNK", "siLMNA.DNK")
INPUTS = ("GSE300197_RNA.counts.txt.gz", "hg38-ncbiRefSeqSelect.txt.gz") + tuple(
    f"GSE300197_{name}.CR.zscore.bw" for name in TRACKS
)
AUTOSOMES = tuple(f"chr{i}" for i in range(1, 23))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): safe_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [safe_json(v) for v in value]
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_json(path: Path, value: Any) -> None:
    with path.open("x") as handle:
        json.dump(safe_json(value), handle, indent=2, allow_nan=False, sort_keys=True)
        handle.write("\n")


def write_tsv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    if fields is None:
        fields = sorted({key for row in rows for key in row})
    with path.open("x", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            clean = safe_json(row)
            writer.writerow({k: "" if clean.get(k) is None else clean[k] for k in fields})


def validate_inputs(data: Path, manifest_path: Path) -> dict[str, Any]:
    if sha256(manifest_path) != MANIFEST_SHA:
        raise ValueError("input manifest differs from frozen discovery manifest")
    manifest = json.loads(manifest_path.read_text())
    entries = {item["path"]: item for item in manifest["files"]}
    if set(entries) != set(INPUTS) or len(manifest["files"]) != len(INPUTS):
        raise ValueError("unexpected or duplicate discovery input set")
    for name, item in entries.items():
        path = data / name
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"not a regular admitted input: {name}")
        if path.stat().st_size != item["bytes"] or sha256(path) != item["sha256"]:
            raise ValueError(f"input hash or length mismatch: {name}")
    return manifest


def read_counts(path: Path, expected_columns: list[str]) -> tuple[list[str], np.ndarray]:
    symbols: list[str] = []
    counts: list[list[int]] = []
    seen: set[str] = set()
    with gzip.open(path, "rt", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        header = next(reader)
        # R write.table may leave the row-name header empty or omit it entirely.
        if header == expected_columns:
            pass
        elif len(header) == len(expected_columns) + 1 and header[1:] == expected_columns:
            pass
        else:
            raise ValueError(f"unexpected RNA column order: {header}")
        for row in reader:
            if len(row) != len(expected_columns) + 1:
                raise ValueError("RNA row width mismatch")
            symbol = row[0]
            if not symbol or symbol in seen:
                raise ValueError("empty or duplicated RNA symbol")
            if any(not cell.isdigit() for cell in row[1:]):
                raise ValueError("RNA values must be nonnegative integer counts")
            values = [int(cell) for cell in row[1:]]
            if max(values) > 10**12:
                raise ValueError("RNA count exceeds admitted arithmetic range")
            seen.add(symbol)
            symbols.append(symbol)
            counts.append(values)
            if len(counts) > 200_000:
                raise ValueError("RNA row limit exceeded")
    if not counts:
        raise ValueError("empty RNA matrix")
    result = np.asarray(counts, dtype=np.int64)
    totals = result.sum(axis=0)
    if np.any(totals <= 0) or np.any(totals > 2**53):
        raise ValueError("invalid or imprecise library total")
    return symbols, result


def contrast(log_values: np.ndarray, n_control: int) -> np.ndarray:
    return log_values[:, n_control:].mean(axis=1) - log_values[:, :n_control].mean(axis=1)


def normalize_rna(counts: np.ndarray, n_control: int) -> dict[str, Any]:
    counts = np.asarray(counts, dtype=np.float64)
    if counts.ndim != 2 or not 1 < n_control < counts.shape[1] - 1:
        raise ValueError("need at least two columns per condition")
    if not np.all(np.isfinite(counts)) or np.any(counts < 0) or np.any(counts != np.floor(counts)):
        raise ValueError("RNA values must be finite nonnegative integers")
    totals = counts.sum(axis=0)
    if np.any(totals <= 0):
        raise ValueError("zero library total")
    cpm = counts / totals * 1_000_000
    log_cpm = np.log2(cpm + 0.5)
    primary = contrast(log_cpm, n_control)
    loo = []
    for omitted in range(counts.shape[1]):
        control = [i for i in range(n_control) if i != omitted]
        case = [i for i in range(n_control, counts.shape[1]) if i != omitted]
        loo.append(log_cpm[:, case].mean(axis=1) - log_cpm[:, control].mean(axis=1))
    positive = np.all(counts > 0, axis=1)
    if not np.any(positive):
        raise ValueError("median-ratio sensitivity has no all-positive genes")
    log_counts = np.log(counts[positive])
    ratios = np.exp(log_counts - log_counts.mean(axis=1, keepdims=True))
    size_factors = np.median(ratios, axis=0)
    size_factors /= np.exp(np.log(size_factors).mean())
    median_cpm = (counts / size_factors) / totals.mean() * 1_000_000
    return {
        "totals": totals, "cpm": cpm, "log_cpm": log_cpm,
        "primary": primary, "loo": np.asarray(loo).T,
        "median_ratio": contrast(np.log2(median_cpm + 0.5), n_control),
        "size_factors": size_factors, "size_factor_genes": int(positive.sum()),
        "control_mean_cpm": cpm[:, :n_control].mean(axis=1),
        "expressed": (np.sum(cpm[:, :n_control] >= 1, axis=1) >= 2)
        & (cpm[:, :n_control].mean(axis=1) >= 1),
    }


def annotation_tss(strand: str, start: int, end: int) -> int:
    if strand not in ("+", "-") or not 0 <= start < end:
        raise ValueError("invalid transcript coordinates")
    return start if strand == "+" else end - 1


def read_annotation(path: Path) -> tuple[dict[str, dict[str, Any]], set[str]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    with gzip.open(path, "rt") as handle:
        for line in handle:
            row = line.rstrip("\n").split("\t")
            if len(row) != 16:
                raise ValueError("RefSeq Select schema mismatch")
            if row[2] not in AUTOSOMES:
                continue
            start, end = int(row[4]), int(row[5])
            gene = {"symbol": row[12], "transcript": row[1], "chromosome": row[2],
                    "strand": row[3], "tx_start": start, "tx_end": end,
                    "tss": annotation_tss(row[3], start, end), "transcript_span": end - start}
            groups.setdefault(row[12], []).append(gene)
    ambiguous = {symbol for symbol, genes in groups.items() if len(genes) != 1}
    unique = {symbol: genes[0] for symbol, genes in groups.items() if len(genes) == 1}
    for chromosome in AUTOSOMES:
        genes = [gene for gene in unique.values() if gene["chromosome"] == chromosome]
        positions = np.sort(np.asarray([gene["tss"] for gene in genes], dtype=np.int64))
        for gene in genes:
            # Inclusive +/-1 Mb neighbourhood, including the gene's own TSS.
            gene["tss_count_1mb"] = int(np.searchsorted(positions, gene["tss"] + 1_000_000, "right")
                                      - np.searchsorted(positions, gene["tss"] - 1_000_000, "left"))
    return unique, ambiguous


class CommonTrackSegments:
    """Interval integrals over exactly the same finite bases in every track."""

    def __init__(self, tracks: list[list[tuple[int, int, float]]], chromosome_length: int):
        if chromosome_length <= 0:
            raise ValueError("invalid chromosome length")
        self.length = chromosome_length
        arrays = [np.asarray(track, dtype=np.float64).reshape(-1, 3) for track in tracks]
        for intervals in arrays:
            if len(intervals) and (np.any(intervals[:, 0] < 0)
                                  or np.any(intervals[:, 1] > chromosome_length)
                                  or np.any(intervals[:, 1] <= intervals[:, 0])
                                  or np.any(intervals[1:, 0] < intervals[:-1, 1])):
                raise ValueError("invalid or overlapping source intervals")
        endpoints = [np.asarray([0, chromosome_length], dtype=np.int64)]
        endpoints.extend(array[:, :2].astype(np.int64).ravel() for array in arrays)
        self.edges = np.unique(np.concatenate(endpoints))
        starts, ends = self.edges[:-1], self.edges[1:]
        values = np.zeros((len(starts), len(tracks)), dtype=np.float64)
        valid = np.ones(len(starts), dtype=bool)
        for column, intervals in enumerate(arrays):
            if not len(intervals):
                valid[:] = False
                continue
            index = np.searchsorted(intervals[:, 0], starts, side="right") - 1
            safe = np.maximum(index, 0)
            covered = (index >= 0) & (intervals[safe, 1] >= ends) & np.isfinite(intervals[safe, 2])
            valid &= covered
            values[:, column] = np.where(covered, intervals[safe, 2], 0)
        self.rates = np.column_stack([valid.astype(float), np.where(valid[:, None], values, 0)])
        areas = self.rates * (ends - starts)[:, None]
        self.prefix = np.vstack([np.zeros((1, self.rates.shape[1])), np.cumsum(areas, axis=0)])

    def integral(self, coordinate: int) -> np.ndarray:
        if not 0 <= coordinate <= self.length:
            raise ValueError("coordinate outside chromosome")
        if coordinate == self.length:
            return self.prefix[-1]
        index = int(np.searchsorted(self.edges, coordinate, side="right") - 1)
        return self.prefix[index] + self.rates[index] * (coordinate - self.edges[index])

    def window(self, tss: int, half_width: int) -> dict[str, Any]:
        if not 0 <= tss < self.length or half_width <= 0:
            raise ValueError("invalid TSS window")
        start, end = max(0, tss - half_width), min(self.length, tss + half_width)
        totals = self.integral(end) - self.integral(start)
        covered = float(totals[0])
        return {"start": start, "end": end, "covered_bases": covered,
                "coverage": covered / (end - start),
                "means": totals[1:] / covered if covered > 0 else np.full(self.rates.shape[1] - 1, np.nan)}


def profile_fields(profile: dict[str, Any], half_width: int) -> dict[str, Any]:
    prefix = f"h{half_width}_"
    values = {prefix + key: profile[key] for key in ("start", "end", "coverage", "covered_bases")}
    valid = profile["coverage"] >= 0.9
    means = profile["means"] if valid else np.full(4, np.nan)
    values[prefix + "status"] = "evaluable" if valid else "insufficient_common_coverage"
    values.update({prefix + name: float(means[i]) for i, name in enumerate(TRACKS)})
    gain, residual = means[1] - means[0], means[3] - means[2]
    values.update({prefix + "gain": gain, prefix + "dnk_residual": residual,
                   prefix + "dnk_interaction": residual - gain,
                   prefix + "dnk_control_main": means[2] - means[0],
                   prefix + "dnk_case_main": means[3] - means[1]})
    return values


def select_candidates(rows: list[dict[str, Any]], exclusions: set[str], maximum: int = 10,
                      spacing: int = 500_000) -> list[dict[str, Any]]:
    pool = []
    for row in rows:
        if not row.get("signal_screen", False):
            continue
        reasons = []
        if row["symbol"] in exclusions:
            reasons.append("known_result_excluded_from_novelty")
        if row["rna_contrast_cpm"] > -0.5:
            reasons.append("rna_threshold")
        if not row["loo_all_negative"]:
            reasons.append("leave_one_column_out_direction")
        if not row["h50000_dnk_interaction"] < 0:
            reasons.append("dnk_descriptive_interaction")
        row["candidate_filter_failures"] = ";".join(reasons)
        row["candidate_qualified_before_spacing"] = not reasons
        if not reasons:
            pool.append(row)
    pool.sort(key=lambda row: (row["rna_contrast_cpm"], -row["h50000_gain"], row["symbol"]))
    selected = []
    for row in pool:
        if any(row["chromosome"] == prior["chromosome"] and abs(row["tss"] - prior["tss"]) < spacing
               for prior in selected):
            row["candidate_selection_status"] = "excluded_spacing"
            continue
        if len(selected) == maximum:
            row["candidate_selection_status"] = "beyond_maximum"
            continue
        row["candidate_selection_status"] = "selected"
        row["candidate_rank"] = len(selected) + 1
        selected.append(row)
    return selected


def spearman(x: np.ndarray, y: np.ndarray) -> float:
    if len(x) < 2:
        return float("nan")
    left, right = rankdata(x), rankdata(y)
    left -= left.mean()
    right -= right.mean()
    denominator = np.linalg.norm(left) * np.linalg.norm(right)
    return float(np.dot(left, right) / denominator) if denominator else float("nan")


def association_statistics(rows: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    eligible = [row for row in rows if row.get("eligible", False)]
    baseline = [row for row in eligible if row["baseline_eligible"]]
    features = ("baseline_log2_mean_cpm", "log10_transcript_span", "baseline_lmnb1", "log1p_tss_count_1mb")
    feature_matrix = np.asarray([[np.log2(row["control_mean_cpm"] + 0.5), np.log10(row["transcript_span"]),
                                 row["h50000_siScr.mCh"], np.log1p(row["tss_count_1mb"])]
                                for row in baseline], dtype=float).reshape(-1, 4)
    means = feature_matrix.mean(axis=0) if len(baseline) else np.zeros(4)
    scales = feature_matrix.std(axis=0, ddof=0) if len(baseline) else np.zeros(4)
    z = (feature_matrix - means) / np.where(scales > 0, scales, 1)
    z[:, scales == 0] = 0
    matching = []
    anchors = []
    balance = []
    nonscreen = np.asarray([not row["signal_screen"] for row in baseline], dtype=bool)
    for index, anchor in enumerate(baseline):
        if not anchor["signal_screen"]:
            continue
        pool = [j for j, row in enumerate(baseline) if nonscreen[j]
                and row["chromosome"] == anchor["chromosome"] and abs(row["tss"] - anchor["tss"]) > 1_000_000]
        if len(pool) < 5:
            matching.append({"anchor": anchor["symbol"], "status": "fewer_than_five_controls", "available_controls": len(pool)})
            continue
        ranked = sorted(pool, key=lambda j: (float(np.sum((z[j] - z[index]) ** 2)), baseline[j]["symbol"]))[:5]
        control_rows = [baseline[j] for j in ranked]
        delta = anchor["rna_contrast_cpm"] - np.mean([row["rna_contrast_cpm"] for row in control_rows])
        difference = z[index] - z[ranked].mean(axis=0)
        match = {"anchor": anchor["symbol"], "status": "matched", "chromosome": anchor["chromosome"],
                 "tss": anchor["tss"], "anchor_rna_contrast": anchor["rna_contrast_cpm"],
                 "control_mean_rna_contrast": anchor["rna_contrast_cpm"] - delta, "matched_difference": delta,
                 "controls": ";".join(row["symbol"] for row in control_rows),
                 "maximum_squared_distance": float(np.sum((z[ranked[-1]] - z[index]) ** 2))}
        match.update({"balance_" + name: float(difference[i]) for i, name in enumerate(features)})
        matching.append(match)
        anchors.append(match)
        balance.append(difference)
    class_stats: dict[str, Any] = {"matched_anchors": len(anchors), "excluded_anchors": len(matching) - len(anchors),
                                  "feature_names": features, "feature_means": means, "feature_population_sd": scales}
    if anchors:
        effects = np.asarray([item["matched_difference"] for item in anchors])
        blocks: dict[tuple[str, int], list[float]] = {}
        for item in anchors:
            blocks.setdefault((item["chromosome"], item["tss"] // 1_000_000), []).append(item["matched_difference"])
        keys = sorted(blocks)
        block_sum = np.asarray([sum(blocks[key]) for key in keys])
        block_n = np.asarray([len(blocks[key]) for key in keys])
        rng = np.random.default_rng(SEED)
        bootstrap = []
        for _ in range(2000):
            sampled = rng.integers(0, len(keys), len(keys))
            bootstrap.append(float(block_sum[sampled].sum() / block_n[sampled].sum()))
        chromosomes = sorted({item["chromosome"] for item in anchors}, key=lambda name: int(name[3:]))
        loo = {}
        for chromosome in chromosomes:
            values = [item["matched_difference"] for item in anchors if item["chromosome"] != chromosome]
            loo[chromosome] = float(np.mean(values)) if values else None
        class_stats.update({"mean_difference": float(effects.mean()), "anchor_blocks": len(keys),
                            "spatial_bootstrap_95_percentile": np.quantile(bootstrap, [0.025, 0.975], method="linear"),
                            "bootstrap_seed": SEED, "bootstrap_draws": 2000,
                            "mean_standardized_covariate_difference": np.asarray(balance).mean(axis=0),
                            "leave_one_chromosome_out": loo,
                            "distinct_control_genes": len({gene for item in anchors for gene in item["controls"].split(";")}),
                            "interpretation": "Descriptive anchor-block interval only; shared/distant controls and spatial dependence preclude biological CI."})
    else:
        class_stats["status"] = "no_evaluable_matched_anchors"
    full_correlation = spearman(np.asarray([r["h50000_gain"] for r in eligible]),
                                np.asarray([r["rna_contrast_cpm"] for r in eligible]))
    by_chromosome = {chrom: sorted([row for row in eligible if row["chromosome"] == chrom],
                                  key=lambda row: (row["tss"], row["symbol"])) for chrom in AUTOSOMES}
    omitted = {chrom: len(values) for chrom, values in by_chromosome.items() if len(values) < 41}
    groups = [values for values in by_chromosome.values() if len(values) >= 41]
    subset = [row for group in groups for row in group]
    x = np.asarray([row["h50000_gain"] for row in subset])
    y = np.asarray([row["rna_contrast_cpm"] for row in subset])
    observed = spearman(x, y)
    circular: dict[str, Any] = {"full_universe_spearman": full_correlation,
                               "null_subset_observed_spearman": observed,
                               "null_subset_genes": len(subset), "omitted_chromosomes_gene_counts": omitted}
    null_rows = []
    if np.isfinite(observed):
        xr = rankdata(x)
        yr = rankdata(y)
        xr -= xr.mean()
        yr -= yr.mean()
        denominator = np.linalg.norm(xr) * np.linalg.norm(yr)
        starts = np.cumsum([0] + [len(group) for group in groups])
        rng = np.random.default_rng(SEED)
        for draw in range(1999):
            shifted = np.empty_like(yr)
            for start, end in zip(starts[:-1], starts[1:]):
                offset = int(rng.integers(20, end - start - 20 + 1))
                shifted[start:end] = np.roll(yr[start:end], offset)
            null_rows.append({"draw": draw + 1, "spearman": float(np.dot(xr, shifted) / denominator)})
        values = np.asarray([item["spearman"] for item in null_rows])
        circular.update({"draws": 1999, "seed": SEED,
                         "lower_tail": float((1 + np.sum(values <= observed)) / 2000),
                         "null_2_5_50_97_5_percentiles": np.quantile(values, [0.025, 0.5, 0.975], method="linear"),
                         "interpretation": "Gene-order circular diagnostic, not exact-distance preservation, biological or locus significance."})
    else:
        circular["status"] = "undefined_correlation_or_no_eligible_chromosomes"
    return {"matched_class": class_stats, "continuous_spatial_null": circular}, matching, null_rows


def run(data: Path, out: Path, registration_path: Path, manifest_path: Path) -> dict[str, Any]:
    if sha256(registration_path) != REGISTRATION_SHA:
        raise ValueError("registration differs from the reviewed frozen campaign")
    registration = json.loads(registration_path.read_text())
    if not registration["status"].startswith("frozen_"):
        raise ValueError("cannot execute a draft registration")
    lock_path = Path(__file__).with_name("requirements.lock")
    if sha256(lock_path) != LOCK_SHA:
        raise ValueError("dependency lock differs from frozen toolchain")
    if (np.__version__, scipy.__version__, pyBigWig.__version__) != ("2.3.3", "1.16.2", "0.3.24"):
        raise ValueError("installed scientific dependencies do not match locked versions")
    manifest = validate_inputs(data, manifest_path)
    out.mkdir(parents=True, exist_ok=False)
    write_json(out / "intent.json", {"campaign_id": registration["campaign_id"],
                                    "registration_sha256": REGISTRATION_SHA, "inputs_manifest_sha256": MANIFEST_SHA,
                                    "analysis_sha256": sha256(Path(__file__)), "requirements_lock_sha256": LOCK_SHA,
                                    "inputs": manifest, "python": platform.python_version(),
                                    "numpy": np.__version__, "scipy": scipy.__version__, "pybigwig": pyBigWig.__version__})
    columns = registration["discovery"]["rna_columns"]["control"] + registration["discovery"]["rna_columns"]["case"]
    symbols, counts = read_counts(data / INPUTS[0], columns)
    rna = normalize_rna(counts, 3)
    annotation, ambiguous = read_annotation(data / INPUTS[1])
    rows: list[dict[str, Any]] = []
    for i, symbol in enumerate(symbols):
        row: dict[str, Any] = {"symbol": symbol, "control_mean_cpm": float(rna["control_mean_cpm"][i]),
                              "rna_contrast_cpm": float(rna["primary"][i]),
                              "rna_contrast_median_ratio": float(rna["median_ratio"][i]),
                              "loo_all_negative": bool(np.all(rna["loo"][i] < 0)),
                              "loo_min": float(rna["loo"][i].min()), "loo_max": float(rna["loo"][i].max()),
                              "expression_eligible": bool(rna["expressed"][i]), "eligible": False,
                              "baseline_eligible": False, "signal_screen": False,
                              "candidate_qualified_before_spacing": False, "candidate_selection_status": "not_qualified"}
        for j, column in enumerate(columns):
            row["count_" + column] = int(counts[i, j])
            row["cpm_" + column] = float(rna["cpm"][i, j])
            row["loo_without_" + column] = float(rna["loo"][i, j])
        if symbol in ambiguous:
            row["annotation_status"] = "ambiguous_excluded"
        elif symbol not in annotation:
            row["annotation_status"] = "no_unique_autosomal_match"
        else:
            row.update(annotation[symbol])
            row["annotation_status"] = "unique_autosomal_match"
        rows.append(row)
    bigwigs = [pyBigWig.open(str(data / f"GSE300197_{name}.CR.zscore.bw")) for name in TRACKS]
    try:
        chromosome_maps = [handle.chroms() for handle in bigwigs]
        for chromosome in AUTOSOMES:
            lengths = [mapping.get(chromosome) for mapping in chromosome_maps]
            if any(length is None for length in lengths) or len(set(lengths)) != 1:
                raise ValueError(f"chromosome length mismatch: {chromosome}")
            segments = CommonTrackSegments([list(handle.intervals(chromosome) or ()) for handle in bigwigs], lengths[0])
            for row in rows:
                if row.get("chromosome") != chromosome:
                    continue
                for half_width in (25_000, 50_000, 100_000):
                    row.update(profile_fields(segments.window(row["tss"], half_width), half_width))
                row["eligible"] = row["expression_eligible"] and row["h50000_status"] == "evaluable"
                row["baseline_eligible"] = row["eligible"] and row["h50000_siScr.mCh"] <= 0
    finally:
        for handle in bigwigs:
            handle.close()
    baseline = [row for row in rows if row["baseline_eligible"]]
    threshold = float(np.quantile([row["h50000_gain"] for row in baseline], 0.9, method="linear")) if baseline else float("nan")
    for row in baseline:
        row["signal_screen"] = row["h50000_gain"] > 0 and row["h50000_gain"] >= threshold
    candidates = select_candidates(rows, set(registration["screen"]["known_exclusions"]))
    statistics, matching, null_rows = association_statistics(rows)
    for row in candidates:
        for half_width in (25_000, 100_000):
            row[f"h{half_width}_sensitivity_gain_positive"] = (bool(row[f"h{half_width}_gain"] > 0)
                if row[f"h{half_width}_status"] == "evaluable" else None)
            row[f"h{half_width}_sensitivity_interaction_negative"] = (bool(row[f"h{half_width}_dnk_interaction"] < 0)
                if row[f"h{half_width}_status"] == "evaluable" else None)
        row["median_ratio_direction_negative"] = row["rna_contrast_median_ratio"] < 0
        residual = row["h50000_dnk_residual"]
        row["dnk_pattern"] = "reversal" if residual < 0 else ("attenuation_without_reversal" if residual < row["h50000_gain"] else "no_attenuation")
    write_tsv(out / "gene-measurements.tsv", rows)
    write_tsv(out / "matched-controls.tsv", matching, None if matching else ["anchor", "status"])
    write_tsv(out / "circular-null.tsv", null_rows, ["draw", "spearman"])
    selected = {"campaign_id": registration["campaign_id"], "status": "discovery_candidates_frozen_before_external_counts",
                "registration_sha256": REGISTRATION_SHA, "analysis_sha256": sha256(Path(__file__)),
                "requirements_lock_sha256": LOCK_SHA, "inputs_manifest_sha256": MANIFEST_SHA, "inputs": manifest,
                "gene_measurements_sha256": sha256(out / "gene-measurements.tsv"),
                "ordered_candidates": candidates, "candidate_count": len(candidates),
                "external_expression_accessed_by_this_program": False,
                "claim_ceiling": registration["claim_ceiling"]}
    write_json(out / "candidates.frozen.json", selected)
    summary = {"campaign_id": registration["campaign_id"], "status": "exploratory_discovery_computed",
               "registration_sha256": REGISTRATION_SHA, "analysis_sha256": sha256(Path(__file__)),
               "candidate_freeze_sha256": sha256(out / "candidates.frozen.json"),
               "rna_rows": len(rows), "rna_columns": columns, "library_totals": rna["totals"],
               "median_ratio_size_factors": rna["size_factors"], "median_ratio_positive_genes": rna["size_factor_genes"],
               "annotation_unique_autosomal_symbols": len(annotation), "annotation_ambiguous_symbols": sorted(ambiguous),
               "expression_eligible": sum(row["expression_eligible"] for row in rows),
               "eligible_universe": sum(row["eligible"] for row in rows), "baseline_eligible": len(baseline),
               "gain_90_percentile_linear": threshold, "signal_screen_genes": sum(row["signal_screen"] for row in rows),
               "candidate_qualified_before_spacing": sum(row["candidate_qualified_before_spacing"] for row in rows),
               "ordered_candidate_symbols": [row["symbol"] for row in candidates], "statistics": statistics,
               "known_gene_controls": [row for row in rows if row["symbol"] in registration["screen"]["known_exclusions"]],
               "implementation_details": {"quantiles": "NumPy linear", "matching_sd": "population ddof=0",
                   "tss_neighbour_count": "inclusive +/-1Mb, includes own TSS, unique autosomal annotation",
                   "sensitivity_role": "secondary; does not change primary candidates", "no_gene_DE_p_values": True,
                   "interval_weighting": "piecewise constant source intervals; shared finite-base mask"},
               "limitations": [registration["claim_ceiling"], registration["discovery"]["unit_caveat"],
                   registration["discovery"]["chromatin"], registration["screen"]["dnk_interpretation"],
                   registration["rna"]["absolute_expression_caveat"]]}
    write_json(out / "summary.json", summary)
    write_json(out / "outputs.manifest.json", {"files": [{"path": path.name, "bytes": path.stat().st_size,
                                                          "sha256": sha256(path)} for path in sorted(out.iterdir()) if path.is_file()]})
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True, help="New directory; existing results are never overwritten")
    parser.add_argument("--registration", type=Path, default=Path(__file__).with_name("registration.frozen.json"))
    parser.add_argument("--inputs-manifest", type=Path, default=Path(__file__).with_name("inputs.discovery.json"))
    args = parser.parse_args()
    result = run(args.data, args.out, args.registration, args.inputs_manifest)
    print(json.dumps(safe_json({key: result[key] for key in ("status", "rna_rows", "eligible_universe", "signal_screen_genes", "ordered_candidate_symbols", "candidate_freeze_sha256")})))


if __name__ == "__main__":
    main()
