#!/usr/bin/env python3
"""Verify a retained public input and reproduce the full-table RNA filter.

No download, model call, or differential-expression inference occurs here.
"""
from __future__ import annotations

import argparse
import csv
from decimal import Decimal, localcontext
import gzip
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from bio_lab.measurements import filter_rna  # noqa: E402


def calibrate(path: Path) -> dict:
    provenance = json.loads((ROOT / "tests/fixtures/bio/rna-provenance.json").read_text())
    if path.is_symlink() or not path.is_file() or path.stat().st_size != provenance["compressed_bytes"]:
        raise ValueError("expected the retained bounded compressed source file")
    source_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    if source_hash != provenance["compressed_sha256"]:
        raise ValueError("source bytes changed; admit a new dataset version explicitly")
    observed = filter_rna(path)
    # Independent Decimal expression and raw CSV traversal, not production helpers.
    with gzip.open(path, "rt", newline="") as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))
    names = list(provenance["library_totals"])
    totals = {sample: sum(int(row[sample]) for row in rows) for sample in names}
    if totals != provenance["library_totals"] or len(rows) != provenance["source_rows"]:
        raise ValueError("full-source projection metadata mismatch")
    with localcontext() as context:
        context.prec = 60
        expected = [row["Geneid"] for row in rows if sum(
            Decimal(row[sample]) * Decimal(10**6) / Decimal(totals[sample]) > Decimal("0.26")
            for sample in names) >= 4]
    if observed["passing_genes"] != expected:
        raise ValueError("independent full-input arithmetic disagrees")
    # Verify the checked-in subset was projected from these source bytes.
    selected = ["\t".join(["Geneid"] + names)] + [
        "\t".join([r["Geneid"]] + [r[s] for s in names]) for r in rows[:128]]
    projection = ("\n".join(selected) + "\n").encode()
    if hashlib.sha256(projection).hexdigest() != provenance["fixture_sha256"]:
        raise ValueError("fixture does not reproduce from source")
    gene_list_hash = hashlib.sha256(("\n".join(expected) + "\n").encode()).hexdigest()
    return {"contract": "bio.public-calibration.v1", "source_url": provenance["url"],
            "source_sha256": source_hash, "source_rows": len(rows), "libraries": len(names),
            "passing_genes": len(expected), "passing_gene_ids_sha256": gene_list_hash,
            "method": observed["method"], "independent_arithmetic": "passed",
            "fixture_projection": "verified against full source",
            "scientific_status": "preprocessing calibration; no new biological finding or differential expression"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rna", required=True, type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = calibrate(args.rna)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("x") as stream:
            stream.write(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
