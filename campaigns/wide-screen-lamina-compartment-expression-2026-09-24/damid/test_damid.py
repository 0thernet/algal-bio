import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import damid as DM
def r(x): return {"rho": x, "p_neg": 0.0002 if x <= -0.05 else 0.5, "p_pos": 0.0002 if x >= 0.05 else 0.5}
class T(unittest.TestCase):
    def test_labels(self):
        self.assertEqual(DM.label({"P_batch": r(-0.2), "P_all": r(-0.2), "PL_within": r(0.01), "PL_cross": r(-0.05)}), "REPLICATED")
        self.assertEqual(DM.label({"P_batch": r(-0.2), "P_all": r(-0.2), "PL_within": r(0.01), "PL_cross": r(-0.15)}), "DIRECTION_ONLY")
        self.assertEqual(DM.label({"P_batch": r(-0.2), "P_all": r(-0.02), "PL_within": r(0.0), "PL_cross": r(0.0)}), "NOT_REPLICATED")
        self.assertEqual(DM.label({"P_batch": r(0.2), "P_all": r(0.1), "PL_within": r(0.0), "PL_cross": r(0.0)}), "OPPOSITE")
        self.assertEqual(DM.label({"P_batch": r(-0.2), "P_all": r(-0.2), "PL_within": r(-0.09), "PL_cross": r(0.0)}), "REPLICATED")
if __name__ == "__main__": unittest.main()
