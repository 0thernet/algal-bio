#!/usr/bin/env python3
"""Build the acute-lamina predictor on hg19 500 kb tiles by lifting GSE300197 bins.

Method: each 10 kb interval of the four condition-merged LMNB1 CUT&RUN z-score
bigWigs (hg38) is lifted by its midpoint with pyliftover (UCSC hg38ToHg19 chain);
intervals whose midpoint fails to lift, lifts to a non-autosome, or lifts to a
different chromosome than the source are dropped. Lifted intervals are assigned to
the hg19 500 kb tile containing the lifted midpoint and averaged (equal weight per
10 kb interval). Tiles with fewer than MIN_FRACTION of their 50 possible intervals
are set to NaN. Columns match the hg38 predictor of the compartment campaign:
dlam = siLMNA - siScr per arm (mCh, DNK). TSS density from hg19 RefSeq Select.
"""
import argparse, gzip, hashlib, json, sys
from pathlib import Path
import numpy as np
import pyBigWig
from pyliftover import LiftOver

AUTOSOMES = [f"chr{i}" for i in range(1, 23)]
TILE = 500_000
MIN_FRACTION = 0.5

def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def read_sizes(p):
    d = {}
    for line in open(p):
        c, L = line.split()[:2]
        if c in AUTOSOMES:
            d[c] = int(L)
    return d

def tiles_for(sizes):
    return [(c, s, min(s + TILE, sizes[c])) for c in AUTOSOMES for s in range(0, sizes[c], TILE)]

def lift_track(bw_path, lo, sizes, index):
    bw = pyBigWig.open(str(bw_path))
    n = len(index)
    acc = np.zeros(n); cnt = np.zeros(n)
    stats = {"intervals": 0, "lifted": 0, "dropped_unmapped": 0, "dropped_chrom_change": 0}
    for c in AUTOSOMES:
        if c not in bw.chroms():
            continue
        for s, e, v in bw.intervals(c) or ():
            stats["intervals"] += 1
            mid = (s + e) // 2
            r = lo.convert_coordinate(c, mid)
            if not r:
                stats["dropped_unmapped"] += 1; continue
            c2, p2 = r[0][0], r[0][1]
            if c2 != c:
                stats["dropped_chrom_change"] += 1; continue
            if p2 >= sizes[c2]:
                stats["dropped_unmapped"] += 1; continue
            i = index[(c2, (p2 // TILE) * TILE)]
            acc[i] += v; cnt[i] += 1
            stats["lifted"] += 1
    bw.close()
    means = np.where(cnt >= MIN_FRACTION * (TILE // 10_000), acc / np.maximum(cnt, 1), np.nan)
    return means, cnt, stats

def tss_density(refseq_gz, index):
    counts = np.zeros(len(index)); seen = set()
    with gzip.open(refseq_gz, "rt") as fh:
        for line in fh:
            p = line.rstrip("\n").split("\t")
            if len(p) < 6 or p[2] not in AUTOSOMES:
                continue
            tss = int(p[4]) if p[3] == "+" else int(p[5])
            key = (p[2], tss)
            if key in seen:
                continue
            seen.add(key)
            k = (p[2], (tss // TILE) * TILE)
            if k in index:
                counts[index[k]] += 1
    return counts

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--chain", required=True)
    ap.add_argument("--chrom-sizes", required=True)
    ap.add_argument("--refseq", required=True)
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args()
    data = Path(a.data_dir); out = Path(a.out_dir); out.mkdir(parents=True, exist_ok=True)
    files = {"siScr_mCh": "GSE300197_siScr.mCh.CR.zscore.bw", "siLMNA_mCh": "GSE300197_siLMNA.mCh.CR.zscore.bw",
             "siScr_DNK": "GSE300197_siScr.DNK.CR.zscore.bw", "siLMNA_DNK": "GSE300197_siLMNA.DNK.CR.zscore.bw"}
    sizes = read_sizes(a.chrom_sizes); tiles = tiles_for(sizes)
    index = {(c, s): i for i, (c, s, _e) in enumerate(tiles)}
    lo = LiftOver(a.chain)
    cols = {}; cnts = {}; stats = {}; hashes = {}
    for k, f in files.items():
        hashes[k] = sha256(data / f)
        cols[k], cnts[k], stats[k] = lift_track(data / f, lo, sizes, index)
    hashes["chain"] = sha256(a.chain); hashes["chrom_sizes"] = sha256(a.chrom_sizes); hashes["refseq"] = sha256(a.refseq)
    tss = tss_density(a.refseq, index)
    dl_m = cols["siLMNA_mCh"] - cols["siScr_mCh"]; dl_d = cols["siLMNA_DNK"] - cols["siScr_DNK"]
    cov_min = np.min(np.stack([cnts[k] for k in files]), axis=0) / (TILE // 10_000)
    tsv = out / "predictor_hg19.tsv"
    with open(tsv, "w") as fh:
        fh.write("tile_id\tchrom\tstart\tend\tsiScr_mCh\tsiLMNA_mCh\tdlam_mCh\tsiScr_DNK\tsiLMNA_DNK\tdlam_DNK\tcov_min\ttss_count\n")
        for i, (c, s, e) in enumerate(tiles):
            fh.write(f"{c}:{s}-{e}\t{c}\t{s}\t{e}\t" + "\t".join(f"{x:.6f}" for x in (cols['siScr_mCh'][i], cols['siLMNA_mCh'][i], dl_m[i], cols['siScr_DNK'][i], cols['siLMNA_DNK'][i], dl_d[i])) + f"\t{cov_min[i]:.4f}\t{int(tss[i])}\n")
    man = {"schema": "bio.compartment-predictor-hg19.v1", "method": __doc__.strip(), "tile": TILE, "min_fraction": MIN_FRACTION,
           "n_tiles": len(tiles), "n_tiles_predictor_finite": int(np.isfinite(dl_m).sum()), "lift_stats": stats,
           "input_sha256": hashes, "predictor_tsv_sha256": sha256(tsv), "numpy": np.__version__, "python": sys.version.split()[0]}
    json.dump(man, open(out / "predictor_hg19.manifest.json", "w"), indent=2)
    print(json.dumps({k: v for k, v in man.items() if k != "method"}, indent=1))

if __name__ == "__main__":
    main()
