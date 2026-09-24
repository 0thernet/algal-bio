#!/usr/bin/env python3
"""freeze.py <stage>
pre-discovery: binds config, code, tests, features, external inputs, the pre-discovery review
  and the interpreter/library versions; refuses if any results exist.
survivors: re-checks every pre-discovery hash, then binds the discovery output (survivor list
  and the separate all-pairs file); refuses if a confirmation result exists."""
import datetime, hashlib, json, platform, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
def sha(p):
    h = hashlib.sha256()
    with open(ROOT / p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""): h.update(chunk)
    return h.hexdigest()
stage = sys.argv[1]
now = datetime.datetime.now(datetime.timezone.utc).isoformat()
extra = {}
if stage == "pre-discovery":
    if any((ROOT / "results").iterdir()): sys.exit("refusing: results already exist")
    files = ["registration/config.json", "code/screen.py", "code/test_screen.py", "code/build_features.py",
             "code/add_external.py", "features/tiles.tsv", "features/tiles.base.tsv", "features/manifest.json",
             "design/plan.md", "design/pre-discovery-review.json", "design/repair-review.json", "registration/freeze.py"]
    files += sorted(str(p.relative_to(ROOT)) for p in (ROOT / "data/external").iterdir() if p.is_file())
    import numpy, scipy
    extra = {"python": platform.python_version(), "numpy": numpy.__version__, "scipy": scipy.__version__,
             "repairs_after_review": "blocker (baseline PC1 covariate for each KO-minus-WT delta) and minors (unordered exclusions, 10-tile minimum shift, all-pairs stats in a separate file, confirm hash checks, wider freeze binding, 6 new tests) applied after the review and verified by the 11-test suite; an independent repair review (design/repair-review.json) returned PASS with no blocking items; its minors (confirm re-checks the screen.py hash; freeze binds itself and the repair review) were applied before this freeze"}
    out = ROOT / "registration/freeze-pre-discovery.json"
elif stage == "survivors":
    if (ROOT / "results/confirmation.json").exists(): sys.exit("refusing: confirmation already run")
    pre = json.load(open(ROOT / "registration/freeze-pre-discovery.json"))["sha256"]
    bad = [f for f, h in pre.items() if sha(f) != h]
    if bad: sys.exit(f"refusing: changed since pre-discovery freeze: {bad}")
    files = ["results/discovery.json", "results/discovery-all.json", "registration/freeze-pre-discovery.json"]
    out = ROOT / "registration/freeze-survivors.json"
else:
    sys.exit("stage must be pre-discovery or survivors")
if out.exists(): sys.exit(f"refusing: {out.name} exists")
json.dump({"schema": "bio.wide-screen-freeze.v2", "stage": stage, "frozen_utc": now,
           "sha256": {f: sha(f) for f in files}, **extra}, open(out, "w"), indent=1)
print(stage, "frozen", now, len(files), "files")
