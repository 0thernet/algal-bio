#!/usr/bin/env python3
"""Binds the LBR registration before any GSE277503 data file exists locally."""
import datetime, hashlib, json, platform, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
def sha(p): return hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
out = ROOT / "lbr/freeze.json"
if out.exists(): sys.exit("refusing: freeze exists")
if any((ROOT / "lbr/data").iterdir()) or any((ROOT / "lbr/results").iterdir()): sys.exit("refusing: data or results present")
files = ["lbr/protocol.json", "lbr/lbr.py", "lbr/test_lbr.py", "lbr/freeze.py", "design/lbr-review.json",
         "code/screen.py", "panel/panel.py", "features/tiles.tsv"]
import numpy, scipy
json.dump({"schema": "bio.lbr-freeze.v1", "frozen_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
           "sha256": {f: sha(f) for f in files}, "python": platform.python_version(), "numpy": numpy.__version__,
           "scipy": scipy.__version__}, open(out, "w"), indent=1)
print("frozen", len(files), "files")
