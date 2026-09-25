import sys, unittest
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import lbr as L

def world(seed, gc_effect, flatten=0.6, n_chr=8, per=700, noise=0.15, st_noise=None, batch_gc=0.0):
    rng = np.random.default_rng(seed)
    chrom = np.repeat([f"chr{i+1}" for i in range(n_chr)], per)
    walk = np.concatenate([np.convolve(rng.normal(size=per), np.ones(15) / 15, "same") for _ in range(n_chr)])
    gc = -walk + 0.3 * rng.normal(size=walk.size)          # AT-rich = high lamina
    lam = walk / walk.std()
    tss = rng.poisson(2 * np.exp(-0.5 * lam)).astype(float)
    zgc = (gc - gc.mean()) / gc.std()
    f = lambda v: np.tanh(v) * 1.5                          # nonlinear profile
    t = {k: f(lam) + noise * rng.normal(size=lam.size) for k in ("WT_r13", "WT_r14", "ST_r6", "ST_r7", "WT_T2B_r13", "WT_T2B_r14")}
    for k in ("LBRKO_r13", "LBRKO_r14", "LBRKO_T2B_r13", "LBRKO_T2B_r14"):
        t[k] = flatten * f(lam) + gc_effect * zgc + noise * rng.normal(size=lam.size)   # non-uniform flattening
    if st_noise:
        for k in ("ST_r6", "ST_r7"): t[k] = f(lam) + st_noise * rng.normal(size=lam.size)
    for k in t:  # experiment-level GC bias, opposite in r13 and r14 (ST_r6 is in r13, ST_r7 in r14)
        sgn = 1 if k.endswith("r13") or k == "ST_r6" else -1
        t[k] = t[k] + sgn * batch_gc * zgc
    return chrom, gc, tss, t

def run_world(chrom, gc, tss, t, n_shift=200):
    out = {}
    for arm in ("linear", "flexible"):
        res = {}
        for i, (k, (y, b)) in enumerate(L.tests_for(t).items()):
            res[k] = (L.S.test_pair(gc, y, [tss, b], chrom, n_shift, i) if arm == "linear"
                      else L.test_design(gc, y, tss, L.flex_basis(b), chrom, n_shift, i))
        res["label"] = L.label(res); out[arm] = res
    return out, L.final_label(out["linear"]["label"], out["flexible"]["label"])

class T(unittest.TestCase):
    def test_quantile_map(self):
        rng = np.random.default_rng(0); a, b = rng.normal(size=500), rng.exponential(size=500)
        a[3] = np.nan; q = L.quantile_map(a, b)
        m = np.isfinite(q)
        self.assertTrue(np.isnan(q[3]))
        self.assertAlmostEqual(np.corrcoef(np.argsort(np.argsort(a[m])), np.argsort(np.argsort(q[m])))[0, 1], 1.0)
        self.assertLess(abs(np.median(q[m]) - np.median(b[m])), 0.05)

    def test_flex_removes_nonlinear_baseline(self):
        rng = np.random.default_rng(1); n = 4000
        chrom = np.repeat([f"chr{i}" for i in range(1, 9)], n // 8)
        b = rng.normal(size=n); x = b ** 2 + 0.5 * rng.normal(size=n); y = np.sin(2 * b) + b ** 2 + 0.5 * rng.normal(size=n)
        tss = rng.random(n)
        lin = L.S.test_pair(x, y, [tss, b], chrom, 50, 0)["rho"]
        flex = L.test_design(x, y, tss, L.flex_basis(b), chrom, 50, 0)["rho"]
        self.assertGreater(abs(lin), 0.1); self.assertLess(abs(flex), 0.05)

    def test_pure_flattening_not_supported(self):
        out, fin = run_world(*world(2, gc_effect=0.0))
        self.assertNotEqual(fin, "SUPPORTED")
        self.assertNotEqual(out["flexible"]["label"], "SUPPORTED")

    def test_noisy_baseline_flattening_leak_caught(self):
        out, fin = run_world(*world(5, gc_effect=0.0, flatten=0.6, st_noise=1.2))
        self.assertGreater(out["linear"]["P_r13"]["rho"], 0.2)      # the leak exists, in the registered direction
        self.assertEqual(out["linear"]["label"], "FLATTENING_EXPLAINED")
        self.assertNotEqual(fin, "SUPPORTED")

    def test_real_effect_survives_flattening_control(self):
        out, fin = run_world(*world(6, gc_effect=0.2, flatten=0.6, st_noise=0.5))
        self.assertEqual(fin, "SUPPORTED")

    def test_batch_gc_bias_flags_placebo(self):
        out, fin = run_world(*world(7, gc_effect=0.3, flatten=1.0, batch_gc=0.15))
        self.assertEqual(out["linear"]["label"], "DIRECTION_ONLY")
        self.assertNotEqual(fin, "SUPPORTED")

    def test_noise_matched_hits_target(self):
        rng = np.random.default_rng(8); wt = rng.normal(size=3000); ko = wt + 0.8 * rng.normal(size=3000)
        sim, sd, target = L.noise_matched(wt + 0.1 * rng.normal(size=3000), wt, ko, 0)
        self.assertAlmostEqual(L.spearmanr(sim, wt)[0], target, places=3); self.assertGreater(sd, 0)

    def test_real_gc_effect_supported(self):
        out, fin = run_world(*world(3, gc_effect=0.35))
        self.assertEqual(fin, "SUPPORTED", (out["linear"]["label"], out["flexible"]["label"]))

    def test_opposite(self):
        out, fin = run_world(*world(4, gc_effect=-0.35))
        self.assertEqual(fin, "OPPOSITE")

    def test_label_rules(self):
        def r(p1, p2, pl1=0.0, pl2=0.0, f1=0.0, f2=0.0, pp=0.001):
            mk = lambda v: {"rho": v, "p_pos": pp if v > 0 else 1.0, "p_neg": pp if v < 0 else 1.0}
            return {"P_r13": mk(p1), "P_r14": mk(p2), "PL_batch": mk(pl1), "PL_st": mk(pl2), "FL_r13": mk(f1), "FL_r14": mk(f2)}
        self.assertEqual(L.label(r(0.2, 0.2)), "SUPPORTED")
        self.assertEqual(L.label(r(0.2, 0.2, f1=0.15)), "FLATTENING_EXPLAINED")
        self.assertEqual(L.label(r(0.2, 0.2, pl2=-0.12)), "DIRECTION_ONLY")
        self.assertEqual(L.label(r(0.2, 0.04)), "NOT_SUPPORTED")
        self.assertEqual(L.label(r(0.2, 0.2, pp=0.02)), "NOT_SUPPORTED")
        self.assertEqual(L.label(r(-0.2, -0.2)), "OPPOSITE")
        self.assertEqual(L.final_label("SUPPORTED", "FLATTENING_EXPLAINED"), "NOT_ROBUST_TO_ADJUSTMENT")
        self.assertEqual(L.final_label("NOT_SUPPORTED", "SUPPORTED"), "NOT_SUPPORTED")

if __name__ == "__main__":
    unittest.main()
