"""Evaluate only frozen candidates in an external public expression matrix.

Header mapping is an explicit metadata-only intake artifact; never choose a
mapping from expression outcomes. No network, inference, or candidate selection.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import gzip
import hashlib
import json
from pathlib import Path
import platform

import numpy as np
import pyBigWig
import scipy

from analysis import normalize_rna, safe_json, sha256, write_json, write_tsv


def validate_header_mapping(mapping):
    header = mapping["header"]
    if len(set(header)) != len(header):
        raise ValueError("Duplicate external header names")
    if mapping["identifier_kind"] != "provided_exact_gene_symbol":
        raise ValueError("Explicit pinned crosswalk required before identifier-only data can be evaluated")
    gene_column = header.index(mapping["gene_symbol_column"])
    controls = [header.index(v) for v in mapping["control_columns"]]
    cases = [header.index(v) for v in mapping["case_columns"]]
    columns = controls + cases
    if len(controls) != 6 or len(cases) != 6 or len(set(columns)) != 12 or gene_column in columns:
        raise ValueError("Require separate gene symbols and six unique libraries per genotype")
    return gene_column, controls, cases


def evaluate_candidates(frozen, symbols, counts, n_control):
    if len(symbols) != len(counts):
        raise ValueError("Identifier/count length mismatch")
    multiplicity = Counter(symbols)
    index = {s: i for i, s in enumerate(symbols) if s and multiplicity[s] == 1}
    normalized = normalize_rna(counts, n_control)
    outcomes = []
    for candidate in frozen["ordered_candidates"]:
        symbol = candidate["symbol"]
        record = {"symbol": symbol, "discovery_rank": candidate["candidate_rank"],
                  "predicted_direction": "down", "pass": False}
        if symbol not in index:
            record["status"] = "ambiguous_symbol" if multiplicity[symbol] > 1 else "missing_symbol"
        else:
            i = index[symbol]
            primary = float(normalized["primary"][i])
            sensitivity = float(normalized["median_ratio"][i])
            loo = normalized["loo"][i].tolist()
            passed = primary < 0 and sensitivity < 0 and max(loo) < 0
            record.update({"status": "direction_corroborated" if passed else "direction_not_corroborated",
                           "pass": bool(passed), "rna_contrast_cpm": primary,
                           "rna_contrast_median_ratio": sensitivity,
                           "loo_min": min(loo), "loo_max": max(loo), "loo_all_negative": max(loo) < 0,
                           "control_mean_cpm": float(normalized["cpm"][i, :n_control].mean()),
                           "case_mean_cpm": float(normalized["cpm"][i, n_control:].mean()),
                           "all_counts": counts[i].tolist(),
                           "all_log2_cpm": normalized["log_cpm"][i].tolist(),
                           "all_loo_contrasts": loo})
        outcomes.append(record)
    return outcomes, normalized


def run(args):
    if args.out.exists():
        raise ValueError("Output must be new; retain previous observations")
    freeze = json.loads(args.freeze_receipt.read_text())
    if sha256(args.candidates) != freeze["candidate_freeze_sha256"]:
        raise ValueError("Candidate freeze changed")
    candidates = json.loads(args.candidates.read_text())
    if candidates["analysis_sha256"] != sha256(Path(__file__).with_name("analysis.py")):
        raise ValueError("Discovery analysis code changed after candidate freeze")
    if sha256(Path(__file__).with_name("requirements.lock")) != candidates["requirements_lock_sha256"]:
        raise ValueError("Scientific dependency lock changed after candidate freeze")
    if (np.__version__, scipy.__version__, pyBigWig.__version__) != ("2.3.3", "1.16.2", "0.3.24"):
        raise ValueError("Scientific dependency versions differ from frozen discovery runtime")
    mapping = json.loads(args.mapping.read_text())
    if sha256(args.counts) != mapping["matrix_sha256"]:
        raise ValueError("External matrix differs from intake")
    if mapping["candidate_freeze_sha256"] != freeze["candidate_freeze_sha256"]:
        raise ValueError("External intake not bound to frozen candidates")
    header = mapping["header"]
    gene_column, control_columns, case_columns = validate_header_mapping(mapping)
    columns = control_columns + case_columns
    symbols, rows = [], []
    with gzip.open(args.counts, "rt", newline="") as f:
        reader = csv.reader(f, delimiter=mapping["delimiter"])
        if next(reader) != header:
            raise ValueError("Count header changed")
        for row in reader:
            if len(row) != len(header):
                raise ValueError("Count row width mismatch")
            values = [float(row[i]) for i in columns]
            if not all(np.isfinite(x) and 0 <= x <= 10**12 and x == int(x) for x in values):
                raise ValueError("Noninteger/invalid external raw counts")
            symbols.append(row[gene_column])
            rows.append(values)
            if len(rows) > 200_000:
                raise ValueError("External row limit")
    if symbols and sum(s.startswith("ENSG") or s.startswith("NM_") for s in symbols) > len(symbols) / 2:
        raise ValueError("Identifier-like column is not an admitted gene-symbol mapping")
    counts = np.asarray(rows, dtype=np.float64)
    if np.any(counts.sum(axis=0) > 2**53):
        raise ValueError("External library total exceeds precise arithmetic")
    outcomes, normalized = evaluate_candidates(candidates, symbols, counts, len(control_columns))
    args.out.mkdir()
    write_tsv(args.out / "candidate-outcomes.tsv", outcomes)
    result = {"status": "external_direction_check_completed", "accession": "GSE304575",
              "candidate_freeze_sha256": sha256(args.candidates),
              "external_matrix_sha256": sha256(args.counts), "header_mapping_sha256": sha256(args.mapping),
              "analysis_sha256": sha256(Path(__file__)), "discovery_analysis_sha256": candidates["analysis_sha256"],
              "requirements_lock_sha256": candidates["requirements_lock_sha256"],
              "runtime": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__, "pybigwig": pyBigWig.__version__},
              "expression_rows": len(symbols), "columns_in_analysis_order": [header[i] for i in columns],
              "control_library_count": 6, "case_library_count": 6,
              "library_totals": normalized["totals"], "median_ratio_size_factors": normalized["size_factors"],
              "median_ratio_positive_genes": normalized["size_factor_genes"],
              "frozen_candidates": len(outcomes),
              "evaluable_candidates": sum(v["status"] not in {"ambiguous_symbol", "missing_symbol"} for v in outcomes),
              "direction_corroborated": sum(v["pass"] for v in outcomes), "outcomes": outcomes,
              "limitations": ["Direction-only corroboration of a distinct perturbation; not chromatin or causal mechanism validation.",
                              "One patient background; biological culture independence unresolved.",
                              "No significance or novelty established by sign agreement; genes were selected on discovery effect size.",
                              "Compositional relative RNA measurements; no absolute transcription claim.",
                              "External results cannot replace or add candidates."]}
    write_json(args.out / "summary.json", result)
    print(json.dumps(safe_json({k: result[k] for k in ["frozen_candidates", "evaluable_candidates", "direction_corroborated", "outcomes"]}), indent=2))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ["counts", "mapping", "candidates", "freeze-receipt", "out"]:
        p.add_argument("--" + name, type=Path, required=True)
    run(p.parse_args())


if __name__ == "__main__":
    main()
