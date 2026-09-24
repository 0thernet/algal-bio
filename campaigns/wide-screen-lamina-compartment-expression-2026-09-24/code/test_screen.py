import json, subprocess, sys, tempfile, unittest
from pathlib import Path
import numpy as np
import screen as S

def make(d, rho_plant, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for c in range(1, 23):
        n = 240
        # smooth (autocorrelated) latent fields per chromosome
        base = np.convolve(rng.normal(size=n + 20), np.ones(21) / 21, "valid")[:n]
        noise = np.convolve(rng.normal(size=n + 20), np.ones(21) / 21, "valid")[:n]
        x = base; y = rho_plant * base + np.sqrt(1 - rho_plant**2) * noise
        z = np.convolve(rng.normal(size=n + 20), np.ones(21) / 21, "valid")[:n]
        for i in range(n):
            rows.append((f"chr{c}", i * 500000, x[i], y[i], z[i], rng.normal()))
    p = Path(d) / "f.tsv"
    with open(p, "w") as fh:
        fh.write("tile_id\tchrom\tstart\tX\tY\tZ\tW\n")
        for c, s, x, y, z, w in rows: fh.write(f"{c}:{s}\t{c}\t{s}\t{x}\t{y}\t{z}\t{w}\n")
    cfg = {"predictors": ["X", "Z", "W"], "outcomes": ["Y"], "covariates": [], "excluded_pairs": [],
           "selection": {"n_shift": 200, "seed": 1, "min_n": 100, "min_abs_rho": 0.1, "p_max": 0.01},
           "confirmation": {"n_shift": 200, "seed": 2, "min_n": 100, "min_abs_rho": 0.05, "alpha": 0.05}}
    json.dump(cfg, open(Path(d) / "c.json", "w"))
    return p, Path(d) / "c.json"

def freeze_survivors(d):
    import hashlib
    json.dump({"sha256": {"results/discovery.json": hashlib.sha256(open(f"{d}/disc.json", "rb").read()).hexdigest()}},
              open(f"{d}/freeze-survivors.json", "w"))

def run(d, f, c):
    subprocess.run([sys.executable, "screen.py", "discovery", "--features", str(f), "--config", str(c), "--out", f"{d}/disc.json"], check=True, capture_output=True)
    freeze_survivors(d)
    subprocess.run([sys.executable, "screen.py", "confirm", "--features", str(f), "--config", str(c), "--survivors", f"{d}/disc.json", "--out", f"{d}/conf.json"], check=True, capture_output=True)
    return json.load(open(f"{d}/disc.json")), json.load(open(f"{d}/conf.json"))

class ScreenTests(unittest.TestCase):
    def test_planted_signal_survives_and_confirms(self):
        with tempfile.TemporaryDirectory() as d:
            disc, conf = run(d, *make(d, 0.5))
            self.assertIn({"predictor": "X", "outcome": "Y", "sign": 1}, disc["survivors"])
            self.assertTrue(any(r["predictor"] == "X" and r["confirmed"] for r in conf["results"]))

    def test_null_rarely_survives(self):
        hits = 0
        for s in range(4):
            with tempfile.TemporaryDirectory() as d:
                disc, conf = run(d, *make(d, 0.0, seed=10 + s))
                hits += sum(r["confirmed"] for r in conf["results"])
        self.assertEqual(hits, 0)

    def test_confirm_uses_only_even_chromosomes(self):
        chrom = np.array(["chr1", "chr2", "chr21", "chr22"])
        self.assertEqual(list(S.half(chrom, "even")), [False, True, False, True])

    def test_shift_stays_within_chromosome(self):
        rng = np.random.default_rng(0)
        chrom = np.array(["chr1"] * 5 + ["chr2"] * 5); x = np.arange(10.0)
        y = S.shift_within(x, chrom, rng)
        self.assertEqual(sorted(y[:5]), list(range(5))); self.assertEqual(sorted(y[5:]), list(range(5, 10)))

    def test_excluded_and_same_source_pairs_dropped(self):
        cfg = {"predictors": ["A", "B", "C"], "outcomes": ["B"], "excluded_pairs": [["A", "B"]], "same_source_groups": [["B", "C"]]}
        self.assertEqual(S.pairs_from(cfg), [])

    def test_covariate_removes_confounded_pair(self):
        # X and Y both track Z; with Z as covariate the X-Y pair must not confirm
        with tempfile.TemporaryDirectory() as d:
            rng = np.random.default_rng(3); rows = []
            sm = lambda: np.convolve(rng.normal(size=260), np.ones(21) / 21, "valid")[:240]
            for c in range(1, 23):
                z, a, b = sm(), sm(), sm()
                for i in range(240): rows.append((c, i, z[i] + 0.4 * a[i], z[i] + 0.4 * b[i], z[i]))
            f = Path(d) / "f.tsv"
            with open(f, "w") as fh:
                fh.write("tile_id\tchrom\tstart\tX\tY\tZ\n")
                for c, i, x, y, z in rows: fh.write(f"chr{c}:{i}\tchr{c}\t{i}\t{x}\t{y}\t{z}\n")
            base = {"predictors": ["X"], "outcomes": ["Y"], "excluded_pairs": [],
                    "selection": {"n_shift": 200, "seed": 1, "min_n": 100, "min_abs_rho": 0.1, "p_max": 0.01},
                    "confirmation": {"n_shift": 200, "seed": 2, "min_n": 100, "min_abs_rho": 0.05, "alpha": 0.05}}
            json.dump(dict(base, covariates=[]), open(Path(d) / "c.json", "w"))
            disc, _ = run(d, f, Path(d) / "c.json")
            self.assertEqual(len(disc["survivors"]), 1)  # confounded pair passes unadjusted
            json.dump(dict(base, covariates=["Z"]), open(Path(d) / "c.json", "w"))
            disc, conf = run(d, f, Path(d) / "c.json")
            self.assertFalse(any(r["confirmed"] for r in conf["results"]))

    def test_pair_covariates_extra_and_self_drop(self):
        cfg = {"covariates": ["gc", "base_a"], "feature_extra_covariates": {"delta_b": ["base_b"]}}
        self.assertEqual(S.pair_covariates(cfg, "x", "delta_b"), ["gc", "base_a", "base_b"])
        self.assertEqual(S.pair_covariates(cfg, "delta_b", "base_a"), ["gc", "base_b"])
        self.assertEqual(S.pair_covariates(cfg, "base_b", "delta_b"), ["gc", "base_a"])

    def test_exclusion_is_unordered(self):
        cfg = {"predictors": ["A", "B"], "outcomes": ["A", "B"], "excluded_pairs": [["B", "A"]]}
        self.assertEqual(S.pairs_from(cfg), [])

    def test_min_shift(self):
        chrom = np.array(["chr1"] * 100); x = np.arange(100.0)
        for s in range(50):
            y = S.shift_within(x, chrom, np.random.default_rng(s))
            k = (100 - y[0]) % 100
            self.assertTrue(10 <= k <= 90)

    def test_confirm_refuses_tampered_survivors(self):
        with tempfile.TemporaryDirectory() as d:
            f, c = make(d, 0.5)
            subprocess.run([sys.executable, "screen.py", "discovery", "--features", str(f), "--config", str(c), "--out", f"{d}/disc.json"], check=True, capture_output=True)
            freeze_survivors(d)
            j = json.load(open(f"{d}/disc.json")); j["survivors"].append({"predictor": "W", "outcome": "Y", "sign": 1})
            json.dump(j, open(f"{d}/disc.json", "w"))
            r = subprocess.run([sys.executable, "screen.py", "confirm", "--features", str(f), "--config", str(c), "--survivors", f"{d}/disc.json", "--out", f"{d}/conf.json"], capture_output=True)
            self.assertNotEqual(r.returncode, 0)
            self.assertFalse(Path(f"{d}/conf.json").exists())

    def test_discovery_stats_in_separate_file(self):
        with tempfile.TemporaryDirectory() as d:
            disc, _ = run(d, *make(d, 0.5))
            self.assertNotIn("all", disc)
            self.assertTrue(Path(f"{d}/disc-all.json").exists())

if __name__ == "__main__":
    unittest.main()
