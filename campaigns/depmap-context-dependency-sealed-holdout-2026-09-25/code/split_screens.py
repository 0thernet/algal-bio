#!/usr/bin/env python3
"""Route ScreenGeneEffect.csv rows by library suffix without computing anything on them.

AV (Avana Cas9, Broad)      -> data/discovery/ScreenGeneEffect.AV.csv
KY (KY Cas9, Sanger)        -> data/sealed/ScreenGeneEffect.KY.csv   (holdout; never opened before freeze)
CD (Humagne-CD Cas12a)      -> data/other/ScreenGeneEffect.CD.csv    (not used)
The header line is copied to every part. A receipt records line counts and sha256 of each part.
"""
import hashlib, json, os, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = f"{ROOT}/data/sealed/ScreenGeneEffect.csv"  # unsplit source, kept sealed: it carries the KY rows
parts = {"AV": f"{ROOT}/data/discovery/ScreenGeneEffect.AV.csv",
         "KY": f"{ROOT}/data/sealed/ScreenGeneEffect.KY.csv",
         "CD": f"{ROOT}/data/other/ScreenGeneEffect.CD.csv"}
for p in parts.values():
    os.makedirs(os.path.dirname(p), exist_ok=True)
outs = {k: open(p, "w") for k, p in parts.items()}
counts = {k: 0 for k in parts}
with open(src) as fh:
    header = fh.readline()
    for o in outs.values():
        o.write(header)
    for line in fh:
        sid = line.split(",", 1)[0]
        lib = re.search(r"\.([A-Z]+)\d+$", sid).group(1)
        outs[lib].write(line)
        counts[lib] += 1
for o in outs.values():
    o.close()
def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 24), b""):
            h.update(c)
    return h.hexdigest()
receipt = {"source": "data/depmap24q4/ScreenGeneEffect.csv", "source_sha256": sha(src),
           "parts": {k: {"path": os.path.relpath(p, ROOT), "rows": counts[k], "sha256": sha(p)} for k, p in parts.items()},
           "header_columns": len(header.rstrip("\n").split(",")) - 1}
json.dump(receipt, open(f"{ROOT}/data/split.receipt.json", "w"), indent=1)
print(json.dumps(receipt, indent=1))
