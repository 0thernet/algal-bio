#!/usr/bin/env python3
"""Binds the libvar/ registration before any GSE135834 data file exists locally."""
import datetime, hashlib, json, platform, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
def sha(p): return hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
out = ROOT / "libvar/freeze.json"
if out.exists(): sys.exit("refusing: freeze exists")
if any((ROOT / "libvar/data").iterdir()) or any((ROOT / "libvar/results").iterdir()):
    sys.exit("refusing: data or results present")
files = ["libvar/protocol.json", "libvar/libvar.py", "libvar/test_libvar.py", "libvar/freeze.py",
         "libvar/build_mm10_features.py", "libvar/features/mm10_tiles.tsv", "libvar/features/manifest.json",
         "features/tiles.tsv", "code/build_features.py", "code/add_external.py",
         "mef/features/mm9_tiles.tsv", "mef/features/manifest.json", "mef/build_mm9_features.py",
         "code/screen.py", "design/libvar-review.json", "design/prior-art-libvar.md",
         "damid/intake.json", "lbr/intake.json", "mef/intake.json",
         "damid/protocol.json", "lbr/protocol.json", "mef/protocol.json",
         "damid/results/result.json", "lbr/results/result.json", "mef/results/result.json"]
import numpy, scipy, pyBigWig
json.dump({"schema": "bio.libvar-freeze.v1", "frozen_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
           "sha256": {f: sha(f) for f in files},
           "python": platform.python_version(), "numpy": numpy.__version__,
           "scipy": scipy.__version__, "pyBigWig": getattr(pyBigWig, "__version__", "unknown")}, open(out, "w"), indent=1)
print("frozen", len(files), "files")
