import json, sys, unittest
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import libvar2 as V

def mk_res(pairs):
    out = {}
    for k, (rr, rs) in pairs.items():
        out[k] = {"raw": {"rho": rr, "n": 4000}, "scale_free": {"rho": rs}}
    return out

def base_pairs():
    """46-pair world matching the registered key structure, all strong."""
    p = {}
    for g in ("cw_0h", "cw_6h"):
        for s in ("12", "13", "14", "23", "24", "34"): p[f"LV2_{g}_{s}"] = (-0.2, -0.15)
    for g in ("cw_24h", "cw_96h"):
        for s in ("12", "13", "23"): p[f"LV2_{g}_{s}"] = (-0.2, -0.15)
    for g in ("wapl_0h", "wapl_6h", "wapl_24h", "wapl_96h"):
        for s in ("12", "13", "23"): p[f"LV2_{g}_{s}"] = (-0.15, -0.12)
    for k in ("ctcf_0h", "ctcf_6h", "ctcf_24h", "ctcf_96h", "pt_0h", "ptn_0h", "ptn_24h",
              "rad21_0h", "rad21_6h", "rad21_24h", "dmso_0h", "dmso_24h",
              "eed_0h", "eed_24h", "gsk_0h", "gsk_24h"): p[f"LV2_{k}"] = (-0.12, -0.1)
    return p

class T(unittest.TestCase):
    def test_pairs_resolve_and_count(self):
        ids = list(V.P["pairs"]); self.assertEqual(len(ids), 46)
        files = V.P["cohorts"]["esc"]["files"]
        for k, v in V.P["pairs"].items():
            self.assertIn(v["a"], files, k); self.assertIn(v["b"], files, k)
        # every file key used by at least one pair or XC
        used = {v["a"] for v in V.P["pairs"].values()} | {v["b"] for v in V.P["pairs"].values()} | \
               {v["a"] for v in V.P["cross_condition_reported_only"].values()} | {v["b"] for v in V.P["cross_condition_reported_only"].values()}
        self.assertEqual(set(files), used)

    def test_xc_and_groups_resolve(self):
        files = V.P["cohorts"]["esc"]["files"]
        for k, v in V.P["cross_condition_reported_only"].items():
            self.assertIn(v["a"], files, k); self.assertIn(v["b"], files, k)
        for g, ks in V.P["generality_groups"].items():
            if g == "note": continue
            for k in ks: self.assertIn(k, V.P["pairs"], f"{g}:{k}")

    def test_label_systematic(self):
        lab, pooled = V.pooled_label(mk_res(base_pairs()))
        self.assertEqual(lab, "SYSTEMATIC"); self.assertTrue(pooled["p4"])
        self.assertEqual(len([g for g, m in pooled["group_medians"].items() if m >= 0.05]), 6)

    def test_label_not_supported_when_group_pairs_flat(self):
        p = base_pairs()
        for k in list(p):
            if "wapl" in k or "cw" in k: p[k] = (0.01, 0.0)   # 22 of 46 strong -> frac < 0.6
        lab, pooled = V.pooled_label(mk_res(p))
        self.assertEqual(lab, "NOT_SUPPORTED"); self.assertFalse(pooled["p1"])

    def test_label_partial_p4_only_fails(self):
        p = base_pairs()
        # flatten all 4 wapl groups + cw_6h -> 1/6 groups pass; pooled stats still pass
        for k in list(p):
            if "wapl" in k or "cw_6h" in k: p[k] = (0.02, 0.0)
        lab, pooled = V.pooled_label(mk_res(p))
        self.assertFalse(pooled["p4"]); self.assertEqual(lab, "PARTIAL")

    def test_p4_requires_both_genotypes(self):
        p = base_pairs()
        # all 4 wapl groups strong, both cw groups flat -> 4/6 groups pass but only WAPL
        for k in list(p):
            if "cw_" in k: p[k] = (0.02, 0.0)
        lab, pooled = V.pooled_label(mk_res(p))
        self.assertFalse(pooled["p4"])
        self.assertEqual(len([g for g, m in pooled["group_medians"].items() if m >= 0.05]), 4)

    def test_p2_needs_four_eligible(self):
        p = {k: (0.01, 0.0) for k in base_pairs()}; p["LV2_cw_0h_12"] = (-0.2, -0.15)
        lab, pooled = V.pooled_label(mk_res(p))
        self.assertNotEqual(lab, "SYSTEMATIC"); self.assertFalse(pooled["p2"])

    def test_cond_class(self):
        self.assertEqual(V.cond_class("LV2_dmso_24h"), "drug_control")
        self.assertEqual(V.cond_class("LV2_wapl_0h_12"), "untreated_0h")
        self.assertEqual(V.cond_class("LV2_ctcf_0h"), "untreated_0h")
        self.assertEqual(V.cond_class("LV2_wapl_6h_12"), "iaa_treated")
        self.assertEqual(V.cond_class("LV2_ptn_24h"), "iaa_treated")

    def test_seed_scheme_matches_protocol(self):
        self.assertEqual(V.ARMS, (("raw", 0), ("scale_free", 100)))  # 20263101/20263201 via +off
        self.assertIn("20263301", V.P["test_per_pair"])
        src = Path(V.__file__).read_text()
        self.assertIn("20263101 + off", src)   # registered-pair seed base used in run()
        self.assertIn("20263301 + i", src)     # XC seed base used in run()

    def test_prefix_rule(self):
        # GSM id prefix derivation used in fetch()
        for gsm, want in (("GSM5509284", "GSM5509nnn"), ("GSM5898024", "GSM5898nnn")):
            self.assertEqual(gsm[:-3] + "nnn", want)
        tpl = V.P["cohorts"]["esc"]["url_template"]
        url = tpl.format(prefix="GSM5509nnn/GSM5509284", file="GSM5509284_x.bw")
        self.assertEqual(url, "https://ftp.ncbi.nlm.nih.gov/geo/samples/GSM5509nnn/GSM5509284/suppl/GSM5509284_x.bw")

if __name__ == "__main__":
    unittest.main()
