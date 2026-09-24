import gzip
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compartment as C  # noqa: E402


class TileMeans(unittest.TestCase):
    def test_tiles_cover_chromosome_in_order(self):
        t = C.tiles_for({"chr1": 1_200_000, "chr2": 500_000}, ["chr1", "chr2"], 500_000)
        self.assertEqual(t, [("chr1", 0, 500_000), ("chr1", 500_000, 1_000_000), ("chr1", 1_000_000, 1_200_000), ("chr2", 0, 500_000)])

    def test_coverage_weighted_mean_and_partial_cover(self):
        starts = [0, 100, 300]
        ends = [100, 200, 400]
        vals = [1.0, 3.0, float("nan")]
        means, cov = C.interval_tile_means(starts, ends, vals, [(0, 200), (150, 350), (500, 600)])
        self.assertAlmostEqual(means[0], 2.0)
        self.assertAlmostEqual(cov[0], 1.0)
        # tile 150-350: covered 150-200 by 3.0 (50 bp); 300-350 NaN excluded
        self.assertAlmostEqual(means[1], 3.0)
        self.assertAlmostEqual(cov[1], 50 / 200)
        self.assertTrue(np.isnan(means[2]))
        self.assertEqual(cov[2], 0.0)

    def test_rejects_unsorted(self):
        with self.assertRaises(ValueError):
            C.interval_tile_means([100, 0], [200, 100], [1, 2], [(0, 200)])

    def test_bedgraph_reader_and_tile_means(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.bedGraph.gz"
            with gzip.open(p, "wt") as fh:
                fh.write("track type=bedGraph\n")
                fh.write("chr2\t0\t500000\t-0.5\n")
                fh.write("chr1\t500000\t1000000\t2.0\n")
                fh.write("chr1\t0\t250000\t1.0\n")
            tiles = [("chr1", 0, 500000), ("chr1", 500000, 1000000), ("chr2", 0, 500000), ("chr3", 0, 500000)]
            m, cov = C.bedgraph_tile_means(p, tiles, 0.5)
            self.assertAlmostEqual(m[0], 1.0)  # half covered, passes 0.5
            self.assertAlmostEqual(cov[0], 0.5)
            self.assertAlmostEqual(m[1], 2.0)
            self.assertAlmostEqual(m[2], -0.5)
            self.assertTrue(np.isnan(m[3]))
            m2, _ = C.bedgraph_tile_means(p, tiles, 0.6)
            self.assertTrue(np.isnan(m2[0]))

    def test_bigwig_tile_means_matches_manual(self):
        import pyBigWig

        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "t.bw"
            bw = pyBigWig.open(str(p), "w")
            bw.addHeader([("chr1", 1_000_000)])
            bw.addEntries(["chr1"] * 3, [0, 10_000, 600_000], ends=[10_000, 20_000, 700_000], values=[1.0, 3.0, 5.0])
            bw.close()
            tiles = [("chr1", 0, 500_000), ("chr1", 500_000, 1_000_000)]
            m, cov = C.bigwig_tile_means(p, tiles, 0.0)
            self.assertAlmostEqual(m[0], 2.0)
            self.assertAlmostEqual(cov[0], 20_000 / 500_000)
            self.assertAlmostEqual(m[1], 5.0)
            m2, _ = C.bigwig_tile_means(p, tiles, 0.5)
            self.assertTrue(np.isnan(m2[0]))

    def test_tss_density(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "ref.txt.gz"
            rows = [
                ["0", "NM_1", "chr1", "+", "100", "900", "0", "0", "1", "", "", "0", "A", "", "", ""],
                ["0", "NM_2", "chr1", "-", "100", "600000", "0", "0", "1", "", "", "0", "B", "", "", ""],
                ["0", "NM_3", "chr1", "+", "100", "900", "0", "0", "1", "", "", "0", "A", "", "", ""],  # duplicate TSS
                ["0", "NM_4", "chrX", "+", "100", "900", "0", "0", "1", "", "", "0", "X", "", "", ""],
            ]
            with gzip.open(p, "wt") as fh:
                for r in rows:
                    fh.write("\t".join(r) + "\n")
            tiles = [("chr1", 0, 500_000), ("chr1", 500_000, 1_000_000)]
            dens = C.tss_density(p, tiles, ["chr1"], 500_000)
            self.assertEqual(list(dens), [1.0, 1.0])


class Statistics(unittest.TestCase):
    def test_spearman_matches_scipy(self):
        rng = np.random.default_rng(1)
        for _ in range(20):
            x = rng.normal(size=200)
            y = 0.3 * x + rng.normal(size=200)
            self.assertAlmostEqual(C.spearman(x, y), stats.spearmanr(x, y).statistic, places=12)

    def test_partial_spearman_removes_shared_covariate(self):
        rng = np.random.default_rng(2)
        z = rng.normal(size=5000)
        x = z + 0.1 * rng.normal(size=5000)
        y = z + 0.1 * rng.normal(size=5000)
        self.assertGreater(C.spearman(x, y), 0.9)
        self.assertLess(abs(C.partial_spearman(x, y, [z])), 0.1)

    def test_partial_spearman_keeps_independent_signal(self):
        rng = np.random.default_rng(3)
        z = rng.normal(size=5000)
        u = rng.normal(size=5000)
        x = z + u
        y = z - u
        self.assertLess(C.partial_spearman(x, y, [z]), -0.9)

    def test_circular_shift_preserves_within_chromosome_multiset(self):
        rng = np.random.default_rng(4)
        chrom = np.array(["a"] * 5 + ["b"] * 7 + ["c"])
        vals = np.arange(13, dtype=float)
        for _ in range(50):
            perm = C.circular_shift_index(chrom, rng)
            self.assertEqual(sorted(perm.tolist()), list(range(13)))
            for c in "ab":
                idx = np.flatnonzero(chrom == c)
                self.assertEqual(sorted(vals[perm][idx].tolist()), sorted(vals[idx].tolist()))
                self.assertFalse(np.array_equal(perm[idx], idx))  # non-zero offset
            self.assertEqual(perm[12], 12)

    def test_permutation_p_identity_is_max_extreme(self):
        # constant statistic -> p = 1
        chrom = np.array(["a"] * 20)
        obs, p_neg, p_pos, null = C.permutation_test(lambda perm: 0.0, chrom, 99, 0)
        self.assertEqual(p_neg, 1.0)
        self.assertEqual(p_pos, 1.0)

    def test_permutation_test_reproducible(self):
        rng = np.random.default_rng(5)
        chrom = np.repeat([f"c{i}" for i in range(4)], 50)
        x = rng.normal(size=200)
        y = rng.normal(size=200)
        f = lambda perm: C.spearman(x[perm], y)  # noqa: E731
        a = C.permutation_test(f, chrom, 200, 7)
        b = C.permutation_test(f, chrom, 200, 7)
        self.assertEqual(a[1], b[1])
        self.assertTrue(np.array_equal(a[3], b[3]))


class EndToEnd(unittest.TestCase):
    def _make(self, d: Path, effect: float, n_chr=6, tiles_per=120, seed=11):
        rng = np.random.default_rng(seed)
        chroms = [f"chr{i}" for i in range(1, n_chr + 1)]
        tiles = [(c, k * 500_000, (k + 1) * 500_000) for c in chroms for k in range(tiles_per)]
        n = len(tiles)
        # smooth baseline compartment signal
        base = np.concatenate([np.convolve(rng.normal(size=tiles_per + 10), np.ones(11) / 11, mode="valid") for _ in chroms])
        base_lam = -base + 0.3 * rng.normal(size=n)  # lamina anti-correlates with PC1
        dlam = rng.normal(size=n)
        dpc1_signal = effect * dlam
        density = np.clip(np.round(5 + 4 * base + rng.normal(size=n)), 0, None)
        pred = d / "predictor.tsv"
        with open(pred, "w") as fh:
            fh.write("tile_id\tchrom\tstart\tend\tsiScr_mCh\tsiLMNA_mCh\tdlam_mCh\tsiScr_DNK\tsiLMNA_DNK\tdlam_DNK\tcov_min\ttss_count\n")
            for i, (c, s, e) in enumerate(tiles):
                fh.write(f"{c}:{s}-{e}\t{c}\t{s}\t{e}\t{base_lam[i]:.6g}\t{base_lam[i]+dlam[i]:.6g}\t{dlam[i]:.6g}\t{base_lam[i]:.6g}\t{base_lam[i]+dlam[i]:.6g}\t{dlam[i]:.6g}\t1.0\t{int(density[i])}\n")
        samples = {}
        odir = d / "outcome"
        odir.mkdir()
        spec = [("GSM1", "corrected_1", "rep1", 0), ("GSM2", "corrected_1", "rep2", 0), ("GSM3", "corrected_2", "rep1", 0), ("GSM4", "corrected_2", "rep2", 0), ("GSM5", "mutant", "rep1", 1), ("GSM6", "mutant", "rep2", 1)]
        for gsm, line, rep, is_mut in spec:
            vals = base + 0.15 * rng.normal(size=n) + (dpc1_signal if is_mut else 0.0)
            fn = f"{gsm}.PC1.bedGraph.gz"
            with gzip.open(odir / fn, "wt") as fh:
                for (c, s, e), v in zip(tiles, vals):
                    fh.write(f"{c}\t{s}\t{e}\t{v:.5f}\n")
            samples[gsm] = {"line": line, "replicate": rep, "filename": fn}
        reg = {
            "campaign_id": "synthetic",
            "tiles": {"size": 500_000, "chromosomes": chroms, "min_coverage": 0.5},
            "predictor": {"files": {}},
            "outcome": {"samples": samples, "corrected_lines": ["corrected_1", "corrected_2"]},
            "orientation": {"min_abs_rho_gene_density": 0.3, "min_rho_per_chromosome": 0.2, "floor_sensitivity": [0.0, 0.3]},
            "null": {"permutations": 199, "seed": 3},
            "pass_criteria": {"unadjusted_rho_max": -0.10, "adjusted_rho_max": -0.05, "p_max": 0.01, "min_eligible_tiles": 500, "adjusted_to_unadjusted_ratio_min": 0.5, "standardised_unadjusted_rho_max": -0.10},
        }
        rp = d / "reg.json"
        C.dump_json(reg, rp)
        return reg, pred, odir, rp

    def test_planted_negative_effect_passes(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            reg, pred, odir, rp = self._make(d, effect=-0.4)
            s = C.run_registered(reg, pred, odir, d / "res", C.sha256_path(rp), None, allow_unfrozen=True)
            self.assertTrue(s["orientation"]["ok"])
            self.assertFalse(s["orientation"]["flipped"])
            self.assertTrue(s["registered_pass"])
            self.assertFalse(s["registered_opposite_direction"])
            self.assertEqual(s["n_tiles_eligible"], 720)
            for r in s["contrasts"].values():
                self.assertLess(r["unadjusted_rho"], -0.10)
                self.assertLess(r["adjusted_rho"], -0.05)
                self.assertTrue(r["replicate_pairs_all_negative"])
            self.assertTrue((d / "res" / "summary.json").exists())
            self.assertTrue((d / "res" / "tiles.tsv").exists())

    def test_null_does_not_pass(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            reg, pred, odir, rp = self._make(d, effect=0.0, seed=12)
            s = C.run_registered(reg, pred, odir, d / "res", "x", None, allow_unfrozen=True)
            self.assertFalse(s["registered_pass"])
            for r in s["contrasts"].values():
                self.assertGreater(r["unadjusted_p_negative"], 0.01)

    def test_positive_effect_is_opposite_direction(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            reg, pred, odir, rp = self._make(d, effect=0.4, seed=13)
            s = C.run_registered(reg, pred, odir, d / "res", "x", None, allow_unfrozen=True)
            self.assertFalse(s["registered_pass"])
            self.assertTrue(s["registered_opposite_direction"])

    def test_sign_flip_is_detected_and_result_unchanged(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            reg, pred, odir, rp = self._make(d, effect=-0.4)
            s1 = C.run_registered(reg, pred, odir, d / "r1", "x", None, allow_unfrozen=True)
            for fn in os.listdir(odir):
                p = odir / fn
                lines = gzip.open(p, "rt").read().splitlines()
                with gzip.open(p, "wt") as fh:
                    for l in lines:
                        c, s, e, v = l.split("\t")
                        fh.write(f"{c}\t{s}\t{e}\t{-float(v):.5f}\n")
            s2 = C.run_registered(reg, pred, odir, d / "r2", "x", None, allow_unfrozen=True)
            self.assertTrue(s2["orientation"]["flipped"])
            self.assertEqual(sorted(s2["orientation"]["flipped_chromosomes"]), sorted(reg["tiles"]["chromosomes"]))
            self.assertEqual(s2["orientation"]["excluded_chromosomes"], [])
            self.assertTrue(s2["registered_pass"])
            for c in s1["contrasts"]:
                self.assertAlmostEqual(s1["contrasts"][c]["unadjusted_rho"], s2["contrasts"][c]["unadjusted_rho"], places=4)

    def test_single_chromosome_flip_is_repaired(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            reg, pred, odir, rp = self._make(d, effect=-0.4)
            s1 = C.run_registered(reg, pred, odir, d / "r1", "x", None, allow_unfrozen=True)
            for fn in os.listdir(odir):
                p = odir / fn
                lines = gzip.open(p, "rt").read().splitlines()
                with gzip.open(p, "wt") as fh:
                    for l in lines:
                        c, s, e, v = l.split("\t")
                        sign = -1.0 if c == "chr3" else 1.0
                        fh.write(f"{c}\t{s}\t{e}\t{sign*float(v):.5f}\n")
            s2 = C.run_registered(reg, pred, odir, d / "r2", "x", None, allow_unfrozen=True)
            self.assertEqual(s2["orientation"]["flipped_chromosomes"], ["chr3"])
            self.assertEqual(s2["n_tiles_eligible"], s1["n_tiles_eligible"])
            for c in s1["contrasts"]:
                self.assertAlmostEqual(s1["contrasts"][c]["unadjusted_rho"], s2["contrasts"][c]["unadjusted_rho"], places=4)

    def test_uninformative_chromosome_is_excluded(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            reg, pred, odir, rp = self._make(d, effect=-0.4)
            rng = np.random.default_rng(99)
            for fn in os.listdir(odir):
                p = odir / fn
                lines = gzip.open(p, "rt").read().splitlines()
                with gzip.open(p, "wt") as fh:
                    for l in lines:
                        c, s, e, v = l.split("\t")
                        if c == "chr2":
                            v = f"{rng.normal():.5f}"  # destroys gene-density relation on chr2
                        fh.write(f"{c}\t{s}\t{e}\t{v}\n")
            s2 = C.run_registered(reg, pred, odir, d / "r2", "x", None, allow_unfrozen=True)
            self.assertIn("chr2", s2["orientation"]["excluded_chromosomes"])
            self.assertEqual(s2["n_tiles_eligible"], 600)
            self.assertEqual(s2["orientation"]["per_chromosome"]["chr2"]["excluded"], True)

    def test_too_few_tiles_fails(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            reg, pred, odir, rp = self._make(d, effect=-0.4)
            reg["pass_criteria"]["min_eligible_tiles"] = 10_000
            s = C.run_registered(reg, pred, odir, d / "res", "x", None, allow_unfrozen=True)
            self.assertFalse(s["registered_pass"])

    def test_freeze_guard_rejects_edited_registration(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            reg, pred, odir, rp = self._make(d, effect=-0.4)
            here = Path(C.__file__).resolve().parent
            good = {"registration_sha256": C.sha256_path(rp), "code_sha256": C.sha256_path(C.__file__), "test_sha256": C.sha256_path(here / "test_compartment.py"), "requirements_lock_sha256": C.sha256_path(here / "requirements.lock"), "predictor_tsv_sha256": C.sha256_path(pred)}
            fp = d / "freeze.json"
            C.dump_json(dict(good, registration_sha256="0" * 64), fp)
            ip = d / "intake.json"
            C.dump_json({"freeze_sha256": C.sha256_path(fp), "files": [{"filename": m["filename"], "sha256": C.sha256_path(odir / m["filename"])} for m in reg["outcome"]["samples"].values()]}, ip)
            args = ["run", "--registration", str(rp), "--freeze", str(fp), "--intake", str(ip), "--predictor", str(pred), "--outcome-dir", str(odir), "--out-dir", str(d / "res")]
            with self.assertRaises(SystemExit):
                C.main(args)
            # correct freeze but intake bound to a different freeze hash
            C.dump_json(good, fp)
            with self.assertRaises(SystemExit):
                C.main(args)
            # correct freeze and intake binding, but one outcome file substituted
            C.dump_json({"freeze_sha256": C.sha256_path(fp), "files": [{"filename": m["filename"], "sha256": C.sha256_path(odir / m["filename"])} for m in reg["outcome"]["samples"].values()]}, ip)
            first = next(iter(reg["outcome"]["samples"].values()))["filename"]
            with gzip.open(odir / first, "at") as fh:
                fh.write("chr1\t0\t500000\t0.0\n")
            with self.assertRaises(SystemExit):
                C.main(args)
            self.assertFalse((d / "res" / "summary.json").exists())

    def test_unfrozen_run_is_refused_by_default(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            reg, pred, odir, rp = self._make(d, effect=-0.4)
            with self.assertRaises(SystemExit):
                C.run_registered(reg, pred, odir, d / "res", "x", None)
            self.assertFalse((d / "res" / "summary.json").exists())

    def test_full_cli_run_with_valid_receipts(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            reg, pred, odir, rp = self._make(d, effect=-0.4)
            here = Path(C.__file__).resolve().parent
            fp = d / "freeze.json"
            C.dump_json({"registration_sha256": C.sha256_path(rp), "code_sha256": C.sha256_path(C.__file__), "test_sha256": C.sha256_path(here / "test_compartment.py"), "requirements_lock_sha256": C.sha256_path(here / "requirements.lock"), "predictor_tsv_sha256": C.sha256_path(pred)}, fp)
            ip = d / "intake.json"
            C.dump_json({"freeze_sha256": C.sha256_path(fp), "files": [{"filename": m["filename"], "sha256": C.sha256_path(odir / m["filename"])} for m in reg["outcome"]["samples"].values()]}, ip)
            rc = C.main(["run", "--registration", str(rp), "--freeze", str(fp), "--intake", str(ip), "--predictor", str(pred), "--outcome-dir", str(odir), "--out-dir", str(d / "res")])
            self.assertEqual(rc, 0)
            s = json.load(open(d / "res" / "summary.json"))
            self.assertTrue(s["registered_run"])
            self.assertTrue(s["outcome_hashes_verified_against_intake"])
            self.assertTrue(s["registered_pass"])

    def test_pure_amplitude_artefact_does_not_pass(self):
        # mutant PC1 = 1.25 x corrected PC1 with no dlam relation: unadjusted arm can
        # look "significant" through the baseline/dlam correlation; the adjusted,
        # ratio and standardised components must block it.
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            reg, pred, odir, rp = self._make(d, effect=0.0, seed=21)
            for fn in os.listdir(odir):
                p = odir / fn
                lines = gzip.open(p, "rt").read().splitlines()
                with gzip.open(p, "wt") as fh:
                    for l in lines:
                        c, s, e, v = l.split("\t")
                        scale = 1.25 if fn.startswith(("GSM5", "GSM6")) else 1.0
                        fh.write(f"{c}\t{s}\t{e}\t{scale*float(v):.5f}\n")
            s = C.run_registered(reg, pred, odir, d / "res", "x", None, allow_unfrozen=True)
            self.assertFalse(s["registered_pass"])
            for r in s["contrasts"].values():
                self.assertFalse(r["component_pass"]["adjusted_to_unadjusted_ratio"] and r["component_pass"]["standardised_effect"] and r["component_pass"]["adjusted_effect"])
            for c in s["scale_diagnostic"].values():
                self.assertAlmostEqual(c["median_chromosome_sd_ratio"], 1.25, delta=0.08)

    def test_scale_diagnostic_and_sensitivity_reported(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            reg, pred, odir, rp = self._make(d, effect=-0.4)
            s = C.run_registered(reg, pred, odir, d / "res", "x", None, allow_unfrozen=True)
            self.assertEqual(sorted(s["orientation_floor_sensitivity"].keys()), ["0.0", "0.3"])
            for r in s["contrasts"].values():
                self.assertLess(r["standardised"]["unadjusted_rho"], -0.10)
                self.assertTrue(r["component_pass"]["adjusted_to_unadjusted_ratio"])


if __name__ == "__main__":
    unittest.main()
