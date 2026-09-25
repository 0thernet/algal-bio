#!/usr/bin/env python3
"""Binds the libvar2/ registration before any GSE181693 data file exists locally."""
import datetime, hashlib, json, platform, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
def sha(p): return hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
out = ROOT / "libvar2/freeze.json"
if out.exists(): sys.exit("refusing: freeze exists")
if any((ROOT / "libvar2/data").iterdir()) or any((ROOT / "libvar2/results").iterdir()):
    sys.exit("refusing: data or results present")
files = ["libvar2/protocol.json", "libvar2/libvar2.py", "libvar2/test_libvar2.py", "libvar2/freeze.py",
         "libvar/libvar.py", "libvar/features/mm10_tiles.tsv", "libvar/features/manifest.json",
         "libvar/build_mm10_features.py",
         "code/screen.py", "design/libvar2-review.json", "design/prior-art-libvar.md",
         "libvar/protocol.json", "libvar/results/result.json", "libvar/intake.json"]
import numpy, scipy, pyBigWig
json.dump({"schema": "bio.libvar-freeze.v1", "frozen_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
           "sha256": {f: sha(f) for f in files},
           "python": platform.python_version(), "numpy": numpy.__version__,
           "scipy": scipy.__version__, "pyBigWig": getattr(pyBigWig, "__version__", "unknown")}, open(out, "w"), indent=1)
print("frozen", len(files), "files")
