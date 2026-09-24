#!/usr/bin/env python3
"""Freeze the registration: copy protocol.draft.json -> protocol.frozen.json with
status/frozen_utc/predictor hash bound, and write freeze.json with SHA-256 of
every frozen artefact. Refuses to run if any outcome file already exists."""
import datetime, hashlib, json, os, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[1]
def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()
outcome_dir = ROOT / "data" / "GSE126459"
if outcome_dir.exists() and any(outcome_dir.iterdir()):
    sys.exit("refusing to freeze: outcome files already present")
draft = json.load(open(ROOT / "registration" / "protocol.draft.json"))
review = json.load(open(ROOT / "design" / "independent-review.json"))
if review.get("verdict") not in ("PASS", "PASS_WITH_REPAIRS"):
    sys.exit(f"refusing to freeze: review verdict {review.get('verdict')}")
if "round_3" not in review:
    sys.exit("refusing to freeze: amendment round_3 review missing")
pred_manifest = json.load(open(ROOT / "results" / "predictor" / "predictor.manifest.json"))
pred_sha = sha(ROOT / "results" / "predictor" / "predictor.tsv")
assert pred_sha == pred_manifest["predictor_tsv_sha256"]
frozen = dict(draft)
frozen["status"] = "frozen"
frozen["frozen_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
frozen["predictor"] = dict(draft["predictor"], predictor_tsv_sha256=pred_sha)
fp = ROOT / "registration" / "protocol.frozen.json"
with open(fp, "w") as fh:
    json.dump(frozen, fh, indent=2); fh.write("\n")
arch = ROOT / "registration" / "archive-002"
arch.mkdir(exist_ok=True)
for name in ("compartment.py", "test_compartment.py", "requirements.lock"):
    (arch / name).write_bytes((ROOT / "code" / name).read_bytes())
receipt = {
    "schema": "bio.freeze-receipt.v1",
    "campaign_id": frozen["campaign_id"],
    "frozen_utc": frozen["frozen_utc"],
    "registration_sha256": sha(fp),
    "registration_draft_sha256": sha(ROOT / "registration" / "protocol.draft.json"),
    "code_sha256": sha(ROOT / "code" / "compartment.py"),
    "test_sha256": sha(ROOT / "code" / "test_compartment.py"),
    "requirements_lock_sha256": sha(ROOT / "code" / "requirements.lock"),
    "predictor_tsv_sha256": pred_sha,
    "predictor_manifest_sha256": sha(ROOT / "results" / "predictor" / "predictor.manifest.json"),
    "independent_review_sha256": sha(ROOT / "design" / "independent-review.json"),
    "skeptical_review_sha256": sha(ROOT / "design" / "skeptical-review.md"),
    "protocol_design_sha256": sha(ROOT / "design" / "protocol.md"),
    "outcome_files_present_at_freeze": False,
    "freeze_number": 2,
    "archived_bytes": "registration/archive-002/{compartment.py,test_compartment.py,requirements.lock}",
    "retired_freeze_001_sha256": sha(ROOT / "registration" / "freeze-001.json"),
    "retired_intake_001_sha256": sha(ROOT / "registration" / "intake-001.json"),
    "amendment": "amend-001 (chromosome-name adapter after run-001 zero-tile failure); intake-001 files retained unopened under data/GSE126459.intake-001 and re-downloaded for intake-002",
    "outcome_expected": {g: m["filename"] for g, m in frozen["outcome"]["samples"].items()},
}
with open(ROOT / "registration" / "freeze.json", "w") as fh:
    json.dump(receipt, fh, indent=2); fh.write("\n")
print(json.dumps(receipt, indent=2))
