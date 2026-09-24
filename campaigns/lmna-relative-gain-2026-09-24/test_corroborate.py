import unittest

import numpy as np

from corroborate import evaluate_candidates, validate_header_mapping


class CorroborationTests(unittest.TestCase):
    def test_direction_order_missing_and_ambiguous(self):
        frozen = {"ordered_candidates": [
            {"symbol": name, "candidate_rank": i + 1}
            for i, name in enumerate(["down", "up", "missing", "dup"])]}
        counts = np.array([[200] * 6 + [30] * 6, [30] * 6 + [200] * 6,
                           [100] * 12, [100] * 12, [400] * 12])
        outcomes, _ = evaluate_candidates(frozen, ["down", "up", "dup", "dup", "stable"], counts, 6)
        self.assertEqual([r["symbol"] for r in outcomes], ["down", "up", "missing", "dup"])
        self.assertTrue(outcomes[0]["pass"])
        self.assertLess(outcomes[0]["rna_contrast_median_ratio"], 0)
        self.assertLess(outcomes[0]["loo_max"], 0)
        self.assertFalse(outcomes[1]["pass"])
        self.assertGreater(outcomes[1]["rna_contrast_cpm"], 0)
        self.assertEqual(outcomes[2]["status"], "missing_symbol")
        self.assertEqual(outcomes[3]["status"], "ambiguous_symbol")

    def test_invalid_counts_do_not_become_findings(self):
        frozen = {"ordered_candidates": [{"symbol": "a", "candidate_rank": 1}]}
        with self.assertRaises(ValueError):
            evaluate_candidates(frozen, ["a"], np.array([[0.1] * 12]), 6)
        with self.assertRaises(ValueError):
            evaluate_candidates(frozen, [], np.array([[1] * 12]), 6)

    def test_ambiguous_column_mapping_stops(self):
        m = {"header": ["symbol"] + [f"c{i}" for i in range(12)],
             "gene_symbol_column": "symbol", "identifier_kind": "provided_exact_gene_symbol",
             "control_columns": [f"c{i}" for i in range(6)],
             "case_columns": [f"c{i}" for i in range(6, 12)]}
        self.assertEqual(validate_header_mapping(m), (0, list(range(1, 7)), list(range(7, 13))))
        m["header"].append("c0")
        with self.assertRaises(ValueError):
            validate_header_mapping(m)
        m["header"].pop()
        m["gene_symbol_column"] = "c0"
        with self.assertRaises(ValueError):
            validate_header_mapping(m)


if __name__ == "__main__":
    unittest.main()
