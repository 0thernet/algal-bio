"""Synthetic unit tests for pc1.py (run: python -m unittest test_pc1 -v)."""

from __future__ import annotations

import gzip
import json
import math
import os
import tempfile
import unittest

import numpy as np

import pc1


def _block_model(n=40, block=5, seed=1, enrich=1.4, deplete=0.6, scale=2000.0, decay_exp=0.8):
    """Two-compartment block model with distance decay, bin biases and Poisson noise.

    Returns (raw symmetric count matrix, planted labels (+1 A / -1 B), bias).
    """
    labels = np.array([1 if (i // block) % 2 == 0 else -1 for i in range(n)])
    rng = np.random.default_rng(seed)
    bias = rng.uniform(0.5, 1.5, n)
    d = np.abs(np.arange(n)[:, None] - np.arange(n)[None, :])
    decay = 1.0 / (1.0 + d) ** decay_exp
    same = labels[:, None] == labels[None, :]
    mu = scale * decay * np.where(same, enrich, deplete) * bias[:, None] * bias[None, :]
    upper = np.triu(rng.poisson(mu)).astype(np.float64)
    raw = upper + upper.T - np.diag(np.diag(upper))
    return raw, labels, bias


def _planted_density(labels, seed=2):
    rng = np.random.default_rng(seed)
    return np.where(labels > 0, 8.0, 1.0) + rng.integers(0, 3, labels.shape[0])


class TmpDirMixin:
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def path(self, name):
        return os.path.join(self.tmp, name)

    def write(self, name, text, gz=False):
        p = self.path(name)
        if gz:
            with gzip.open(p, "wt") as fh:
                fh.write(text)
        else:
            with open(p, "w") as fh:
                fh.write(text)
        return p


# Small two-chromosome toy genome: chr1 = 2.5 Mb (5 bins of 500 kb), chr2 = 1.2 Mb (3 bins).
SIZES = {"chr1": 2_500_000, "chr2": 1_200_000}

# (chrom1, pos1, chrom2, pos2) -- pos are 1-based as in HiC-Pro.
PAIRS = [
    ("chr1", 1, "chr1", 500_000),           # bins (0, 0)  -> diagonal
    ("chr1", 500_001, "chr1", 100),         # bins (1, 0)  -> reversed order
    ("chr1", 100, "chr1", 500_001),         # bins (0, 1)
    ("chr1", 1_000_001, "chr1", 2_400_000),  # bins (2, 4)
    ("chr1", 2_499_999, "chr1", 1_000_002),  # bins (4, 2)
    ("chr1", 2_499_999, "chr1", 1_000_002),  # bins (4, 2)
    ("chr2", 1, "chr2", 1_200_000),         # bins (0, 2)
    ("chr2", 600_000, "chr2", 600_001),     # bins (1, 1)
    ("chr1", 10, "chr2", 10),               # trans
    ("chr2", 10, "chr1", 10),               # trans
    ("chrX", 10, "chrX", 20),               # non-autosome
    ("chr1", 10, "chrX", 20),               # trans + non-autosome
    ("chr1", 2_500_001, "chr1", 10),        # out of range
]


def expected_matrices():
    m1 = np.zeros((5, 5))
    m1[0, 0] += 1
    m1[0, 1] += 2
    m1[1, 0] += 2
    m1[2, 4] += 3
    m1[4, 2] += 3
    m2 = np.zeros((3, 3))
    m2[0, 2] += 1
    m2[2, 0] += 1
    m2[1, 1] += 1
    return {"chr1": m1, "chr2": m2}


def pairs_text(strip_chr=False, extra_cols=True):
    lines = []
    for k, (c1, p1, c2, p2) in enumerate(PAIRS):
        if strip_chr:
            c1, c2 = c1[3:], c2[3:]
        cols = [f"read{k}", c1, str(p1), "+", c2, str(p2), "-"]
        if extra_cols:
            cols += ["150", "HIC_1_1", "HIC_1_2", "42", "60", "extra"]
        lines.append("\t".join(cols))
    return "\n".join(lines) + "\n"


class TestChromSizes(TmpDirMixin, unittest.TestCase):
    def test_read_chrom_sizes_filters_and_normalises(self):
        p = self.write("sizes.txt", "# comment\n2\t100\nchr1\t200\nchrX\t5\nchrM\t3\nchr1_random\t7\n22\t9\n")
        sizes = pc1.read_chrom_sizes(p)
        self.assertEqual(list(sizes.keys()), ["chr1", "chr2", "chr22"])
        self.assertEqual(sizes, {"chr1": 200, "chr2": 100, "chr22": 9})


class TestBlockModel(unittest.TestCase):
    def test_recovers_planted_compartments(self):
        raw, labels, _bias = _block_model()
        raw[7, :] = 0.0  # a dead bin that must be masked
        raw[:, 7] = 0.0
        balanced, mask = pc1.ice(raw)
        self.assertFalse(mask[7])
        vec, eigval, mask = pc1.compartment_eigenvector(balanced, mask, return_details=True)
        self.assertGreater(eigval, 1.0)
        density = _planted_density(labels)
        oriented, rho = pc1.orient(vec, density)
        self.assertGreater(rho, 0.2)
        kept = np.isfinite(oriented)
        self.assertEqual(int(kept.sum()), 39)
        agreement = np.mean(np.sign(oriented[kept]) == labels[kept])
        self.assertGreaterEqual(agreement, 0.95)
        self.assertAlmostEqual(float(np.std(oriented[kept])), 1.0, places=6)
        self.assertTrue(np.isnan(oriented[7]))

    def test_compute_pc1_records(self):
        raw, labels, _ = _block_model()
        sizes = {"chr1": 40 * 500_000 - 1}  # last bin is shorter
        stats = {}
        records = pc1.compute_pc1({"chr1": raw}, sizes, {"chr1": _planted_density(labels)}, stats=stats)
        self.assertEqual(len(records), 40)
        self.assertEqual(records[-1][2], sizes["chr1"])
        self.assertEqual(records[0][:3], ("chr1", 0, 500_000))
        vals = np.array([r[3] for r in records])
        self.assertGreaterEqual(np.mean(np.sign(vals) == labels), 0.95)
        self.assertEqual(stats["per_chrom"]["chr1"]["n_bins"], 40)
        self.assertTrue(stats["per_chrom"]["chr1"]["oriented"])
        self.assertGreater(stats["per_chrom"]["chr1"]["rho"], 0.2)

    def test_deterministic(self):
        raw, labels, _ = _block_model()
        a = pc1.compute_pc1({"chr1": raw}, {"chr1": 20_000_000}, {"chr1": _planted_density(labels)})
        b = pc1.compute_pc1({"chr1": raw.copy()}, {"chr1": 20_000_000}, {"chr1": _planted_density(labels)})
        self.assertEqual(a, b)


class TestBinValidPairs(TmpDirMixin, unittest.TestCase):
    def _check(self, matrices, stats):
        exp = expected_matrices()
        self.assertEqual(set(matrices), {"chr1", "chr2"})
        for c in exp:
            np.testing.assert_array_equal(matrices[c], exp[c])
            self.assertEqual(matrices[c].dtype, np.float64)
            np.testing.assert_array_equal(matrices[c], matrices[c].T)
        self.assertEqual(stats["total"], len(PAIRS))
        self.assertEqual(stats["kept"], 8)
        self.assertEqual(stats["trans"], 3)
        self.assertEqual(stats["non_autosomal"], 1)
        self.assertEqual(stats["cis"], 9)
        self.assertEqual(stats["out_of_range"], 1)
        self.assertEqual(stats["per_chrom"], {"chr1": 6, "chr2": 2})

    def test_with_chr_prefix_gz(self):
        p = self.write("pairs.gz", pairs_text(), gz=True)
        self._check(*pc1.bin_valid_pairs(p, SIZES))

    def test_without_chr_prefix_plain(self):
        p = self.write("pairs.txt", pairs_text(strip_chr=True, extra_cols=False))
        self._check(*pc1.bin_valid_pairs(p, SIZES))

    def test_chunk_flush(self):
        p = self.write("pairs.gz", pairs_text(), gz=True)
        self._check(*pc1.bin_valid_pairs(p, SIZES, chunk_size=3))

    def test_min_mapq(self):
        p = self.write("pairs.gz", pairs_text(), gz=True)
        m, s = pc1.bin_valid_pairs(p, SIZES, min_mapq=50)
        self.assertEqual(s["mapq_filtered"], len(PAIRS))
        self.assertEqual(s["kept"], 0)
        self.assertEqual(float(m["chr1"].sum()), 0.0)
        p2 = self.write("pairs2.txt", pairs_text(extra_cols=False))
        _m, s2 = pc1.bin_valid_pairs(p2, SIZES, min_mapq=1)
        self.assertEqual(s2["mapq_missing"], len(PAIRS))
        m3, s3 = pc1.bin_valid_pairs(p, SIZES, min_mapq=42)
        self._check(m3, s3)

    def test_custom_bin_size(self):
        p = self.write("pairs.txt", pairs_text())
        m, _ = pc1.bin_valid_pairs(p, {"chr1": 2_500_000}, bin_size=1_000_000)
        self.assertEqual(m["chr1"].shape, (3, 3))
        # pairs 0,1,2 -> (0,0) x3 ; 3,4,5 -> (1,2) x3
        exp = np.zeros((3, 3))
        exp[0, 0] = 3
        exp[1, 2] = 3
        exp[2, 1] = 3
        np.testing.assert_array_equal(m["chr1"], exp)


class TestReadHicproMatrix(TmpDirMixin, unittest.TestCase):
    def _bins_bed(self, strip_chr=False):
        lines, idx = [], 1
        for chrom, size in SIZES.items():
            name = chrom[3:] if strip_chr else chrom
            for b in range(pc1.n_bins(size, 500_000)):
                lines.append(f"{name}\t{b * 500_000}\t{min((b + 1) * 500_000, size)}\t{idx}")
                idx += 1
        # an extra non-autosome bin that must be ignored
        lines.append(f"{'X' if strip_chr else 'chrX'}\t0\t500000\t{idx}")
        return "\n".join(lines) + "\n"

    def _matrix_txt(self):
        # upper-triangular HiC-Pro convention, 1-based ids; chr1 ids 1..5, chr2 ids 6..8, chrX id 9
        entries = [(1, 1, 1), (1, 2, 2), (3, 5, 3), (6, 8, 1), (7, 7, 1), (1, 6, 5), (9, 9, 4)]
        return "\n".join(f"{a}\t{b}\t{v}" for a, b, v in entries) + "\n"

    def test_matches_pairs(self):
        p_pairs = self.write("pairs.gz", pairs_text(), gz=True)
        from_pairs, _ = pc1.bin_valid_pairs(p_pairs, SIZES)
        bed = self.write("bins.bed", self._bins_bed(strip_chr=True))
        mat = self.write("m.matrix.gz", self._matrix_txt(), gz=True)
        from_matrix = pc1.read_hicpro_matrix(bed, mat, SIZES)
        self.assertEqual(set(from_matrix), set(from_pairs))
        for c in from_pairs:
            np.testing.assert_array_equal(from_matrix[c], from_pairs[c])

    def test_symmetric_input_not_doubled(self):
        bed = self.write("bins.bed", self._bins_bed())
        mat = self.write("m.matrix", "1\t2\t2\n2\t1\t2\n1\t1\t1\n")
        m = pc1.read_hicpro_matrix(bed, mat, SIZES)
        self.assertEqual(m["chr1"][0, 1], 2)
        self.assertEqual(m["chr1"][1, 0], 2)
        self.assertEqual(m["chr1"][0, 0], 1)

    def test_wrong_resolution_raises(self):
        bed = self.write("bins.bed", "chr1\t0\t250000\t1\nchr1\t250000\t500000\t2\n")
        mat = self.write("m.matrix", "1\t2\t1\n")
        with self.assertRaises(ValueError):
            pc1.read_hicpro_matrix(bed, mat, SIZES)


class TestIce(unittest.TestCase):
    def test_row_sums_equal_and_sparse_masked(self):
        raw, _labels, _bias = _block_model(n=30)
        raw[3, :] = 0.0
        raw[:, 3] = 0.0
        raw[5, :] = 0.0
        raw[:, 5] = 0.0
        raw[5, 6] = raw[6, 5] = 4.0  # only one non-zero entry: below min_nnz
        balanced, mask = pc1.ice(raw, min_nnz=10)
        self.assertFalse(mask[3])
        self.assertFalse(mask[5])
        self.assertEqual(int(mask.sum()), 28)
        self.assertTrue(np.isnan(balanced[3]).all())
        self.assertTrue(np.isnan(balanced[:, 5]).all())
        sub = balanced[np.ix_(mask, mask)]
        self.assertTrue(np.isfinite(sub).all())
        rs = sub.sum(axis=1)
        self.assertLess(np.max(np.abs(rs / rs.mean() - 1.0)), 1e-4)
        np.testing.assert_allclose(sub, sub.T)

    def test_bias_removed(self):
        raw, _labels, bias = _block_model(n=30, scale=20000.0)
        balanced, mask = pc1.ice(raw, tol=1e-9)
        # ICE of (b_i b_j K_ij) where K has equal row sums should reproduce K up to scale
        d = np.abs(np.arange(30)[:, None] - np.arange(30)[None, :])
        unbiased = raw / (bias[:, None] * bias[None, :])
        # correlation between balanced and unbiased entries should be very high
        b = balanced[np.ix_(mask, mask)].ravel()
        u = unbiased[np.ix_(mask, mask)].ravel()
        self.assertGreater(np.corrcoef(b, u)[0, 1], 0.99)

    def test_all_masked(self):
        balanced, mask = pc1.ice(np.zeros((4, 4)))
        self.assertFalse(mask.any())
        self.assertTrue(np.isnan(balanced).all())

    def test_isolated_rows_masked_after_restriction(self):
        # bin 0 has 12 non-zeros, all in bins 1..12, which themselves are sparse -> everything masked
        n = 14
        m = np.zeros((n, n))
        m[0, 1:13] = 1
        m[1:13, 0] = 1
        _b, mask = pc1.ice(m, min_nnz=10)
        self.assertFalse(mask.any())


class TestObservedOverExpected(unittest.TestCase):
    def test_diagonal_means_are_one(self):
        raw, _l, _b = _block_model(n=20)
        balanced, mask = pc1.ice(raw)
        oe = pc1.observed_over_expected(balanced, mask)
        n = raw.shape[0]
        for d in range(n):
            i = np.arange(n - d)
            vals = oe[i, i + d]
            vals = vals[np.isfinite(vals)]
            self.assertAlmostEqual(float(vals.mean()), 1.0, places=9)

    def test_empty_diagonal_is_one_and_mask_is_nan(self):
        m = np.zeros((4, 4))
        m[0, 0] = m[1, 1] = m[2, 2] = 2.0
        m[0, 1] = m[1, 0] = m[1, 2] = m[2, 1] = 1.0
        mask = np.array([True, True, True, False])
        oe = pc1.observed_over_expected(m, mask)
        self.assertEqual(oe[0, 2], 1.0)  # separation 2 has no signal -> 1.0
        self.assertTrue(np.isnan(oe[3]).all())
        self.assertTrue(np.isnan(oe[:, 3]).all())
        self.assertEqual(oe[0, 1], 1.0)


class TestOrient(unittest.TestCase):
    def test_flips_negative(self):
        v = np.array([1.0, 2.0, 3.0, np.nan, -1.0, -2.0])
        g = np.array([5, 4, 3, 100, 8, 9], dtype=float)
        out, rho = pc1.orient(v, g)
        self.assertLess(rho, -0.2)
        np.testing.assert_array_equal(out[np.isfinite(v)], -v[np.isfinite(v)])
        self.assertTrue(np.isnan(out[3]))

    def test_keeps_positive(self):
        v = np.array([1.0, 2.0, 3.0, 4.0])
        g = np.array([1.0, 2.0, 3.0, 4.0])
        out, rho = pc1.orient(v, g)
        self.assertAlmostEqual(rho, 1.0)
        np.testing.assert_array_equal(out, v)

    def test_below_threshold_is_nan(self):
        rng = np.random.default_rng(0)
        v = rng.standard_normal(200)
        g = rng.standard_normal(200)
        out, rho = pc1.orient(v, g, min_abs_rho=0.5)
        self.assertTrue(np.isfinite(rho))
        self.assertLess(abs(rho), 0.5)
        self.assertTrue(np.isnan(out).all())

    def test_constant_density_is_nan(self):
        out, rho = pc1.orient(np.array([1.0, 2.0, 3.0]), np.zeros(3))
        self.assertTrue(math.isnan(rho))
        self.assertTrue(np.isnan(out).all())


class TestTssDensity(TmpDirMixin, unittest.TestCase):
    def test_strand_aware_counts(self):
        rows = [
            # bin name chrom strand txStart txEnd cdsStart cdsEnd exonCount ...
            ("585", "NM_1", "chr1", "+", "10", "999_999"),        # TSS 10 -> bin 0
            ("585", "NM_2", "chr1", "-", "10", "500_000"),        # TSS 499_999 -> bin 0
            ("585", "NM_3", "chr1", "-", "10", "500_001"),        # TSS 500_000 -> bin 1
            ("585", "NM_4", "1", "+", "2_400_000", "2_500_000"),   # no chr prefix -> bin 4
            ("585", "NM_5", "chrX", "+", "10", "20"),             # ignored
            ("585", "NM_6", "chr1_random", "+", "10", "20"),      # ignored
            ("585", "NM_7", "chr2", "-", "0", "1_200_000"),       # TSS 1_199_999 -> chr2 bin 2
            ("585", "NM_8", "chr1", "+", "9_000_000", "9_000_100"),  # beyond size -> ignored
        ]
        text = "#bin\tname\tchrom\tstrand\ttxStart\ttxEnd\tcdsStart\tcdsEnd\n" + "".join(
            "\t".join(x.replace("_", "") for x in r) + "\t0\t0\t1\n" for r in rows)
        p = self.write("refseq.txt.gz", text, gz=True)
        d = pc1.tss_density(p, SIZES, 500_000)
        np.testing.assert_array_equal(d["chr1"], [2, 1, 0, 0, 1])
        np.testing.assert_array_equal(d["chr2"], [0, 0, 1])

    def test_without_bin_column(self):
        p = self.write("refseq.txt", "NM_1\tchr1\t-\t10\t500001\t0\t0\n")
        d = pc1.tss_density(p, SIZES, 500_000)
        np.testing.assert_array_equal(d["chr1"], [0, 1, 0, 0, 0])


class TestBedGraph(TmpDirMixin, unittest.TestCase):
    def test_round_trip(self):
        records = [
            ("chr1", 0, 500_000, 0.123456789012345678, 0.5),
            ("chr1", 500_000, 1_000_000, float("nan"), 0.5),
            ("chr1", 1_000_000, 1_234_567, -1.0 / 3.0, 0.5),
            ("chr2", 0, 500_000, 2.5e-7, 0.3),
        ]
        p = self.path("out.bedGraph")
        n = pc1.write_bedgraph(records, p)
        self.assertEqual(n, 3)
        back = pc1.read_bedgraph(p)
        expected = [(c, s, e, v) for c, s, e, v, _ in records if math.isfinite(v)]
        self.assertEqual(back, expected)
        with open(p) as fh:
            first = fh.readline().rstrip("\n").split("\t")
        self.assertEqual(first[:3], ["chr1", "0", "500000"])


class TestCli(TmpDirMixin, unittest.TestCase):
    def _write_inputs(self):
        raw, labels, _ = _block_model(n=40, scale=200.0)
        n = raw.shape[0]
        size = n * 500_000
        sizes_p = self.write("sizes.txt", f"1\t{size}\nchrX\t100\n")
        # expand the block-model matrix into an allValidPairs file (upper triangle, once per pair)
        lines = []
        k = 0
        for i in range(n):
            for j in range(i, n):
                for _ in range(int(raw[i, j])):
                    lines.append(f"r{k}\t1\t{i * 500_000 + 1}\t+\t1\t{j * 500_000 + 250_000}\t-\t100\t1\t2\t60\t60")
                    k += 1
        pairs_p = self.write("pairs.allValidPairs.gz", "\n".join(lines) + "\n", gz=True)
        density = _planted_density(labels)
        rows = []
        g = 0
        for b in range(n):
            for _ in range(int(density[b])):
                rows.append(f"1\tNM_{g}\tchr1\t+\t{b * 500_000 + 7}\t{b * 500_000 + 1000}\t0\t0\t1")
                g += 1
        refseq_p = self.write("refseq.txt.gz", "\n".join(rows) + "\n", gz=True)
        return sizes_p, pairs_p, refseq_p, raw, labels

    def test_pairs_and_matrix_commands(self):
        sizes_p, pairs_p, refseq_p, raw, labels = self._write_inputs()
        out_p = self.path("pc1.bedGraph")
        stats_p = self.path("stats.json")
        rc = pc1.main(["pairs", "--pairs", pairs_p, "--chrom-sizes", sizes_p, "--refseq", refseq_p,
                       "--out", out_p, "--stats", stats_p])
        self.assertEqual(rc, 0)
        back = pc1.read_bedgraph(out_p)
        self.assertEqual(len(back), 40)
        vals = np.array([v for _c, _s, _e, v in back])
        self.assertGreaterEqual(np.mean(np.sign(vals) == labels), 0.95)
        with open(stats_p) as fh:
            stats = json.load(fh)
        self.assertEqual(stats["pairs"]["kept"], int(np.triu(raw).sum()))
        self.assertEqual(stats["pairs"]["trans"], 0)
        self.assertEqual(stats["per_chrom"]["chr1"]["n_bins"], 40)
        self.assertGreater(stats["per_chrom"]["chr1"]["rho"], 0.2)
        self.assertIn("eigenvalue", stats["per_chrom"]["chr1"])

        # same data through the matrix path must give the identical bedGraph
        bins_lines = [f"1\t{b * 500_000}\t{(b + 1) * 500_000}\t{b + 1}" for b in range(40)]
        bed_p = self.write("bins.bed", "\n".join(bins_lines) + "\n")
        mat_lines = [f"{i + 1}\t{j + 1}\t{int(raw[i, j])}" for i in range(40) for j in range(i, 40) if raw[i, j]]
        mat_p = self.write("raw.matrix", "\n".join(mat_lines) + "\n")
        out2_p = self.path("pc1_matrix.bedGraph")
        rc = pc1.main(["matrix", "--bins", bed_p, "--matrix", mat_p, "--chrom-sizes", sizes_p,
                       "--refseq", refseq_p, "--out", out2_p])
        self.assertEqual(rc, 0)
        self.assertEqual(pc1.read_bedgraph(out2_p), back)


class PairsLayoutDetectionTests(unittest.TestCase):
    def test_4dn_layout_gives_same_matrix_as_hicpro(self):
        import tempfile, gzip, os
        sizes = {"chr1": 2_000_000, "chr2": 1_000_000}
        hic = ["r1\tchr1\t10\t+\tchr1\t600000\t-", "r2\t1\t1500000\t-\t1\t20\t+", "r3\tchr1\t5\t+\tchr2\t5\t+", "r4\tchr2\t100\t+\tchr2\t200\t-"]
        pairs = ["#columns: readID chr1 pos1 chr2 pos2 strand1 strand2", "r1\tchr1\t10\tchr1\t600000\t+\t-", "r2\t1\t1500000\t1\t20\t-\t+", "r3\tchr1\t5\tchr2\t5\t+\t+", "r4\tchr2\t100\tchr2\t200\t+\t-"]
        with tempfile.TemporaryDirectory() as d:
            a = os.path.join(d, "a.txt"); b = os.path.join(d, "b.txt.gz")
            open(a, "w").write("\n".join(hic) + "\n")
            with gzip.open(b, "wt") as fh:
                fh.write("\n".join(pairs) + "\n")
            ma, sa = pc1.bin_valid_pairs(a, sizes, 500_000)
            mb, sb = pc1.bin_valid_pairs(b, sizes, 500_000)
        self.assertEqual(sa["format"], "hicpro"); self.assertEqual(sb["format"], "pairs")
        for c in sizes:
            np.testing.assert_array_equal(ma[c], mb[c])
        self.assertEqual(sb["trans"], 1); self.assertEqual(sb["kept"], 3)


if __name__ == "__main__":
    unittest.main()
