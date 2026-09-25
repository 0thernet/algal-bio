import re, struct, sys, tempfile, unittest
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import mef as M
import build_mm9_features as BF

def world(seed, effect=-0.35, drug_effect=0.0, n_chr=8, per=700, noise=0.15, pup_gc=None, lib_gc=None, expand=1.0):
    rng = np.random.default_rng(seed)
    chrom = np.repeat([f"chr{i+1}" for i in range(n_chr)], per)
    walk = np.concatenate([np.convolve(rng.normal(size=per), np.ones(15) / 15, "same") for _ in range(n_chr)])
    gc = -walk + 0.3 * rng.normal(size=walk.size)          # AT-rich = high lamina
    lam = walk / walk.std(); n = lam.size
    tss = rng.poisson(2 * np.exp(-0.5 * lam)).astype(float)
    zgc = (gc - gc.mean()) / gc.std()
    f = lambda v: np.tanh(v) * 1.5
    pup = pup_gc or {"p15": 0.0, "p18": 0.0, "x17": 0.0}   # embryo-level GC offset, shared by that embryo's tracks
    t = {f"WT_{p}": f(lam) + pup[p] * zgc + noise * rng.normal(size=n) for p in ("p15", "p18", "x17")}
    for p in ("p15", "x17"): t[f"AC_{p}"] = expand * f(lam) + effect * zgc + pup[p] * zgc + noise * rng.normal(size=n)
    for d in ("BIX", "DZN", "TSA"):
        for p in ("p18", "x17"): t[f"{d}_{p}"] = f(lam) + drug_effect * zgc + pup[p] * zgc + noise * rng.normal(size=n)
    for k, v in (lib_gc or {}).items(): t[k] = t[k] + v * zgc   # library-level GC bias of one track
    return chrom, gc, tss, t

def run_world(chrom, gc, tss, t, n_shift=200):
    out = M.run_tests(t, gc, tss, chrom, n_shift=n_shift)
    fin = M.final_label(out["raw"]["label"], out["flexible"]["label"], out["scale_free"]["label"])
    return out, fin, M.specificity(out["raw"], fin)

def write_2bit(path, seqs):
    code = {"T": 0, "C": 1, "A": 2, "G": 3, "N": 0}
    idx_len = sum(1 + len(k) + 4 for k in seqs); off = 16 + idx_len; idx, recs = b"", b""
    for name, s in seqs.items():
        nb = [(m.start(), m.end() - m.start()) for m in re.finditer("N+", s)]
        v = [code[c] for c in s] + [0] * (-len(s) % 4)
        packed = bytes((v[i] << 6) | (v[i + 1] << 4) | (v[i + 2] << 2) | v[i + 3] for i in range(0, len(v), 4))
        rec = (struct.pack("<II", len(s), len(nb)) + b"".join(struct.pack("<I", a) for a, _ in nb)
               + b"".join(struct.pack("<I", l) for _, l in nb) + struct.pack("<II", 0, 0) + packed)
        idx += bytes([len(name)]) + name.encode() + struct.pack("<I", off); off += len(rec); recs += rec
    Path(path).write_bytes(struct.pack("<IIII", 0x1A412743, 0, len(seqs), 0) + idx + recs)

class T(unittest.TestCase):
    def test_real_effect_replicated_and_specific(self):
        out, fin, spec = run_world(*world(1, effect=-0.35))
        self.assertEqual(fin, "REPLICATED", {a: out[a]["label"] for a in ("raw", "flexible", "scale_free")})
        self.assertEqual(spec, "SPECIFIC")

    def test_null_not_replicated(self):
        out, fin, spec = run_world(*world(2, effect=0.0))
        self.assertNotEqual(fin, "REPLICATED"); self.assertEqual(spec, "NOT_APPLICABLE")

    def test_between_embryo_gc_variation_caught(self):
        out, fin, _ = run_world(*world(3, effect=-0.3, pup_gc={"p15": 0.3, "p18": -0.3, "x17": 0.1}))
        self.assertEqual(out["raw"]["label"], "DIRECTION_ONLY"); self.assertNotEqual(fin, "REPLICATED")

    def test_library_gc_bias_in_one_wt_caught(self):
        out, fin, _ = run_world(*world(9, effect=-0.3, lib_gc={"WT_p18": 0.35}))
        self.assertEqual(out["raw"]["label"], "DIRECTION_ONLY"); self.assertNotEqual(fin, "REPLICATED")

    def test_range_expansion_leak_caught(self):
        out, fin, _ = run_world(*world(4, effect=0.0, expand=2.0, noise=0.5))
        self.assertLess(out["raw"]["P_p15"]["rho"], -0.08)          # the leak exists, in the registered direction
        self.assertEqual(out["raw"]["label"], "RANGE_EXPLAINED")    # placebos pass; the range controls catch it
        self.assertNotEqual(fin, "REPLICATED")

    def test_real_effect_with_mild_expansion_replicated(self):
        out, fin, _ = run_world(*world(11, effect=-0.35, expand=1.2, noise=0.3))
        self.assertEqual(fin, "REPLICATED", {a: out[a]["label"] for a in ("raw", "flexible", "scale_free")})

    def test_opposite(self):
        out, fin, _ = run_world(*world(5, effect=0.35))
        self.assertEqual(fin, "OPPOSITE")

    def test_generic_when_drugs_share_the_gradient(self):
        out, fin, spec = run_world(*world(6, effect=-0.35, drug_effect=-0.35))
        self.assertEqual(fin, "REPLICATED"); self.assertEqual(spec, "GENERIC")

    def test_label_rules(self):
        def r(p1, p2, pl=(0.0, 0.0, 0.0), fl=(0.0, 0.0), pp=0.001):
            mk = lambda v: {"rho": v, "p_pos": pp if v > 0 else 1.0, "p_neg": pp if v < 0 else 1.0}
            d = {"P_p15": mk(p1), "P_x17": mk(p2)}
            d.update({k: mk(v) for k, v in zip(M.PLAC, pl)}); d.update({k: mk(v) for k, v in zip(M.RANGE, fl)})
            return d
        self.assertEqual(M.label(r(-0.2, -0.2)), "REPLICATED")
        self.assertEqual(M.label(r(-0.2, -0.2, pl=(0.0, 0.0, -0.1))), "DIRECTION_ONLY")
        self.assertEqual(M.label(r(-0.2, -0.2, pl=(0.099, 0.0, 0.0))), "REPLICATED")
        self.assertEqual(M.label(r(-0.2, -0.2, fl=(-0.1, 0.0))), "RANGE_EXPLAINED")
        self.assertEqual(M.label(r(-0.2, -0.2, fl=(0.3, 0.0))), "REPLICATED")
        self.assertEqual(M.label(r(-0.2, -0.04)), "NOT_REPLICATED")
        self.assertEqual(M.label(r(-0.2, -0.2, pp=0.02)), "NOT_REPLICATED")
        self.assertEqual(M.label(r(0.2, 0.2)), "OPPOSITE")
        self.assertEqual(M.final_label("REPLICATED", "REPLICATED", "RANGE_EXPLAINED"), "NOT_ROBUST")
        self.assertEqual(M.final_label("DIRECTION_ONLY", "REPLICATED", "REPLICATED"), "DIRECTION_ONLY")
        mk = lambda v: {"rho": v}
        raw = {"P_p15": mk(-0.2), "P_x17": mk(-0.2)}
        raw.update({k: mk(0.0) for k in M.DRUGS}); self.assertEqual(M.specificity(raw, "REPLICATED"), "SPECIFIC")
        raw.update({k: mk(-0.15) for k in M.DRUGS}); self.assertEqual(M.specificity(raw, "REPLICATED"), "GENERIC")
        raw.update({M.DRUGS[0]: mk(-0.3)}); raw.update({k: mk(0.0) for k in M.DRUGS[1:]}); self.assertEqual(M.specificity(raw, "REPLICATED"), "MIXED")
        self.assertEqual(M.specificity(raw, "DIRECTION_ONLY"), "NOT_APPLICABLE")

    def test_contrast_wiring_matches_protocol(self):
        names = ["WT_p15", "WT_p18", "WT_x17", "AC_p15", "AC_x17"] + [f"{d}_{p}" for d in ("BIX", "DZN", "TSA") for p in ("p18", "x17")]
        t = {k: np.full(4, float(2 ** i)) for i, k in enumerate(names)}             # sentinel tracks: every sum is unique
        d = M.tests_for(t)
        order = M.P["statistic"].split("test order ")[1].split(";")[0].split(", ")
        self.assertEqual(list(d), order)
        v = lambda *ks: sum(t[k][0] for k in ks)
        expect = {"P_p15": (v("AC_p15") - v("WT_p15"), v("WT_p18", "WT_x17") / 2), "P_x17": (v("AC_x17") - v("WT_x17"), v("WT_p15", "WT_p18") / 2),
                  "PL_15_18": (v("WT_p15") - v("WT_p18"), v("WT_x17")), "PL_x17_18": (v("WT_x17") - v("WT_p18"), v("WT_p15")),
                  "PL_x17_15": (v("WT_x17") - v("WT_p15"), v("WT_p18")),
                  "FL_p15": (v("AC_p15") - v("WT_p15"), v("WT_x17")), "FL_x17": (v("AC_x17") - v("WT_x17"), v("WT_p15"))}  # constant src maps onto constant AC
        for drug in ("BIX", "DZN", "TSA"):
            expect[f"D_{drug}_p18"] = (v(f"{drug}_p18") - v("WT_p18"), v("WT_p15", "WT_x17") / 2)
            expect[f"D_{drug}_x17"] = (v(f"{drug}_x17") - v("WT_x17"), v("WT_p15", "WT_p18") / 2)
        for k, (dy, b) in expect.items():
            self.assertAlmostEqual(d[k][0][0], dy, msg=k); self.assertAlmostEqual(d[k][1][0], b, msg=k)

    def test_abort_on_small_n(self):
        chrom, gc, tss, t = world(7, n_chr=2, per=700)
        with self.assertRaises(SystemExit): M.run_tests(t, gc, tss, chrom, n_shift=20)

    def test_build_check_and_coverage(self):
        import pyBigWig
        with tempfile.TemporaryDirectory() as d:
            for name, L in (("mm9.bw", M.MM9_CHR1), ("mm10.bw", 195471971)):
                bw = pyBigWig.open(str(Path(d) / name), "w"); bw.addHeader([("chr1", L)])
                bw.addEntries(["chr1"], [0], ends=[150000], values=[2.0]); bw.close()
            bw = pyBigWig.open(str(Path(d) / "ens.bw"), "w"); bw.addHeader([("1", M.MM9_CHR1)])   # Ensembl-style name
            bw.addEntries(["1"], [0], ends=[400000], values=[3.0]); bw.close()
            self.assertTrue(M.check_build(Path(d) / "mm9.bw")); self.assertFalse(M.check_build(Path(d) / "mm10.bw"))
            self.assertTrue(M.check_build(Path(d) / "ens.bw"))
            c, s, e = np.array(["chr1"]), np.array([0]), np.array([500000])
            self.assertTrue(np.isnan(M.tile_values(Path(d) / "mm9.bw", c, s, e, 0.5)[0]))
            self.assertEqual(M.tile_values(Path(d) / "mm9.bw", c, s, e, 0.1)[0], 2.0)
            self.assertEqual(M.tile_values(Path(d) / "ens.bw", c, s, e, 0.5)[0], 3.0)

    def test_coverage_fallback_rule(self):
        orig = M.tile_values
        try:
            def stub(f, chrom, start, end, min_cov):
                v = np.full(5000, np.nan); v[: (3400 if (f == "a" and min_cov == 0.5) else 4000)] = 1.0; return v
            M.tile_values = stub
            self.assertEqual(M.tile_all({"a": "a", "b": "b"}, None, None, None)[1], 0.1)
            self.assertEqual(M.tile_all({"b": "b"}, None, None, None)[1], 0.5)
        finally:
            M.tile_values = orig

    def test_twobit_gc_and_n(self):
        seqs = {"chr1": "GGCCAATTNNNNGCGA" + "AT", "chr2": "ACGT" * 3}
        with tempfile.TemporaryDirectory() as d:
            write_2bit(Path(d) / "t.2bit", seqs)
            tb = BF.twobit_tiles(Path(d) / "t.2bit", ["chr1", "chr2"], 8)
        size, gc, nf = tb["chr1"]
        self.assertEqual(size, 18)
        self.assertAlmostEqual(gc[0], 4 / 8); self.assertAlmostEqual(nf[0], 0.0)      # GGCCAATT
        self.assertAlmostEqual(gc[1], 3 / 4); self.assertAlmostEqual(nf[1], 0.5)      # NNNNGCGA
        self.assertAlmostEqual(gc[2], 0.0); self.assertAlmostEqual(nf[2], 0.0)        # AT (partial tile)
        self.assertAlmostEqual(tb["chr2"][1][0], 0.5); self.assertEqual(tb["chr2"][0], 12)

if __name__ == "__main__":
    unittest.main()
