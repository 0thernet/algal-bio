#!/usr/bin/env python3
"""Freeze the replication registration. Refuses if any GSE314556 outcome file exists,
if the independent review verdict is not PASS/PASS_WITH_REPAIRS, or if the method
validation record is missing. Binds SHA-256 of every artefact the run checks and
archives their bytes under registration/archive-<n>/."""
import datetime, hashlib, json, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[1]
def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
n = int(sys.argv[1]) if len(sys.argv) > 1 else 1
outcome_dir = ROOT / "data" / "GSE314556"
if outcome_dir.exists() and any(outcome_dir.iterdir()):
    sys.exit("refusing to freeze: outcome files already present")
draft = json.load(open(ROOT / "registration" / "protocol.draft.json"))
review = json.load(open(ROOT / "design" / "independent-review.json"))
if review.get("verdict") not in ("PASS", "PASS_WITH_REPAIRS"):
    sys.exit(f"refusing to freeze: review verdict {review.get('verdict')}")
mv = json.load(open(ROOT / "design" / "method-validation.json"))
if not mv.get("passed"):
    sys.exit("refusing to freeze: method validation not passed")
for k, f in (("code_pc1_sha256", "code/pc1.py"), ("test_pc1_sha256", "code/test_pc1.py")):
    if draft["outcome"]["pc1_pipeline"][k] != sha(ROOT / f):
        sys.exit(f"refusing to freeze: draft {k} does not match {f}")
if mv.get("script_sha256") != sha(ROOT / "design" / "validate_pc1.py"):
    sys.exit("refusing to freeze: method validation record was produced by different validate_pc1.py bytes")
if mv["code_pc1_sha256"] != sha(ROOT / "code" / "pc1.py"):
    sys.exit("refusing to freeze: method validation was run with different pc1.py bytes")
pred = ROOT / "results" / "predictor" / "predictor_hg19.tsv"
if sha(pred) != draft["predictor"]["predictor_tsv_sha256"]:
    sys.exit("refusing to freeze: predictor hash mismatch")
frozen = dict(draft)
frozen["status"] = "frozen"
frozen["frozen_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
frozen["outcome"]["method_validation"]["status"] = draft["outcome"]["method_validation"]["status"] + "; record bound at freeze (design/method-validation.json)"
frozen["outcome"]["method_validation"]["record_sha256"] = sha(ROOT / "design" / "method-validation.json")
fp = ROOT / "registration" / "protocol.frozen.json"
if fp.exists() or (ROOT / "registration" / "freeze.json").exists():
    sys.exit("refusing to freeze: protocol.frozen.json or freeze.json already exists; retire them as freeze-<n> first")
with open(fp, "w") as fh:
    json.dump(frozen, fh, indent=2); fh.write("\n")
bound = {
    "registration_sha256": fp,
    "code_replicate_sha256": ROOT / "code" / "replicate.py",
    "code_compartment_sha256": ROOT / "code" / "compartment.py",
    "code_pc1_sha256": ROOT / "code" / "pc1.py",
    "test_replicate_sha256": ROOT / "code" / "test_replicate.py",
    "test_pc1_sha256": ROOT / "code" / "test_pc1.py",
    "requirements_lock_sha256": ROOT / "code" / "requirements.lock",
    "predictor_tsv_sha256": pred,
    "chrom_sizes_sha256": ROOT / "tools" / draft["tiles"]["chrom_sizes_file"],
    "refseq_sha256": ROOT / "tools" / draft["orientation"]["refseq_file"],
    "predictor_manifest_sha256": ROOT / "results" / "predictor" / "predictor_hg19.manifest.json",
    "lift_predictor_sha256": ROOT / "code" / "lift_predictor.py",
    "independent_review_sha256": ROOT / "design" / "independent-review.json",
    "skeptical_review_sha256": ROOT / "design" / "skeptical-review.md",
    "protocol_design_sha256": ROOT / "design" / "fixed-protocol.md",
    "method_validation_sha256": ROOT / "design" / "method-validation.json",
    "method_validation_script_sha256": ROOT / "design" / "validate_pc1.py",
    "method_validation_attempts_sha256": ROOT / "design" / "method-validation-attempts.md",
    "prior_art_caruso_sha256": ROOT / "prior-art" / "caruso-2026.md",
    "null_sd_estimate_sha256": ROOT / "design" / "null-sd-estimate.json",
    "registration_draft_sha256": ROOT / "registration" / "protocol.draft.json",
}
arch = ROOT / "registration" / f"archive-{n:03d}"
arch.mkdir(exist_ok=True)
receipt = {"schema": "bio.freeze-receipt.v2", "campaign_id": frozen["campaign_id"], "frozen_utc": frozen["frozen_utc"], "freeze_number": n}
for k, p in bound.items():
    receipt[k] = sha(p)
    if p.stat().st_size < 50_000_000:
        (arch / p.name).write_bytes(p.read_bytes())
receipt["archived_bytes"] = str(arch.relative_to(ROOT)) + "/ (every bound file; predictor tsv included)"
receipt["outcome_files_present_at_freeze"] = False
receipt["outcome_expected"] = {g: {"filename": m["filename"], "bytes_expected": m["bytes_expected"]} for g, m in frozen["outcome"]["samples"].items()}
with open(ROOT / "registration" / "freeze.json", "w") as fh:
    json.dump(receipt, fh, indent=2); fh.write("\n")
print(json.dumps(receipt, indent=2))
