#!/usr/bin/env python3
"""Method validation gate (pre-freeze): run code/pc1.py on two GSE126459 valid-pairs files
(hg38) and compare with the deposited HOMER 500 kb PC1 of the same samples.
V1: per-sample genome-wide Spearman >= 0.80 after per-chromosome orientation of both
    tracks against TSS density (flip where negative; chromosomes with |rho|<0.2 dropped).
V2: Spearman of per-tile deltas (mutant - corrected.1) >= 0.50.
Thresholds are fixed in registration/protocol.draft.json and read from there.
Usage: validate_pc1.py <deposited-PC1-dir>. Per-chromosome agreement is recorded as well."""
import hashlib, json, subprocess, sys, time
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))
import compartment as C
PY = sys.executable
def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()
reg = json.load(open(ROOT / "registration" / "protocol.draft.json"))
crit = reg["outcome"]["method_validation"]["criteria"]
val = ROOT / "data" / "GSE126459-validation"
dep = Path(sys.argv[1])  # directory holding the deposited GSE126459 PC1 bedGraphs (kept outside Git)
samples = {"GSM3602092": ("GSM3602092_HiC_mutant_rep1_allValidPairs.pairs.txt.gz", "GSM3602092_HiC_mutant_rep1_500KB_Active.PC1.bedGraph.gz"),
           "GSM3602088": ("GSM3602088_HiC_corrected.1_rep1_allValidPairs.pairs.txt.gz", "GSM3602088_HiC_corrected.1_rep1_500KB_Active.PC1.bedGraph.gz")}
sizes = {}
for line in open(ROOT / "tools" / "hg38.chrom.sizes"):
    c, L = line.split()[:2]
    if c in C.AUTOSOMES:
        sizes[c] = int(L)
tiles = C.tiles_for(sizes)
chrom = np.array([t[0] for t in tiles])
density = C.tss_density(ROOT / "tools" / "hg38-ncbiRefSeqSelect.txt.gz", tiles)
out = ROOT / "design" / "method-validation-runs"; out.mkdir(exist_ok=True)
rec = {"schema": "bio.method-validation.v1", "code_pc1_sha256": sha(ROOT / "code" / "pc1.py"), "script_sha256": sha(Path(__file__)), "criteria": crit, "inputs": {}, "samples": {}, "attempt_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
pipe, depo = {}, {}
for gsm, (pairs, pc1dep) in samples.items():
    bg = out / f"{gsm}.pipeline.bedGraph"; st = out / f"{gsm}.stats.json"
    t0 = time.time()
    subprocess.run([PY, str(ROOT / "code" / "pc1.py"), "pairs", "--pairs", str(val / pairs), "--chrom-sizes", str(ROOT / "tools" / "hg38.chrom.sizes"),
                    "--refseq", str(ROOT / "tools" / "hg38-ncbiRefSeqSelect.txt.gz"), "--bin-size", "500000", "--out", str(bg), "--stats", str(st)], check=True)
    rec["inputs"][gsm] = {"pairs_sha256": sha(val / pairs), "deposited_pc1_sha256": sha(dep / pc1dep), "pipeline_seconds": round(time.time() - t0, 1)}
    pipe[gsm], _ = C.bedgraph_tile_means(bg, tiles, 0.5)
    depo[gsm], _ = C.bedgraph_tile_means(dep / pc1dep, tiles, 0.5)
def orient(P):
    P1, keep, per, fl, ex = C.orient_tracks({"x": P}, chrom, density, ["x"], C.AUTOSOMES, 0.2)
    return P1["x"], keep, fl, ex
res = {}
finite = np.ones(len(tiles), bool)
for gsm in samples:
    finite &= np.isfinite(pipe[gsm]) & np.isfinite(depo[gsm])
for gsm in samples:
    p, kp, flp, exp_ = orient(np.where(finite, pipe[gsm], np.nan))
    d, kd, fld, exd = orient(np.where(finite, depo[gsm], np.nan))
    k = kp & kd & finite
    rho = C.spearman(p[k], d[k])
    per_chrom = {}
    for c in C.AUTOSOMES:
        kc = k & (chrom == c)
        per_chrom[c] = C.spearman(p[kc], d[kc]) if kc.sum() >= 10 else None
    res[gsm] = {"n_tiles": int(k.sum()), "spearman_pipeline_vs_deposited": rho, "per_chromosome_spearman": per_chrom, "pipeline_flipped": flp, "pipeline_excluded": exp_, "deposited_flipped": fld, "deposited_excluded": exd, "V1_pass": bool(rho >= crit["V1_per_sample_spearman_vs_deposited_pc1_min"])}
    pipe[gsm], depo[gsm] = p, d
k = finite & np.isfinite(pipe["GSM3602092"]) & np.isfinite(pipe["GSM3602088"]) & np.isfinite(depo["GSM3602092"]) & np.isfinite(depo["GSM3602088"])
dp = pipe["GSM3602092"][k] - pipe["GSM3602088"][k]; dd = depo["GSM3602092"][k] - depo["GSM3602088"][k]
rec["samples"] = res
rec["delta"] = {"n_tiles": int(k.sum()), "spearman_delta_pipeline_vs_deposited": C.spearman(dp, dd), "V2_pass": bool(C.spearman(dp, dd) >= crit["V2_delta_spearman_min"])}
rec["passed"] = bool(all(r["V1_pass"] for r in res.values()) and rec["delta"]["V2_pass"])
json.dump(rec, open(ROOT / "design" / "method-validation.json", "w"), indent=2)
print(json.dumps({k: v for k, v in rec.items() if k in ("samples", "delta", "passed")}, indent=1))
