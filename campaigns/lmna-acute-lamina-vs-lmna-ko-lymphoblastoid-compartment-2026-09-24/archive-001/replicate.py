#!/usr/bin/env python3
"""Registered replication: acute lamina change (GSE300197, lifted to hg19) versus
LMNA-KO compartment shift in GM12878 (GSE314556 Hi-C, valid pairs -> PC1).

Pipeline (every parameter read from the frozen registration by subscript, fail-closed):
  1. check_bindings: every bound hash against freeze.json; every outcome pairs file
     against intake.json (hash AND byte count against bytes_expected).
  2. run_pc1: pc1.py per sample (pairs -> 500 kb ICE -> O/E -> Pearson -> leading
     eigenvector -> orient by TSS density) with masking/orientation parameters passed
     from the registration; no extra MAPQ filter.
  3. pipeline_qc: per-sample per-chromosome orientation rho and cross-sample concordance
     (Spearman of each sample's PC1 with the WT mean, per chromosome). A chromosome is
     excluded genome-wide if any sample is unoriented there or its concordance is below
     the registered minimum. More than the registered maximum of excluded autosomes gives
     the verdict PIPELINE_FAILURE (all statistics are still computed and reported).
  4. Frozen evaluator compartment.run_registered on the QC-filtered bedGraphs under an
     adapter registration (KO = "mutant", WT = single corrected line; tier_a thresholds).
  5. Cross replicate pairs, compartment-strength ratio (mean eigenvalue share of the
     correlation matrix, scale-invariant), mechanical verdict; summary.json.
"""
import argparse, hashlib, json, subprocess, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import compartment as C  # frozen evaluator, hash-bound


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_bindings(reg, reg_path, freeze, intake, predictor, outcome_dir, tools_dir):
    exp = {
        "registration_sha256": sha(reg_path),
        "code_replicate_sha256": sha(HERE / "replicate.py"),
        "code_compartment_sha256": sha(HERE / "compartment.py"),
        "code_pc1_sha256": sha(HERE / "pc1.py"),
        "test_replicate_sha256": sha(HERE / "test_replicate.py"),
        "test_pc1_sha256": sha(HERE / "test_pc1.py"),
        "requirements_lock_sha256": sha(HERE / "requirements.lock"),
        "predictor_tsv_sha256": sha(predictor),
        "chrom_sizes_sha256": sha(tools_dir / reg["tiles"]["chrom_sizes_file"]),
        "refseq_sha256": sha(tools_dir / reg["orientation"]["refseq_file"]),
    }
    bad = {k: (v, freeze.get(k)) for k, v in exp.items() if freeze.get(k) != v}
    if bad:
        raise SystemExit(f"freeze binding mismatch: {bad}")
    if intake["freeze_sha256"] != sha(freeze["_path"]):
        raise SystemExit("intake receipt does not bind this freeze receipt")
    ih = {f["filename"]: f for f in intake["files"]}
    got = {}
    for gsm, m in reg["outcome"]["samples"].items():
        p = outcome_dir / m["filename"]
        entry = ih.get(m["filename"])
        if entry is None:
            raise SystemExit(f"outcome {m['filename']} missing from intake receipt")
        nbytes = p.stat().st_size
        if nbytes != int(m["bytes_expected"]) or int(entry["bytes"]) != int(m["bytes_expected"]):
            raise SystemExit(f"outcome {m['filename']} byte count {nbytes} / intake {entry['bytes']} != registered {m['bytes_expected']}")
        h = sha(p)
        if entry["sha256"] != h:
            raise SystemExit(f"outcome {m['filename']} hash {h} != intake {entry['sha256']}")
        got[gsm] = {"sha256": h, "bytes": nbytes}
    return exp, got


def pc1_command(reg, m, outcome_dir, tools_dir, python, bg, st):
    """argv for one pc1.py run; every numeric option comes from the registration."""
    fp = reg["fixed_parameters_explicit"]
    cmd = [python, str(HERE / "pc1.py"), "pairs", "--pairs", str(outcome_dir / m["filename"]),
           "--chrom-sizes", str(tools_dir / reg["tiles"]["chrom_sizes_file"]),
           "--refseq", str(tools_dir / reg["orientation"]["refseq_file"]),
           "--bin-size", str(reg["tiles"]["size"]),
           "--min-abs-rho", str(fp["pc1_min_abs_rho_per_chromosome"]),
           "--min-nnz", str(fp["ice_min_nnz"]),
           "--out", str(bg), "--stats", str(st)]
    if fp["extra_mapq_filter"] is not None:
        cmd += ["--min-mapq", str(fp["extra_mapq_filter"])]
    return cmd


def run_pc1(reg, outcome_dir, out_dir, tools_dir, python):
    pc1_dir = out_dir / "pc1"
    pc1_dir.mkdir(parents=True, exist_ok=True)
    stats = {}
    for gsm, m in reg["outcome"]["samples"].items():
        bg = pc1_dir / f"{gsm}.pc1.bedGraph"
        st = pc1_dir / f"{gsm}.pc1.stats.json"
        cmd = pc1_command(reg, m, outcome_dir, tools_dir, python, bg, st)
        subprocess.run(cmd, check=True)
        stats[gsm] = json.load(open(st))
    return pc1_dir, stats


def eigen_share(stats):
    """Mean over oriented chromosomes of eigenvalue / (n_bins - n_masked): the fraction of
    correlation-matrix variance carried by PC1; invariant to the per-chromosome unit
    scaling of the eigenvector."""
    vals = []
    for c, s in stats["per_chrom"].items():
        if s.get("eigenvalue") is not None and s.get("oriented"):
            n = s["n_bins"] - s["n_masked"]
            if n > 0:
                vals.append(s["eigenvalue"] / n)
    return float(np.mean(vals)) if vals else float("nan")


def pipeline_qc(reg, pc1_dir, pc1_stats, tiles):
    """Per-sample orientation and cross-sample concordance; returns (qc_dir, qc_record)."""
    qc = reg["pipeline_qc"]
    samples = reg["outcome"]["samples"]
    chrom = np.array([t[0] for t in tiles])
    pc1 = {g: C.bedgraph_tile_means(pc1_dir / f"{g}.pc1.bedGraph", tiles, reg["tiles"]["min_coverage"])[0] for g in samples}
    wt = [g for g, m in samples.items() if m["condition"] == "WT"]
    # Reference for each sample: mean of the WT samples other than itself (leave-one-out for
    # WT samples, so a WT replicate is never compared with a mean that contains it).
    reference = {g: np.nanmean(np.stack([pc1[w] for w in wt if w != g]), axis=0) for g in samples}
    per_sample = {}
    excluded = {}
    for g in samples:
        rec = {"orientation_rho": {}, "concordance_with_wt_reference": {}, "unoriented": [], "low_concordance": [],
               "reference": [w for w in wt if w != g]}
        for c in reg["tiles"]["chromosomes"]:
            st = pc1_stats[g]["per_chrom"].get(c, {})
            rec["orientation_rho"][c] = st.get("rho")
            idx = np.flatnonzero(chrom == c)
            ok = np.isfinite(pc1[g][idx]) & np.isfinite(reference[g][idx])
            if not st.get("oriented") or ok.sum() < qc["min_tiles_per_chromosome"]:
                rec["unoriented"].append(c)
                excluded.setdefault(c, []).append(f"{g}:unoriented")
                rec["concordance_with_wt_reference"][c] = None
                continue
            r = C.spearman(pc1[g][idx][ok], reference[g][idx][ok])
            rec["concordance_with_wt_reference"][c] = r
            if r < qc["min_cross_sample_concordance"]:
                rec["low_concordance"].append(c)
                excluded.setdefault(c, []).append(f"{g}:concordance={r:.3f}")
        per_sample[g] = rec
    qc_dir = pc1_dir.parent / "pc1-qc"
    qc_dir.mkdir(exist_ok=True)
    for g in samples:
        with open(pc1_dir / f"{g}.pc1.bedGraph", encoding="utf-8") as src, open(qc_dir / f"{g}.pc1.bedGraph", "w", encoding="utf-8") as dst:
            for line in src:
                c = line.split("\t", 1)[0]
                if c not in excluded:
                    dst.write(line)
    record = {"rule": qc, "per_sample": per_sample, "excluded_chromosomes": excluded,
              "n_excluded": len(excluded), "pipeline_failure": len(excluded) > qc["max_excluded_autosomes"],
              "eigen_share_per_sample": {g: eigen_share(pc1_stats[g]) for g in samples}}
    return qc_dir, record


def adapter_registration(reg):
    """Map the v3 registration onto the frozen compartment evaluator's v2 shape."""
    t = reg["pass_criteria"]["tier_a"]
    samples = {}
    for gsm, m in reg["outcome"]["samples"].items():
        samples[gsm] = {"filename": f"{gsm}.pc1.bedGraph", "line": "mutant" if m["condition"] == "KO" else "WT", "replicate": int(m["replicate"])}
    return {
        "campaign_id": reg["campaign_id"],
        "tiles": {"min_coverage": reg["tiles"]["min_coverage"], "chromosomes": reg["tiles"]["chromosomes"]},
        "outcome": {"samples": samples, "corrected_lines": ["WT"]},
        "orientation": {"min_rho_per_chromosome": reg["orientation"]["min_rho_per_chromosome"],
                        "min_abs_rho_gene_density": reg["orientation"]["min_abs_rho_gene_density"],
                        "floor_sensitivity": reg["orientation"]["floor_sensitivity"]},
        "null": {"permutations": reg["null"]["permutations"], "seed": reg["null"]["seed"]},
        "pass_criteria": {"unadjusted_rho_max": t["unadjusted_rho_max"], "adjusted_rho_max": t["adjusted_rho_max"],
                          "p_max": t["p_max"], "min_eligible_tiles": t["min_eligible_tiles"],
                          "adjusted_to_unadjusted_ratio_min": t["adjusted_to_unadjusted_ratio_min"],
                          "standardised_unadjusted_rho_max": t["standardised_unadjusted_rho_max"]},
    }


def cross_pairs(core_tiles_tsv, reg):
    rows = [l.rstrip("\n").split("\t") for l in open(core_tiles_tsv, encoding="utf-8")]
    col = {k: i for i, k in enumerate(rows[0])}
    rows = rows[1:]
    dlam = np.array([float(r[col["dlam_mCh"]]) for r in rows])
    ko = [g for g, m in reg["outcome"]["samples"].items() if m["condition"] == "KO"]
    wt = [g for g, m in reg["outcome"]["samples"].items() if m["condition"] == "WT"]
    pc = {g: np.array([float(r[col[f"pc1_{g}"]]) for r in rows]) for g in ko + wt}
    out = {}
    for k in ko:
        for w in wt:
            out[f"{k}-{w}"] = C.spearman(dlam, pc[k] - pc[w])
    return out


def verdict(reg, core, res, pairs, pipeline_failure):
    """Mechanical verdict; the only outcome labels are the keys of interpretation_precommitted."""
    t = reg["pass_criteria"]["tier_a"]
    comp = dict(res["component_pass"])
    comp["replicate_pairs"] = bool(all(v < 0 for v in pairs.values()))
    tier_a = bool(core["orientation"]["ok"] and core["n_tiles_eligible"] >= t["min_eligible_tiles"] and all(comp.values()))
    tier_b = bool(tier_a and res["adjusted_rho"] <= reg["pass_criteria"]["tier_b"]["adjusted_rho_max"])
    od = reg["pass_criteria"]["opposite_direction"]
    opposite = bool(core["orientation"]["ok"] and res["unadjusted_rho"] >= od["unadjusted_rho_min"] and res["unadjusted_p_positive"] <= od["p_positive_max"])
    std = res["standardised"]
    direction_consistent = bool(core["orientation"]["ok"] and res["unadjusted_rho"] < 0 and res["adjusted_rho"] < 0 and std["unadjusted_rho"] < 0
                                and res["unadjusted_p_negative"] <= t["p_max"] and res["adjusted_p_negative"] <= t["p_max"]
                                and std["unadjusted_p_negative"] <= t["p_max"] and comp["replicate_pairs"])
    if pipeline_failure:
        label = "PIPELINE_FAILURE"
    elif tier_b:
        label = "TIER_B_PASS"
    elif tier_a:
        label = "TIER_A_PASS"
    elif opposite:
        label = "OPPOSITE"
    elif direction_consistent:
        label = "NOT_PASSED_DIRECTION_CONSISTENT"
    else:
        label = "NOT_PASSED"
    return {"label": label, "tier_a_components": comp, "tier_a_pass": tier_a, "tier_b_pass": tier_b,
            "opposite": opposite, "direction_consistent": direction_consistent,
            "interpretation": reg["interpretation_precommitted"][label]}


def run(reg_path, freeze_path, intake_path, predictor, outcome_dir, out_dir, tools_dir, python):
    reg = C.load_json(reg_path)
    freeze = C.load_json(freeze_path); freeze["_path"] = freeze_path
    intake = C.load_json(intake_path)
    exp, outcome_files = check_bindings(reg, reg_path, freeze, intake, predictor, outcome_dir, tools_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    pc1_dir, pc1_stats = run_pc1(reg, outcome_dir, out_dir, tools_dir, python)
    pred = C.read_predictor(predictor)
    qc_dir, qc = pipeline_qc(reg, pc1_dir, pc1_stats, pred["tiles"])
    core_dir = out_dir / "core"
    core = C.run_registered(adapter_registration(reg), predictor, qc_dir, core_dir, exp["registration_sha256"], sha(freeze_path), intake_hashes=None)
    res = core["contrasts"]["WT"]
    pairs = cross_pairs(core_dir / "tiles.tsv", reg)
    v = verdict(reg, core, res, pairs, qc["pipeline_failure"])
    ko = [g for g, m in reg["outcome"]["samples"].items() if m["condition"] == "KO"]
    wt = [g for g, m in reg["outcome"]["samples"].items() if m["condition"] == "WT"]
    es = qc["eigen_share_per_sample"]
    strength_ratio = float(np.mean([es[g] for g in ko]) / np.mean([es[g] for g in wt]))
    lo, hi = reg["confound_flags"]["global_strength_ratio_range"]
    summary = {
        "schema": "bio.compartment-replication-result.v2",
        "campaign_id": reg["campaign_id"],
        "registered_run": True,
        "bindings": exp,
        "freeze_sha256": sha(freeze_path),
        "intake_sha256": sha(intake_path),
        "outcome_pairs": outcome_files,
        "outcome_pairs_verified_against_intake_hash_and_bytes": True,
        "note_on_core_flag": "core.outcome_hashes_verified_against_intake is False because the core evaluator sees derived bedGraphs; the pairs files were verified above",
        "pc1_stats": pc1_stats,
        "cis_pairs_kept": {g: s["pairs"]["kept"] for g, s in pc1_stats.items()},
        "pipeline_qc": qc,
        "core": core,
        "all_replicate_pairs_rho": pairs,
        "verdict": v,
        "registered_verdict": v["label"],
        "confound_flags": {
            "compartment_strength_ratio_ko_over_wt": strength_ratio,
            "global_strength_flag": not (lo <= strength_ratio <= hi),
            "replicate_concordance_sd_ratio_reported_only": core["scale_diagnostic"]["WT"]["genome_sd_ratio"],
        },
        "numpy": np.__version__, "scipy": __import__("scipy").__version__, "python": sys.version.split()[0],
    }
    C.dump_json(summary, out_dir / "summary.json")
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--registration", required=True)
    ap.add_argument("--freeze", required=True)
    ap.add_argument("--intake", required=True)
    ap.add_argument("--predictor", required=True)
    ap.add_argument("--outcome-dir", required=True)
    ap.add_argument("--tools-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--python", default=sys.executable)
    a = ap.parse_args(argv)
    s = run(Path(a.registration), Path(a.freeze), Path(a.intake), Path(a.predictor), Path(a.outcome_dir), Path(a.out_dir), Path(a.tools_dir), a.python)
    print(json.dumps({"registered_verdict": s["registered_verdict"], "verdict": s["verdict"], "confound_flags": s["confound_flags"], "pairs": s["all_replicate_pairs_rho"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
