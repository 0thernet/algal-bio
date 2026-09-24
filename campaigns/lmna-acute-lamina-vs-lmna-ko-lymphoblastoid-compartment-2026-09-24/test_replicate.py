import json, os, sys, tempfile, unittest
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import replicate as R
import compartment as C

def reg():
    return json.load(open(Path(__file__).resolve().parents[1] / "registration" / "protocol.draft.json"))

class AdapterTests(unittest.TestCase):
    def test_adapter_maps_roles_and_thresholds(self):
        a = R.adapter_registration(reg())
        lines = {g: m["line"] for g, m in a["outcome"]["samples"].items()}
        self.assertEqual(sorted(lines.values()), ["WT", "WT", "mutant", "mutant"])
        self.assertEqual(a["outcome"]["corrected_lines"], ["WT"])
        self.assertEqual(a["pass_criteria"]["unadjusted_rho_max"], -0.05)
        self.assertEqual(a["pass_criteria"]["adjusted_rho_max"], -0.05)
        self.assertEqual(a["pass_criteria"]["standardised_unadjusted_rho_max"], -0.05)
        self.assertEqual(a["null"]["seed"], 20260925)
        self.assertEqual(a["null"]["permutations"], 5000)
        for g, m in a["outcome"]["samples"].items():
            self.assertEqual(m["filename"], f"{g}.pc1.bedGraph")

    def test_thresholds_are_read_by_subscript(self):
        r = reg(); del r["pass_criteria"]["tier_a"]["p_max"]
        with self.assertRaises(KeyError):
            R.adapter_registration(r)

class CrossPairTests(unittest.TestCase):
    def test_cross_pairs_signs(self):
        r = reg()
        ko = [g for g, m in r["outcome"]["samples"].items() if m["condition"] == "KO"]
        wt = [g for g, m in r["outcome"]["samples"].items() if m["condition"] == "WT"]
        rng = np.random.default_rng(1); n = 300
        dlam = rng.normal(size=n)
        base = rng.normal(size=n)
        pc = {w: base + rng.normal(scale=0.1, size=n) for w in wt}
        pc.update({k: base - 0.5 * dlam + rng.normal(scale=0.1, size=n) for k in ko})
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "tiles.tsv"
            with open(p, "w") as fh:
                fh.write("tile_id\tchrom\tdlam_mCh\t" + "\t".join(f"pc1_{g}" for g in ko + wt) + "\n")
                for i in range(n):
                    fh.write(f"t{i}\tchr1\t{dlam[i]}\t" + "\t".join(str(pc[g][i]) for g in ko + wt) + "\n")
            out = R.cross_pairs(p, r)
        self.assertEqual(len(out), 4)
        self.assertTrue(all(v < 0 for v in out.values()))

class EndToEndSyntheticTests(unittest.TestCase):
    """Runs the frozen evaluator through the adapter on synthetic PC1 bedGraphs (unfrozen, synthetic-only path)."""
    def test_planted_negative_association_passes_tier_a(self):
        r = reg(); a = R.adapter_registration(r); a["null"]["permutations"] = 200
        rng = np.random.default_rng(7)
        sizes = {f"chr{i}": 60_000_000 for i in range(1, 23)}
        tiles = C.tiles_for(sizes)
        n = len(tiles)
        tss = rng.poisson(5, size=n).astype(float)
        base_pc1 = 0.5 * (tss - tss.mean()) / tss.std() + rng.normal(scale=0.5, size=n)
        dlam = rng.normal(scale=0.2, size=n)
        base_lam = -0.3 * base_pc1 + rng.normal(scale=0.5, size=n)
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            pred = d / "predictor.tsv"
            with open(pred, "w") as fh:
                fh.write("tile_id\tchrom\tstart\tend\tsiScr_mCh\tsiLMNA_mCh\tdlam_mCh\tsiScr_DNK\tsiLMNA_DNK\tdlam_DNK\tcov_min\ttss_count\n")
                for i, (c, s, e) in enumerate(tiles):
                    fh.write(f"{c}:{s}-{e}\t{c}\t{s}\t{e}\t{base_lam[i]}\t{base_lam[i]+dlam[i]}\t{dlam[i]}\t{base_lam[i]}\t{base_lam[i]+dlam[i]}\t{dlam[i]}\t1.0\t{int(tss[i])}\n")
            od = d / "pc1"; od.mkdir()
            for g, m in a["outcome"]["samples"].items():
                shift = -0.6 * dlam if m["line"] == "mutant" else 0.0
                v = base_pc1 + shift + rng.normal(scale=0.15, size=n)
                with open(od / m["filename"], "w") as fh:
                    for i, (c, s, e) in enumerate(tiles):
                        fh.write(f"{c}\t{s}\t{e}\t{v[i]:.6f}\n")
            core = C.run_registered(a, pred, od, d / "core", "reg", None, intake_hashes=None, allow_unfrozen=True)
            pairs = R.cross_pairs(d / "core" / "tiles.tsv", r)
        self.assertTrue(core["orientation"]["ok"])
        self.assertTrue(core["contrasts"]["WT"]["clone_pass"], core["contrasts"]["WT"]["component_pass"])
        self.assertTrue(all(v < 0 for v in pairs.values()))
        self.assertTrue(core["unfrozen_synthetic_run"])

    def test_null_association_does_not_pass(self):
        r = reg(); a = R.adapter_registration(r); a["null"]["permutations"] = 200
        rng = np.random.default_rng(11)
        sizes = {f"chr{i}": 60_000_000 for i in range(1, 23)}
        tiles = C.tiles_for(sizes); n = len(tiles)
        tss = rng.poisson(5, size=n).astype(float)
        base_pc1 = 0.5 * (tss - tss.mean()) / tss.std() + rng.normal(scale=0.5, size=n)
        dlam = rng.normal(scale=0.2, size=n)
        with tempfile.TemporaryDirectory() as d:
            d = Path(d); pred = d / "predictor.tsv"
            with open(pred, "w") as fh:
                fh.write("tile_id\tchrom\tstart\tend\tsiScr_mCh\tsiLMNA_mCh\tdlam_mCh\tsiScr_DNK\tsiLMNA_DNK\tdlam_DNK\tcov_min\ttss_count\n")
                for i, (c, s, e) in enumerate(tiles):
                    fh.write(f"{c}:{s}-{e}\t{c}\t{s}\t{e}\t0.0\t{dlam[i]}\t{dlam[i]}\t0.0\t{dlam[i]}\t{dlam[i]}\t1.0\t{int(tss[i])}\n")
            od = d / "pc1"; od.mkdir()
            for g, m in a["outcome"]["samples"].items():
                v = base_pc1 + rng.normal(scale=0.15, size=n)
                with open(od / m["filename"], "w") as fh:
                    for i, (c, s, e) in enumerate(tiles):
                        fh.write(f"{c}\t{s}\t{e}\t{v[i]:.6f}\n")
            core = C.run_registered(a, pred, od, d / "core", "reg", None, intake_hashes=None, allow_unfrozen=True)
        self.assertFalse(core["contrasts"]["WT"]["clone_pass"])
        self.assertFalse(core["registered_pass"])

class BindingTests(unittest.TestCase):
    def test_run_refuses_on_binding_mismatch(self):
        r = reg()
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            rp = d / "reg.json"; json.dump(r, open(rp, "w"))
            fz = d / "freeze.json"; json.dump({"registration_sha256": "0" * 64}, open(fz, "w"))
            ik = d / "intake.json"; json.dump({"freeze_sha256": "x", "files": []}, open(ik, "w"))
            (d / "pred.tsv").write_text("x"); (d / "hg19.chrom.sizes").write_text("chr1\t10\n"); (d / "hg19.ncbiRefSeqSelect.txt.gz").write_bytes(b"")
            with self.assertRaises(SystemExit):
                R.run(rp, fz, ik, d / "pred.tsv", d, d / "out", d, sys.executable)

class VerdictTests(unittest.TestCase):
    def _res(self, u, a, s, pu=0.0002, pa=0.0002, ps=0.0002, ratio_ok=True, ppos=0.999):
        comp = {"unadjusted_effect": u <= -0.05, "unadjusted_p": pu <= 0.01, "adjusted_effect": a <= -0.05, "adjusted_p": pa <= 0.01,
                "adjusted_to_unadjusted_ratio": ratio_ok, "standardised_effect": s <= -0.05, "standardised_p": ps <= 0.01, "replicate_pairs": True}
        return {"unadjusted_rho": u, "adjusted_rho": a, "unadjusted_p_negative": pu, "adjusted_p_negative": pa, "unadjusted_p_positive": ppos,
                "standardised": {"unadjusted_rho": s, "unadjusted_p_negative": ps}, "component_pass": comp}
    def _core(self, ok=True, n=5000):
        return {"orientation": {"ok": ok}, "n_tiles_eligible": n}
    def test_labels(self):
        r = reg(); neg = {"a": -0.1, "b": -0.2, "c": -0.05, "d": -0.01}
        self.assertEqual(R.verdict(r, self._core(), self._res(-0.08, -0.12, -0.07), neg, False)["label"], "TIER_B_PASS")
        self.assertEqual(R.verdict(r, self._core(), self._res(-0.08, -0.08, -0.07), neg, False)["label"], "TIER_A_PASS")
        self.assertEqual(R.verdict(r, self._core(), self._res(-0.04, -0.06, -0.03), neg, False)["label"], "NOT_PASSED_DIRECTION_CONSISTENT")
        self.assertEqual(R.verdict(r, self._core(), self._res(-0.04, -0.06, -0.03, pu=0.2), neg, False)["label"], "NOT_PASSED")
        self.assertEqual(R.verdict(r, self._core(), self._res(0.09, 0.05, 0.08, pu=0.9, pa=0.9, ps=0.9, ppos=0.001), {"a": 0.1}, False)["label"], "OPPOSITE")
        self.assertEqual(R.verdict(r, self._core(), self._res(-0.08, -0.12, -0.07), neg, True)["label"], "PIPELINE_FAILURE")
        pos = dict(neg, d=0.01)
        self.assertEqual(R.verdict(r, self._core(), self._res(-0.08, -0.12, -0.07), pos, False)["label"], "NOT_PASSED")
        self.assertEqual(R.verdict(r, self._core(ok=False), self._res(-0.08, -0.12, -0.07), neg, False)["label"], "NOT_PASSED")
    def test_every_label_has_precommitted_interpretation(self):
        r = reg()
        for lab in ("TIER_B_PASS", "TIER_A_PASS", "NOT_PASSED_DIRECTION_CONSISTENT", "NOT_PASSED", "OPPOSITE", "PIPELINE_FAILURE"):
            self.assertIn(lab, r["interpretation_precommitted"])

class EigenShareAndQcTests(unittest.TestCase):
    def test_eigen_share(self):
        st = {"per_chrom": {"chr1": {"n_bins": 100, "n_masked": 20, "eigenvalue": 16.0, "oriented": True}, "chr2": {"n_bins": 50, "n_masked": 0, "eigenvalue": 5.0, "oriented": True}, "chr3": {"n_bins": 50, "n_masked": 0, "eigenvalue": 25.0, "oriented": False}}}
        self.assertAlmostEqual(R.eigen_share(st), (0.2 + 0.1) / 2)
    def test_pipeline_qc_excludes_discordant_and_unoriented(self):
        r = reg(); samples = r["outcome"]["samples"]
        sizes = {"chr1": 5_000_000, "chr2": 5_000_000, "chr3": 5_000_000}
        r["tiles"]["chromosomes"] = list(sizes)
        tiles = C.tiles_for(sizes, chroms=list(sizes))
        rng = np.random.default_rng(3); n = len(tiles); base = rng.normal(size=n)
        chrom = np.array([t[0] for t in tiles])
        with tempfile.TemporaryDirectory() as d:
            d = Path(d); pd_ = d / "pc1"; pd_.mkdir()
            stats = {}
            for g, m in samples.items():
                v = base + rng.normal(scale=0.1, size=n)
                if g == "GSM9401863":
                    v[chrom == "chr2"] = rng.normal(size=(chrom == "chr2").sum())  # discordant
                with open(pd_ / f"{g}.pc1.bedGraph", "w") as fh:
                    for i, (c, s, e) in enumerate(tiles):
                        if not (g == "GSM9401862" and c == "chr3"):  # unoriented chromosome omitted
                            fh.write(f"{c}\t{s}\t{e}\t{v[i]:.5f}\n")
                stats[g] = {"per_chrom": {c: {"n_bins": 10, "n_masked": 0, "eigenvalue": 3.0, "rho": 0.5, "oriented": not (g == "GSM9401862" and c == "chr3")} for c in sizes}}
            qc_dir, rec = R.pipeline_qc(r, pd_, stats, tiles)
            self.assertEqual(sorted(rec["excluded_chromosomes"]), ["chr2", "chr3"])
            self.assertEqual(rec["per_sample"]["GSM9401860"]["reference"], ["GSM9401861"])
            self.assertEqual(rec["per_sample"]["GSM9401862"]["reference"], ["GSM9401860", "GSM9401861"])
            self.assertLess(rec["per_sample"]["GSM9401860"]["concordance_with_wt_reference"]["chr1"], 1.0)
            self.assertFalse(rec["pipeline_failure"])
            kept = {l.split("\t")[0] for l in open(qc_dir / "GSM9401860.pc1.bedGraph")}
            self.assertEqual(kept, {"chr1"})
            r["pipeline_qc"]["max_excluded_autosomes"] = 1
            _, rec2 = R.pipeline_qc(r, pd_, stats, tiles)
            self.assertTrue(rec2["pipeline_failure"])

class Pc1CommandTests(unittest.TestCase):
    def test_argv_from_registration(self):
        r = reg(); m = r["outcome"]["samples"]["GSM9401860"]
        fp = r["fixed_parameters_explicit"]
        cmd = R.pc1_command(r, m, Path("/o"), Path("/t"), "py", Path("/x/a.bedGraph"), Path("/x/a.json"))
        self.assertEqual(cmd[:3], ["py", str(Path(R.__file__).resolve().parent / "pc1.py"), "pairs"])
        self.assertEqual(cmd[cmd.index("--pairs") + 1], str(Path("/o") / m["filename"]))
        self.assertEqual(cmd[cmd.index("--bin-size") + 1], str(r["tiles"]["size"]))
        self.assertEqual(cmd[cmd.index("--min-abs-rho") + 1], str(fp["pc1_min_abs_rho_per_chromosome"]))
        self.assertEqual(cmd[cmd.index("--min-nnz") + 1], str(fp["ice_min_nnz"]))
        self.assertEqual(cmd[cmd.index("--chrom-sizes") + 1], str(Path("/t") / r["tiles"]["chrom_sizes_file"]))
        self.assertEqual(cmd[cmd.index("--refseq") + 1], str(Path("/t") / r["orientation"]["refseq_file"]))
        self.assertEqual("--min-mapq" in cmd, fp["extra_mapq_filter"] is not None)
        fp["extra_mapq_filter"] = 30
        cmd = R.pc1_command(r, m, Path("/o"), Path("/t"), "py", Path("/x/a.bedGraph"), Path("/x/a.json"))
        self.assertEqual(cmd[cmd.index("--min-mapq") + 1], "30")


class BytesEnforcementTests(unittest.TestCase):
    def test_truncated_outcome_refused(self):
        r = reg()
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            for f in ("hg19.chrom.sizes",): (d / f).write_text("chr1\t10\n")
            (d / "hg19.ncbiRefSeqSelect.txt.gz").write_bytes(b"")
            (d / "pred.tsv").write_text("x")
            rp = d / "reg.json"; json.dump(r, open(rp, "w"))
            fz = d / "freeze.json"
            here = Path(R.__file__).resolve().parent
            fzd = {"registration_sha256": R.sha(rp), "code_replicate_sha256": R.sha(here / "replicate.py"), "code_compartment_sha256": R.sha(here / "compartment.py"),
                   "code_pc1_sha256": R.sha(here / "pc1.py"), "test_replicate_sha256": R.sha(here / "test_replicate.py"), "test_pc1_sha256": R.sha(here / "test_pc1.py"),
                   "requirements_lock_sha256": R.sha(here / "requirements.lock"), "predictor_tsv_sha256": R.sha(d / "pred.tsv"),
                   "chrom_sizes_sha256": R.sha(d / "hg19.chrom.sizes"), "refseq_sha256": R.sha(d / "hg19.ncbiRefSeqSelect.txt.gz")}
            json.dump(fzd, open(fz, "w"))
            files = []
            for g, m in r["outcome"]["samples"].items():
                (d / m["filename"]).write_bytes(b"abc")  # truncated relative to bytes_expected
                files.append({"filename": m["filename"], "bytes": 3, "sha256": R.sha(d / m["filename"])})
            ik = d / "intake.json"; json.dump({"freeze_sha256": R.sha(fz), "files": files}, open(ik, "w"))
            fzd2 = json.load(open(fz)); fzd2["_path"] = fz
            with self.assertRaises(SystemExit) as cm:
                R.check_bindings(r, rp, fzd2, json.load(open(ik)), d / "pred.tsv", d, d)
            self.assertIn("byte count", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
