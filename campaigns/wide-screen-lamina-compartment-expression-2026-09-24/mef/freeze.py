#!/usr/bin/env python3
"""Binds the mef/ registration before any GSE124205 data file exists locally."""
import datetime, hashlib, json, platform, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
def sha(p): return hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
out = ROOT / "mef/freeze.json"
if out.exists(): sys.exit("refusing: freeze exists")
if any((ROOT / "mef/data").iterdir()) or any((ROOT / "mef/results").iterdir()): sys.exit("refusing: data or results present")
files = ["mef/protocol.json", "mef/mef.py", "mef/test_mef.py", "mef/freeze.py", "mef/build_mm9_features.py",
         "mef/features/mm9_tiles.tsv", "mef/features/manifest.json", "design/mef-review.json", "design/prior-art-mef.md",
         "code/screen.py", "lbr/lbr.py", "panel/panel.py"]
import numpy, scipy, pyBigWig
json.dump({"schema": "bio.mef-freeze.v1", "frozen_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
           "sha256": {f: sha(f) for f in files}, "python": platform.python_version(), "numpy": numpy.__version__,
           "scipy": scipy.__version__, "pyBigWig": getattr(pyBigWig, "__version__", "unknown")}, open(out, "w"), indent=1)
print("frozen", len(files), "files")
