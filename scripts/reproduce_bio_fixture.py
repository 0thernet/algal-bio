#!/usr/bin/env python3
"""Offline real-data fixture reproduction plus a separately implemented oracle."""
from __future__ import annotations

import argparse
import csv
from decimal import Decimal, localcontext
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from bio_lab.measurements import compare_cscore, filter_rna  # noqa: E402


def reproduce() -> dict:
    fixture = ROOT / "tests/fixtures/bio"
    provenance = json.loads((fixture / "rna-provenance.json").read_text())
    path = fixture / "rna-counts.tsv"
    if hashlib.sha256(path.read_bytes()).hexdigest() != provenance["fixture_sha256"]:
        raise ValueError("RNA fixture differs from retained source projection")
    observed = filter_rna(path, library_totals=provenance["library_totals"])
    # Independent decimal implementation over raw CSV, sharing no production parser.
    with path.open() as stream, localcontext() as context:
        context.prec = 60
        rows = list(csv.DictReader(stream, delimiter="\t"))
        expected = [r["Geneid"] for r in rows if sum(
            Decimal(r[s]) / Decimal(total) * Decimal(10**6) > Decimal("0.26")
            for s, total in provenance["library_totals"].items()) >= 4]
    if observed["passing_genes"] != expected:
        raise ValueError("independent RNA filtering calculation disagrees")
    for condition in ("plus", "minus"):
        meta = json.loads((fixture / f"cscore-{condition}-provenance.json").read_text())
        if hashlib.sha256((fixture / f"cscore-{condition}.bedgraph").read_bytes()).hexdigest() != meta["fixture_sha256"]:
            raise ValueError("chromatin fixture source digest mismatch")
    chromatin = compare_cscore(fixture / "cscore-plus.bedgraph", fixture / "cscore-minus.bedgraph")
    # A second sum over raw text confirms the exact interval delta, independent of adapter parsing.
    read_values = lambda name: [Decimal(line.split("\t")[3]) for line in (fixture / name).read_text().splitlines()]
    refs, changed = read_values("cscore-plus.bedgraph"), read_values("cscore-minus.bedgraph")
    reference_delta = (sum(changed) - sum(refs)) / len(refs)
    if Decimal(chromatin["mean_interval_delta"]) != reference_delta:
        raise ValueError("independent chromatin arithmetic disagrees")
    expected_summary = json.loads((fixture / "expected.json").read_text())
    actual = {"rna_genes": observed["genes"], "rna_passing": observed["passing_count"],
              "chromatin_intervals": chromatin["intervals"], "chromatin_mean_delta": chromatin["mean_interval_delta"]}
    if actual != expected_summary:
        raise ValueError("frozen fixture measurements changed")
    return {"contract": "bio.fixture-reproduction.v1", "rna": observed, "chromatin": chromatin,
            "independent_arithmetic": "passed", "scientific_status": "calibration only; no novel or confirmatory biological claim"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true", required=True)
    parser.add_argument("--json", action="store_true", help="emit the full bounded measurement for the lab adapter")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = reproduce()
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("x") as stream:
            stream.write(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result if args.json else {"status": "passed", "genes": result["rna"]["genes"],
                      "passing": result["rna"]["passing_count"], "intervals": result["chromatin"]["intervals"],
                      "scope": result["scientific_status"]}))
