"""Descriptive measurements over pinned public data, not discovery scoring."""

from __future__ import annotations

import csv
from decimal import Decimal, InvalidOperation
import gzip
import hashlib
import io
from pathlib import Path
from typing import Any

MAX_BYTES = 64 * 1024 * 1024
MAX_ROWS = 200_000
MAX_LIBRARIES = 128
ANNOTATION = ["Chr", "Start", "End", "Strand", "Length"]


def read_text(path: Path) -> tuple[str, str]:
    """Bound decompression as well as the compressed artifact."""
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError("invalid input file or byte bound")
    payload = path.read_bytes()
    if len(payload) > MAX_BYTES:
        raise ValueError("input grew beyond byte bound")
    if path.suffix == ".gz":
        with gzip.GzipFile(fileobj=io.BytesIO(payload)) as stream:
            data = stream.read(MAX_BYTES + 1)
    else:
        data = payload
    if len(data) > MAX_BYTES:
        raise ValueError("decompressed input exceeds byte bound")
    return data.decode("utf-8"), hashlib.sha256(payload).hexdigest()


def _natural(value: str) -> int:
    if not value.isascii() or not value.isdigit() or len(value) > 16:
        raise ValueError("counts and coordinates must be bounded nonnegative integers")
    return int(value)


def read_counts(path: Path) -> dict[str, Any]:
    text, source_hash = read_text(path)
    reader = csv.reader(io.StringIO(text), delimiter="\t")
    header = next(reader, [])
    if not header or header[0] != "Geneid":
        raise ValueError("expected Geneid header")
    offset = 6 if header[1:6] == ANNOTATION else 1
    samples = header[offset:]
    if not 1 <= len(samples) <= MAX_LIBRARIES or len(set(samples)) != len(samples):
        raise ValueError("invalid or repeated sample columns")
    if any(not s or len(s) > 128 for s in samples):
        raise ValueError("invalid sample identifier")
    rows: dict[str, list[int]] = {}
    totals = [0] * len(samples)
    for fields in reader:
        if len(rows) >= MAX_ROWS or len(fields) != len(header):
            raise ValueError("row count or width exceeds contract")
        gene = fields[0]
        if not gene or len(gene) > 128 or gene in rows:
            raise ValueError("missing, oversized, or duplicate gene identifier")
        values = [_natural(value) for value in fields[offset:]]
        rows[gene] = values
        totals = [old + new for old, new in zip(totals, values, strict=True)]
    if not rows:
        raise ValueError("empty RNA table")
    return {"input_sha256": source_hash, "samples": samples, "rows": rows,
            "observed_totals": dict(zip(samples, totals, strict=True))}


def filter_rna(path: Path, *, library_totals: dict[str, int] | None = None) -> dict[str, Any]:
    """Reproduce the author's *pre-TMM* CPM > 0.26 in >=4 libraries filter.

    Exact integer arithmetic avoids rounding at the cutoff. For a row subset,
    full-source library totals must be supplied; subset normalization changes
    the question. This is not edgeR differential expression or significance.
    """
    table = read_counts(path)
    samples = table["samples"]
    if len(samples) < 4:
        raise ValueError("the registered filter needs at least four libraries")
    totals = table["observed_totals"] if library_totals is None else library_totals
    if set(totals) != set(samples):
        raise ValueError("library totals do not match sample identities")
    if any(type(v) is not int or v <= 0 or v > 10**16 for v in totals.values()):
        raise ValueError("library totals must be positive bounded integers")
    if any(totals[s] < table["observed_totals"][s] for s in samples):
        raise ValueError("full library total smaller than observed subset")
    passing = []
    for gene, values in table["rows"].items():
        above = sum(count * 100_000_000 > 26 * totals[s]
                    for s, count in zip(samples, values, strict=True))
        if above >= 4:
            passing.append(gene)
    return {
        "contract": "bio.rna-filter.v1", "input_sha256": table["input_sha256"],
        "method": "raw CPM > 0.26 in at least 4 libraries; before TMM",
        "library_totals_origin": "supplied-full-source" if library_totals is not None else "all-input-rows",
        "library_totals": totals, "libraries": len(samples), "genes": len(table["rows"]),
        "passing_genes": passing, "passing_count": len(passing),
        "inference": "descriptive preprocessing reproduction; no differential-expression or biological-replication claim",
    }


def _bedgraph(path: Path) -> tuple[dict[tuple[str, int, int], Decimal], str, int]:
    text, source_hash = read_text(path)
    rows: dict[tuple[str, int, int], Decimal] = {}
    last_end: dict[str, int] = {}
    last_start: dict[str, int] = {}
    overlaps = 0
    for fields in csv.reader(io.StringIO(text), delimiter="\t"):
        if len(fields) != 4 or len(rows) >= MAX_ROWS:
            raise ValueError("invalid bedGraph row width or bound")
        chrom, raw_start, raw_end, raw_value = fields
        start, end = _natural(raw_start), _natural(raw_end)
        if not chrom or len(chrom) > 64 or end <= start:
            raise ValueError("invalid interval")
        if len(raw_value) > 64:
            raise ValueError("oversized measurement")
        try:
            value = Decimal(raw_value)
        except InvalidOperation as exc:
            raise ValueError("invalid measurement") from exc
        if not value.is_finite() or abs(value) > 1_000_000:
            raise ValueError("nonfinite or unbounded measurement")
        key = (chrom, start, end)
        if key in rows:
            raise ValueError("duplicate genomic interval")
        if chrom in last_start and start < last_start[chrom]:
            raise ValueError("genomic interval starts must be nondecreasing within each chromosome")
        if chrom in last_end and start < last_end[chrom]:
            overlaps += 1
        last_start[chrom] = start
        last_end[chrom] = max(last_end.get(chrom, 0), end)
        rows[key] = value
    if not rows:
        raise ValueError("empty bedGraph")
    return rows, source_hash, overlaps


def compare_cscore(reference: Path, perturbed: Path) -> dict[str, Any]:
    """Pair exact source intervals; never silently lift over or drop unmatched rows."""
    ref, ref_hash, ref_overlap = _bedgraph(reference)
    obs, obs_hash, obs_overlap = _bedgraph(perturbed)
    if ref.keys() != obs.keys():
        raise ValueError("genomic intervals differ; explicit build/coordinate reconciliation required")
    delta = [obs[key] - ref[key] for key in ref]
    return {
        "contract": "bio.cscore-summary.v1", "reference_sha256": ref_hash,
        "perturbed_sha256": obs_hash, "intervals": len(delta),
        "mean_interval_delta": str(sum(delta) / len(delta)),
        "positive_intervals": sum(v > 0 for v in delta),
        "negative_intervals": sum(v < 0 for v in delta),
        "unchanged_intervals": sum(v == 0 for v in delta),
        "source_coordinate_overlaps": {"reference": ref_overlap, "perturbed": obs_overlap},
        "inference": "descriptive genotype-aggregate track; intervals are not independent biological replicates",
        "coordinate_policy": "exact source coordinates retained; mean of intervals, not a genomic-length integral",
    }
