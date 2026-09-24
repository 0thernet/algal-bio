#!/usr/bin/env python3
"""Enforce the current prospective no-go; do not fabricate candidate assessment."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.check_registration import check_registration, read_json  # noqa: E402

READINESS_KEYS = {
    "contract", "campaign", "status", "decision", "source_registration", "source_registration_sha256",
    "question", "new_registration_required", "missing", "candidate_selection", "holdout_opened", "interpretation",
}
QUESTION = "Whether unperturbed chromatin features improve independent expression-response prediction beyond an expression-only baseline"
MISSING_REQUIREMENTS = [
    "An independent matched or crossed cohort with resolved biological replication and compatible assays",
    "Domain review of the estimand, precision, controls and empirical follow-up endpoint",
    "A frozen search/evaluation split with qualified evaluator isolation and a contamination audit",
    "Measured live investigator qualification with verified model, price and funded resource envelope",
]
INTERPRETATION = "This is a documented readiness decision, not a search with zero surviving candidates and not a biological negative finding."


def readiness(registered: Path, run: Path | None = None, *, root: Path = ROOT) -> dict:
    if registered.resolve() != (root / "campaigns/prospective-001").resolve():
        raise ValueError("only the reviewed current readiness record is supported; new studies need an admitted evaluator")
    plan = read_json(registered / "registration.json")
    if not isinstance(plan, dict) or set(plan) != READINESS_KEYS:
        raise ValueError("unexpected readiness fields; no new scientific claims are admitted")
    if plan.get("contract") != "bio.prospective-readiness.v1" or plan.get("status") != "not_run" or plan.get("decision") != "no_go":
        raise ValueError("editing a readiness decision cannot activate candidate evaluation")
    source = root / "campaigns/lamina-context-pilot/registration.json"
    check_registration(source.parent, root=root)
    if plan.get("source_registration") != source.relative_to(root).as_posix() or \
            hashlib.sha256(source.read_bytes()).hexdigest() != plan.get("source_registration_sha256"):
        raise ValueError("prospective decision no longer matches its source registration")
    active = read_json(source)
    if active["decision"]["status"] != "data_limited" or active["splits"]["holdout"]["status"] != "unselected":
        raise ValueError("a new biological design requires independent review and a new registered evaluator")
    if plan.get("candidate_selection") != "not_performed" or plan.get("holdout_opened") is not False or \
            plan.get("new_registration_required") is not True or plan.get("missing") != MISSING_REQUIREMENTS or \
            plan.get("campaign") != "prospective-001" or plan.get("question") != QUESTION or \
            plan.get("interpretation") != INTERPRETATION:
        raise ValueError("unsupported prospective state")
    if run is not None:
        # Do not even read candidate prose or evaluator inputs behind a closed gate.
        raise ValueError("candidate evaluation denied: no qualified prospective study exists; supplied run was not opened")
    return {
        "contract": "bio.prospective-decision.v1", "campaign": "prospective-001",
        "registration_sha256": hashlib.sha256((registered / "registration.json").read_bytes()).hexdigest(),
        "status": "not_run", "decision": "no_go", "candidates_assessed": 0,
        "holdout_opened": False, "reasons": plan["missing"], "interpretation": plan["interpretation"],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registered", type=Path, required=True)
    parser.add_argument("--run", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        report = readiness(args.registered, args.run)
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open("x") as stream:
                stream.write(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))
    except (ValueError, OSError, KeyError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)
