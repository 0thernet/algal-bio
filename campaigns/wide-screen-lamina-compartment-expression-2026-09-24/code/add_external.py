#!/usr/bin/env python3
"""Append genome-annotation features to features/tiles.tsv (in place, recorded in manifest):
gc (mean GC fraction, UCSC gc5Base), cpg_n (CpG islands with start in tile), gap_frac,
giemsa (cytoband stain: gneg 0, gpos25..100 -> 0.25..1, acen/gvar/stalk NaN), arm_pos
(0 at centromere, 1 at telomere)."""
import gzip, hashlib, json
from pathlib import Path
import numpy as np, pyBigWig
ROOT = Path(__file__).resolve().parents[1]; EXT = ROOT / "data/external"; TILE = 500_000
rows = [l.rstrip("\n").split("\t") for l in open(ROOT / "features/tiles.tsv")]
hdr, rows = rows[0], rows[1:]
tiles = [(r[1], int(r[2])) for r in rows]; tid = {t: k for k, t in enumerate(tiles)}; n = len(tiles)
F = {k: np.zeros(n) for k in ("cpg_n", "gap_frac")}
for l in gzip.open(EXT / "cpgIslandExt.txt.gz", "rt"):
    f = l.split("\t"); k = tid.get((f[1], int(f[2]) // TILE * TILE))
    if k is not None: F["cpg_n"][k] += 1
for l in gzip.open(EXT / "gap.txt.gz", "rt"):
    f = l.split("\t"); c, s, e = f[1], int(f[2]), int(f[3])
    for t in range(s // TILE * TILE, e, TILE):
        k = tid.get((c, t))
        if k is not None: F["gap_frac"][k] += (min(e, t + TILE) - max(s, t)) / TILE
stain = {"gneg": 0.0, "gpos25": .25, "gpos50": .5, "gpos75": .75, "gpos100": 1.0}
F["giemsa"] = np.full(n, np.nan); cen = {}; size = {}
for l in gzip.open(EXT / "cytoBand.txt.gz", "rt"):
    c, s, e, _, g = l.rstrip("\n").split("\t"); s, e = int(s), int(e)
    size[c] = max(size.get(c, 0), e)
    if g == "acen": cen.setdefault(c, []).extend([s, e])
    if g in stain:
        for t in range(s // TILE * TILE, e, TILE):
            k = tid.get((c, t))
            if k is not None and (min(e, t + TILE) - max(s, t)) >= TILE / 2: F["giemsa"][k] = stain[g]
F["arm_pos"] = np.full(n, np.nan)
for k, (c, s) in enumerate(tiles):
    if c in cen:
        m = s + TILE / 2; lo, hi = min(cen[c]), max(cen[c])
        F["arm_pos"][k] = (lo - m) / lo if m < lo else (m - hi) / (size[c] - hi) if m > hi else 0.0
bw = pyBigWig.open(str(EXT / "hg38.gc5Base.bw"))
bc = bw.chroms()
F["gc"] = np.array([(bw.stats(c, s, min(s + TILE, bc[c]), type="mean")[0] or np.nan) / 100 if c in bc and s < bc[c] else np.nan for c, s in tiles])
F["gc"][F["gap_frac"] > 0.5] = np.nan
cols = [c for c in F if c not in hdr]
with open(ROOT / "features/tiles.tsv", "w") as fh:
    fh.write("\t".join(hdr + cols) + "\n")
    for k, r in enumerate(rows): fh.write("\t".join(r + [f"{F[c][k]:.6g}" for c in cols]) + "\n")
m = json.load(open(ROOT / "features/manifest.json"))
m["columns"] += cols; m["external"] = {"code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    "inputs_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(EXT.glob("*.gz"))},
    "gc5Base_bytes": (EXT / "hg38.gc5Base.bw").stat().st_size}
m["finite_per_column"].update({c: int(np.isfinite(F[c]).sum()) for c in cols})
json.dump(m, open(ROOT / "features/manifest.json", "w"), indent=1)
print({c: int(np.isfinite(F[c]).sum()) for c in cols})
