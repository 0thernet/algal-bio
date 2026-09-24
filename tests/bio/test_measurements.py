from decimal import Decimal
import gzip
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from bio_lab.measurements import compare_cscore, filter_rna, read_counts


def table(tmp_path, data):
    path = tmp_path / "counts.tsv"
    path.write_text("Geneid\ta\tb\tc\td\n" + data)
    return path


def test_threshold_is_strict_and_subset_uses_full_totals(tmp_path):
    path = table(tmp_path, "at\t26\t26\t26\t26\nabove\t27\t27\t27\t27\n")
    result = filter_rna(path, library_totals={s: 100_000_000 for s in "abcd"})
    assert result["passing_genes"] == ["above"]
    assert result["library_totals_origin"] == "supplied-full-source"


@pytest.mark.parametrize("row", ["g\t-1\t0\t0\t0\n", "g\tnan\t0\t0\t0\n", "g\t1.2\t0\t0\t0\n", "g\t1\t0\n", "g\t1\t0\t0\t0\ng\t1\t0\t0\t0\n"])
def test_malformed_and_duplicate_counts_rejected(tmp_path, row):
    with pytest.raises(ValueError):
        read_counts(table(tmp_path, row))


def test_zero_library_and_incompatible_totals_rejected(tmp_path):
    path = table(tmp_path, "g\t1\t0\t1\t1\n")
    with pytest.raises(ValueError):
        filter_rna(path)
    with pytest.raises(ValueError):
        filter_rna(path, library_totals={s: True for s in "abcd"})
    with pytest.raises(ValueError):
        filter_rna(path, library_totals={s: 10 for s in "abc"})


def test_gzip_and_plain_counts_agree(tmp_path):
    path = table(tmp_path, "g\t1\t2\t3\t4\n")
    archive = tmp_path / "counts.tsv.gz"
    archive.write_bytes(gzip.compress(path.read_bytes()))
    assert read_counts(path)["rows"] == read_counts(archive)["rows"]


def test_source_intervals_are_not_silently_aligned(tmp_path):
    ref = tmp_path / "ref.bedgraph"
    changed = tmp_path / "changed.bedgraph"
    ref.write_text("chr1\t0\t10\t0.5\n")
    changed.write_text("chr1\t1\t10\t0.6\n")
    with pytest.raises(ValueError, match="reconciliation"):
        compare_cscore(ref, changed)


def test_coordinate_overlap_retained_without_replication_claim(tmp_path):
    ref = tmp_path / "ref.bedgraph"
    changed = tmp_path / "changed.bedgraph"
    ref.write_text("chr1\t0\t11\t0.5\nchr1\t10\t21\t0.6\n")
    changed.write_text("chr1\t0\t11\t0.6\nchr1\t10\t21\t0.4\n")
    result = compare_cscore(ref, changed)
    assert Decimal(result["mean_interval_delta"]) == Decimal("-0.05")
    assert result["source_coordinate_overlaps"]["reference"] == 1
    assert "not independent" in result["inference"]


def test_nested_intervals_keep_the_longest_prior_extent(tmp_path):
    path = tmp_path / "nested.bedgraph"
    path.write_text("chr1\t0\t100\t0.5\nchr1\t10\t20\t0.6\nchr1\t30\t40\t0.7\n")
    result = compare_cscore(path, path)
    assert result["source_coordinate_overlaps"] == {"reference": 2, "perturbed": 2}
    assert Decimal(result["mean_interval_delta"]) == 0


def test_out_of_order_intervals_are_rejected_instead_of_counted_as_overlap(tmp_path):
    path = tmp_path / "unsorted.bedgraph"
    path.write_text("chr1\t10\t20\t0.5\nchr1\t0\t5\t0.6\n")
    with pytest.raises(ValueError, match="nondecreasing"):
        compare_cscore(path, path)


def test_real_fixture_reproduces_independently():
    spec = importlib.util.spec_from_file_location("fixture_reproduction", ROOT / "scripts/reproduce_bio_fixture.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.reproduce()["independent_arithmetic"] == "passed"


def test_fixture_runs_under_isolated_stdlib_python_from_unrelated_directory(tmp_path):
    # Neither an import hook nor a same-name module on a caller-controlled path
    # may enter the fixed measurement. The script admits src explicitly.
    marker = tmp_path / "hook-ran"
    (tmp_path / "sitecustomize.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('loaded')\n"
    )
    (tmp_path / "csv.py").write_text("raise RuntimeError('unadmitted CSV implementation')\n")
    result = subprocess.run(
        [sys.executable, "-I", "-S", str(ROOT / "scripts/reproduce_bio_fixture.py"), "--offline", "--json"],
        cwd=tmp_path, env={"PYTHONPATH": str(tmp_path)}, capture_output=True, text=True, check=True,
    )
    assert not marker.exists()
    assert result.stderr == ""
    observed = json.loads(result.stdout)
    assert observed["independent_arithmetic"] == "passed"
    assert observed["rna"]["passing_count"] == 28
    assert observed["chromatin"]["mean_interval_delta"] == "0.04620996875"
