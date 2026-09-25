import json, sys, tempfile, unittest
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import libvar as V

def mk_res(pairs):
    """pairs: {id: (rho_raw, rho_sf)} -> result dict in run() shape."""
    out = {}
    for k, (rr, rs) in pairs.items():
        out[k] = {"raw": {"rho": rr, "p_neg": 0.001 if rr < 0 else 1.0, "p_pos": 0.001 if rr > 0 else 1.0, "n": 4000},
                  "scale_free": {"rho": rs}}
    return out

def world(seed, lib_gc=0.0, n_chr=6, per=700, noise=0.15):
    """Two 'same-condition' tracks; lib_gc adds a GC-correlated bias to track B."""
    rng = np.random.default_rng(seed)
    chrom = np.repeat([f"chr{i+1}" for i in range(n_chr)], per)
    walk = np.concatenate([np.convolve(rng.normal(size=per), np.ones(15) / 15, "same") for _ in range(n_chr)])
    gc = -walk + 0.3 * rng.normal(size=walk.size)
    lam = walk / walk.std(); zgc = (gc - gc.mean()) / gc.std()
    tss = rng.poisson(2 * np.exp(-0.5 * lam)).astype(float)
    a = np.tanh(lam) * 1.5 + noise * rng.normal(size=lam.size)
    b = np.tanh(lam) * 1.5 + lib_gc * zgc + noise * rng.normal(size=lam.size)
    return chrom, gc, tss, a, b

class T(unittest.TestCase):
    def test_pairs_resolve_and_count(self):
        ids = list(V.P["pairs"])
        self.assertEqual(len(ids), 22)
        self.assertEqual(len([k for k in ids if k.startswith("LV_opc")]), 6)
        for k, v in V.P["pairs"].items():
            files = V.P["cohorts"][v["cohort"]]["files"]
            self.assertIn(v["a"], files, k); self.assertIn(v["b"], files, k)

    def test_label_systematic(self):
        pairs = {f"LV_x{i}": (-0.2, -0.15) for i in range(16)}; pairs.update({f"LV_opc_{i}": (-0.1, -0.08) for i in range(6)})
        lab, pooled = V.pooled_label(mk_res(pairs))
        self.assertEqual(lab, "SYSTEMATIC"); self.assertTrue(pooled["p4"])

    def test_label_p4_boundary_exactly_four(self):
        pairs = {f"LV_x{i}": (-0.2, -0.15) for i in range(16)}
        pairs.update({f"LV_opc_{i}": (-0.1, -0.08) for i in range(4)}); pairs.update({f"LV_opc_z{i}": (0.01, 0.0) for i in range(2)})
        lab, pooled = V.pooled_label(mk_res(pairs))
        self.assertEqual(lab, "SYSTEMATIC"); self.assertTrue(pooled["p4"])
        pairs[f"LV_opc_0"] = (0.01, 0.0)
        lab2, pooled2 = V.pooled_label(mk_res(pairs))
        self.assertEqual(lab2, "PARTIAL"); self.assertFalse(pooled2["p4"])

    def test_label_partial_when_holdout_flat(self):
        pairs = {f"LV_x{i}": (-0.2, -0.15) for i in range(16)}; pairs.update({f"LV_opc_{i}": (0.01, 0.0) for i in range(6)})
        lab, pooled = V.pooled_label(mk_res(pairs))
        self.assertEqual(lab, "PARTIAL"); self.assertFalse(pooled["p4"])

    def test_label_not_supported_when_flat(self):
        pairs = {f"LV_x{i}": (0.01, 0.0) for i in range(16)}; pairs.update({f"LV_opc_{i}": (0.01, 0.0) for i in range(6)})
        lab, _ = V.pooled_label(mk_res(pairs))
        self.assertEqual(lab, "NOT_SUPPORTED")

    def test_p2_needs_four_eligible(self):
        pairs = {f"LV_x{i}": (-0.2, -0.15) for i in range(3)}; pairs.update({f"LV_z{i}": (0.01, 0.0) for i in range(15)})
        pairs.update({f"LV_opc_{i}": (0.01, 0.0) for i in range(6)})
        lab, pooled = V.pooled_label(mk_res(pairs))
        self.assertNotEqual(lab, "SYSTEMATIC"); self.assertFalse(pooled["p2"])

    def test_pair_test_recovers_planted_gradient(self):
        chrom, gc, tss, a, b = world(3, lib_gc=0.4)
        r = V.pair_test(a, b, gc, tss, chrom, 123)
        self.assertLess(r["rho"], -0.3); self.assertLessEqual(r["p_neg"], 0.01)

    def test_pair_test_flat_world(self):
        chrom, gc, tss, a, b = world(4, lib_gc=0.0)
        r = V.pair_test(a, b, gc, tss, chrom, 124)
        self.assertTrue(np.isfinite(r["rho"])); self.assertLess(abs(r["rho"]), 0.5)

    def test_run_pairs_aborts_on_small_n(self):
        chrom, gc, tss, a, b = world(5, n_chr=1, per=700)
        with self.assertRaises(SystemExit):
            V.run_pairs({"P1": ("a", "b")}, {"a": a, "b": b}, gc, tss, chrom, 1, n_shift_check=3000)

    def test_prior_sha_both_receipt_styles(self):
        with tempfile.TemporaryDirectory() as d:
            p1 = Path(d) / "intake.json"; p2 = Path(d) / "inputs.discovery.json"
            json.dump({"files": {"k": {"file": "x.bw", "sha256": "aaa"}}}, open(p1, "w"))
            json.dump({"files": [{"path": "y.bw", "sha256": "bbb"}]}, open(p2, "w"))
            old = dict(V.RECEIPTS)
            try:
                V.RECEIPTS["mef"], V.RECEIPTS["hipsc"] = p1, p2
                self.assertEqual(V.prior_sha("mef", "x.bw"), "aaa")
                self.assertEqual(V.prior_sha("hipsc", "y.bw"), "bbb")
                self.assertIsNone(V.prior_sha("mef", "zz.bw"))
            finally:
                V.RECEIPTS.update(old)

    def test_check_build_and_tile_values(self):
        import pyBigWig
        with tempfile.TemporaryDirectory() as d:
            for name, L in (("hg38.bw", 248956422), ("mm9.bw", 197195432), ("mm10.bw", 195471971)):
                bw = pyBigWig.open(str(Path(d) / name), "w"); bw.addHeader([("chr1", L)])
                bw.addEntries(["chr1"], [0], ends=[150000], values=[2.0]); bw.close()
            self.assertTrue(V.check_build(Path(d) / "hg38.bw", 248956422))
            self.assertFalse(V.check_build(Path(d) / "hg38.bw", 195471971))
            self.assertTrue(V.check_build(Path(d) / "mm10.bw", 195471971))
            c, s, e = np.array(["chr1"]), np.array([0]), np.array([500000])
            self.assertTrue(np.isnan(V.tile_values(Path(d) / "mm10.bw", c, s, e, 0.5)[0]))
            self.assertEqual(V.tile_values(Path(d) / "mm10.bw", c, s, e, 0.1)[0], 2.0)

    def test_seed_order_matches_protocol(self):
        # every registered pair gets a distinct seed block in pair order; XC block starts at 20262901
        mine = [k for k, v in V.P["pairs"].items() if v["cohort"] == "opc"]
        self.assertEqual(mine, ["LV_opc_pf_8_9", "LV_opc_pf_8_10", "LV_opc_pf_9_10",
                                "LV_opc_t3_18_19", "LV_opc_t3_18_20", "LV_opc_t3_19_20"])

if __name__ == "__main__":
    unittest.main()
