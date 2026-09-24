import sys, unittest
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent)); import panel as PN
def mk(r):  # fake result dict
    return {"rho": r, "p_pos": 0.0002 if r > 0.05 else 0.5, "p_neg": 0.0002 if r < -0.05 else 0.5}
def res(nc, lv, spec):
    d = {n: {"A": mk(nc), "B": mk(nc)} for n in PN.P["non_cardiac"]}
    d["heart_LV"] = {"A": mk(lv), "B": mk(lv)}; d["LV_specific"] = {"A": mk(spec), "B": mk(spec)}
    return d
class T(unittest.TestCase):
    def test_labels(self):
        self.assertEqual(PN.label(res(0.12, 0.03, -0.10))["label"], "EROSION_SUPPORTED")
        self.assertEqual(PN.label(res(0.12, 0.10, 0.0))["label"], "P1_ONLY")
        self.assertEqual(PN.label(res(0.10, 0.20, 0.0))["label"], "LEAK_PATTERN")
        self.assertEqual(PN.label(res(0.10, 0.08, 0.10))["label"], "LEAK_PATTERN")
        self.assertEqual(PN.label(res(0.01, 0.01, 0.0))["label"], "NOT_SUPPORTED")
    def test_orient(self):
        chrom = np.array(["chr1"] * 50 + ["chr2"] * 50); tss = np.tile(np.arange(50.0), 2)
        v = np.concatenate([np.arange(50.0), -np.arange(50.0)])
        o = PN.orient(v, chrom, tss)
        self.assertTrue(np.all(np.diff(o[:50]) > 0) and np.all(np.diff(o[50:]) > 0))
    def test_tile_track_synthetic_bigwig(self):
        import pyBigWig, tempfile, os
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, "t.bw"); bw = pyBigWig.open(f, "w")
            bw.addHeader([("1", 1200000)])  # no chr prefix; 1.2 Mb chromosome
            bw.addEntries(["1"] * 3, [0, 500000, 1000000], ends=[500000, 1000000, 1200000], values=[1.0, 2.0, 3.0]); bw.close()
            chrom = np.array(["chr1", "chr1", "chr1", "chr2"]); start = np.array([0, 500000, 1000000, 0])
            v = PN.tile_track(f, chrom, start)
            self.assertEqual(v[0], 1.0); self.assertEqual(v[1], 2.0); self.assertEqual(v[2], 3.0)  # last tile clamped
            self.assertTrue(np.isnan(v[3]))
    def test_nan_rho_would_not_pass(self):
        d = res(0.12, 0.03, -0.10); d["heart_LV"]["A"]["rho"] = float("nan")
        self.assertNotEqual(PN.label(d)["label"], "LEAK_PATTERN")

if __name__ == "__main__": unittest.main()
