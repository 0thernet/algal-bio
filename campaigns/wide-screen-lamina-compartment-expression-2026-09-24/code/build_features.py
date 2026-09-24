#!/usr/bin/env python3
"""Per-tile feature table (hg38, 500 kb, chr1-22) from inputs already on disk.
Writes features/tiles.tsv and features/manifest.json. Prints only shape and counts."""
import gzip, hashlib, json, math, sys
from pathlib import Path
import numpy as np
from pyliftover import LiftOver

R = Path("<home>/Documents/research")
LIVE = R / "biology-live-2026-09-24/data"
COMP = R / "biology-compartment-2026-09-24"
REPL = R / "biology-replication-2026-09-24"
OUT = Path(__file__).resolve().parents[1] / "features"
TILE = 500_000
CHROMS = [f"chr{i}" for i in range(1, 23)]

def sha(p):
    h = hashlib.sha256(); h.update(Path(p).read_bytes()); return h.hexdigest()

inputs = {}
def use(p):
    inputs[str(Path(p).relative_to(R))] = sha(p); return p

# base grid + lamina predictor
rows = [l.rstrip("\n").split("\t") for l in open(use(COMP / "results/predictor/predictor.tsv"))]
hdr, rows = rows[0], rows[1:]
ix = {c: i for i, c in enumerate(hdr)}
tiles = [(r[ix["chrom"]], int(r[ix["start"]])) for r in rows]
tid = {t: k for k, t in enumerate(tiles)}
n = len(tiles)
F = {}
for c in ("siScr_mCh", "dlam_mCh", "siScr_DNK", "dlam_DNK", "tss_count"):
    F[c] = np.array([float(r[ix[c]]) for r in rows])

def bedgraph(path, prefix=""):
    v = np.full(n, np.nan)
    op = gzip.open if str(path).endswith(".gz") else open
    for line in op(use(path), "rt"):
        if line.startswith("track"): continue
        c, s, e, x = line.split()[:4]
        c = c if c.startswith("chr") else "chr" + c
        k = tid.get((c, int(s) // TILE * TILE))
        if k is not None: v[k] = float(x)
    return v

# GSE126459 R225X vs corrected (HOMER PC1, hg38)
g = COMP / "data/GSE126459"
pc = {s: bedgraph(next(g.glob(f"{s}_*.bedGraph.gz"))) for s in
      ["GSM3602088", "GSM3602089", "GSM3602090", "GSM3602091", "GSM3602092", "GSM3602093"]}
corr = np.nanmean([pc[s] for s in ["GSM3602088", "GSM3602089", "GSM3602090", "GSM3602091"]], axis=0)
mut = np.nanmean([pc["GSM3602092"], pc["GSM3602093"]], axis=0)
F["pc1_cm_base"] = corr; F["dpc1_cm_r225x"] = mut - corr

# GSE314556 GM12878 KO vs WT (own pc1.py, hg19) mapped via hg38 tile midpoint -> hg19
lo = LiftOver(str(use(REPL / "tools/hg38ToHg19.over.chain.gz")))
p1 = REPL / "results/run-001/pc1"
def hg19_track(s):
    d = {}
    for line in open(use(p1 / f"{s}.pc1.bedGraph")):
        c, a, b, x = line.split()[:4]; d[(c, int(a) // TILE * TILE)] = float(x)
    return d
t19 = {s: hg19_track(s) for s in ["GSM9401860", "GSM9401861", "GSM9401862", "GSM9401863"]}
wt = np.full(n, np.nan); ko = np.full(n, np.nan)
for k, (c, s) in enumerate(tiles):
    m = lo.convert_coordinate(c, s + TILE // 2)
    if not m or m[0][0] != c: continue
    key = (c, int(m[0][1]) // TILE * TILE)
    a = [t19[x].get(key, np.nan) for x in ("GSM9401860", "GSM9401861")]
    b = [t19[x].get(key, np.nan) for x in ("GSM9401862", "GSM9401863")]
    if all(map(np.isfinite, a + b)): wt[k] = np.mean(a); ko[k] = np.mean(b)
F["pc1_lcl_base"] = wt; F["dpc1_lcl_ko"] = ko - wt

# gene TSS -> tile (RefSeq Select, one row per gene symbol)
tss = {}
for line in gzip.open(use(LIVE / "hg38-ncbiRefSeqSelect.txt.gz"), "rt"):
    f = line.split("\t"); c, strand, sym = f[2], f[3], f[12]
    if c in CHROMS and sym not in tss:
        tss[sym] = (c, int(f[4]) if strand == "+" else int(f[5]))

def tile_lfc(counts, a_cols, b_cols, min_mean=10):
    """mean over genes in tile of log2((mean b + 1)/(mean a + 1)) after CPM scaling."""
    lib = {c: sum(v[c] for v in counts.values()) for c in a_cols + b_cols}
    acc = [[] for _ in range(n)]
    for sym, v in counts.items():
        if sym not in tss: continue
        cpm = {c: v[c] / lib[c] * 1e6 for c in lib}
        ma = np.mean([cpm[c] for c in a_cols]); mb = np.mean([cpm[c] for c in b_cols])
        if (np.mean([v[c] for c in a_cols + b_cols])) < min_mean: continue
        c, p = tss[sym]; k = tid.get((c, p // TILE * TILE))
        if k is not None: acc[k].append(math.log2((mb + 1) / (ma + 1)))
    return np.array([np.mean(x) if len(x) >= 2 else np.nan for x in acc]), np.array([len(x) for x in acc])

def read_counts(path, sep):
    op = gzip.open if str(path).endswith(".gz") else open
    lines = [l.rstrip("\r\n").lstrip("﻿").split(sep) for l in op(use(path), "rt", encoding="utf-8")]
    h = lines[0]; h = h[1:] if h[0] in ("", "Gene") else h
    d = {}
    for l in lines[1:]:
        if len(l) == len(h) + 1: d[l[0]] = dict(zip(h, map(float, l[1:])))
    return h, d

h, d = read_counts(LIVE / "GSE300197_RNA.counts.txt.gz", "\t")
F["lfc_ipsc_silmna"], F["n_genes_ipsc"] = tile_lfc(d, [c for c in h if c.startswith("siScr")], [c for c in h if c.startswith("siLMNA")])
h, d = read_counts(LIVE / "GSE304575_Raw_Counts_table.csv.gz", ";")
F["lfc_cm_h222p"], F["n_genes_cm"] = tile_lfc(d, [c for c in h if "_C1-3_" in c], [c for c in h if "H222P" in c])

OUT.mkdir(exist_ok=True)
cols = list(F)
with open(OUT / "tiles.tsv", "w") as fh:
    fh.write("tile_id\tchrom\tstart\t" + "\t".join(cols) + "\n")
    for k, (c, s) in enumerate(tiles):
        fh.write(f"{c}:{s}-{s+TILE}\t{c}\t{s}\t" + "\t".join(f"{F[x][k]:.6g}" for x in cols) + "\n")
json.dump({"schema": "bio.wide-screen-features.v1", "n_tiles": n, "columns": cols, "inputs_sha256": inputs,
           "finite_per_column": {x: int(np.isfinite(F[x]).sum()) for x in cols},
           "code_sha256": sha(__file__)}, open(OUT / "manifest.json", "w"), indent=1)
print("tiles", n, {x: int(np.isfinite(F[x]).sum()) for x in cols})
