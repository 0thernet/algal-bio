#!/usr/bin/env python3
"""Freeze the registration: protocol, code, tests, receipts, selection.

Unlike the earlier campaign the holdout is not yet on disk at freeze time:
the freeze binds registration/holdout_map.json (the registered URL list and
column patterns) plus every code path that can touch the holdout, and
confirm.py independently verifies each fetched sealed file against
data/sealed/fetch.receipt.json before reading it.

Write-once: refuses to run if registration/freeze.json exists.
"""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import campaign as C


def top_digest(sha_map):
    import hashlib
    h = hashlib.sha256()
    for f, v in sorted(sha_map.items()):
        h.update(f"{f}\x00{v}\n".encode())
    return h.hexdigest()


REQUIRED = [
    "registration/protocol.json",
    "registration/holdout_map.json",
    "registration/gold_controls.json",
    "registration/prefreeze-review.json",
    "prior-art/prior-art-paralog-sl.md",
    "README.campaign.md",
    "code/campaign.py", "code/prep.py", "code/screen.py", "code/annotate.py",
    "code/gold.py", "code/freeze.py", "code/make_protocol.py",
    "code/fetch_holdout.py", "code/confirm.py",
    "data/prep/prep.receipt.json", "data/prep/pair_universe.csv",
    "data/prep/ctx_group.json", "data/prep/ky_pos.json",
    "data/prep/lof_gene_models.json",
    "data/refs/depmap-refs.receipt.json",
    "tests/test_paralog.py",
    "results/screen.real.json", "results/selection.real.csv",
    "results/selection.annotated.csv", "results/candidates.real.csv",
    "results/annotate.summary.json",
]


def main():
    fz = f"{C.ROOT}/registration/freeze.json"
    if os.path.exists(fz):
        sys.exit("refusing: registration/freeze.json already exists; the freeze is write-once")
    shas = {}
    for rel in REQUIRED:
        p = f"{C.ROOT}/{rel}"
        if not os.path.exists(p):
            sys.exit(f"refusing: required file missing: {rel}")
        shas[rel] = C.sha(p)
    # every placebo selection that exists at freeze time is bound too
    for f in sorted(os.listdir(f"{C.ROOT}/results")):
        if f.startswith("selection.placebo") or f.startswith("candidates.placebo") \
                or f.startswith("screen.placebo"):
            rel = f"results/{f}"
            shas[rel] = C.sha(f"{C.ROOT}/{rel}")
    # prep outputs bind through the receipt hashes as well
    prep = json.load(open(f"{C.ROOT}/data/prep/prep.receipt.json"))
    for k, v in prep.get("outputs", {}).items():
        p = f"{C.ROOT}/{k}"
        if not os.path.exists(p):
            sys.exit(f"refusing: prep output {k} missing")
        if C.sha(p) != v:
            sys.exit(f"refusing: prep output {k} does not match its receipt")
    frozen = {"frozen_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "schema": "bio.paralog-sl-freeze.v1",
              "sha256": shas,
              "sealed_unopened": {"sha256": {},
                                  "note": "holdout files are fetched AFTER this freeze by "
                                          "code/fetch_holdout.py and verified against "
                                          "data/sealed/fetch.receipt.json by code/confirm.py"},
              "prep_outputs_verified": list(prep.get("outputs", {}))}
    frozen["top_digest"] = top_digest(shas)
    json.dump(frozen, open(fz, "w"), indent=1)
    print(json.dumps({"frozen_utc": frozen["frozen_utc"], "files": len(shas),
                      "top_digest": frozen["top_digest"][:16]}, indent=1))


if __name__ == "__main__":
    main()
