#!/usr/bin/env python3
"""Freeze campaign C's registration. Write-once."""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import campaign as C

REQUIRED = [
    "registration/protocol.json",
    "registration/depmap_pairs.csv",
    "registration/depmap_gold_controls.json",
    "registration/prefreeze-review.json",
    "prior-art/prior-art-rnai.md",
    "README.campaign.md",
    "code/campaign.py", "code/prep.py", "code/freeze.py",
    "code/fetch_holdout.py", "code/confirm.py",
    "tests/test_rnai.py",
    "data/prep/prep.receipt.json", "data/prep/d2_model_map.json",
]

FORBIDDEN = ["results/confirmation.csv", "results/confirmation.summary.json"]


def main():
    fz = f"{C.ROOT}/registration/freeze.json"
    if os.path.exists(fz):
        sys.exit("refusing: registration/freeze.json already exists")
    for f in FORBIDDEN:
        if os.path.exists(f"{C.ROOT}/{f}"):
            sys.exit(f"refusing: confirmation output exists before the "
                     f"freeze: {f}")
    if os.path.exists(f"{C.ROOT}/data/sealed/fetch.receipt.json"):
        sys.exit("refusing: sealed files were fetched before the freeze")
    shas = {}
    for rel in REQUIRED:
        p = f"{C.ROOT}/{rel}"
        if not os.path.exists(p):
            sys.exit(f"refusing: required file missing: {rel}")
        shas[rel] = C.sha(p)
    for f in sorted(os.listdir(f"{C.ROOT}/registration")):
        if f.startswith("depmap_placebo"):
            rel = f"registration/{f}"
            shas[rel] = C.sha(f"{C.ROOT}/{rel}")
    import hashlib
    h = hashlib.sha256()
    for f, v in sorted(shas.items()):
        h.update(f"{f}\x00{v}\n".encode())
    frozen = {"frozen_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "schema": "bio.rnai-confirm-freeze.v1", "sha256": shas,
              "top_digest": h.hexdigest()}
    json.dump(frozen, open(fz, "w"), indent=1)
    print(json.dumps({"frozen_utc": frozen["frozen_utc"], "files": len(shas)},
                     indent=1))


if __name__ == "__main__":
    main()
