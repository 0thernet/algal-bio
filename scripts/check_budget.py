#!/usr/bin/env python3
"""Independent integer accounting audit; Bun verifies hashes and event transitions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
COST_KEYS = {"inferenceMicros", "computeMicros", "storageMicros", "egressMicros", "recoveryMicros"}
MAX_MICROS = 1_000_000_000_000


def money(value: object) -> int:
    if type(value) is not int or not 0 <= value <= MAX_MICROS:
        raise ValueError("Money must be a nonnegative bounded integer number of micros")
    return value


def cost(value: dict) -> int:
    if type(value) is not dict or set(value) != COST_KEYS:
        raise ValueError("Every cost component, including recovery, must be priced")
    return money(sum(money(item) for item in value.values()))


def audit(directory: Path) -> dict:
    integrity = subprocess.run(
        ["bun", str(ROOT / "orchestrator/check-journal.ts"), str(directory.resolve())],
        capture_output=True, text=True, check=True,
    )
    chain = json.loads(integrity.stdout)
    events = [json.loads(path.read_text()) for path in sorted(directory.glob("[0-9]*.json"))]
    if events[0]["kind"] != "campaign-created":
        raise ValueError("Missing registered campaign")
    config = events[0]["data"]["config"]
    if config["currency"] != "USD":
        raise ValueError("Unsupported accounting currency")
    budget = money(config["budgetMicros"])
    tasks: dict[str, dict] = {}
    spent = 0
    breach = False
    for event in events[1:]:
        kind, data = event["kind"], event["data"]
        task_id = data.get("taskId")
        if kind == "campaign-created":
            raise ValueError("Campaign configuration cannot be rewritten")
        if kind == "task-proposed":
            task_id = data["proposal"]["taskId"]
            if task_id in tasks:
                raise ValueError("Duplicate task")
            tasks[task_id] = {"estimate": cost(data["estimate"]), "components": data["estimate"], "reserved": 0, "status": "proposed", "attempts": 0}
        elif kind == "task-revised":
            if tasks[task_id]["status"] not in {"proposed", "rejected"}:
                raise ValueError("Admitted cost cannot be revised")
            tasks[task_id].update(estimate=cost(data["estimate"]), components=data["estimate"], status="proposed")
        elif kind == "task-retried":
            if tasks[task_id]["status"] not in {"failed", "cancelled"}:
                raise ValueError("Retry did not reconcile its previous attempt")
            tasks[task_id]["status"] = "proposed"
        elif kind == "task-rejected":
            if tasks[task_id]["status"] != "proposed":
                raise ValueError("Cannot reject a task with an unreconciled reservation")
            tasks[task_id]["status"] = "rejected"
        elif kind == "task-admitted":
            task = tasks[task_id]
            if task["status"] != "proposed" or breach or any(t["status"] in {"uncertain", "submitting"} for t in tasks.values()):
                raise ValueError("Admission occurred while spend or state was unresolved")
            if spent + sum(t["reserved"] for t in tasks.values()) + task["estimate"] > budget:
                raise ValueError("Admission exceeded frozen budget")
            task.update(reserved=task["estimate"], status="reserved", attempts=task["attempts"] + 1)
        elif kind in {"dispatch-intent", "job-observed", "spend-uncertain"}:
            task = tasks[task_id]
            if task["status"] not in {"reserved", "submitting", "submitted", "uncertain"}:
                raise ValueError("Provider state occurred without a reservation")
            task["status"] = {"dispatch-intent": "submitting", "job-observed": "submitted", "spend-uncertain": "uncertain"}[kind]
        elif kind == "task-settled":
            task = tasks[task_id]
            if task["status"] not in {"reserved", "submitting", "submitted", "uncertain"}:
                raise ValueError("Attempt settled more than once or without a reservation")
            if data["status"] not in {"completed", "failed", "cancelled"}:
                raise ValueError("Invalid final state")
            actual = cost(data["actualCost"])
            exceeded = any(data["actualCost"][key] > task["components"][key] for key in COST_KEYS) or spent + actual > budget
            if data["breached"] is not exceeded:
                raise ValueError("Incorrect budget-breach record")
            breach |= exceeded
            spent += actual
            task.update(reserved=0, status=data["status"])
    return {"schema": "algal-bio.budget-audit.v1", **chain, "budgetMicros": budget, "spentMicros": spent,
            "reservedMicros": sum(task["reserved"] for task in tasks.values()),
            "uncertain": any(task["status"] in {"uncertain", "submitting"} for task in tasks.values()),
            "breached": breach, "tasks": len(tasks), "scope": "offline synthetic accounting; no live provider qualification"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--fixtures", action="store_true")
    mode.add_argument("--journal", type=Path, help="Path to append-only events directory")
    args = parser.parse_args()
    if args.fixtures:
        with tempfile.TemporaryDirectory(prefix="bio-budget-") as temporary:
            result = subprocess.run(
                ["bun", str(ROOT / "orchestrator/fixtures.ts"), temporary],
                check=True, capture_output=True, text=True,
            )
            fixture = json.loads(result.stdout)
            report = {"fixture": fixture, "independentAudit": audit(Path(temporary) / fixture["journal"])}
            if report["independentAudit"]["spentMicros"] != fixture["spentMicros"]:
                raise ValueError("Independent accounting disagreed with coordinator")
    else:
        report = audit(args.journal)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
