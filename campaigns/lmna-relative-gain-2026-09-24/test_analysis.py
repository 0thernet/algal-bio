"""Focused synthetic checks; this file never reads a biological source matrix."""
import gzip
import tempfile
import unittest
from pathlib import Path

import numpy as np

import analysis


class IntervalTests(unittest.TestCase):
    def setUp(self):
        self.segments = analysis.CommonTrackSegments([
            [(0, 4, 2), (4, 8, 4), (8, 12, float("nan"))],
            [(0, 2, 1), (2, 10, 3)],
            [(1, 6, 10), (6, 12, 20)],
            [(0, 12, -2)],
        ], 12)

    def test_common_finite_base_mask_and_exact_weighting(self):
        result = self.segments.window(6, 6)
        self.assertEqual(result["covered_bases"], 7)
        self.assertEqual(result["coverage"], 7 / 12)
        np.testing.assert_allclose(result["means"], [22 / 7, 19 / 7, 90 / 7, -2])
        partial = self.segments.window(3, 2)
        self.assertEqual(partial["coverage"], 1)
        np.testing.assert_allclose(partial["means"], [2.5, 2.5, 10, -2])

    def test_clipped_half_open_window_and_missing_data(self):
        clipped = self.segments.window(0, 3)
        self.assertEqual((clipped["start"], clipped["end"]), (0, 3))
        self.assertEqual(clipped["covered_bases"], 2)
        absent = analysis.CommonTrackSegments([[], [(0, 12, 1)]], 12).window(5, 2)
        self.assertEqual(absent["coverage"], 0)
        self.assertTrue(np.all(np.isnan(absent["means"])))
        fields = analysis.profile_fields(self.segments.window(6, 6), 50_000)
        self.assertEqual(fields["h50000_status"], "insufficient_common_coverage")
        self.assertTrue(np.isnan(fields["h50000_gain"]))

    def test_reject_overlaps_and_reverse_strand_tss(self):
        with self.assertRaises(ValueError):
            analysis.CommonTrackSegments([[(0, 4, 2), (3, 8, 4)]], 12)
        self.assertEqual(analysis.annotation_tss("+", 10, 30), 10)
        self.assertEqual(analysis.annotation_tss("-", 10, 30), 29)


class RnaTests(unittest.TestCase):
    def test_total_denominators_and_all_seven_loo_directions(self):
        counts = np.array([[10, 10, 10, 5, 5, 5, 5], [10, 10, 10, 15, 15, 15, 15], [20] * 7])
        values = analysis.normalize_rna(counts, 3)
        np.testing.assert_equal(values["totals"], [40] * 7)
        expected = np.log2(125000 + 0.5) - np.log2(250000 + 0.5)
        self.assertAlmostEqual(values["primary"][0], expected)
        np.testing.assert_allclose(values["loo"][0], [expected] * 7)
        self.assertTrue(np.all(values["loo"][0] < 0))
        self.assertAlmostEqual(values["primary"][2], 0)
        self.assertLess(values["median_ratio"][0], 0)

    def test_library_scaling_invariance_and_invalid_counts(self):
        scales = np.arange(1, 8)
        counts = np.array([10, 20, 30])[:, None] * scales[None, :]
        values = analysis.normalize_rna(counts, 3)
        np.testing.assert_allclose(values["primary"], 0, atol=1e-12)
        np.testing.assert_allclose(values["median_ratio"], 0, atol=1e-12)
        np.testing.assert_allclose(values["size_factors"], scales / np.exp(np.log(scales).mean()))
        with self.assertRaises(ValueError):
            analysis.normalize_rna(np.zeros((3, 7)), 3)
        with self.assertRaises(ValueError):
            analysis.normalize_rna(counts + 0.1, 3)

    def test_count_header_order_and_duplicate_symbols(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.tsv.gz"
            with gzip.open(path, "wt") as handle:
                handle.write('""\t"a"\t"b"\n"G"\t1\t2\n')
            genes, matrix = analysis.read_counts(path, ["a", "b"])
            self.assertEqual(genes, ["G"])
            np.testing.assert_equal(matrix, [[1, 2]])
            with self.assertRaises(ValueError):
                analysis.read_counts(path, ["b", "a"])
            with gzip.open(path, "at") as handle:
                handle.write('"G"\t3\t4\n')
            with self.assertRaises(ValueError):
                analysis.read_counts(path, ["a", "b"])


class SelectionTests(unittest.TestCase):
    def test_deterministic_ties_spacing_and_no_exclusion_backfill(self):
        def row(symbol, position, chromosome="chr1", rna=-1):
            return {"symbol": symbol, "tss": position, "chromosome": chromosome,
                    "signal_screen": True, "rna_contrast_cpm": rna,
                    "h50000_gain": 1, "h50000_dnk_interaction": -0.2,
                    "loo_all_negative": True}
        rows = [row("B", 999_999), row("A", 500_000), row("C", 1_000_000),
                row("D", 500_000, "chr2"), row("KNOWN", 2_000_000, rna=-2)]
        selected = analysis.select_candidates(rows, {"KNOWN"})
        self.assertEqual([item["symbol"] for item in selected], ["A", "C", "D"])
        self.assertEqual(rows[0]["candidate_selection_status"], "excluded_spacing")
        self.assertFalse(rows[-1]["candidate_qualified_before_spacing"])

    def test_controls_selected_without_response_filter_and_short_chromosome_null(self):
        rows = []
        for i in range(7):
            rows.append({"symbol": f"G{i}", "eligible": True, "baseline_eligible": True,
                         "signal_screen": i == 0, "chromosome": "chr1", "tss": i * 2_000_000,
                         "control_mean_cpm": 10, "transcript_span": 1000, "tss_count_1mb": 1,
                         "h50000_siScr.mCh": -1, "h50000_gain": 2 if i == 0 else i / 10,
                         "rna_contrast_cpm": -1 if i == 0 else 1})
        stats, matches, null = analysis.association_statistics(rows)
        self.assertEqual(matches[0]["controls"], "G1;G2;G3;G4;G5")
        self.assertEqual(matches[0]["matched_difference"], -2)
        self.assertEqual(stats["matched_class"]["matched_anchors"], 1)
        self.assertEqual(stats["continuous_spatial_null"]["omitted_chromosomes_gene_counts"]["chr1"], 7)
        self.assertEqual(null, [])


if __name__ == "__main__":
    unittest.main()
