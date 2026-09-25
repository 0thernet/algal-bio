#!/usr/bin/env python3
"""Mouse (mm9) 500 kb tile features for the mef/ campaign, built from genome annotation only.

Inputs in mef/ref (UCSC goldenPath/mm9; hashes written to the manifest): mm9.2bit, refGene.txt.gz,
cpgIslandExt.txt.gz. No outcome data is read. Autosomes chr1-chr19, tiles start at 0 every 500 kb,
the last tile of each chromosome is partial (as in the hg38 grid).
Columns mirror the hg38 features used by damid/:
  gc        fraction G+C over non-N bases of the tile (the hg38 gc came from the UCSC gc5Base track,
            which mm9 lacks); NaN when n_frac > 0.5 (hg38: gap_frac > 0.5)
  n_frac    fraction of N bases in the tile (the hg38 analogue is gap_frac from the UCSC gap table)
  tss_count TSS count per tile, one TSS per gene symbol: the 5' end base of that symbol's longest refGene
            transcript (txStart on +, txEnd - 1 on -) (hg38 used RefSeq Select, one transcript per gene; mm9 has no Select track)
  cpg_n     CpG islands whose start lies in the tile (reported-only robustness covariate)
Writes mef/features/mm9_tiles.tsv and mef/features/manifest.json; prints counts only."""
import gzip, hashlib, json, mmap, struct
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
REF, OUT = HERE / "ref", HERE / "features"
TILE = 500_000
CHROMS = [f"chr{i}" for i in range(1, 20)]

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def twobit_tiles(path, chroms, tile):
    """Per chromosome: (length, gc fraction over non-N bases per tile, N fraction per tile)."""
    out = {}
    with open(path, "rb") as fh, mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ) as mm:
        e = "<" if struct.unpack("<I", mm[:4])[0] == 0x1A412743 else ">"
        version, count = struct.unpack(e + "II", mm[4:12])
        osz, ofmt = (8, "Q") if version == 1 else (4, "I")
        pos, index = 16, {}
        for _ in range(count):
            ns = mm[pos]; name = mm[pos + 1:pos + 1 + ns].decode()
            index[name] = struct.unpack(e + ofmt, mm[pos + 1 + ns:pos + 1 + ns + osz])[0]; pos += 1 + ns + osz
        for c in chroms:
            p = index[c]
            size, nb = struct.unpack(e + "II", mm[p:p + 8]); p += 8
            ns_ = np.frombuffer(mm, dtype=e + "u4", count=nb, offset=p).copy(); p += 4 * nb   # copies: no views may outlive the mmap
            nl_ = np.frombuffer(mm, dtype=e + "u4", count=nb, offset=p).copy(); p += 4 * nb
            mb = struct.unpack(e + "I", mm[p:p + 4])[0]; p += 4 + 8 * mb + 4
            packed = np.frombuffer(mm, dtype=np.uint8, count=(size + 3) // 4, offset=p).copy()
            codes = np.empty(packed.size * 4, dtype=np.uint8)
            codes[0::4] = packed >> 6; codes[1::4] = (packed >> 4) & 3; codes[2::4] = (packed >> 2) & 3; codes[3::4] = packed & 3
            codes = codes[:size]
            isn = np.zeros(size, dtype=bool)
            for s, l in zip(ns_.tolist(), nl_.tolist()): isn[s:s + l] = True
            gcb = ((codes == 1) | (codes == 3)) & ~isn  # 2bit codes: T=0 C=1 A=2 G=3; N blocks are stored as T
            starts = np.arange(0, size, tile)
            lens = np.minimum(starts + tile, size) - starts
            acgt = np.add.reduceat((~isn).astype(np.int64), starts)
            gcn = np.add.reduceat(gcb.astype(np.int64), starts)
            with np.errstate(invalid="ignore", divide="ignore"):
                out[c] = (size, np.where(acgt > 0, gcn / acgt, np.nan), 1 - acgt / lens)
    return out

def main():
    OUT.mkdir(exist_ok=True)
    ins = {f: sha(REF / f) for f in ("mm9.2bit", "refGene.txt.gz", "cpgIslandExt.txt.gz")}
    tb = twobit_tiles(REF / "mm9.2bit", CHROMS, TILE)
    tiles = [(c, s) for c in CHROMS for s in range(0, tb[c][0], TILE)]
    tid = {t: k for k, t in enumerate(tiles)}; n = len(tiles)
    gc = np.concatenate([tb[c][1] for c in CHROMS]); nf = np.concatenate([tb[c][2] for c in CHROMS])
    gc[nf > 0.5] = np.nan
    best = {}
    for line in gzip.open(REF / "refGene.txt.gz", "rt"):
        f = line.rstrip("\n").split("\t"); c, strand, a, b, sym = f[2], f[3], int(f[4]), int(f[5]), f[12]
        if c in CHROMS and (sym not in best or b - a > best[sym][0]):
            best[sym] = (b - a, c, a if strand == "+" else b - 1)  # txEnd is exclusive: the minus-strand TSS base is b - 1
    tss = np.zeros(n)
    for _, c, p in best.values():
        k = tid.get((c, p // TILE * TILE))
        if k is not None: tss[k] += 1
    cpg = np.zeros(n)
    for line in gzip.open(REF / "cpgIslandExt.txt.gz", "rt"):
        f = line.split("\t"); k = tid.get((f[1], int(f[2]) // TILE * TILE))
        if k is not None: cpg[k] += 1
    with open(OUT / "mm9_tiles.tsv", "w") as fh:
        fh.write("tile_id\tchrom\tstart\ttss_count\tgc\tn_frac\tcpg_n\n")
        for k, (c, s) in enumerate(tiles):
            fh.write(f"{c}:{s}-{min(s + TILE, tb[c][0])}\t{c}\t{s}\t{int(tss[k])}\t{gc[k]:.6g}\t{nf[k]:.6g}\t{int(cpg[k])}\n")
    json.dump({"schema": "bio.mef-features.v1", "assembly": "mm9", "tile": TILE, "chromosomes": CHROMS, "n_tiles": n,
               "chrom_sizes": {c: tb[c][0] for c in CHROMS}, "inputs_sha256": ins,
               "input_sources": {f: "https://hgdownload.soe.ucsc.edu/goldenPath/mm9/" + ("bigZips/" if f.endswith("2bit") else "database/") + f for f in ins},
               "columns": ["tss_count", "gc", "n_frac", "cpg_n"], "genes_with_tss": len(best)}, open(OUT / "manifest.json", "w"), indent=1)
    print("tiles", n, "gc finite", int(np.isfinite(gc).sum()), "genes", len(best), "cpg islands placed", int(cpg.sum()))

if __name__ == "__main__":
    main()
